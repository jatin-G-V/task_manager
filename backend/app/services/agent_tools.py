import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from app.services import task_service
from app.services.clash import find_clashes
from app.services.dedupe import judge, shortlist
from app.services.task_parser import parse_task_text
from app.services.taskfmt import clock, day_word, when_text
from app.services.timeutil import normalize_model_dt, to_local


logger = logging.getLogger(__name__)

MAX_ITEMS = 10
PENDING_TTL_SECONDS = 600

# Decisions waiting for the user, per user:
#   user_id -> {"expires": <timestamp>, "queue": [conflict, ...]}
# In memory, so it only works with ONE server worker. If you run several workers,
# move this into a small table (user_id, payload jsonb, expires_at).
_pending = {}

# fields that define WHEN a task happens (used by "move the existing task")
TIME_FIELDS = (
    "schedule_type",
    "deadline",
    "scheduled_start",
    "scheduled_end",
    "has_explicit_time",
)


# ============================================================
# Reply text (written by code, so it is fast and cannot drift)
# ============================================================

def _quoted(title) -> str:
    return f"\u201c{title}\u201d"


def _with_when(title, when) -> str:
    return f"{_quoted(title)} ({when})" if when else _quoted(title)


def _clash_when(task: dict) -> str:
    start = to_local(task["scheduled_start"])
    end = to_local(task["scheduled_end"]) if task.get("scheduled_end") else None
    if end and end > start:
        end_label = clock(end) if end.date() == start.date() else f"{day_word(end)} {clock(end)}"
        return f"{day_word(start)} {clock(start)}–{end_label}"
    return f"{day_word(start)} at {clock(start)}"


def _created_text(tasks: list) -> str:
    def line(task):
        when = when_text(task)
        return f"{_quoted(task['title'])} \u2014 {when}" if when else _quoted(task["title"])

    if len(tasks) == 1:
        when = when_text(tasks[0])
        suffix = f" \u2014 {when}" if when else ""
        return f"Added {_quoted(tasks[0]['title'])}{suffix}."

    return f"Added {len(tasks)} tasks:\n" + "\n".join(line(t) for t in tasks)


def _error_text(title, error: str) -> str:
    lowered = error.lower()

    if "past" in lowered or "already ended" in lowered:
        return (
            f"I couldn't add {_quoted(title)} because that time has already passed. "
            "What time would you like?"
        )

    return f"I couldn't add {_quoted(title)}: {error}"


def _question(conflict: dict, remaining: int) -> str:
    new = _with_when(conflict["title"], conflict["new_when"])

    if conflict.get("kind") == "schedule_clash":
        targets = conflict["targets"]
        target = _with_when(targets[0]["title"], targets[0]["when"])
        extra = len(targets) - 1
        with_more = f" and {extra} more task{'s' if extra != 1 else ''}" if extra else ""
        text = (
            f"{new} overlaps with {target}{with_more}. "
            "Keep the existing task and skip this one, add it anyway, or tell me a different time?"
        )
        if remaining > 0:
            text += f" ({remaining} more task{'s' if remaining != 1 else ''} to check after this.)"
        return text

    target = _with_when(conflict["target"]["title"], conflict["target"]["when"])

    if conflict["relation"] == "part_of":
        text = (
            f"{new} sounds like part of your existing {target}. "
            "Add it inside that task, or keep it as a separate task?"
        )
    else:
        text = (
            f"{new} looks like your existing {target}. "
            "Keep the existing one, move it to the new time, or add this as a separate task?"
        )

    if remaining > 0:
        text += f" ({remaining} more to check after this.)"

    return text


# ============================================================
# add_tasks
# ============================================================

def _safe_parse(text: str):
    try:
        return parse_task_text(text), None
    except ValueError as exc:
        return None, str(exc)


def add_tasks(user_id: str, args: dict) -> dict:
    items = [
        s.strip()
        for s in (args.get("items") or [])
        if isinstance(s, str) and s.strip()
    ][:MAX_ITEMS]

    if not items:
        raise ValueError("items must contain at least one task.")

    started = time.perf_counter()

    # 1) Parse every item at the same time (the calls are I/O bound)
    with ThreadPoolExecutor(max_workers=min(4, len(items))) as pool:
        parsed_items = list(pool.map(_safe_parse, items))

    parse_done = time.perf_counter()

    # 2) One read of the open tasks, then handle the items one by one so a later
    #    item can also be compared with the items created just before it.
    open_tasks = task_service.list_tasks(user_id, limit=200)

    created, errors, conflicts = [], [], []
    judge_seconds = 0.0

    for text, (parsed, error) in zip(items, parsed_items):
        if error:
            errors.append((text, error))
            continue

        if not parsed.pop("is_task", True):
            errors.append((text, "That doesn't look like a task."))
            continue

        parsed.pop("related", None)
        title = parsed.get("title") or text

        candidates = shortlist(parsed, open_tasks)

        hit = None
        if candidates:
            judge_started = time.perf_counter()
            hit = judge(parsed, candidates)
            judge_seconds += time.perf_counter() - judge_started

        if hit:
            conflicts.append(
                {
                    "kind": "duplicate",
                    "relation": hit["relation"],
                    "title": title,
                    "new_when": when_text(parsed),
                    "raw": text,
                    "parsed": parsed,
                    "target": {
                        "id": hit["task"]["id"],
                        "title": hit["task"]["title"],
                        "when": when_text(hit["task"]),
                    },
                }
            )
            continue

        clashes = find_clashes(parsed, open_tasks)
        if clashes:
            conflicts.append(
                {
                    "kind": "schedule_clash",
                    "title": title,
                    "new_when": _clash_when(parsed),
                    "raw": text,
                    "parsed": parsed,
                    "targets": [
                        {
                            "id": task["id"],
                            "title": task["title"],
                            "when": _clash_when(task),
                        }
                        for task in clashes
                    ],
                }
            )
            continue

        try:
            task = task_service.create_task(user_id, parsed)
        except ValueError as exc:
            errors.append((title, str(exc)))
            continue

        created.append(task)
        open_tasks.append(task)

    logger.info(
        "ADD_TASKS items=%d parse=%.2fs judge=%.2fs total=%.2fs created=%d conflicts=%d errors=%d",
        len(items),
        parse_done - started,
        judge_seconds,
        time.perf_counter() - started,
        len(created),
        len(conflicts),
        len(errors),
    )

    # 3) Hold conflicts for the user's decision
    if conflicts:
        _pending[user_id] = {
            "expires": time.time() + PENDING_TTL_SECONDS,
            "queue": conflicts,
        }
    else:
        _pending.pop(user_id, None)

    parts = []

    if created:
        parts.append(_created_text(created))

    for title, error in errors:
        parts.append(_error_text(title, error))

    if conflicts:
        parts.append(_question(conflicts[0], len(conflicts) - 1))

    return {
        "status": "needs_decision" if conflicts else ("created" if created else "failed"),
        "created": [{"id": t["id"], "title": t["title"]} for t in created],
        "reply": "\n".join(parts),
    }


# ============================================================
# resolve_pending
# ============================================================

_ALLOWED = {
    "duplicate": {"keep_existing", "update_existing", "add_separate"},
    "part_of": {"merge", "add_separate"},
    "schedule_clash": {"keep_existing", "add_anyway", "reschedule_new"},
}


def resolve_pending(user_id: str, args: dict) -> dict:
    state = _pending.get(user_id)

    if not state or state["expires"] < time.time() or not state["queue"]:
        _pending.pop(user_id, None)
        return {
            "status": "nothing_pending",
            "reply": "There's nothing waiting for a decision. Tell me the task you'd like to add.",
        }

    conflict = state["queue"][0]
    choice = args.get("choice")

    kind = conflict.get("kind", "duplicate")

    if kind == "schedule_clash":
        if choice not in _ALLOWED["schedule_clash"]:
            raise ValueError(
                "For a schedule clash, choose keep_existing, add_anyway, or reschedule_new."
            )

        if choice == "keep_existing":
            done = f"Okay, I kept the existing task and skipped {_quoted(conflict['title'])}."

        elif choice == "add_anyway":
            task = task_service.create_task(user_id, conflict["parsed"])
            done = f"Added {_quoted(task['title'])} anyway, despite the time overlap."

        else:
            new_start = args.get("new_scheduled_start")
            if not new_start:
                raise ValueError("Please provide the new scheduled start time.")

            parsed = dict(conflict["parsed"])
            parsed["schedule_type"] = "scheduled"
            parsed["deadline"] = None
            parsed["scheduled_start"] = normalize_model_dt(new_start)
            if args.get("new_scheduled_end"):
                parsed["scheduled_end"] = normalize_model_dt(args["new_scheduled_end"])
            elif parsed.get("duration"):
                parsed["scheduled_end"] = (
                    to_local(parsed["scheduled_start"])
                    + timedelta(minutes=parsed["duration"])
                ).isoformat()
            else:
                parsed["scheduled_end"] = None
            parsed["has_explicit_time"] = True

            clashes = find_clashes(parsed, task_service.list_tasks(user_id, limit=200))
            if clashes:
                conflict["parsed"] = parsed
                conflict["new_when"] = _clash_when(parsed)
                conflict["targets"] = [
                    {
                        "id": task["id"],
                        "title": task["title"],
                        "when": _clash_when(task),
                    }
                    for task in clashes
                ]
                state["expires"] = time.time() + PENDING_TTL_SECONDS
                return {
                    "status": "needs_decision",
                    "reply": _question(conflict, len(state["queue"]) - 1),
                }

            task = task_service.create_task(user_id, parsed)
            done = f"Added {_quoted(task['title'])} at {when_text(task) or 'the new time'}."

        state["queue"].pop(0)
        if state["queue"]:
            state["expires"] = time.time() + PENDING_TTL_SECONDS
            done += "\n" + _question(state["queue"][0], len(state["queue"]) - 1)
        else:
            _pending.pop(user_id, None)
        return {"status": "resolved", "reply": done}

    # "merge them" on a duplicate means: one task is enough
    if conflict["relation"] == "duplicate" and choice == "merge":
        choice = "keep_existing"

    if choice not in _ALLOWED[conflict["relation"]]:
        raise ValueError(
            f"choice must be one of {sorted(_ALLOWED[conflict['relation']])} for this question."
        )

    parsed = conflict["parsed"]
    target = conflict["target"]
    title = conflict["title"]

    if choice == "keep_existing":
        done = f"Okay, I kept {_quoted(target['title'])} as it is."

    elif choice == "update_existing":
        updates = {field: parsed.get(field) for field in TIME_FIELDS}

        if parsed.get("duration") is not None:
            updates["duration"] = parsed["duration"]
            updates["estimated_time_minutes"] = parsed["duration"]

        task_service.update_task(user_id, target["id"], updates)

        when = when_text(parsed)
        done = f"Moved {_quoted(target['title'])} to {when or 'the new time'}."

    elif choice == "merge":
        task_service.merge_into_task(user_id, target["id"], title)
        done = f"Added {_quoted(title)} to {_quoted(target['title'])}."

    else:  # add_separate
        clashes = find_clashes(parsed, task_service.list_tasks(user_id, limit=200))
        if clashes:
            conflict["kind"] = "schedule_clash"
            conflict["new_when"] = _clash_when(parsed)
            conflict["targets"] = [
                {
                    "id": task["id"],
                    "title": task["title"],
                    "when": _clash_when(task),
                }
                for task in clashes
            ]
            state["expires"] = time.time() + PENDING_TTL_SECONDS
            return {
                "status": "needs_decision",
                "reply": _question(conflict, len(state["queue"]) - 1),
            }

        task = task_service.create_task(user_id, parsed)
        when = when_text(task)
        suffix = f" \u2014 {when}" if when else ""
        done = f"Added {_quoted(task['title'])} as a separate task{suffix}."

    # only after it worked: this decision is finished
    state["queue"].pop(0)

    if state["queue"]:
        state["expires"] = time.time() + PENDING_TTL_SECONDS
        done += "\n" + _question(state["queue"][0], len(state["queue"]) - 1)
    else:
        _pending.pop(user_id, None)

    return {"status": "resolved", "reply": done}


# ============================================================
# update_task
# ============================================================

# Only these fields can be changed by the agent (protects id, user_id, status, ...).
# estimated_time_minutes is intentionally absent: it is synced from duration below.
UPDATABLE_FIELDS = {
    "title", "section", "brief", "schedule_type", "deadline",
    "scheduled_start", "scheduled_end", "has_explicit_time",
    "is_recurring", "recurrence", "recurrence_end",
    "duration", "effort", "urgency",
}

# Fields the user may explicitly empty. The model lists them in clear_fields
# instead of sending null, so a stray null can never wipe a value.
CLEARABLE_FIELDS = {
    "brief", "deadline", "scheduled_start", "scheduled_end",
    "recurrence", "recurrence_end", "duration", "effort", "urgency",
}


def update_task(user_id: str, args: dict) -> dict:
    args = dict(args)
    task_id = args.pop("task_id")
    clear_fields = args.pop("clear_fields", None) or []

    # keep only whitelisted fields that actually carry a value (drops stray nulls)
    updates = {
        k: v for k, v in args.items()
        if k in UPDATABLE_FIELDS and v is not None
    }

    for field in clear_fields:
        if field in CLEARABLE_FIELDS:
            updates[field] = None

    if not updates:
        raise ValueError("No valid changes were provided.")

    # datetimes typed by the model are local time; store them with the offset
    for field in ("deadline", "scheduled_start", "scheduled_end", "recurrence_end"):
        if updates.get(field):
            updates[field] = normalize_model_dt(updates[field])

    # explicit duration always wins: keep estimated time in sync
    if updates.get("duration") is not None:
        updates["estimated_time_minutes"] = updates["duration"]

    # switching schedule type: drop the fields the new type must not have
    if updates.get("schedule_type") == "flexible":
        updates.setdefault("scheduled_start", None)
        updates.setdefault("scheduled_end", None)
    elif updates.get("schedule_type") == "scheduled":
        updates.setdefault("deadline", None)

    # turning recurrence off: drop its pattern and end date
    if updates.get("is_recurring") is False:
        updates.setdefault("recurrence", None)
        updates.setdefault("recurrence_end", None)

    return task_service.update_task(user_id, task_id, updates)


# ============================================================
# complete / delete
# ============================================================

def _ids(args: dict) -> list:
    ids = args["task_ids"]
    return [ids] if isinstance(ids, str) else ids


def complete_task(user_id: str, args: dict) -> dict:
    ids = _ids(args)
    done = task_service.complete_tasks(user_id, ids)
    return {"completed_count": len(done), "requested": len(ids)}


def delete_task(user_id: str, args: dict) -> dict:
    ids = _ids(args)
    gone = task_service.delete_tasks(user_id, ids)
    return {"deleted_count": len(gone), "requested": len(ids)}


# ============================================================
# read / recommend
# ============================================================

def list_tasks(user_id: str, args: dict) -> list:
    return task_service.list_tasks(
        user_id,
        section=args.get("section"),
        status=args.get("status"),
        search=args.get("search"),
        limit=args.get("limit", 20),
    )


def get_task(user_id: str, args: dict) -> dict:
    task_id = args["task_id"]

    task = task_service.get_task(user_id, task_id)

    if not task:
        raise LookupError("Task not found")

    return task


def recommend_task(user_id: str, args: dict) -> list:
    limit = max(1, min(int(args.get("limit", 3)), 5))
    return task_service.recommend_tasks(
        user_id,
        limit=limit,
        exclude_ids=args.get("exclude_ids") or [],
    )


def recommend_for_mood(user_id: str, args: dict) -> list:
    energy = args.get("energy")
    if energy not in ("low", "medium", "high"):
        raise ValueError("energy must be low, medium or high.")
    return task_service.recommend_tasks(
        user_id,
        energy=energy,
        exclude_ids=args.get("exclude_ids") or [],
    )


def daily_digest(user_id: str, args: dict) -> dict:
    return task_service.get_daily_digest(user_id)


# ============================================================
# Tool schemas
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_tasks",
            "description": (
                "Create one or more tasks. Put EACH separate task in its own entry of items, "
                "in the user's own words, including its own day/time (if one day or time applies "
                "to several tasks, repeat it in every entry). Call it ONCE per user message, never "
                "once per task. The system parses the tasks, checks for duplicates and exact-time "
                "overlaps, and writes the reply itself, so do not add a reply of your own."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 10,
                        "description": "One entry per task, each exactly as the user described it.",
                    }
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_pending",
            "description": (
                "Apply the user's answer to the pending add_tasks question. Use ONLY after add_tasks "
                "has asked about a duplicate, part-of task, or exact-time clash; never call add_tasks "
                "again for that pending task. For duplicates: keep_existing, update_existing, merge, "
                "or add_separate. For time clashes: keep_existing skips the new task, add_anyway "
                "creates it despite the overlap, and reschedule_new requires new_scheduled_start "
                "(plus new_scheduled_end only if supplied by the user)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "choice": {
                        "type": "string",
                        "enum": [
                            "keep_existing", "update_existing", "merge", "add_separate",
                            "add_anyway", "reschedule_new",
                        ],
                    },
                    "new_scheduled_start": {
                        "type": "string",
                        "description": "Required for reschedule_new: replacement start as ISO-8601 datetime with timezone, based only on the user's stated time.",
                    },
                    "new_scheduled_end": {
                        "type": "string",
                        "description": "Optional replacement end as ISO-8601 datetime with timezone, only when the user specified an end time.",
                    },
                },
                "required": ["choice"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": (
                "Update an existing task. Include ONLY the fields the user wants to change. "
                "To remove a value (for example clear a deadline), put its name in "
                "clear_fields. Never send null."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "title": {"type": "string"},
                    "section": {"type": "string", "enum": ["work", "personal", "leisure"]},
                    "brief": {"type": "string"},
                    "schedule_type": {"type": "string", "enum": ["flexible", "scheduled"]},
                    "deadline": {"type": "string", "description": "ISO-8601 datetime"},
                    "scheduled_start": {"type": "string", "description": "ISO-8601 datetime"},
                    "scheduled_end": {"type": "string", "description": "ISO-8601 datetime"},
                    "has_explicit_time": {"type": "boolean"},
                    "is_recurring": {"type": "boolean"},
                    "recurrence": {"type": "string"},
                    "recurrence_end": {"type": "string", "description": "ISO-8601 datetime"},
                    "duration": {
                        "type": "integer",
                        "description": "Explicit duration in minutes. Only when the user states one."
                    },
                    "effort": {"type": "string", "enum": ["low", "medium", "high"]},
                    "urgency": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                    "clear_fields": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "brief", "deadline", "scheduled_start", "scheduled_end",
                                "recurrence", "recurrence_end", "duration", "effort", "urgency"
                            ]
                        },
                        "description": "Fields to empty. Use only when the user asks to remove a value."
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark an existing task as completed.",
            "parameters": {
                "type": "object",
                "properties": {"task_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["task_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete an existing task. Always requires explicit user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {"task_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["task_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List the user's tasks, optionally filtered by section, status, or title search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": ["string", "null"],
                        "enum": ["work", "personal", "leisure", None]
                    },
                    "status": {
                        "type": ["string", "null"],
                        "enum": ["pending", "in_progress", "completed", None]
                    },
                    "search": {"type": ["string", "null"]},
                    "limit": {"type": "integer"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_task",
            "description": "Get the full details of a specific task.",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_task",
            "description": (
                "Recommend what to work on right now. Use when the user asks what to do next "
                "and has NOT said anything about their mood or energy. Pass exclude_ids with "
                "the ids already suggested if the user wants a different suggestion."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "How many tasks, 1 to 5. Default 3."},
                    "exclude_ids": {"type": "array", "items": {"type": "string"}}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_for_mood",
            "description": (
                "Recommend tasks matched to the user's current energy. ONLY call this when the "
                "user themselves says how they feel or how much energy they have "
                "(e.g. 'I'm tired', 'I'm feeling sharp'). Never guess or ask for it. "
                "tired/drained/low energy -> low; okay/normal -> medium; energetic/focused -> high."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "energy": {"type": "string", "enum": ["low", "medium", "high"]},
                    "exclude_ids": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["energy"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "daily_digest",
            "description": "Give an overview of the user's day: tasks due today, tasks at risk, overdue tasks, and the suggested focus.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
]


TOOL_FUNCTIONS = {
    "add_tasks": add_tasks,
    "resolve_pending": resolve_pending,
    "update_task": update_task,
    "complete_task": complete_task,
    "delete_task": delete_task,
    "list_tasks": list_tasks,
    "get_task": get_task,
    "recommend_task": recommend_task,
    "recommend_for_mood": recommend_for_mood,
    "daily_digest": daily_digest,
}
