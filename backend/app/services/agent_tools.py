from app.services import task_service
from typing import Any

from app.services.task_parser import parse_task_text

def add_task(user_id: str, args: dict) -> dict:
    raw_text = args["raw_text"]
    parsed = parse_task_text(raw_text)

    is_task = parsed.pop("is_task", True)
    if not is_task:
        raise ValueError("That doesn't look like a task, so nothing was created.")

    return task_service.create_task(user_id, parsed)

# ---------- update_task ----------
# Only these fields can be changed by the agent (protects id, user_id, status, ...).
# estimated_time_minutes is intentionally absent: it is synced from duration below.
UPDATABLE_FIELDS = {
    "title", "section", "brief", "schedule_type", "deadline",
    "scheduled_start", "scheduled_end", "has_explicit_time",
    "is_recurring", "recurrence", "recurrence_end",
    "duration", "effort", "urgency",
}

# Fields the user may explicitly empty. The model lists them in `clear_fields`
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

    task = task_service.get_task(
        user_id,
        task_id
    )

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

TOOLS = [
    
{
    "type": "function",
    "function": {
        "name": "add_task",
        "description": "Create a new task from the user's own description of what they want to do. Pass their wording through as-is — do not extract section/effort/urgency/deadline yourself, the system parses it properly using the same logic as manual task entry.",
        "parameters": {
            "type": "object",
            "properties": {
                "raw_text": {
                    "type": "string",
                    "description": "The task exactly as the user described it, in their own words."
                }
            },
            "required": ["raw_text"]
        }
    }

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
},{
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
                    "enum": ["pending", "in_progress", "completed", "blocked", None]
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
            "properties": {
                "task_id": {"type": "string"}
            },
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
        "description": "Give an overview of the user's tasks for today, including due tasks, blocked tasks, and suggested focus.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}
]

TOOL_FUNCTIONS = {
    "add_task": add_task,
    "update_task": update_task,
    "complete_task": complete_task,
    "delete_task": delete_task,
    "list_tasks": list_tasks,
    "get_task": get_task,
    "recommend_task": recommend_task,
    "recommend_for_mood": recommend_for_mood,
    "daily_digest": daily_digest,
}