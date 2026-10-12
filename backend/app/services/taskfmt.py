"""
Small formatting helpers for replies the backend writes itself.

when_text(task) -> "today at 7:00 PM", "tomorrow", "today after 6:00 PM", "due Fri, Oct 9", ...
"""

from datetime import datetime
from typing import Optional

from app.services.timeutil import now_local, to_local


def clock(d: datetime) -> str:
    return f"{d.hour % 12 or 12}:{d.minute:02d} {'AM' if d.hour < 12 else 'PM'}"


def day_word(d: datetime) -> str:
    diff = (d.date() - now_local().date()).days

    if diff == 0:
        return "today"
    if diff == 1:
        return "tomorrow"
    if diff == -1:
        return "yesterday"

    return f"{d:%a, %b} {d.day}"


def when_text(task: dict) -> Optional[str]:
    start = task.get("scheduled_start")
    end = task.get("scheduled_end")
    deadline = task.get("deadline")
    explicit = task.get("has_explicit_time")

    if task.get("schedule_type") == "scheduled" and start:
        s = to_local(start)

        # exact time: "today at 7:00 PM"
        if explicit:
            return f"{day_word(s)} at {clock(s)}"

        e = to_local(end) if end else None

        # multi-day window ("this week"): "by Fri, Oct 9"
        if e and e.date() != s.date():
            return f"by {day_word(e)}"

        # whole-day window ("tomorrow"): "tomorrow"
        if e and s.hour == 0 and e.hour == 23:
            return day_word(s)

        # open-ended evening ("tonight"): "today after 6:00 PM"
        if e and e.hour == 23 and e.minute == 59:
            return f"{day_word(s)} after {clock(s)}"

        if e:
            return f"{day_word(s)}, {clock(s)}-{clock(e)}"

        return day_word(s)

    if deadline:
        d = to_local(deadline)
        if explicit:
            return f"due {day_word(d)} at {clock(d)}"
        return f"due {day_word(d)}"

    return None