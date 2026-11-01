import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from groq import RateLimitError

from app.services import task_service
from app.services.clash import find_clashes
from app.services.dedupe import judge, shortlist
from app.services.recommendation import PINNED_WINDOW_MIN
from app.services.recurrence import next_occurrence, rrule_to_text, snap_first_occurrence
from app.services.task_parser import parse_task_text, parse_task_texts
from app.services.taskfmt import clock, day_word, when_text
from app.services.timeutil import normalize_model_dt, now_local, to_local


logger = logging.getLogger(__name__)

MAX_ITEMS = 10
PARSER_BATCH_SIZE = 4
PENDING_TTL_SECONDS = 600

# Decisions waiting for the user, per user:
#   user_id -> {"expires": <timestamp>, "queue": [conflict, ...]}
# In memory by design; lost on refresh or restart, and requires a single server worker.
_pending = {}
_delete_pending = {}


def clear_user_pending(user_id: str) -> None:
    """Clear this user's in-memory decisions when a new chat begins."""
    _pending.pop(user_id, None)
    _delete_pending.pop(user_id, None)

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


def _recurrence_text(task: dict) -> str | None:
    if not task.get("is_recurring") or not task.get("recurrence"):
        return None
    return rrule_to_text(task.get("recurrence"), task.get("recurrence_end"))


def _task_view(task: dict) -> dict:
    """Give the agent local, user-facing task facts without storage fields."""
    explicit = bool(task.get("has_explicit_time"))
    start = to_local(task["scheduled_start"]) if task.get("scheduled_start") else None
    end = to_local(task["scheduled_end"]) if task.get("scheduled_end") else None

    if task.get("schedule_type") == "scheduled" and explicit and start and end:
        end_label = clock(end) if end.date() == start.date() else f"{day_word(end)} {clock(end)}"
        when = f"{day_word(start)} {clock(start)}–{end_label}"
    else:
        when = when_text(task)

    overdue_at = None
    if task.get("schedule_type") == "scheduled":
        overdue_at = task.get("scheduled_start") if explicit else (task.get("scheduled_end") or task.get("scheduled_start"))
    else:
        overdue_at = task.get("deadline")
    if overdue_at and explicit:
        overdue_at = to_local(overdue_at) + timedelta(minutes=PINNED_WINDOW_MIN)
    is_overdue = bool(
        overdue_at
        and task.get("status") not in {"completed", "dropped"}
        and to_local(overdue_at) < now_local()
    )

    result = {
        "id": task.get("id"),
        "title": task.get("title"),
        "section": task.get("section") or "personal",
        "brief": task.get("brief"),
        "when": when,
        "is_overdue": is_overdue,
        "effort": task.get("effort"),
        "urgency": task.get("urgency"),
        "is_blocked": bool(task.get("is_blocked")),
        "repeats": _recurrence_text(task),
    }
    # duration is user-provided; estimated_time_minutes is intentionally hidden.
    if task.get("duration") is not None:
        result["duration_minutes"] = task["duration"]
    return result


def _update_error(exc: ValueError) -> str:
    if "past" in str(exc).lower() or "already ended" in str(exc).lower():
        return "That time is already in the past. Please choose a future time."
    return str(exc)


def _update_one(user_id: str, task_id: str, updates: dict) -> dict:
    try:
        return task_service.update_task(user_id, task_id, updates)
    except ValueError as exc:
        raise ValueError(_update_error(exc)) from exc


def _digest_view(digest: dict) -> dict:
    return {
        key: [_task_view(task) for task in digest.get(key, [])]
        for key in ("due_today", "scheduled_today", "at_risk", "overdue")
    } | {
        "suggested_focus": (
            _task_view(digest["suggested_focus"])
            if digest.get("suggested_focus") else None
        )
    }


def _created_text(tasks: list) -> str:
    def line(task):
        when = when_text(task)
        details = [when] if when else []
        recurrence = _recurrence_text(task)
        if recurrence:
            details.append(recurrence)
            current_occurrence = task.get("scheduled_start") or task.get("deadline")
            if current_occurrence:
                try:
                    next_fields = next_occurrence(task, to_local(current_occurrence))
                    next_value = (
                        (next_fields or {}).get("scheduled_start")
                        or (next_fields or {}).get("deadline")
                    )
                    if next_value:
                        next_local = to_local(next_value)
                        next_label = day_word(next_local)
                        if task.get("has_explicit_time"):
                            next_label += f" at {clock(next_local)}"
                        details.append(f"next: {next_label}")
                except ValueError:
                    # Creation validation should make this unreachable; never
                    # fail task creation just because an old row is malformed.
                    logger.exception("Could not format next recurrence for task %s", task.get("id"))
        if task.get("duration") is not None:
            details.append(f"{task['duration']} minutes")
        suffix = f" \u2014 {', '.join(details)}" if details else ""
        return f"{_quoted(task['title'])}{suffix}"

    if len(tasks) == 1:
        return f"Added {line(tasks[0])}."

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

    if conflict.get("kind") == "past_time":
        return (
            f"{new} is already in the past. What future time should I use instead?"
        )

    if conflict.get("kind") == "update_clash":
        examples = conflict.get("overlaps", [])
        details = "; ".join(
            f"{_with_when(item['title'], item['when'])} overlaps {_with_when(item['other_title'], item['other_when'])}"
            for item in examples[:2]
        )
        more = len(examples) - 2
        if more > 0:
            details += f" and {more} more overlap{'s' if more != 1 else ''}"
        text = (
            f"These changes would create a schedule clash: {details}. "
            "Keep the current times, apply the changes anyway, or give me different times?"
        )
        if remaining > 0:
            text += f" ({remaining} more decision{'s' if remaining != 1 else ''} after this.)"
        return text

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
            "Add it inside that task, keep it as a separate task, or skip it?"
        )
    else:
        if conflict.get("new_when") == conflict.get("target", {}).get("when"):
            choices = "Keep the existing task, or add this as a separate task?"
        else:
            choices = (
                "Keep the existing task, move it to the new time, "
                "or add this as a separate task?"
            )
        text = f"{new} looks like your existing {target}. {choices}"

    if remaining > 0:
        text += f" ({remaining} more to check after this.)"

    return text


def _expired_question(conflict: dict) -> str:
    if conflict.get("kind") == "update_clash":
        title = conflict.get("title") or "those tasks"
        return f"The schedule-change question for {_quoted(title)} expired; I left the tasks unchanged. You can ask me to reschedule them again."
    title = conflict.get("title") or "that task"
    return f"The unanswered question about {_quoted(title)} expired, so I didn't add it. Tell me if you still want to add it."


def _same_pending_decision(left: dict, right: dict) -> bool:
    """Recognize a retried decision so repeated agent calls don't grow the queue."""
    if (left.get("title") or "").strip().casefold() != (right.get("title") or "").strip().casefold():
        return False

    left_target = left.get("target", {}).get("id")
    right_target = right.get("target", {}).get("id")
    if left_target and right_target:
        return left_target == right_target

    # A past-time question has no duplicate target yet. If the corrected time
    # causes duplicate detection to find one, replace that held item in place.
    if left.get("kind") == "past_time" or right.get("kind") == "past_time":
        return True

    left_targets = tuple(sorted(item.get("id", "") for item in left.get("targets", [])))
    right_targets = tuple(sorted(item.get("id", "") for item in right.get("targets", [])))
    if left_targets or right_targets:
        return left_targets == right_targets

    left_parsed = left.get("parsed", {})
    right_parsed = right.get("parsed", {})
    return all(
        left_parsed.get(field) == right_parsed.get(field)
        for field in ("scheduled_start", "scheduled_end", "deadline")
    )


def _merge_pending_queue(existing: list, incoming: list) -> list:
    """Keep one pending decision per task/target, updating it with newer timing."""
    queue = list(existing)
    for conflict in incoming:
        match = next(
            (index for index, held in enumerate(queue) if _same_pending_decision(held, conflict)),
            None,
        )
        if match is None:
            queue.append(conflict)
        else:
            queue[match] = conflict
    return queue


# ============================================================
# add_tasks
# ============================================================

def _safe_parse(text: str):
    try:
        return parse_task_text(text), None
    except RateLimitError:
        # One rate-limited parser request should not abort every item in the
        # batch. Successful parses can still proceed to validation and save.
        logger.warning("Task parser rate-limited while parsing one add_tasks item")
        return None, "The task parser is temporarily rate-limited. Please retry shortly."
    except ValueError as exc:
        return None, str(exc)
    except Exception:
        # Keep provider/network failures scoped to this item rather than letting
        # ThreadPoolExecutor.map raise and cancel the whole add_tasks operation.
        logger.exception("Task parser failed for one add_tasks item")
        return None, "The task parser is temporarily unavailable. Please retry shortly."


def add_tasks(user_id: str, args: dict) -> dict:
    items = [
        s.strip()
        for s in (args.get("items") or [])
        if isinstance(s, str) and s.strip()
    ][:MAX_ITEMS]

    if not items:
        raise ValueError("items must contain at least one task.")

    started = time.perf_counter()

    # 1) Preserve the existing one-task parser. For multiple tasks, batch a
    #    few descriptions per call to avoid repeating the large parser prompt.
    #    If the batch response is malformed, fall back to the exact old
    #    per-item path. On a rate limit, don't immediately retry the same work.
    if len(items) == 1:
        parsed_items = [_safe_parse(items[0])]
    else:
        parsed_items = []
        for start in range(0, len(items), PARSER_BATCH_SIZE):
            chunk = items[start : start + PARSER_BATCH_SIZE]
            try:
                batch = parse_task_texts(chunk)
                parsed_items.extend((parsed, None) for parsed in batch)
            except RateLimitError:
                logger.warning("Task parser rate-limited while parsing a batch")
                rate_limited = "The task parser is temporarily rate-limited. Please retry shortly."
                remaining = len(items) - start
                parsed_items.extend((None, rate_limited) for _ in range(remaining))
                break
            except ValueError:
                logger.exception("Batch task parse failed; falling back to per-item parsing")
                with ThreadPoolExecutor(max_workers=min(4, len(chunk))) as pool:
                    parsed_items.extend(pool.map(_safe_parse, chunk))
            except Exception:
                logger.exception("Task parser unavailable while parsing a batch")
                unavailable = "The task parser is temporarily unavailable. Please retry shortly."
                remaining = len(items) - start
                parsed_items.extend((None, unavailable) for _ in range(remaining))
                break

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
        parsed = snap_first_occurrence(parsed)
        title = parsed.get("title") or text

        # Reject impossible dates before duplicate detection. Otherwise an old
        # time can produce a duplicate question first, then fail only after the
        # user chooses "add separate", leaving that obsolete question queued.
        try:
            task_service.validate_new_task_data(parsed)
        except ValueError as exc:
            if "past" in str(exc).lower() or "already ended" in str(exc).lower():
                conflicts.append(
                    {
                        "kind": "past_time",
                        "title": title,
                        "new_when": when_text(parsed),
                        "raw": text,
                        "parsed": parsed,
                    }
                )
            else:
                errors.append((title, str(exc)))
            continue

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

    # A task that was just created must not leave an old question about the
    # same title waiting (it would be shown again, with stale times).
    created_titles = {
        " ".join((t.get("title") or "").casefold().split()) for t in created
    }
    stale_state = _pending.get(user_id)
    if stale_state and created_titles:
        stale_state["queue"] = [
            item for item in stale_state["queue"]
            if item.get("kind") == "update_clash"
            or " ".join((item.get("title") or "").casefold().split()) not in created_titles
        ]
        if not stale_state["queue"]:
            _pending.pop(user_id, None)

    # 3) Hold conflicts for the user's decision
    pending = _pending.get(user_id)
    expired_pending = None
    if pending and pending["expires"] < time.time():
        expired_pending = (pending.get("queue") or [None])[0]
        _pending.pop(user_id, None)
        pending = None

    if conflicts:
        queue = _merge_pending_queue(pending["queue"] if pending else [], conflicts)
        _pending[user_id] = {
            "expires": time.time() + PENDING_TTL_SECONDS,
            "queue": queue,
        }
    elif pending:
        # An unrelated new task must not silently discard an unanswered decision.
        pending["expires"] = time.time() + PENDING_TTL_SECONDS

    parts = []

    if created:
        parts.append(_created_text(created))

    if expired_pending:
        parts.append(_expired_question(expired_pending))

    for title, error in errors:
        parts.append(_error_text(title, error))

    pending = _pending.get(user_id)
    if pending and pending["queue"]:
        parts.append(_question(pending["queue"][0], len(pending["queue"]) - 1))

    return {
        "status": "needs_decision" if pending else ("created" if created else "failed"),
        "created": [{"id": t["id"], "title": t["title"]} for t in created],
        "reply": "\n".join(parts),
    }


# ============================================================
# resolve_pending
# ============================================================

_ALLOWED = {
    "duplicate": {"keep_existing", "update_existing", "add_separate"},
    # keep_existing = skip the new task and leave the existing one unchanged
    "part_of": {"merge", "add_separate", "keep_existing"},
    "schedule_clash": {"keep_existing", "add_anyway", "reschedule_new"},
    "past_time": {"reschedule_new", "cancel"},
}


def resolve_pending(user_id: str, args: dict) -> dict:
    state = _pending.get(user_id)

    if not state or state["expires"] < time.time() or not state["queue"]:
        expired_conflict = (
            state.get("queue", [None])[0]
            if state and state.get("expires", 0) < time.time() and state.get("queue")
            else None
        )
        _pending.pop(user_id, None)
        return {
            "status": "nothing_pending",
            "reply": _expired_question(expired_conflict) if expired_conflict else "There's nothing waiting for a decision. Tell me the task you'd like to add.",
        }

    conflict = state["queue"][0]
    choice = args.get("choice")

    kind = conflict.get("kind", "duplicate")

    if kind == "past_time":
        if choice == "cancel":
            done = f"Okay, I didn't add {_quoted(conflict['title'])}."
            state["queue"].pop(0)
            if state["queue"]:
                state["expires"] = time.time() + PENDING_TTL_SECONDS
                done += "\n" + _question(state["queue"][0], len(state["queue"]) - 1)
            else:
                _pending.pop(user_id, None)
            return {"status": "resolved", "reply": done}

        if choice != "reschedule_new":
            if choice == "add_separate":
                conflict["prefer_separate"] = True
            state["expires"] = time.time() + PENDING_TTL_SECONDS
            return {
                "status": "needs_decision",
                "reply": f"{_quoted(conflict['title'])} still needs a future time. What time should I use?",
            }

        parsed = dict(conflict["parsed"])
        if parsed.get("schedule_type") == "scheduled":
            new_start = args.get("new_scheduled_start")
            if not new_start:
                raise ValueError("Please provide the replacement start time.")
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
        else:
            new_deadline = args.get("new_deadline")
            if not new_deadline:
                raise ValueError("Please provide the replacement deadline.")
            parsed["deadline"] = normalize_model_dt(new_deadline)

        try:
            task_service.validate_new_task_data(parsed)
        except ValueError as exc:
            if "past" in str(exc).lower() or "already ended" in str(exc).lower():
                conflict["parsed"] = parsed
                conflict["new_when"] = when_text(parsed)
                state["expires"] = time.time() + PENDING_TTL_SECONDS
                return {"status": "needs_decision", "reply": _question(conflict, len(state["queue"]) - 1)}
            raise

        # The user supplied a valid replacement time. Run the normal safety
        # checks now, while retaining the held task and its other parsed fields.
        open_tasks = task_service.list_tasks(user_id, limit=200)
        candidates = [] if conflict.get("prefer_separate") else shortlist(parsed, open_tasks)
        hit = judge(parsed, candidates) if candidates else None
        if hit:
            conflict.update(
                {
                    "kind": "duplicate",
                    "relation": hit["relation"],
                    "parsed": parsed,
                    "new_when": when_text(parsed),
                    "target": {
                        "id": hit["task"]["id"],
                        "title": hit["task"]["title"],
                        "when": when_text(hit["task"]),
                    },
                }
            )
            state["expires"] = time.time() + PENDING_TTL_SECONDS
            return {"status": "needs_decision", "reply": _question(conflict, len(state["queue"]) - 1)}

        clashes = find_clashes(parsed, open_tasks)
        if clashes:
            conflict.update(
                {
                    "kind": "schedule_clash",
                    "parsed": parsed,
                    "new_when": _clash_when(parsed),
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
            state["expires"] = time.time() + PENDING_TTL_SECONDS
            return {"status": "needs_decision", "reply": _question(conflict, len(state["queue"]) - 1)}

        task = task_service.create_task(user_id, parsed)
        done = f"Added {_quoted(task['title'])} — {when_text(task) or 'without a date'}."
        state["queue"].pop(0)
        if state["queue"]:
            state["expires"] = time.time() + PENDING_TTL_SECONDS
            done += "\n" + _question(state["queue"][0], len(state["queue"]) - 1)
        else:
            _pending.pop(user_id, None)
        return {"status": "resolved", "reply": done}

    if kind == "update_clash":
        if choice == "keep_existing":
            other_changes = []
            schedule_fields = set(TIME_FIELDS) | {"duration", "estimated_time_minutes"}
            for item in conflict["changes"]:
                remaining = {
                    key: value for key, value in item["updates"].items()
                    if key not in schedule_fields
                }
                if remaining:
                    other_changes.append(_update_one(user_id, item["task_id"], remaining))
            done = (
                "I kept the current times and applied the other requested changes."
                if other_changes
                else "Okay, I left those tasks at their current times."
            )
        elif choice == "update_anyway":
            changed = []
            for item in conflict["changes"]:
                changed.append(
                    _update_one(user_id, item["task_id"], item["updates"])
                )
            names = ", ".join(_quoted(task.get("title") or "Untitled task") for task in changed)
            done = f"Updated {names}, as requested. These times will overlap."
        else:
            raise ValueError("For these schedule changes, choose keep_existing or update_anyway. If you want different times, tell me the times to use.")

        state["queue"].pop(0)
        if state["queue"]:
            state["expires"] = time.time() + PENDING_TTL_SECONDS
            done += "\n" + _question(state["queue"][0], len(state["queue"]) - 1)
        else:
            _pending.pop(user_id, None)
        return {"status": "resolved", "reply": done}

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
        if conflict["relation"] == "part_of":
            done = (
                f"Okay, I didn't add {_quoted(title)} and left "
                f"{_quoted(target['title'])} as it is."
            )
        else:
            done = f"Okay, I kept {_quoted(target['title'])} as it is."

    elif choice == "update_existing":
        updates = {field: parsed.get(field) for field in TIME_FIELDS}

        if parsed.get("duration") is not None:
            updates["duration"] = parsed["duration"]
            updates["estimated_time_minutes"] = parsed["duration"]

        _update_one(user_id, target["id"], updates)

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

        try:
            task = task_service.create_task(user_id, parsed)
        except ValueError as exc:
            if "past" in str(exc).lower() or "already ended" in str(exc).lower():
                conflict["kind"] = "past_time"
                # The user has already chosen to keep this as a separate task.
                # Preserve that decision while asking for a future time; otherwise
                # the corrected time gets sent through duplicate detection again
                # and the same duplicate question is shown repeatedly.
                conflict["prefer_separate"] = True
                conflict["new_when"] = when_text(parsed)
                state["expires"] = time.time() + PENDING_TTL_SECONDS
                return {"status": "needs_decision", "reply": _question(conflict, len(state["queue"]) - 1)}
            raise
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


def _settle_pending_clashes(user_id: str, changed_views: list):
    """After a task's time changed, re-check the held exact-time clashes.

    A held task whose clash is now gone is created right away. One that still
    clashes is asked again with the CURRENT times (the stored question text
    would be stale). Returns the full reply, or None when no clash was waiting.
    """
    state = _pending.get(user_id)
    if not state or state["expires"] < time.time():
        return None

    clash_items = [c for c in state["queue"] if c.get("kind") == "schedule_clash"]
    if not clash_items:
        return None

    open_tasks = task_service.list_tasks(user_id, limit=200)
    added = []

    for conflict in clash_items:
        clashes = find_clashes(conflict["parsed"], open_tasks)
        if clashes:
            conflict["targets"] = [
                {"id": t["id"], "title": t["title"], "when": _clash_when(t)}
                for t in clashes
            ]
            continue
        try:
            task = task_service.create_task(user_id, conflict["parsed"])
        except ValueError:
            # For example the held time has passed meanwhile; leave it queued.
            continue
        added.append(task)
        open_tasks.append(task)
        state["queue"].remove(conflict)

    parts = [
        f"Moved {_quoted(v['title'])} to {v['when']}."
        for v in changed_views
        if v.get("when")
    ]
    if added:
        parts.append(_created_text(added))

    if state["queue"]:
        state["expires"] = time.time() + PENDING_TTL_SECONDS
        parts.append(_question(state["queue"][0], len(state["queue"]) - 1))
    else:
        _pending.pop(user_id, None)

    return " ".join(parts)


def update_task(user_id: str, args: dict) -> dict:
    args = dict(args)
    task_id = args.pop("task_id", None)
    shift_minutes = args.pop("shift_minutes", None)
    if shift_minutes is not None:
        try:
            shift_minutes = int(shift_minutes)
        except (TypeError, ValueError):
            raise ValueError("shift_minutes must be a whole number of minutes.")
    task_ids = args.pop("task_ids", None)
    ids = list(dict.fromkeys(task_ids or ([task_id] if task_id else [])))
    if not ids:
        raise ValueError("Provide task_id or task_ids.")
    clear_fields = args.pop("clear_fields", None) or []

    # keep only whitelisted fields that actually carry a value (drops stray nulls)
    updates = {
        k: v for k, v in args.items()
        if k in UPDATABLE_FIELDS and v is not None
    }

    for field in clear_fields:
        if field in CLEARABLE_FIELDS:
            updates[field] = None

    if not updates and shift_minutes is None:
        raise ValueError("No valid changes were provided.")

    # A deadline means "complete by"; it is not a calendar block. Switching
    # from a scheduled task also clears its old time block.
    if updates.get("deadline") and "schedule_type" not in updates:
        updates["schedule_type"] = "flexible"
        updates["scheduled_start"] = None
        updates["scheduled_end"] = None
    if updates.get("schedule_type") == "scheduled" and updates.get("deadline"):
        raise ValueError("A scheduled task cannot have a deadline. Choose a start time or a flexible deadline.")

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

    # A user-provided replacement time supersedes a held update for these tasks.
    state = _pending.get(user_id)
    if state:
        state["queue"] = [
            item for item in state["queue"]
            if item.get("kind") != "update_clash"
            or not ({change["task_id"] for change in item.get("changes", [])} & set(ids))
        ]
        if not state["queue"]:
            _pending.pop(user_id, None)

    existing = []
    proposed = []
    per_task_updates = []
    for current_id in ids:
        current = task_service.get_task(user_id, current_id)
        if not current:
            raise LookupError("Task not found")
        existing.append(current)
        item_updates = dict(updates)

        # "shift by N minutes" is calculated here in code, not by the model.
        if shift_minutes is not None:
            if current.get("schedule_type") != "scheduled" or not current.get("scheduled_start"):
                raise ValueError(
                    f"{current.get('title') or 'That task'} has no scheduled time to shift."
                )
            delta = timedelta(minutes=shift_minutes)
            item_updates["scheduled_start"] = (
                to_local(current["scheduled_start"]) + delta
            ).isoformat()
            if current.get("scheduled_end"):
                item_updates["scheduled_end"] = (
                    to_local(current["scheduled_end"]) + delta
                ).isoformat()
        if (
            current.get("schedule_type") == "scheduled"
            and item_updates.get("schedule_type", "scheduled") == "scheduled"
            and current.get("has_explicit_time")
            and item_updates.get("scheduled_start")
            and "scheduled_end" not in item_updates
        ):
            start = to_local(item_updates["scheduled_start"])
            old_start = to_local(current["scheduled_start"]) if current.get("scheduled_start") else None
            old_end = to_local(current["scheduled_end"]) if current.get("scheduled_end") else None
            duration = item_updates.get("duration", current.get("duration"))
            if duration is not None:
                item_updates["scheduled_end"] = (start + timedelta(minutes=duration)).isoformat()
            elif old_start and old_end and old_end > old_start:
                item_updates["scheduled_end"] = (start + (old_end - old_start)).isoformat()
        elif (
            current.get("schedule_type") == "scheduled"
            and item_updates.get("schedule_type", "scheduled") == "scheduled"
            and current.get("has_explicit_time")
            and item_updates.get("duration") is not None
            and current.get("scheduled_start")
            and "scheduled_end" not in item_updates
        ):
            start = to_local(current["scheduled_start"])
            item_updates["scheduled_end"] = (start + timedelta(minutes=item_updates["duration"])).isoformat()

        per_task_updates.append(item_updates)
        merged = {**current, **item_updates}
        if item_updates.get("schedule_type") == "flexible":
            merged.setdefault("scheduled_start", None)
            merged.setdefault("scheduled_end", None)
        elif item_updates.get("schedule_type") == "scheduled":
            merged.setdefault("deadline", None)
        # Validate the whole bulk operation before writing any one task, so a
        # later invalid item cannot leave the earlier items partially updated.
        try:
            task_service._validate_not_in_past(merged, changed_fields=set(item_updates))
        except ValueError as exc:
            raise ValueError(_update_error(exc)) from exc
        proposed.append(merged)

    open_tasks = task_service.list_tasks(user_id, limit=200)
    excluded = set(ids)
    comparison = [task for task in open_tasks if task.get("id") not in excluded]
    overlaps = []
    for current, candidate in zip(existing, proposed):
        candidate["id"] = current["id"]
        for other in ([] if candidate.get("is_blocked") else find_clashes(candidate, comparison)):
            overlaps.append({
                "title": current.get("title") or "Untitled task",
                "when": _clash_when(candidate),
                "other_title": other.get("title") or "Untitled task",
                "other_when": _clash_when(other),
            })
        comparison.append(candidate)

    if overlaps:
        changes = [
            {"task_id": current["id"], "title": current.get("title"), "updates": item_updates}
            for current, item_updates in zip(existing, per_task_updates)
        ]
        pending = _pending.get(user_id)
        queue = pending["queue"] if pending and pending["expires"] >= time.time() else []
        update_conflict = {
            "kind": "update_clash",
            "title": existing[0].get("title") or "these tasks",
            "new_when": overlaps[0]["when"],
            "overlaps": overlaps,
            "changes": changes,
        }
        _pending[user_id] = {
            "expires": time.time() + PENDING_TTL_SECONDS,
            "queue": queue + [update_conflict],
        }
        first_pending = _pending[user_id]["queue"][0]
        return {
            "status": "needs_decision",
            "reply": _question(first_pending, len(_pending[user_id]["queue"]) - 1),
        }

    changed = [
        _update_one(user_id, current["id"], item_updates)
        for current, item_updates in zip(existing, per_task_updates)
    ]
    views = [_task_view(task) for task in changed]

    # If a time changed while an exact-time clash question was waiting, settle
    # that question now (add the held task, or re-ask with the new times).
    time_changed = any(
        field in item_updates
        for item_updates in per_task_updates
        for field in TIME_FIELDS
    )
    if time_changed:
        settled_reply = _settle_pending_clashes(user_id, views)
        if settled_reply:
            return {"status": "updated", "tasks": views, "reply": settled_reply}

    return views if len(views) > 1 else views[0]


# ============================================================
# complete / delete
# ============================================================

def _ids(args: dict) -> list:
    ids = args["task_ids"]
    return [ids] if isinstance(ids, str) else ids


def _is_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _norm_title(value) -> str:
    return " ".join(str(value or "").casefold().split())


def _resolve_task_refs(user_id: str, references: list):
    """Turn task IDs or titles into task rows.

    The chat history the app sends is plain text, so the model often has no
    task ID. If it passes a title instead of an ID, look the task up by title,
    but accept only ONE clear match (never guess between several).
    Returns (tasks, missing, ambiguous).
    """
    tasks, missing, ambiguous = [], [], []
    pools = {}

    def pool(include_completed):
        if include_completed not in pools:
            pools[include_completed] = task_service.list_tasks(
                user_id, limit=500, include_completed=include_completed
            )
        return pools[include_completed]

    for reference in references:
        reference = str(reference).strip()
        if not reference:
            continue

        # A real UUID goes straight to the database. Anything else would make
        # Postgres fail with "invalid input syntax for type uuid".
        if _is_uuid(reference):
            task = task_service.get_task(user_id, reference)
            if task:
                tasks.append(task)
            else:
                missing.append(reference)
            continue

        needle = _norm_title(reference)
        matches = []
        for include_completed in (False, True):
            candidates = pool(include_completed)
            exact = [t for t in candidates if _norm_title(t.get("title")) == needle]
            matches = exact or [
                t for t in candidates if needle and needle in _norm_title(t.get("title"))
            ]
            if matches:
                break

        if len(matches) == 1:
            tasks.append(matches[0])
        elif matches:
            ambiguous.extend(matches)
        else:
            missing.append(reference)

    tasks = list({t["id"]: t for t in tasks}.values())
    ambiguous = list({t["id"]: t for t in ambiguous}.values())
    return tasks, missing, ambiguous


def _ambiguous_text(ambiguous: list) -> str:
    options = "; ".join(
        f"{_quoted(t.get('title') or 'Untitled task')} ({when_text(t) or 'no date'})"
        for t in ambiguous[:5]
    )
    return f"I found more than one matching task: {options}. Which one do you mean?"


def complete_task(user_id: str, args: dict) -> dict:
    tasks, missing, ambiguous = _resolve_task_refs(user_id, _ids(args))
    if ambiguous:
        raise ValueError(_ambiguous_text(ambiguous))
    if missing:
        raise ValueError(f"I couldn't find a task matching {missing[0]!r}.")
    done = task_service.complete_tasks(user_id, [t["id"] for t in tasks])
    return {
        "completed_count": len(done),
        "tasks": [_task_view(task) for task in done],
    }


def delete_task(user_id: str, args: dict) -> dict:
    raw_ids = args.get("task_ids")
    ids = list(dict.fromkeys(raw_ids if isinstance(raw_ids, list) else ([raw_ids] if raw_ids else [])))
    confirmation = args.get("confirmation", "request")
    pending = _delete_pending.get(user_id)

    if confirmation == "cancel":
        _delete_pending.pop(user_id, None)
        return {"status": "cancelled", "reply": "Okay, I left those tasks unchanged."}

    if confirmation == "confirm":
        if (
            not pending
            or pending["expires"] < time.time()
            or (ids and all(_is_uuid(i) for i in ids) and set(pending["task_ids"]) != set(ids))
        ):
            _delete_pending.pop(user_id, None)
            return {
                "status": "not_confirmed",
                "reply": "I don't have a matching deletion waiting for confirmation, so nothing was deleted. Please ask me to delete those tasks again.",
            }
        gone = task_service.delete_tasks(user_id, pending["task_ids"])
        _delete_pending.pop(user_id, None)
        names = ", ".join(_quoted(task.get("title") or "Untitled task") for task in gone)
        if not gone:
            return {"status": "not_found", "reply": "Those tasks were not found, so nothing was deleted."}
        return {
            "status": "deleted",
            "reply": f"Deleted {len(gone)} task{'s' if len(gone) != 1 else ''}: {names}.",
        }

    if confirmation != "request":
        raise ValueError("confirmation must be request, confirm, or cancel.")
    if not ids:
        raise ValueError("Provide task_ids to request deletion confirmation.")

    tasks, missing, ambiguous = _resolve_task_refs(user_id, ids)
    if ambiguous:
        return {"status": "needs_clarification", "reply": _ambiguous_text(ambiguous)}
    if missing or not tasks:
        name = missing[0] if missing else "that"
        return {
            "status": "not_found",
            "reply": f"I couldn't find a task matching {_quoted(name)}, so nothing was deleted. Please use the task title as it appears in your list.",
        }

    _delete_pending[user_id] = {
        "expires": time.time() + PENDING_TTL_SECONDS,
        "task_ids": [task["id"] for task in tasks],
        "titles": [task.get("title") or "Untitled task" for task in tasks],
    }
    names = ", ".join(_quoted(title) for title in _delete_pending[user_id]["titles"])
    return {
        "status": "needs_confirmation",
        "reply": f"Delete {names}? This can't be undone. Reply yes to confirm or no to cancel.",
    }


# ============================================================
# read / recommend
# ============================================================

def list_tasks(user_id: str, args: dict) -> list:
    tasks = task_service.list_tasks(
        user_id,
        section=args.get("section"),
        status=args.get("status"),
        search=args.get("search"),
        limit=args.get("limit", 20),
    )
    return [_task_view(task) for task in tasks]


def get_task(user_id: str, args: dict) -> dict:
    task_id = args["task_id"]

    task = task_service.get_task(user_id, task_id)

    if not task:
        raise LookupError("Task not found")

    return _task_view(task)


def recommend_task(user_id: str, args: dict) -> list:
    limit = 1
    tasks = task_service.recommend_tasks(
        user_id,
        limit=limit,
        exclude_ids=args.get("exclude_ids") or [],
    )
    return [_task_view(task) for task in tasks[:limit]]


def recommend_for_mood(user_id: str, args: dict) -> list:
    energy = args.get("energy")
    if energy not in ("low", "medium", "high"):
        raise ValueError("energy must be low, medium or high.")
    tasks = task_service.recommend_tasks(
        user_id,
        energy=energy,
        exclude_ids=args.get("exclude_ids") or [],
    )
    return [_task_view(task) for task in tasks[:1]]


def daily_digest(user_id: str, args: dict) -> dict:
    return _digest_view(task_service.get_daily_digest(user_id))


# ============================================================
# decline_request (off-topic questions and features the app lacks)
# ============================================================

def decline_request(user_id: str, args: dict) -> dict:
    """Fixed reply, so the model can never answer trivia or fake a feature."""
    if args.get("kind") == "unsupported_feature":
        reply = (
            "This app doesn't have reminders or notifications yet. "
            "I can add it as a task with a time instead, for example "
            "\u201cCall Amit tomorrow at 4 PM\u201d."
        )
    else:
        reply = (
            "I can only help with your tasks and schedule, so I can't help with that. "
            "Want to add a task or see what to do next?"
        )
    return {"status": "declined", "reply": reply}


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
                "Apply the user's answer to a pending duplicate, part-of, exact-time clash, or "
                "schedule-update clash. Never call add_tasks again for a pending creation. "
                "For schedule-update clashes, keep_existing leaves current times unchanged; "
                "update_anyway applies the previously shown changes despite overlap."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "choice": {
                        "type": "string",
                        "enum": [
                            "keep_existing", "update_existing", "merge", "add_separate",
                            "add_anyway", "reschedule_new", "update_anyway", "cancel",
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
                    "new_deadline": {
                        "type": "string",
                        "description": "Replacement deadline for a held flexible task, as ISO-8601 datetime with timezone and based only on the user's stated time.",
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
                "Update one or more existing tasks with the same changes. Use task_id for one task "
                "or task_ids for a bulk update. Include ONLY the fields the user wants to change. "
                "The system checks exact-time overlaps before applying schedule changes and may ask "
                "the user to decide. If the user supplies a different time after that question, "
                "call update_task again with the replacement time; this replaces the held change. "
                "To remove a value (for example clear a deadline), put its name in "
                "clear_fields. Never send null."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "task_ids": {"type": "array", "items": {"type": "string"}},
                    "title": {"type": "string"},
                    "section": {"type": "string", "enum": ["work", "personal", "leisure"]},
                    "brief": {"type": "string"},
                    "schedule_type": {"type": "string", "enum": ["flexible", "scheduled"]},
                    "deadline": {"type": "string", "description": "ISO-8601 datetime"},
                    "scheduled_start": {"type": "string", "description": "ISO-8601 datetime"},
                    "scheduled_end": {"type": "string", "description": "ISO-8601 datetime"},
                    "has_explicit_time": {"type": "boolean"},
                    "is_recurring": {"type": "boolean"},
                    "recurrence": {
                        "type": "string",
                        "description": "RRULE body string only, for example FREQ=DAILY or FREQ=WEEKLY;BYDAY=MO,WE,FR. Do not include RRULE:, DTSTART, UNTIL, or COUNT.",
                    },
                    "recurrence_end": {"type": "string", "description": "ISO-8601 datetime"},
                    "duration": {
                        "type": "integer",
                        "description": "Explicit duration in minutes. Only when the user states one."
                    },
                    "shift_minutes": {
                        "type": "integer",
                        "description": "Move the scheduled time of the task(s) later (positive) or earlier (negative) by this many minutes, keeping the length. Use it for 'shift / push / delay by N minutes'. Do not calculate the new time yourself."
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
                "required": []
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
            "description": (
                "Delete existing tasks only through the confirmation flow. First call with "
                "confirmation=request and task_ids taken from list_tasks (never a title) to show the exact titles; after user yes call with "
                "confirmation=confirm (the stored request identifies the exact tasks; task_ids "
                "may be omitted). If the user says no, use confirmation=cancel. "
                "The first call never deletes anything."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_ids": {"type": "array", "items": {"type": "string"}},
                    "confirmation": {"type": "string", "enum": ["request", "confirm", "cancel"]},
                },
                "required": []
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
                "Recommend ONE best task to work on right now. Use when the user asks what to do next "
                "and has NOT said anything about their mood or energy. Pass exclude_ids with "
                "the ids already suggested if the user wants a different suggestion."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Always use 1; the agent gives one focused suggestion."},
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
                "Recommend ONE task matched to the user's current energy. ONLY call this when the "
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
    {
        "type": "function",
        "function": {
            "name": "decline_request",
            "description": (
                "Call this INSTEAD of answering when the user's message is not about managing their own tasks: "
                "general knowledge or trivia (capitals, facts, news), maths, coding help, writing or translation, "
                "or advice unrelated to their tasks (kind=off_topic). Also call it with kind=unsupported_feature "
                "when the user asks to set up a feature this app does not have: reminders, alarms, notification "
                "settings, calendar sync (for example 'set a reminder 10 minutes before my meetings'). "
                "The system writes the reply; never answer those requests yourself and never add a task for them. "
                "Do NOT call it for greetings, for adding a task, or for questions about the user's own tasks and "
                "schedule. A reminder about one specific thing, like 'remind me to call Amit tomorrow at 4', is a "
                "normal task: use add_tasks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["off_topic", "unsupported_feature"]},
                },
                "required": ["kind"]
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
    "decline_request": decline_request,
}
