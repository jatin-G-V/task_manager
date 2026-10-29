"""Builders for the task dicts used by the pure-logic tests (no database, no network)."""

import itertools
from datetime import datetime, timedelta

# Naive local wall clock, the same convention the recommendation engine uses.
NOW = datetime(2026, 10, 15, 12, 0, 0)

_counter = itertools.count(1)


def h(hours: float = 0, minutes: float = 0, seconds: float = 0) -> timedelta:
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


def iso(moment: datetime) -> str:
    return moment.isoformat()


def task(**overrides) -> dict:
    n = next(_counter)
    base = {
        "id": f"t{n}",
        "title": f"Task {n}",
        "status": "pending",
        "is_blocked": False,
        "section": "work",
        "schedule_type": "flexible",
        "has_explicit_time": False,
        "deadline": None,
        "scheduled_start": None,
        "scheduled_end": None,
        "urgency": "medium",
        "effort": "medium",
        "estimated_time_minutes": None,
        "created_at": f"2026-10-01T09:00:00.{n:06d}",
    }
    base.update(overrides)
    return base


def deadline_task(delta: timedelta, **overrides) -> dict:
    """Flexible task with a deadline `delta` after NOW."""
    return task(deadline=iso(NOW + delta), **overrides)


def meeting(start_delta: timedelta, minutes: int = 30, **overrides) -> dict:
    """Exact-time scheduled task starting `start_delta` after NOW."""
    start = NOW + start_delta
    return task(
        schedule_type="scheduled",
        has_explicit_time=True,
        scheduled_start=iso(start),
        scheduled_end=iso(start + timedelta(minutes=minutes)),
        **overrides,
    )


def window(start_delta: timedelta, end_delta: timedelta, **overrides) -> dict:
    """Vague time window (not an exact appointment)."""
    return task(
        schedule_type="scheduled",
        has_explicit_time=False,
        scheduled_start=iso(NOW + start_delta),
        scheduled_end=iso(NOW + end_delta),
        **overrides,
    )


def ids(items) -> list:
    return [item["id"] for item in items]


def reasons(items) -> list:
    return [item["reason"] for item in items]
