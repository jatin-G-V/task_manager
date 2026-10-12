"""Calendar calculations for the recurrence patterns supported by the app."""

import re
from calendar import monthrange
from datetime import date, datetime, timedelta

from app.services.timeutil import to_local


_WEEKDAYS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}


def _weekday_set(rule: str, default_weekday: int) -> set[int]:
    value = rule.strip().lower()
    if value == "weekly":
        return {default_weekday}
    if value == "weekdays":
        return {0, 1, 2, 3, 4}
    if value == "weekends":
        return {5, 6}
    if value.startswith("weekly on "):
        value = value[len("weekly on "):]
    elif value.startswith("every "):
        value = value[len("every "):]
    if value in {"weekday", "weekdays"}:
        return {0, 1, 2, 3, 4}
    if value in {"weekend", "weekends"}:
        return {5, 6}

    days = set()
    for word in re.split(r",|\band\b|\s+", value):
        word = word.strip()
        if word.endswith("s") and word[:-1] in _WEEKDAYS:
            word = word[:-1]
        if word in _WEEKDAYS:
            days.add(_WEEKDAYS[word])
    return days


def _next_matching_date(rule: str, current: date) -> date:
    value = rule.strip().lower()

    if value in {"daily", "every day"}:
        return current + timedelta(days=1)
    if value in {"monthly", "every month"}:
        year = current.year + (1 if current.month == 12 else 0)
        month = 1 if current.month == 12 else current.month + 1
        return date(year, month, min(current.day, monthrange(year, month)[1]))
    if value in {"yearly", "annually", "every year"}:
        year = current.year + 1
        return date(year, current.month, min(current.day, monthrange(year, current.month)[1]))

    interval = re.fullmatch(r"(?:every\s+)?(\d+)\s+(day|week|month|year)s?", value)
    if interval:
        count = int(interval.group(1))
        unit = interval.group(2)
        if count < 1:
            raise ValueError("recurrence interval must be positive")
        if unit == "day":
            return current + timedelta(days=count)
        if unit == "week":
            return current + timedelta(weeks=count)
        if unit == "month":
            month_index = current.year * 12 + (current.month - 1) + count
            year, month_index = divmod(month_index, 12)
            month = month_index + 1
            return date(year, month, min(current.day, monthrange(year, month)[1]))
        year = current.year + count
        return date(year, current.month, min(current.day, monthrange(year, current.month)[1]))

    weekdays = _weekday_set(value, current.weekday())
    if weekdays:
        for offset in range(1, 8):
            candidate = current + timedelta(days=offset)
            if candidate.weekday() in weekdays:
                return candidate

    raise ValueError(f"unsupported recurrence rule: {rule}")


def next_occurrence(task: dict, completed_at: datetime) -> dict | None:
    """Return the next occurrence's time fields, or None if its series ended."""
    if not task.get("is_recurring") or not task.get("recurrence"):
        return None

    completed_local = to_local(completed_at)
    start_value = task.get("scheduled_start") if task.get("schedule_type") == "scheduled" else None
    deadline_value = task.get("deadline") if task.get("schedule_type") == "flexible" else None
    anchor_value = start_value or deadline_value
    anchor = to_local(anchor_value) if anchor_value else completed_local

    candidate_date = _next_matching_date(task["recurrence"], anchor.date())
    while True:
        if candidate_date < completed_local.date():
            candidate_date = _next_matching_date(task["recurrence"], candidate_date)
            continue

        # Completing shortly after midnight should not skip an occurrence
        # later on that same day. For exact-time tasks the start/deadline must
        # still be ahead; for date windows, keep today's occurrence while its
        # visible window is open.
        day_shift = (candidate_date - anchor.date()).days
        if start_value and task.get("has_explicit_time"):
            next_due_value = to_local(start_value) + timedelta(days=day_shift)
        elif start_value:
            visible_window_end = task.get("scheduled_end") or start_value
            next_due_value = to_local(visible_window_end) + timedelta(days=day_shift)
        elif deadline_value:
            next_due_value = to_local(deadline_value) + timedelta(days=day_shift)
        else:
            next_due_value = None

        if candidate_date == completed_local.date() and next_due_value and next_due_value <= completed_local:
            candidate_date = _next_matching_date(task["recurrence"], candidate_date)
            continue
        break

    recurrence_end = task.get("recurrence_end")
    if recurrence_end and candidate_date > to_local(recurrence_end).date():
        return None

    day_shift = (candidate_date - anchor.date()).days
    updates = {}

    if start_value:
        updates["scheduled_start"] = (to_local(start_value) + timedelta(days=day_shift)).isoformat()
        if task.get("scheduled_end"):
            updates["scheduled_end"] = (
                to_local(task["scheduled_end"]) + timedelta(days=day_shift)
            ).isoformat()
    elif deadline_value:
        updates["deadline"] = (to_local(deadline_value) + timedelta(days=day_shift)).isoformat()

    updates["_occurrence_date"] = candidate_date.isoformat()
    return updates
