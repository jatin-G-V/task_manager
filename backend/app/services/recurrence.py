"""RRULE validation, legacy conversion, display text, and occurrence dates."""

import re
from datetime import datetime, timedelta

from dateutil.rrule import rrulestr

from app.services.timeutil import APP_TZ, to_local


_DAY_CODES = {
    "monday": "MO", "mon": "MO",
    "tuesday": "TU", "tue": "TU", "tues": "TU",
    "wednesday": "WE", "wed": "WE",
    "thursday": "TH", "thu": "TH", "thur": "TH", "thurs": "TH",
    "friday": "FR", "fri": "FR",
    "saturday": "SA", "sat": "SA",
    "sunday": "SU", "sun": "SU",
}
_CODE_TO_SHORT = {
    "MO": "Mon", "TU": "Tue", "WE": "Wed", "TH": "Thu",
    "FR": "Fri", "SA": "Sat", "SU": "Sun",
}
_CODE_ORDER = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


def _parts(rule: str) -> dict[str, str]:
    result = {}
    for part in rule.split(";"):
        if "=" not in part:
            raise ValueError("Use a valid repeating schedule, such as every day or every Monday.")
        key, value = part.split("=", 1)
        result[key.strip().upper()] = value.strip().upper()
    return result


def _day_code(value: str) -> str | None:
    return _DAY_CODES.get(value.strip().lower().rstrip("s"))


def _parse_day_words(value: str) -> list[str]:
    words = re.split(r"\s*(?:,|\band\b)\s*", value.strip(), flags=re.IGNORECASE)
    codes = []
    for word in words:
        word = word.strip().lower()
        code = _day_code(word)
        if not code:
            raise ValueError("I couldn't understand the weekdays in that repeating schedule.")
        if code not in codes:
            codes.append(code)
    return [code for code in _CODE_ORDER if code in codes]


def legacy_to_rrule(text: str) -> str:
    """Convert recurrence strings used by older app versions into RRULE bodies."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("A repeating task needs a valid recurrence pattern.")

    value = text.strip()
    if value.upper().startswith("RRULE:"):
        value = value.split(":", 1)[1].strip()
    if value.upper().startswith("FREQ="):
        return value.upper()

    normalized = re.sub(r"\s+", " ", value.lower()).strip()
    if normalized in {"daily", "every day"}:
        return "FREQ=DAILY"
    if normalized in {"every other day", "every 2 days", "every 2 day"}:
        return "FREQ=DAILY;INTERVAL=2"
    if normalized == "weekly":
        return "FREQ=WEEKLY"
    if normalized in {"monthly", "every month"}:
        return "FREQ=MONTHLY"
    if normalized in {"yearly", "annually", "every year"}:
        return "FREQ=YEARLY"
    if normalized in {"weekdays", "weekday"}:
        return "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
    if normalized in {"weekends", "weekend"}:
        return "FREQ=WEEKLY;BYDAY=SA,SU"

    daily_except = re.fullmatch(r"(?:daily|every day) except (.+)", normalized)
    if daily_except:
        excluded = set(_parse_day_words(daily_except.group(1)))
        included = [day for day in _CODE_ORDER if day not in excluded]
        if not included:
            raise ValueError("A repeating schedule must include at least one day.")
        return "FREQ=WEEKLY;BYDAY=" + ",".join(included)

    interval = re.fullmatch(r"(?:every )?(\d+) (day|week|month|year)s?", normalized)
    if interval:
        count = int(interval.group(1))
        if count < 1:
            raise ValueError("The repeat interval must be at least one.")
        unit = interval.group(2)
        frequency = {"day": "DAILY", "week": "WEEKLY", "month": "MONTHLY", "year": "YEARLY"}[unit]
        return f"FREQ={frequency};INTERVAL={count}"

    weekly = re.fullmatch(r"(?:weekly on|every) (.+)", normalized)
    if weekly:
        days = _parse_day_words(weekly.group(1))
        return "FREQ=WEEKLY;BYDAY=" + ",".join(days)

    raise ValueError("I couldn't understand that repeating schedule. Please choose a supported repeat pattern.")


def _canonical_rule(rule: str) -> str:
    if not isinstance(rule, str) or not rule.strip():
        raise ValueError("A repeating task needs a valid recurrence pattern.")
    body = rule.strip()
    if body.upper().startswith("RRULE:"):
        body = body.split(":", 1)[1].strip()
    if not body.upper().startswith("FREQ="):
        body = legacy_to_rrule(body)
    return body.upper()


def validate_rule(rule: str) -> None:
    """Raise a user-friendly ValueError if a recurrence is not a valid RRULE."""
    body = _canonical_rule(rule)
    parts = _parts(body)
    if "FREQ" not in parts:
        raise ValueError("A repeating schedule must include a frequency.")
    if any(key in parts for key in ("DTSTART", "UNTIL", "COUNT")):
        raise ValueError("Keep the repeat pattern separate from its start and end dates.")
    try:
        rrulestr(body, dtstart=datetime(2000, 1, 1))
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("I couldn't understand that repeating schedule. Please choose a supported pattern.") from exc


def _build_rule(rule: str, anchor: datetime):
    """Build a dateutil rule, clamping month-end and Feb 29 patterns safely.

    For a monthly day 29-31, BYSETPOS=-1 picks that month's last calendar
    day (28/29/30/31). A yearly Feb 29 series similarly uses Feb 28 in
    non-leap years. Every occurrence still derives from the original anchor.
    """
    body = _canonical_rule(rule)
    validate_rule(body)
    parts = _parts(body)
    frequency = parts.get("FREQ")

    if frequency == "MONTHLY":
        raw_days = parts.get("BYMONTHDAY")
        if raw_days:
            days = [int(day) for day in raw_days.split(",")]
            if any(day > 28 for day in days):
                parts["BYMONTHDAY"] = "28,29,30,31"
                parts["BYSETPOS"] = "-1"
        elif not parts.get("BYDAY"):
            parts["BYMONTHDAY"] = str(anchor.day)
            if anchor.day > 28:
                parts["BYMONTHDAY"] = "28,29,30,31"
                parts["BYSETPOS"] = "-1"

    if frequency == "YEARLY" and anchor.month == 2 and anchor.day == 29:
        parts.setdefault("BYMONTH", "2")
        parts["BYMONTHDAY"] = "28,29"
        parts["BYSETPOS"] = "-1"

    cooked = ";".join(f"{key}={value}" for key, value in parts.items())
    try:
        return rrulestr(cooked, dtstart=anchor)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("I couldn't understand that repeating schedule. Please choose a supported pattern.") from exc


def validate_task_recurrence(
    task: dict,
    check_first_date: bool = True,
) -> str | None:
    """Validate and return a canonical RRULE for a recurring task."""
    if not task.get("is_recurring"):
        return None
    recurrence = task.get("recurrence")
    if not recurrence:
        raise ValueError("A repeating task needs a recurrence pattern.")

    canonical = _canonical_rule(recurrence)
    validate_rule(canonical)
    start = task.get("scheduled_start")
    deadline = task.get("deadline")
    if not start and not deadline:
        raise ValueError("A repeating task needs a start time or a deadline")

    if check_first_date:
        first_value = start or deadline
        first = to_local(first_value).replace(tzinfo=None)
        generated = _build_rule(canonical, first).after(
            first - timedelta(microseconds=1),
            inc=True,
        )
        if generated != first:
            raise ValueError("The first date must match the repeating pattern.")
    return canonical


def _local_iso(value: datetime) -> str:
    return value.replace(tzinfo=APP_TZ).isoformat()


def snap_first_occurrence(parsed: dict) -> dict:
    """Move a recurring task's first date forward to its first matching date.

    The parser sometimes returns a date that conflicts with the requested
    recurrence pattern. Preserve its local time and, for scheduled tasks, the
    task's duration while moving it to the first occurrence on or after it.
    """
    result = dict(parsed)
    if not parsed.get("is_recurring"):
        return result

    start_field = (
        "scheduled_start"
        if parsed.get("schedule_type") == "scheduled"
        else "deadline"
    )
    first_value = parsed.get(start_field)
    if not first_value:
        return result

    recurrence = parsed.get("recurrence")
    if not recurrence:
        return result

    try:
        canonical = _canonical_rule(recurrence)
        validate_rule(canonical)
        first = to_local(first_value).replace(tzinfo=None)
        generated = _build_rule(canonical, first).after(
            first - timedelta(microseconds=1),
            inc=True,
        )
    except (ValueError, TypeError, OverflowError):
        return result

    if generated is None or generated == first:
        return result

    delta = generated - first
    result[start_field] = _local_iso(generated)
    if start_field == "scheduled_start" and parsed.get("scheduled_end"):
        try:
            end = to_local(parsed["scheduled_end"]).replace(tzinfo=None)
            result["scheduled_end"] = _local_iso(end + delta)
        except (ValueError, TypeError, OverflowError):
            return dict(parsed)
    return result


def next_occurrence(task: dict, completed_at: datetime) -> dict | None:
    """Return the next occurrence's time fields, or None after the series ends."""
    if not task.get("is_recurring") or not task.get("recurrence"):
        return None

    completed_local = to_local(completed_at)
    start_value = task.get("scheduled_start") if task.get("schedule_type") == "scheduled" else None
    deadline_value = task.get("deadline") if task.get("schedule_type") == "flexible" else None
    anchor_value = task.get("recurrence_anchor") or start_value or deadline_value
    anchor_local = to_local(anchor_value) if anchor_value else completed_local
    anchor = anchor_local.replace(tzinfo=None)
    rule = _build_rule(task["recurrence"], anchor)

    current_value = start_value or deadline_value or anchor_local
    current_start = to_local(current_value).replace(tzinfo=None)
    completed_naive = completed_local.replace(tzinfo=None)
    threshold = max(completed_naive, current_start)
    candidate = rule.after(threshold, inc=False)
    if candidate is None:
        return None

    recurrence_end = task.get("recurrence_end")
    if recurrence_end and candidate.date() > to_local(recurrence_end).date():
        return None

    updates = {}
    if start_value or task.get("schedule_type") == "scheduled":
        updates["scheduled_start"] = _local_iso(candidate)
        current_end = task.get("scheduled_end")
        if current_end:
            end_local = to_local(current_end).replace(tzinfo=None)
            duration = end_local - current_start
            updates["scheduled_end"] = _local_iso(candidate + duration)
    else:
        # Older recurring flexible tasks without a date use completion time
        # as their anchor and receive a real next deadline instead of reappearing.
        updates["deadline"] = _local_iso(candidate)

    updates["_occurrence_date"] = candidate.date().isoformat()
    return updates


def rrule_to_text(rule: str | None, end=None) -> str | None:
    """Render an RRULE (or supported legacy value) as concise user-facing text."""
    if not rule:
        return None
    try:
        parts = _parts(_canonical_rule(rule))
    except ValueError:
        return str(rule).strip()

    frequency = parts.get("FREQ")
    interval = int(parts.get("INTERVAL", "1"))
    byday = parts.get("BYDAY", "").split(",") if parts.get("BYDAY") else []
    if frequency == "DAILY":
        label = "every day" if interval == 1 else f"every {interval} days"
    elif frequency == "WEEKLY" and byday:
        days = [
            _CODE_TO_SHORT[day[-2:]]
            for day in byday
            if day[-2:] in _CODE_TO_SHORT
        ]
        label = "every " + ", ".join(days)
        if interval > 1:
            label = f"every {interval} weeks on " + ", ".join(days)
    elif frequency == "WEEKLY":
        label = "every week" if interval == 1 else f"every {interval} weeks"
    elif frequency == "MONTHLY":
        label = "every month" if interval == 1 else f"every {interval} months"
    elif frequency == "YEARLY":
        label = "every year" if interval == 1 else f"every {interval} years"
    else:
        label = str(rule).strip()

    if end:
        end_local = to_local(end)
        label += f" until {end_local:%a, %b} {end_local.day}"
    return label


__all__ = [
    "legacy_to_rrule",
    "next_occurrence",
    "rrule_to_text",
    "snap_first_occurrence",
    "validate_rule",
    "validate_task_recurrence",
]
