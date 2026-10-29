"""Small helpers shared by the tests. No network and no app imports at module level."""

import json
import uuid
from datetime import timedelta


def unique_title(prefix: str = "task") -> str:
    """A title no other test or real task can share (safe to search for in responses)."""
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def as_list(data) -> list:
    """Accept either a bare list or {"tasks": [...]} style responses."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("tasks", "items", "data", "results"):
            if isinstance(data.get(key), list):
                return data[key]
    raise AssertionError(f"Unexpected list response shape: {str(data)[:200]}")


def contains_text(data, text: str) -> bool:
    """True if `text` appears anywhere inside a JSON-like response."""
    return text in json.dumps(data, default=str)


def future_iso(hours: float = 24) -> str:
    """ISO datetime `hours` from now in the app timezone (always passes the past-time rule)."""
    from app.services.timeutil import now_local

    return (now_local() + timedelta(hours=hours)).isoformat()


def task_payload(**overrides) -> dict:
    """A valid task as task_service.create_task expects it (the parser's output shape).

    Adjust the defaults here ONCE if create_task wants different fields.
    """
    payload = {
        "title": unique_title(),
        "section": "work",
        "brief": None,
        "schedule_type": "flexible",
        "deadline": future_iso(24),
        "scheduled_start": None,
        "scheduled_end": None,
        "has_explicit_time": True,
        "is_recurring": False,
        "recurrence": None,
        "recurrence_end": None,
        "duration": None,
        "estimated_time_minutes": None,
        "effort": "medium",
        "urgency": "medium",
    }
    payload.update(overrides)
    return payload


# ---- database helpers (used by the API tests) ------------------------------

WEEKDAY_CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def db_row(admin, task_id):
    """The task row exactly as stored (service role, bypasses RLS), or None."""
    rows = admin.table("tasks").select("*").eq("id", task_id).execute().data
    return rows[0] if rows else None


def db_rows(admin, user_id, title):
    """Every row of one user with this title (a recurring series shares its title)."""
    return (
        admin.table("tasks").select("*")
        .eq("user_id", user_id).eq("title", title)
        .order("created_at").execute().data
    )


def past_iso(hours: float = 24) -> str:
    return future_iso(-hours)


def recurring_overrides(days_ahead: int = 2, minutes: int = 20, series_days: int = 60):
    """Overrides for seed_task that make a valid weekly task. Returns (overrides, start)."""
    from app.services.timeutil import now_local

    start = (now_local() + timedelta(days=days_ahead)).replace(
        hour=20, minute=0, second=0, microsecond=0
    )
    end = start + timedelta(minutes=minutes)

    overrides = {
        "title": unique_title("rec"),
        "schedule_type": "scheduled",
        "deadline": None,
        "scheduled_start": start.isoformat(),
        "scheduled_end": end.isoformat(),
        "has_explicit_time": True,
        "duration": minutes,
        "estimated_time_minutes": minutes,
        "is_recurring": True,
        "recurrence": f"FREQ=WEEKLY;BYDAY={WEEKDAY_CODES[start.weekday()]}",
        "recurrence_end": (start + timedelta(days=series_days)).isoformat(),
    }
    return overrides, start
