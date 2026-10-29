"""The past-time / consistency rules in task_service._validate_not_in_past (no database used)."""

from datetime import timedelta

import pytest

from app.services.timeutil import now_local

pytestmark = pytest.mark.logic


@pytest.fixture
def validate(settings):
    # imported lazily so the test environment (.env.test) is loaded first
    from app.services import task_service
    return task_service._validate_not_in_past


def when(hours):
    return (now_local() + timedelta(hours=hours)).isoformat()


def flexible(**kw):
    data = {"schedule_type": "flexible", "deadline": when(24), "has_explicit_time": True,
            "scheduled_start": None, "scheduled_end": None, "is_recurring": False,
            "recurrence": None, "recurrence_end": None, "duration": None,
            "estimated_time_minutes": None}
    data.update(kw)
    return data


def scheduled(**kw):
    values = {"schedule_type": "scheduled", "deadline": None, "has_explicit_time": True,
              "scheduled_start": when(24), "scheduled_end": when(25)}
    values.update(kw)
    return flexible(**values)


# ---- deadlines ---------------------------------------------------------------

def test_a_future_deadline_is_accepted(validate):
    validate(flexible())


def test_a_past_deadline_is_rejected(validate):
    with pytest.raises(ValueError, match="past"):
        validate(flexible(deadline=when(-1)))


# ---- exact-time tasks --------------------------------------------------------

def test_exact_time_in_the_future_is_accepted(validate):
    validate(scheduled())


def test_exact_time_in_the_past_is_rejected(validate):
    with pytest.raises(ValueError, match="past"):
        validate(scheduled(scheduled_start=when(-2), scheduled_end=when(-1)))


def test_exact_time_with_a_past_end_is_rejected(validate):
    with pytest.raises(ValueError, match="end time"):
        validate(scheduled(scheduled_start=when(2), scheduled_end=when(-1)))


# ---- vague windows -----------------------------------------------------------

def test_window_that_already_ended_is_rejected(validate):
    with pytest.raises(ValueError, match="already ended"):
        validate(scheduled(has_explicit_time=False, scheduled_start=when(-5), scheduled_end=when(-1)))


def test_window_that_is_still_open_is_accepted(validate):
    validate(scheduled(has_explicit_time=False, scheduled_start=when(-2), scheduled_end=when(5)))


def test_window_without_an_end_uses_its_start(validate):
    with pytest.raises(ValueError, match="already ended"):
        validate(scheduled(has_explicit_time=False, scheduled_start=when(-2), scheduled_end=None))


# ---- recurrence fields -------------------------------------------------------

def test_recurrence_end_in_the_past_is_rejected(validate):
    with pytest.raises(ValueError, match="recurrence end"):
        validate(flexible(recurrence_end=when(-24)))


def test_recurrence_fields_need_is_recurring(validate):
    with pytest.raises(ValueError, match="is_recurring"):
        validate(flexible(recurrence="FREQ=WEEKLY;BYDAY=MO", recurrence_end=when(24 * 30)))


# ---- schedule consistency ----------------------------------------------------

def test_scheduled_needs_a_start(validate):
    with pytest.raises(ValueError, match="requires scheduled_start"):
        validate(flexible(schedule_type="scheduled", deadline=None))


def test_scheduled_cannot_have_a_deadline(validate):
    with pytest.raises(ValueError, match="cannot have a deadline"):
        validate(scheduled(deadline=when(30)))


def test_flexible_cannot_have_a_scheduled_start(validate):
    with pytest.raises(ValueError, match="cannot have scheduled_start"):
        validate(flexible(scheduled_start=when(24)))


# ---- duration and estimate ---------------------------------------------------

def test_duration_must_match_the_estimate(validate):
    validate(flexible(duration=45, estimated_time_minutes=45))
    with pytest.raises(ValueError, match="must equal duration"):
        validate(flexible(duration=45, estimated_time_minutes=30))
    with pytest.raises(ValueError, match="must equal duration"):
        validate(flexible(duration=45))


@pytest.mark.parametrize("bad", [0, -5, True, 1.5, "30"])
def test_duration_must_be_a_positive_integer(validate, bad):
    with pytest.raises(ValueError, match="positive integer"):
        validate(flexible(duration=bad, estimated_time_minutes=bad))


@pytest.mark.parametrize("bad", [0, -5, True, 2.5])
def test_estimate_must_be_a_positive_integer(validate, bad):
    with pytest.raises(ValueError, match="positive integer"):
        validate(flexible(estimated_time_minutes=bad))


# ---- only changed fields are checked against the clock ----------------------

def test_editing_another_field_of_an_overdue_task_is_allowed(validate):
    overdue = flexible(deadline=when(-24))

    validate(overdue, changed_fields={"title"})
    validate(overdue, changed_fields={"brief", "effort"})

    with pytest.raises(ValueError, match="past"):
        validate(overdue, changed_fields={"deadline"})


def test_a_started_exact_task_can_be_renamed(validate):
    started = scheduled(scheduled_start=when(-1), scheduled_end=when(1))

    validate(started, changed_fields={"title"})

    with pytest.raises(ValueError, match="past"):
        validate(started, changed_fields={"scheduled_start"})
