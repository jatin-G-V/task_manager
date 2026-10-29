"""Exact-time clash detection (pure logic). Times are built relative to the real clock
because find_clashes ignores a new task that already lies in the past."""

from datetime import timedelta

import pytest

from app.services.clash import MIN_SLOT_MINUTES, find_clashes, is_exact
from app.services.timeutil import now_local

pytestmark = pytest.mark.logic

BASE = (now_local() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)


def slot(start_min, end_min=None, **overrides):
    """Exact-time task from BASE+start_min to BASE+end_min (minutes)."""
    task = {
        "id": overrides.pop("id", None),
        "status": "pending",
        "is_blocked": False,
        "schedule_type": "scheduled",
        "has_explicit_time": True,
        "scheduled_start": (BASE + timedelta(minutes=start_min)).isoformat(),
        "scheduled_end": (
            (BASE + timedelta(minutes=end_min)).isoformat() if end_min is not None else None
        ),
    }
    task.update(overrides)
    return task


def clashing_ids(new, existing):
    return [t["id"] for t in find_clashes(new, existing)]


def test_partial_overlap_is_a_clash():
    assert clashing_ids(slot(30, 90), [slot(0, 60, id="a")]) == ["a"]


def test_touching_times_are_not_a_clash():
    existing = [slot(0, 60, id="a")]
    assert clashing_ids(slot(60, 90), existing) == []   # starts when the other ends
    assert clashing_ids(slot(-30, 0), existing) == []   # ends when the other starts


def test_containment_and_identical_slots_clash():
    existing = [slot(0, 120, id="a")]
    assert clashing_ids(slot(30, 60), existing) == ["a"]
    assert clashing_ids(slot(0, 120), existing) == ["a"]
    assert clashing_ids(slot(-30, 180), existing) == ["a"]


def test_task_without_an_end_time_occupies_a_short_slot():
    assert MIN_SLOT_MINUTES == 15
    assert clashing_ids(slot(0), [slot(10, 30, id="a")]) == ["a"]   # 10:00-10:15 overlaps 10:10
    assert clashing_ids(slot(0), [slot(15, 30, id="b")]) == []      # touches at 10:15


def test_an_end_before_the_start_is_treated_like_no_end():
    assert clashing_ids(slot(0, -60), [slot(10, 30, id="a")]) == ["a"]


def test_different_days_never_clash():
    assert clashing_ids(slot(0, 60), [slot(24 * 60, 24 * 60 + 60, id="a")]) == []


def test_only_exact_time_tasks_take_part():
    vague = slot(0, 60, id="v", has_explicit_time=False)
    flexible = slot(0, 60, id="f", schedule_type="flexible")

    assert clashing_ids(slot(30, 90), [vague, flexible]) == []
    assert find_clashes(slot(30, 90, has_explicit_time=False), [slot(0, 60, id="a")]) == []
    assert find_clashes(slot(30, 90, schedule_type="flexible"), [slot(0, 60, id="a")]) == []


@pytest.mark.parametrize("flag", [{"is_blocked": True}, {"status": "completed"}, {"status": "dropped"}])
def test_blocked_completed_and_dropped_tasks_do_not_occupy_time(flag):
    assert clashing_ids(slot(30, 90), [slot(0, 60, id="a", **flag)]) == []


def test_a_task_never_clashes_with_itself():
    assert clashing_ids(slot(0, 60, id="same"), [slot(0, 60, id="same")]) == []


def test_results_are_earliest_first_and_limited_to_three():
    existing = [slot(20, 40, id="e20"), slot(5, 25, id="e5"), slot(30, 50, id="e30"), slot(10, 30, id="e10")]
    assert clashing_ids(slot(0, 60), existing) == ["e5", "e10", "e20"]


def test_a_new_task_in_the_past_is_ignored_here():
    # the past-time rule rejects it elsewhere; the clash check must not also complain
    past = slot(-48 * 60 - 60, -48 * 60)
    assert find_clashes(past, [slot(-48 * 60 - 60, -48 * 60, id="a")]) == []


def test_is_exact():
    assert is_exact(slot(0, 60))
    assert not is_exact(slot(0, 60, has_explicit_time=False))
    assert not is_exact(slot(0, 60, schedule_type="flexible"))
    assert not is_exact({"schedule_type": "scheduled", "has_explicit_time": True})
