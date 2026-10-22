from datetime import datetime

import pytest

from app.services.recurrence import (
    legacy_to_rrule,
    next_occurrence,
    validate_rule,
    validate_task_recurrence,
)
from app.services.timeutil import APP_TZ
from app.schemas.task import TaskCreate


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(APP_TZ)


def _scheduled_task(start: str, rule: str, **extra) -> dict:
    return {
        "id": "series-1",
        "schedule_type": "scheduled",
        "scheduled_start": start,
        "scheduled_end": None,
        "deadline": None,
        "has_explicit_time": True,
        "is_recurring": True,
        "recurrence": rule,
        "recurrence_end": None,
        "recurrence_anchor": start,
        **extra,
    }


def _next(task: dict, completed_at: str) -> dict | None:
    return next_occurrence(task, _dt(completed_at))


def test_weekly_mon_wed_fri_advances_across_week_boundary():
    task = _scheduled_task("2026-10-23T09:00:00+05:30", "FREQ=WEEKLY;BYDAY=MO,WE,FR")
    first = _next(task, "2026-10-23T10:00:00+05:30")
    assert first["scheduled_start"] == "2026-10-26T09:00:00+05:30"
    task["scheduled_start"] = first["scheduled_start"]
    second = _next(task, "2026-10-26T10:00:00+05:30")
    assert second["scheduled_start"] == "2026-10-28T09:00:00+05:30"


def test_monthly_day_31_clamps_without_drift():
    task = _scheduled_task(
        "2026-01-31T09:00:00+05:30",
        "FREQ=MONTHLY;BYMONTHDAY=31",
        scheduled_end="2026-01-31T09:45:00+05:30",
    )
    expected = [
        ("2026-01-31T10:00:00+05:30", "2026-02-28T09:00:00+05:30", "2026-02-28T09:45:00+05:30"),
        ("2026-02-28T10:00:00+05:30", "2026-03-31T09:00:00+05:30", "2026-03-31T09:45:00+05:30"),
        ("2026-03-31T10:00:00+05:30", "2026-04-30T09:00:00+05:30", "2026-04-30T09:45:00+05:30"),
    ]
    for completed_at, expected_start, expected_end in expected:
        result = _next(task, completed_at)
        assert result["scheduled_start"] == expected_start
        assert result["scheduled_end"] == expected_end
        task["scheduled_start"] = result["scheduled_start"]
        task["scheduled_end"] = result["scheduled_end"]


def test_yearly_february_29_clamps_in_non_leap_year():
    task = _scheduled_task("2024-02-29T08:30:00+05:30", "FREQ=YEARLY")
    result = _next(task, "2024-02-29T09:00:00+05:30")
    assert result["scheduled_start"] == "2025-02-28T08:30:00+05:30"


def test_daily_except_sunday_skips_sunday():
    task = _scheduled_task(
        "2026-10-24T08:00:00+05:30",
        "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA",
    )
    result = _next(task, "2026-10-24T09:00:00+05:30")
    assert result["scheduled_start"] == "2026-10-26T08:00:00+05:30"


def test_every_two_weeks():
    task = _scheduled_task("2026-10-19T07:00:00+05:30", "FREQ=WEEKLY;INTERVAL=2")
    result = _next(task, "2026-10-19T08:00:00+05:30")
    assert result["scheduled_start"] == "2026-11-02T07:00:00+05:30"


def test_late_completion_skips_past_recurrences():
    task = _scheduled_task("2026-10-19T09:00:00+05:30", "FREQ=WEEKLY;BYDAY=MO")
    result = _next(task, "2026-10-22T11:00:00+05:30")
    assert result["scheduled_start"] == "2026-10-26T09:00:00+05:30"


def test_recurrence_end_includes_last_day_but_stops_after_it():
    task = _scheduled_task(
        "2026-10-19T09:00:00+05:30",
        "FREQ=WEEKLY;BYDAY=MO",
        recurrence_end="2026-10-26T23:59:59+05:30",
    )
    last = _next(task, "2026-10-19T10:00:00+05:30")
    assert last["scheduled_start"] == "2026-10-26T09:00:00+05:30"
    task["scheduled_start"] = last["scheduled_start"]
    assert _next(task, "2026-10-26T10:00:00+05:30") is None


def test_invalid_rule_raises_value_error():
    with pytest.raises(ValueError, match="repeating schedule"):
        validate_rule("FREQ=DAILY;BYDAY=NOTADAY")


def test_recurring_task_without_a_start_or_deadline_is_rejected():
    with pytest.raises(ValueError, match="A repeating task needs a start time or a deadline"):
        validate_task_recurrence({"is_recurring": True, "recurrence": "FREQ=DAILY"})


def test_rest_task_schema_rejects_recurring_task_without_date():
    with pytest.raises(ValueError, match="A repeating task needs a start time or a deadline"):
        TaskCreate(
            title="Read every day",
            section="personal",
            is_recurring=True,
            recurrence="FREQ=DAILY",
        )


def test_first_occurrence_must_match_rule():
    task = _scheduled_task("2026-10-20T09:00:00+05:30", "FREQ=WEEKLY;BYDAY=MO")
    with pytest.raises(ValueError, match="first date must match"):
        validate_task_recurrence(task)


@pytest.mark.parametrize(
    ("legacy", "expected"),
    [
        ("daily", "FREQ=DAILY"),
        ("daily except Sunday", "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA"),
        ("daily except Saturday and Sunday", "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"),
        ("weekly on Monday", "FREQ=WEEKLY;BYDAY=MO"),
        ("weekly on Monday, Wednesday and Friday", "FREQ=WEEKLY;BYDAY=MO,WE,FR"),
        ("monthly", "FREQ=MONTHLY"),
        ("yearly", "FREQ=YEARLY"),
        ("every 2 weeks", "FREQ=WEEKLY;INTERVAL=2"),
        ("weekdays", "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"),
        ("weekends", "FREQ=WEEKLY;BYDAY=SA,SU"),
    ],
)
def test_legacy_patterns_convert(legacy: str, expected: str):
    assert legacy_to_rrule(legacy) == expected


def test_legacy_weekly_pattern_produces_expected_next_date():
    task = _scheduled_task("2026-10-19T09:00:00+05:30", "weekly on Monday")
    result = _next(task, "2026-10-19T10:00:00+05:30")
    assert result["scheduled_start"] == "2026-10-26T09:00:00+05:30"


def test_same_inputs_produce_the_same_occurrence_date():
    task = _scheduled_task("2026-10-19T09:00:00+05:30", "FREQ=DAILY")
    completed_at = "2026-10-19T10:00:00+05:30"
    first = _next(task, completed_at)
    second = _next(task, completed_at)
    assert first["_occurrence_date"] == second["_occurrence_date"]
