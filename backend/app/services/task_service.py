from datetime import datetime, timezone
from typing import Optional
import logging
import re
from uuid import NAMESPACE_URL, uuid5

from rapidfuzz import fuzz
from postgrest.exceptions import APIError

from app.services.recommendation import rank, build_dashboard
from app.services.recurrence import next_occurrence
from app.services.timeutil import now_local, now_local_naive, to_local
from app.db.supabase_client import supabase


logger = logging.getLogger(__name__)


# ============================================================
# Duplicate / similar task helpers
# ============================================================

def _norm(t):
    return re.sub(r"[^a-z0-9 ]", " ", (t or "").lower()).strip()


def _anchor(t):
    v = t.get("scheduled_start") or t.get("deadline")
    return to_local(v) if v else None


def find_similar_tasks(user_id: str, parsed: dict, limit: int = 3) -> list:
    title = _norm(parsed.get("title"))

    if not title:
        return []

    new_when = _anchor(parsed)
    matches = []

    for t in list_tasks(user_id, limit=200):
        score = fuzz.token_sort_ratio(title, _norm(t.get("title")))
        old_when = _anchor(t)

        same_day = (
            (new_when is None and old_when is None)
            or (
                new_when
                and old_when
                and new_when.date() == old_when.date()
            )
        )

        # same day: be sensitive; different day: only near-identical titles
        if (same_day and score >= 80) or (score >= 90):
            matches.append(
                {
                    "id": t["id"],
                    "title": t["title"],
                    "when": t.get("scheduled_start") or t.get("deadline"),
                    "same_day": bool(same_day),
                    "similarity": round(score),
                }
            )

    matches.sort(key=lambda m: (not m["same_day"], -m["similarity"]))

    return matches[:limit]


def candidate_tasks(user_id: str, limit: int = 40) -> list:
    """Open tasks sent to the parser so it can spot duplicates / part-of items."""
    return list_tasks(user_id, limit=limit)


def merge_into_task(user_id: str, task_id: str, item: str) -> dict:
    """Append a small item to the brief of an existing broader task."""
    task = get_task(user_id, task_id)

    if not task:
        raise LookupError("Task not found")

    brief = (task.get("brief") or "").strip()
    item = item.strip()
    new_brief = f"{brief}; {item}" if brief else item

    update_task(user_id, task["id"], {"brief": new_brief})

    return {"status": "merged", "title": task["title"]}


# ============================================================
# CRUD
# ============================================================

def create_task(user_id: str, data: dict) -> dict:
    # Agent parser output may omit a section when the user's intent is unclear.
    # Keep those rows visible in the app's supported task store.
    data = dict(data)
    if data.get("section") not in {"work", "personal", "leisure"}:
        data["section"] = "personal"

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
        logger.warning(
            "get_task lookup failed for id=%s",
            task_id,
            exc_info=True,
        )
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

    # Keep explicit duration and estimated duration aligned for both API and
    # agent updates. A duration-only update should not erase an older deadline.
    if updates.get("duration") is not None:
        merged["estimated_time_minutes"] = updates["duration"]
        updates = {**updates, "estimated_time_minutes": updates["duration"]}

    # Validate temporal values only when the caller changed those values.
    # Schedule and recurrence consistency still use the fully merged row.
    _validate_not_in_past(merged, changed_fields=set(updates))

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


def _ensure_next_occurrence(user_id: str, completed_task: dict) -> Optional[dict]:
    if not completed_task.get("is_recurring") or not completed_task.get("recurrence"):
        return None

    completed_at = completed_task.get("completed_at") or datetime.now(timezone.utc).isoformat()
    try:
        next_fields = next_occurrence(completed_task, to_local(completed_at))
    except ValueError:
        logger.warning(
            "Unsupported recurrence rule %r for task %s; no next occurrence was created",
            completed_task.get("recurrence"),
            completed_task.get("id"),
        )
        return None

    if next_fields is None:
        return None

    occurrence_date = next_fields.pop("_occurrence_date")
    occurrence_anchor = (
        next_fields.get("scheduled_start")
        or next_fields.get("deadline")
        or occurrence_date
    )
    occurrence_id = str(
        uuid5(
            NAMESPACE_URL,
            f"{user_id}:{completed_task['id']}:{occurrence_anchor}",
        )
    )

    fields_to_copy = (
        "title",
        "section",
        "brief",
        "schedule_type",
        "deadline",
        "scheduled_start",
        "scheduled_end",
        "has_explicit_time",
        "is_recurring",
        "recurrence",
        "recurrence_end",
        "duration",
        "estimated_time_minutes",
        "effort",
        "urgency",
        "source_type",
    )
    row = {
        field: completed_task.get(field)
        for field in fields_to_copy
        if field in completed_task
    }
    row.update(next_fields)
    row.update(
        {
            "id": occurrence_id,
            "user_id": user_id,
            "section": row.get("section") or "personal",
            "status": "pending",
            "is_blocked": False,
        }
    )

    try:
        result = supabase.table("tasks").insert(row).execute()
        if result.data:
            return result.data[0]
    except APIError:
        # A retry or concurrent completion can reach the same occurrence.
        # Its deterministic UUID makes insertion idempotent.
        existing = (
            supabase.table("tasks")
            .select("*")
            .eq("id", occurrence_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if existing and existing.data:
            return existing.data
        raise

    existing = (
        supabase.table("tasks")
        .select("*")
        .eq("id", occurrence_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        return existing.data
    raise ValueError("Failed to create the next recurring task occurrence")


def complete_tasks(user_id: str, task_ids: list) -> list:
    if not task_ids:
        return []

    (
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
        .neq("status", "completed")
        .execute()
    )

    result = (
        supabase.table("tasks")
        .select("*")
        .in_("id", task_ids)
        .eq("user_id", user_id)
        .execute()
    )
    completed = [
        task for task in (result.data or [])
        if task.get("status") == "completed"
    ]

    for task in completed:
        _ensure_next_occurrence(user_id, task)

    return completed


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


# ============================================================
# Recommendations / dashboard
# ============================================================

def recommend_tasks(
    user_id: str,
    limit: int = 3,
    energy: Optional[str] = None,
    exclude_ids: Optional[list] = None,
) -> list:
    # list_tasks already skips completed; the engine filters blocked/dropped itself
    tasks = list_tasks(user_id, limit=100)

    # `now` is the local wall clock in the app timezone (see timeutil.py).
    return rank(
        tasks,
        now=now_local_naive(),
        limit=limit,
        energy=energy,
        exclude_ids=exclude_ids or [],
    )


def get_dashboard(
    user_id: str,
    energy: Optional[str] = None,
) -> dict:
    tasks = list_tasks(user_id, limit=500)

    # `now` is the local wall clock in the app timezone (see timeutil.py).
    return build_dashboard(
        tasks,
        now=now_local_naive(),
        energy=energy,
    )


def get_daily_digest(user_id: str) -> dict:
    d = get_dashboard(user_id)

    return {
        "due_today": d["due_today"],
        "at_risk": d["at_risk"],
        "overdue": d["overdue"],
        "suggested_focus": (
            d["suggested"][0]
            if d["suggested"]
            else None
        ),
    }


# ============================================================
# Validation
# ============================================================

def _is_past(value: str) -> bool:
    # Both sides are timezone-aware, so the comparison is always on real instants.
    return to_local(value) < now_local()


def _validate_not_in_past(
    data: dict,
    changed_fields: Optional[set[str]] = None,
) -> None:
    def changed(field: str) -> bool:
        return changed_fields is None or field in changed_fields

    # --------------------------------------------------
    # Duration validation
    # --------------------------------------------------

    # duration is ONLY the duration explicitly provided by the user.
    # It must never be inferred here.
    # When duration exists, estimated_time_minutes must match it.
    duration = data.get("duration")

    if duration is not None:
        if not isinstance(duration, int) or isinstance(duration, bool):
            raise ValueError("duration must be a positive integer.")

        if duration <= 0:
            raise ValueError("duration must be a positive integer.")

        estimated_time = data.get("estimated_time_minutes")

        if estimated_time != duration:
            raise ValueError(
                "estimated_time_minutes must equal duration "
                "when duration is provided."
            )

    # --------------------------------------------------
    # Estimated time validation
    # --------------------------------------------------

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

    if deadline and changed("deadline") and _is_past(deadline):
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
            if changed("scheduled_start") and _is_past(start):
                raise ValueError(
                    f"The scheduled time ({start}) is already in the past."
                )
            if end and changed("scheduled_end") and _is_past(end):
                raise ValueError(
                    f"The scheduled end time ({end}) is already in the past."
                )
        else:
            changed_window = changed("scheduled_start") or changed("scheduled_end")
            if changed_window and _is_past(end or start):
                raise ValueError("That time window has already ended.")

    # --------------------------------------------------
    # Recurrence validation
    # --------------------------------------------------

    recurrence_end = data.get("recurrence_end")

    if recurrence_end and changed("recurrence_end") and _is_past(recurrence_end):
        raise ValueError("The recurrence end date is already in the past.")

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
            raise ValueError("scheduled task requires scheduled_start")

        if data.get("deadline"):
            raise ValueError("scheduled task cannot have a deadline")

    elif schedule_type == "flexible":
        if data.get("scheduled_start"):
            raise ValueError("flexible task cannot have scheduled_start")
