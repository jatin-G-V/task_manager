"""Exact-time task clash detection, with no database access."""

from datetime import timedelta

from app.services.timeutil import now_local, to_local


MIN_SLOT_MINUTES = 15
_IGNORED_STATUSES = {"completed", "dropped"}


def is_exact(task: dict) -> bool:
    return (
        task.get("schedule_type") == "scheduled"
        and bool(task.get("has_explicit_time"))
        and bool(task.get("scheduled_start"))
    )


def _span(task: dict):
    start = to_local(task["scheduled_start"])
    end = to_local(task["scheduled_end"]) if task.get("scheduled_end") else None

    if end is None or end <= start:
        end = start + timedelta(minutes=MIN_SLOT_MINUTES)

    return start, end


def find_clashes(parsed: dict, open_tasks: list, limit: int = 3) -> list:
    """Return overlapping exact-time open tasks, earliest first."""
    if not is_exact(parsed):
        return []

    new_start, new_end = _span(parsed)
    if new_start < now_local():
        return []

    found = []

    for task in open_tasks:
        if task.get("status") in _IGNORED_STATUSES or task.get("is_blocked"):
            continue
        if not is_exact(task):
            continue
        if parsed.get("id") and task.get("id") == parsed.get("id"):
            continue

        start, end = _span(task)
        if new_start < end and start < new_end:
            found.append((start, task))

    found.sort(key=lambda item: item[0])
    return [task for _, task in found[:limit]]
