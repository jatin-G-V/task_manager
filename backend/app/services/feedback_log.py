"""Non-blocking logging of implicit feedback signals.

Rules:
- log_event() never raises and never makes the caller wait.
- Inserts run on a small background thread pool.
- Set FEEDBACK_LOGGING=0 in .env to switch all logging off.
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from app.db.supabase_client import supabase
from app.services.timeutil import now_local, to_local

logger = logging.getLogger(__name__)

ENABLED = os.environ.get("FEEDBACK_LOGGING", "1").strip() == "1"

# A task edited or deleted this soon after creation was probably created wrongly.
EARLY_WINDOW_MINUTES = 10

EVENT_TYPES = {
    "thumb",
    "task_edited_soon",
    "task_deleted_soon",
    "dup_decision",
}

# Only fields the user (or the AI) can really change. estimated_time_minutes and
# recurrence_anchor are synced automatically, so they are left out.
TRACKED_FIELDS = (
    "title", "section", "brief", "schedule_type", "deadline",
    "scheduled_start", "scheduled_end", "has_explicit_time",
    "is_recurring", "recurrence", "recurrence_end",
    "duration", "effort", "urgency",
)
_TIME_FIELDS = {"deadline", "scheduled_start", "scheduled_end", "recurrence_end"}

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="feedback-log")


def _insert(row: dict) -> None:
    try:
        supabase.table("feedback_events").insert(row).execute()
    except Exception as exc:
        logger.warning(
            "feedback event insert failed (%s: %s)",
            type(exc).__name__,
            str(exc)[:200],
        )


def log_event(
    user_id: str,
    event_type: str,
    task_id: Optional[str] = None,
    payload: Optional[dict] = None,
) -> None:
    """Queue one event. Safe to call from anywhere."""
    if not ENABLED:
        return

    try:
        if event_type not in EVENT_TYPES:
            logger.warning("Unknown feedback event type %r ignored", event_type)
            return

        # make sure the payload is plain JSON (datetimes, UUIDs, ...)
        clean_payload = json.loads(json.dumps(payload or {}, default=str))

        row = {
            "user_id": user_id,
            "event_type": event_type,
            "task_id": str(task_id) if task_id else None,
            "payload": clean_payload,
        }
        _executor.submit(_insert, row)
    except Exception:
        logger.warning("Could not queue feedback event %r", event_type, exc_info=True)


# ============================================================
# Early edit / delete of a task
# ============================================================

def _minutes_since_created(row: dict) -> Optional[float]:
    created = row.get("created_at")
    if not created:
        return None
    try:
        return (now_local() - to_local(created)).total_seconds() / 60
    except Exception:
        return None


def _norm(field: str, value):
    if value is None or value == "":
        return None
    if field in _TIME_FIELDS:
        try:
            return to_local(value).isoformat()
        except Exception:
            return str(value)
    return value


def _short(value):
    return value[:200] if isinstance(value, str) else value


def log_task_edit(user_id: str, existing: dict, updates: dict) -> None:
    """Log which fields changed if the task was edited soon after creation."""
    if not ENABLED:
        return
    try:
        age = _minutes_since_created(existing)
        if age is None or age > EARLY_WINDOW_MINUTES:
            return

        changes = {}
        for field in TRACKED_FIELDS:
            if field not in updates:
                continue
            old = existing.get(field)
            new = updates.get(field)
            if _norm(field, old) == _norm(field, new):
                continue
            changes[field] = {"old": _short(old), "new": _short(new)}

        if not changes:
            return

        log_event(
            user_id,
            "task_edited_soon",
            task_id=existing.get("id"),
            payload={
                "minutes_after_create": round(age, 1),
                "source_type": existing.get("source_type"),
                "fields": changes,
            },
        )
    except Exception:
        logger.warning("Could not log task edit", exc_info=True)


def log_task_delete(user_id: str, row: dict) -> None:
    """Log a delete if the task was deleted soon after creation."""
    if not ENABLED:
        return
    try:
        age = _minutes_since_created(row)
        if age is None or age > EARLY_WINDOW_MINUTES:
            return

        log_event(
            user_id,
            "task_deleted_soon",
            task_id=row.get("id"),
            payload={
                "minutes_after_create": round(age, 1),
                "source_type": row.get("source_type"),
                "title": _short((row.get("title") or "")[:80]),
            },
        )
    except Exception:
        logger.warning("Could not log task delete", exc_info=True)