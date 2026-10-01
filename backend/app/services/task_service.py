from datetime import datetime, timezone
from typing import Optional

from app.db.supabase_client import supabase


import logging
from postgrest.exceptions import APIError

logger = logging.getLogger(__name__)

def create_task(user_id: str, data: dict) -> dict:
    _validate_not_in_past(data)

    row = {
        **data,
        "user_id": user_id,
        "status": "pending",
    }

    result = (
        supabase
        .table("tasks")
        .insert(row)
        .execute()
    )

    if not result.data:
        raise ValueError("Failed to create task")

    return result.data[0]
def get_task(user_id: str, task_id: str) -> Optional[dict]:
    try:
        result = (
            supabase
            .table("tasks")
            .select("*")
            .eq("id", task_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except APIError:
        # e.g. the model sent a malformed id; treat as "not found"
        logger.warning("get_task lookup failed for id=%s", task_id, exc_info=True)
        return None

    # some supabase-py versions return None (not an empty response) on 0 rows
    return result.data if result else None




def list_tasks(
    user_id: str,
    section=None,
    status=None,
    search=None,
    limit=20,
) -> list:
    query = (
        supabase
        .table("tasks")
        .select("*")
        .eq("user_id", user_id)
    )

    if section:
        query = query.eq("section", section)

    if status:
        query = query.eq("status", status)
    else:
        query = query.neq("status", "completed")

    if search:
        query = query.ilike("title", f"%{search}%")

    result = (
        query
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return result.data


def update_task(user_id: str, task_id: str, updates: dict) -> dict:
    existing = get_task(user_id, task_id)

    if not existing:
        raise LookupError("Task not found")

    merged = {
        **existing,
        **updates,
    }

    if any(
        key in updates
        for key in (
            "deadline",
            "scheduled_start",
            "scheduled_end",
            "recurrence_end",
            "is_recurring",
            "recurrence",
            "schedule_type",
            "duration",
            "estimated_time_minutes",
        )
    ):
        _validate_not_in_past(merged)

    result = (
        supabase
        .table("tasks")
        .update(updates)
        .eq("id", task_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        raise ValueError("Failed to update task")

    return result.data[0]


def complete_tasks(user_id: str, task_ids: list) -> list:
    result = (
        supabase
        .table("tasks")
        .update(
            {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .in_("id", task_ids)
        .eq("user_id", user_id)
        .execute()
    )

    return result.data


def delete_tasks(user_id: str, task_ids: list) -> list:
    result = (
        supabase
        .table("tasks")
        .delete()
        .in_("id", task_ids)
        .eq("user_id", user_id)
        .execute()
    )

    return result.data


def recommend_tasks(user_id: str, limit: int = 3) -> list:
    candidates = list_tasks(
        user_id,
        status="pending",
        limit=50,
    )

    candidates = [
        task
        for task in candidates
        if not task.get("is_blocked")
    ]

    # Lower rank = higher priority.
    #
    # This matches the current urgency model:
    # urgent > high > medium > low > null
    urgency_rank = {
        "urgent": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
        None: 4,
    }

    def sort_key(task):
        time_signal = (
            task.get("scheduled_start")
            if task.get("has_explicit_time")
            else task.get("deadline")
        )

        return (
            time_signal is None,
            time_signal or "9999",
            urgency_rank.get(task.get("urgency"), 4),
        )

    candidates.sort(key=sort_key)

    return candidates[:limit]


def get_daily_digest(user_id: str) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()

    pending = list_tasks(
        user_id,
        status="pending",
        limit=50,
    )

    due_today = [
        task
        for task in pending
        if (
            task.get("deadline")
            or task.get("scheduled_start")
            or ""
        ).startswith(today)
    ]

    at_risk = [
        task
        for task in pending
        if task.get("is_blocked")
    ]

    suggested = recommend_tasks(user_id, limit=1)

    return {
        "due_today": due_today,
        "at_risk": at_risk,
        "suggested_focus": suggested[0] if suggested else None,
    }


def _is_past(value: str) -> bool:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))

    # Compare on the same clock:
    # naive strings -> naive now
    # aware strings -> aware now
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()

    return dt < now


def _validate_not_in_past(data: dict) -> None:
    # --------------------------------------------------
    # Duration validation
    # --------------------------------------------------
    #
    # duration is ONLY the duration explicitly provided by the user.
    # It must never be inferred here.
    #
    # When duration exists, estimated_time_minutes must match it.
    duration = data.get("duration")

    if duration is not None:
        if not isinstance(duration, int) or isinstance(duration, bool):
            raise ValueError(
                "duration must be a positive integer."
            )

        if duration <= 0:
            raise ValueError(
                "duration must be a positive integer."
            )

        estimated_time = data.get("estimated_time_minutes")

        if estimated_time != duration:
            raise ValueError(
                "estimated_time_minutes must equal duration "
                "when duration is provided."
            )

    # --------------------------------------------------
    # Estimated time validation
    # --------------------------------------------------
    #
    # A valid task should normally have an estimated time.
    # Do not enforce non-null here because non-task input and genuinely
    # unestimable tasks may still legitimately contain null.
    estimated_time = data.get("estimated_time_minutes")

    if estimated_time is not None:
        if (
            not isinstance(estimated_time, int)
            or isinstance(estimated_time, bool)
            or estimated_time <= 0
        ):
            raise ValueError(
                "estimated_time_minutes must be a positive integer."
            )

    # --------------------------------------------------
    # Deadline validation
    # --------------------------------------------------
    deadline = data.get("deadline")

    if deadline and _is_past(deadline):
        raise ValueError(
            f"The deadline ({deadline}) is already in the past."
        )

    # --------------------------------------------------
    # Scheduled time validation
    # --------------------------------------------------
    start = data.get("scheduled_start")
    end = data.get("scheduled_end")

    if start:
        if data.get("has_explicit_time"):
            if _is_past(start):
                raise ValueError(
                    f"The scheduled time ({start}) is already in the past."
                )
        else:
            if _is_past(end or start):
                raise ValueError(
                    "That time window has already ended."
                )

    # --------------------------------------------------
    # Recurrence validation
    # --------------------------------------------------
    recurrence_end = data.get("recurrence_end")

    if recurrence_end and _is_past(recurrence_end):
        raise ValueError(
            "The recurrence end date is already in the past."
        )

    if not data.get("is_recurring"):
        if data.get("recurrence") or data.get("recurrence_end"):
            raise ValueError(
                "recurrence and recurrence_end require is_recurring=true."
            )

    # --------------------------------------------------
    # Schedule consistency
    # --------------------------------------------------
    schedule_type = data.get("schedule_type")

    if schedule_type == "scheduled":
        if not data.get("scheduled_start"):
            raise ValueError(
                "scheduled task requires scheduled_start"
            )

        if data.get("deadline"):
            raise ValueError(
                "scheduled task cannot have a deadline"
            )

    elif schedule_type == "flexible":
        if data.get("scheduled_start"):
            raise ValueError(
                "flexible task cannot have scheduled_start"
            )
