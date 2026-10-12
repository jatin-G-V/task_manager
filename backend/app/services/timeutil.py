"""
Single place for timezone handling.

Rules
  * The app has one working timezone (APP_TIMEZONE, default Asia/Kolkata).
    Later this can become a per-user value.
  * The database stores real instants (timestamptz). Supabase returns them in UTC.
  * The LLM only knows local wall-clock time, so anything it returns is read as
    local time (see parse_model_dt).
  * The recommendation engine compares naive LOCAL wall-clock datetimes.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo


APP_TZ = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))


def now_local() -> datetime:
    """Aware 'now' in the app timezone."""
    return datetime.now(APP_TZ)


def now_local_naive() -> datetime:
    """Naive 'now' showing the local wall clock (what the engine compares with)."""
    return now_local().replace(tzinfo=None)


def utc_offset_str() -> str:
    """Current UTC offset like +05:30."""
    raw = now_local().strftime("%z")  # +0530
    return f"{raw[:3]}:{raw[3:]}"


def to_local(value) -> datetime:
    """Real instant (from the DB or already validated) -> aware local datetime.

    A string without any offset is assumed to already be local time.
    """
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    if dt.tzinfo is None:
        return dt.replace(tzinfo=APP_TZ)

    return dt.astimezone(APP_TZ)


def parse_model_dt(value) -> Optional[datetime]:
    """Datetime written by the LLM -> aware local datetime.

    The model is told the local time and offset, but it sometimes returns
    a bare time or labels it Z / +00:00. Because it never sees UTC, a zero offset
    from the model means 'local wall clock', not a real UTC instant.
    """
    if not value:
        return None

    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    if dt.tzinfo is None or dt.utcoffset() == timedelta(0):
        return dt.replace(tzinfo=APP_TZ)

    return dt.astimezone(APP_TZ)


def normalize_model_dt(value):
    """parse_model_dt, returned as an ISO string with the local offset.
    Unparseable values are returned unchanged so validation can report them."""
    if not value:
        return value

    try:
        return parse_model_dt(value).isoformat()
    except (ValueError, TypeError):
        return value