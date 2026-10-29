"""Recommendation engine: order, tiers, energy mode, dashboard numbers, determinism."""

import random
from datetime import timedelta

import pytest

from app.services.recommendation import build_dashboard, next_scheduled, rank
from tests.unit.factories import (
    NOW, deadline_task, h, ids, meeting, reasons, task, window,
)

pytestmark = pytest.mark.logic


# ---- pinned (happening now) ------------------------------------------------

def test_pinned_meeting_comes_first_then_at_risk():
    m = meeting(h(minutes=5), id="m")
    risky = deadline_task(h(1), id="risky")  # 1h left - 30m estimate = 0.5h slack

    out = rank([risky, m], NOW)

    assert ids(out) == ["m", "risky"]
    assert reasons(out) == ["pinned", "deadline_risk"]


@pytest.mark.parametrize(
    "seconds,pinned",
    [(0, True), (480, True), (481, False), (-480, True), (-481, False)],
)
def test_pinned_window_is_eight_minutes_each_side_inclusive(seconds, pinned):
    m = meeting(timedelta(seconds=seconds), id="m")
    assert ("m" in ids(rank([m], NOW))) == pinned


def test_meeting_outside_the_window_is_upcoming_or_overdue_never_recommended():
    future = meeting(h(minutes=30), id="future")
    started = meeting(h(minutes=-30), id="started")

    d = build_dashboard([future, started], NOW)

    assert d["ranked"] == []
    assert ids(d["upcoming"]) == ["future"]
    assert ids(d["overdue"]) == ["started"]


def test_meeting_inside_its_grace_window_is_not_overdue():
    started_five_minutes_ago = meeting(h(minutes=-5), id="grace")
    d = build_dashboard([started_five_minutes_ago], NOW)

    assert ids(d["ranked"]) == ["grace"]
    assert d["overdue"] == []


# ---- at-risk tier -----------------------------------------------------------

def test_at_risk_tasks_come_before_the_rest_closest_slack_first():
    a = deadline_task(h(2), id="a")  # slack 1.5h
    b = deadline_task(h(3), id="b")  # slack 2.5h
    c = deadline_task(h(4), id="c")  # slack 3.5h -> not at risk

    out = rank([c, b, a], NOW)

    assert ids(out) == ["a", "b", "c"]
    assert reasons(out) == ["deadline_risk", "deadline_risk", "top_score"]


def test_at_risk_boundary_is_three_hours_of_slack_inclusive():
    exactly = deadline_task(h(3.5), id="exactly")                       # slack 3.0h
    just_over = deadline_task(h(3.5, minutes=1), id="over")             # slack 3.0167h

    out = {item["id"]: item["reason"] for item in rank([exactly, just_over], NOW)}

    assert out == {"exactly": "deadline_risk", "over": "top_score"}


def test_estimated_time_shrinks_the_slack():
    long_job = deadline_task(h(4), id="long", estimated_time_minutes=180)  # slack 1h
    short_job = deadline_task(h(4), id="short")                             # slack 3.5h

    out = rank([short_job, long_job], NOW)

    assert ids(out) == ["long", "short"]
    assert reasons(out) == ["deadline_risk", "top_score"]


# ---- ordering of everything else -------------------------------------------

def test_tasks_without_a_deadline_come_after_every_task_that_has_one():
    far = deadline_task(h(24 * 30), id="far")   # slack is capped at 168h
    none = task(id="none")

    assert ids(rank([none, far], NOW)) == ["far", "none"]


def test_higher_urgency_ranks_first_when_deadlines_match():
    low = deadline_task(h(20), id="low", urgency="low")
    urgent = deadline_task(h(20), id="urgent", urgency="urgent")

    assert ids(rank([low, urgent], NOW)) == ["urgent", "low"]


def test_scores_inside_the_tie_band_fall_back_to_section_order():
    leisure = deadline_task(h(20), id="leisure", section="leisure")             # score 13.0
    work = deadline_task(h(20, minutes=9), id="work", section="work")           # score 13.1

    assert ids(rank([leisure, work], NOW)) == ["work", "leisure"]


def test_equal_tasks_are_ordered_by_creation_time():
    older = deadline_task(h(20), id="older", created_at="2026-10-01T08:00:00")
    newer = deadline_task(h(20), id="newer", created_at="2026-10-02T08:00:00")

    assert ids(rank([newer, older], NOW)) == ["older", "newer"]


# ---- who is never recommended ----------------------------------------------

def test_blocked_completed_and_dropped_tasks_are_never_recommended():
    tasks = [
        deadline_task(h(1), id="blocked", is_blocked=True),
        deadline_task(h(1), id="done", status="completed"),
        deadline_task(h(1), id="dropped", status="dropped"),
        deadline_task(h(5), id="ok"),
    ]

    assert ids(rank(tasks, NOW, limit=10)) == ["ok"]

    d = build_dashboard(tasks, NOW)
    for group in ("ranked", "at_risk", "later", "due_today", "suggested"):
        assert "blocked" not in ids(d[group]), group
    assert d["focus"]["id"] == "ok"


def test_blocked_tasks_stay_visible_in_upcoming_but_are_never_the_next_one():
    blocked_soon = meeting(h(2), id="blocked-soon", is_blocked=True)
    plain_later = meeting(h(4), id="plain-later")

    d = build_dashboard([blocked_soon, plain_later], NOW)

    assert ids(d["upcoming"]) == ["blocked-soon", "plain-later"]
    assert d["upcoming"][0]["is_blocked"] is True
    assert d["next_upcoming"]["id"] == "plain-later"
    assert d["next_upcoming_explicit"]["id"] == "plain-later"


def test_exclude_ids_and_limit_are_respected():
    tasks = [deadline_task(h(10 + i), id=f"t{i}") for i in range(5)]

    assert len(rank(tasks, NOW)) == 3
    assert len(rank(tasks, NOW, limit=1)) == 1
    assert "t0" not in ids(rank(tasks, NOW, limit=10, exclude_ids=["t0"]))


# ---- energy / mood mode ------------------------------------------------------

def _effort_pool():
    return [
        deadline_task(h(30), id="heavy", effort="high"),
        deadline_task(h(35), id="mid", effort="medium"),
        deadline_task(h(40), id="light", effort="low"),
    ]


@pytest.mark.parametrize(
    "energy,expected",
    [("low", "light"), ("medium", "mid"), ("high", "heavy")],
)
def test_energy_picks_the_task_whose_effort_matches(energy, expected):
    out = rank(_effort_pool(), NOW, energy=energy)

    assert ids(out) == [expected]
    assert reasons(out) == ["energy_match"]


def test_energy_mode_keeps_the_most_at_risk_task_and_adds_one_match():
    risky = deadline_task(h(1), id="risky", effort="high")
    out = rank([risky] + _effort_pool(), NOW, energy="low")

    assert ids(out) == ["risky", "light"]
    assert reasons(out) == ["deadline_risk", "energy_match"]


def test_a_second_at_risk_task_can_be_the_energy_match():
    first = deadline_task(h(1), id="first", effort="high")
    second = deadline_task(h(2), id="second", effort="low")

    out = rank([first, second], NOW, energy="low")

    assert ids(out) == ["first", "second"]
    assert reasons(out) == ["deadline_risk", "energy_match"]


def test_energy_mode_never_returns_more_than_two_tasks():
    pinned = meeting(h(minutes=2), id="pinned")
    risky = deadline_task(h(1), id="risky")
    out = rank([pinned, risky] + _effort_pool(), NOW, energy="low")

    assert ids(out) == ["pinned", "risky"]
    assert "energy_match" not in reasons(out)


def test_energy_mode_with_nothing_eligible_returns_an_empty_list():
    assert rank([], NOW, energy="low") == []
    assert rank([deadline_task(h(-2), id="late")], NOW, energy="high") == []


# ---- dashboard numbers -------------------------------------------------------

def test_vague_window_states():
    past = window(h(-3), h(-1), id="past")
    open_now = window(h(-1), h(5), id="open")
    future = window(h(1), h(5), id="future")

    d = build_dashboard([past, open_now, future], NOW)

    assert ids(d["overdue"]) == ["past"]
    assert ids(d["ranked"]) == ["open"]
    assert ids(d["upcoming"]) == ["future"]


def test_overdue_deadline_is_listed_as_overdue_not_recommended():
    late = deadline_task(h(-2), id="late")

    d = build_dashboard([late], NOW)

    assert ids(d["overdue"]) == ["late"]
    assert d["ranked"] == [] and d["focus"] is None


def test_due_today_counts_only_eligible_tasks_with_a_time_today():
    today = deadline_task(h(6), id="today")             # 18:00 today
    tomorrow = deadline_task(h(30), id="tomorrow")
    late_today = deadline_task(h(-1), id="late")        # 11:00 today but already overdue
    later_meeting = meeting(h(4), id="meet")            # 16:00 today, not eligible yet

    d = build_dashboard([today, tomorrow, late_today, later_meeting], NOW)

    assert ids(d["due_today"]) == ["today"]
    assert d["counts"]["due_today"] == 1


def test_counts_match_the_lists():
    tasks = [
        deadline_task(h(1), id="risk"),
        deadline_task(h(10), id="later"),
        deadline_task(h(-2), id="late"),
        meeting(h(5), id="meet"),
    ]
    d = build_dashboard(tasks, NOW)
    c = d["counts"]

    assert c["overdue"] == len(d["overdue"]) == 1
    assert c["at_risk"] == len(d["at_risk"]) == 1
    assert c["later"] == len(d["later"]) == 1
    assert c["upcoming"] == len(d["upcoming"]) == 1
    assert c["due_today"] == len(d["due_today"])


def test_focus_is_the_first_ranked_task():
    tasks = [deadline_task(h(10), id="b"), deadline_task(h(2), id="a")]
    d = build_dashboard(tasks, NOW)

    assert d["focus"]["id"] == d["ranked"][0]["id"] == "a"
    assert ids(d["ranked"]) == ids(d["at_risk"]) + ids(d["later"])


def test_focus_and_ranked_ignore_energy_but_suggested_uses_it():
    tasks = [
        deadline_task(h(30), id="heavy", effort="high"),
        deadline_task(h(40), id="light", effort="low"),
    ]

    base = build_dashboard(tasks, NOW)
    low = build_dashboard(tasks, NOW, energy="low")

    assert base["focus"]["id"] == low["focus"]["id"] == "heavy"
    assert ids(base["ranked"]) == ids(low["ranked"])
    assert ids(base["suggested"]) == ["heavy", "light"]
    assert ids(low["suggested"]) == ["light"]


def test_upcoming_schedule_skips_the_meeting_that_is_already_the_focus():
    now_meeting = meeting(h(minutes=5), id="now")
    next_meeting = meeting(h(3), id="next")

    d = build_dashboard([now_meeting, next_meeting], NOW)

    assert d["focus"]["id"] == "now"
    assert d["next_upcoming_explicit"]["id"] == "next"


# ---- next_scheduled ----------------------------------------------------------

@pytest.mark.parametrize("seconds,upcoming", [(480, False), (481, True)])
def test_next_scheduled_starts_strictly_after_the_pinned_window(seconds, upcoming):
    m = meeting(timedelta(seconds=seconds), id="m")

    assert (next_scheduled([m], NOW) is not None) == upcoming
    assert ("m" in ids(rank([m], NOW))) == (not upcoming)


def test_next_scheduled_filters_and_orders():
    later = meeting(h(5), id="later")
    sooner = meeting(h(2), id="sooner")
    vague = window(h(1), h(3), id="vague")
    blocked = meeting(h(1), id="blocked", is_blocked=True)
    done = meeting(h(1), id="done", status="completed")
    flexible = deadline_task(h(1), id="flexible")

    assert next_scheduled([later, vague, blocked, done, flexible, sooner], NOW)["id"] == "sooner"
    assert next_scheduled([later, sooner], NOW, exclude_ids=["sooner"])["id"] == "later"
    assert next_scheduled([vague, blocked, done, flexible], NOW) is None


# ---- no leaks, same input same output ---------------------------------------

def test_estimated_time_is_never_exposed():
    tasks = [
        deadline_task(h(2), id="a", estimated_time_minutes=90),
        deadline_task(h(-2), id="o", estimated_time_minutes=30),
        meeting(h(3), id="m", estimated_time_minutes=30),
    ]
    d = build_dashboard(tasks, NOW)

    for group in ("ranked", "overdue", "upcoming", "later", "at_risk", "suggested", "due_today"):
        for item in d[group]:
            assert "estimated_time_minutes" not in item, group
    assert "estimated_time_minutes" not in d["focus"]
    for item in rank(tasks, NOW, limit=10):
        assert "estimated_time_minutes" not in item


def _mixed_tasks():
    return [
        meeting(h(minutes=3), id="pin"),
        deadline_task(h(1), id="risk1"),
        deadline_task(h(2), id="risk2", urgency="urgent"),
        deadline_task(h(10), id="r3"),
        deadline_task(h(10), id="r4", urgency="low"),
        deadline_task(h(48), id="r5", section="leisure"),
        task(id="nodl"),
        task(id="blk", is_blocked=True),
        deadline_task(h(-3), id="late"),
        meeting(h(6), id="later-meet"),
    ]


def _summary(dashboard):
    return {
        group: ids(dashboard[group])
        for group in ("ranked", "at_risk", "later", "overdue", "upcoming", "due_today", "suggested")
    }


def test_same_input_gives_the_same_output():
    assert _summary(build_dashboard(_mixed_tasks(), NOW)) == _summary(build_dashboard(_mixed_tasks(), NOW))


def test_input_order_does_not_change_the_result():
    base = _mixed_tasks()
    expected = _summary(build_dashboard(base, NOW))

    for seed in range(5):
        shuffled = base[:]
        random.Random(seed).shuffle(shuffled)
        assert _summary(build_dashboard(shuffled, NOW)) == expected
