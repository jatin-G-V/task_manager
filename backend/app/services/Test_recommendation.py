"""
JT-C6 ranking tests.

The expected results below were written by hand from the spec BEFORE running the
engine (same approach as JT-V1). Fixed clock: Friday 2026-10-02 10:00.

Spec recap
  - pinned: explicit-time task within +/- 8 min of its time goes first
  - at-risk: slack <= 3h (slack = deadline - now - hidden estimate), smallest slack first
  - rest: slack / urgency weight, ascending; ties -> work > personal > leisure
  - vague windows eligible only while open; missed meetings are not recommended
"""

from datetime import datetime

from app.services.recommendation import rank

NOW = datetime(2026, 10, 2, 10, 0)


def task(id, title="t", section="work", urgency="medium", effort="medium",
         est=30, schedule_type="flexible", deadline=None, start=None, end=None,
         explicit=None, status="pending", blocked=False, created="2026-10-01T09:00:00"):
    return {
        "id": id, "title": title, "section": section, "urgency": urgency,
        "effort": effort, "estimated_time_minutes": est,
        "schedule_type": schedule_type, "deadline": deadline,
        "scheduled_start": start, "scheduled_end": end,
        "has_explicit_time": explicit, "status": status, "is_blocked": blocked,
        "created_at": created,
    }


def ids(result):
    return [r["id"] for r in result]


def test_pinned_meeting_beats_everything():
    tasks = [
        task("x", urgency="urgent", deadline="2026-10-02T10:40:00"),
        task("m", schedule_type="scheduled", start="2026-10-02T10:05:00", explicit=True),
    ]
    out = rank(tasks, NOW, limit=5)
    assert ids(out) == ["m", "x"]
    assert [r["reason"] for r in out] == ["pinned", "deadline_risk"]


def test_pinned_window_is_8_minutes_each_side():
    tasks = [
        task("in8", schedule_type="scheduled", start="2026-10-02T10:08:00", explicit=True),
        task("out9", schedule_type="scheduled", start="2026-10-02T10:09:00", explicit=True),
        task("past8", schedule_type="scheduled", start="2026-10-02T09:52:00", explicit=True),
        task("past9", schedule_type="scheduled", start="2026-10-02T09:51:00", explicit=True),
    ]
    assert ids(rank(tasks, NOW, limit=10)) == ["past8", "in8"]


def test_vague_window_only_while_open():
    tasks = [
        task("open", schedule_type="scheduled", explicit=False,
             start="2026-10-02T00:00:00", end="2026-10-02T23:59:59"),
        task("future", schedule_type="scheduled", explicit=False,
             start="2026-10-03T00:00:00", end="2026-10-03T23:59:59"),
        task("ended", schedule_type="scheduled", explicit=False,
             start="2026-10-01T00:00:00", end="2026-10-01T23:59:59"),
    ]
    assert ids(rank(tasks, NOW, limit=10)) == ["open"]


def test_slack_divided_by_urgency_and_section_breaks_tie():
    tasks = [
        # slack 20h / 3 = 6.67
        task("A", section="work", urgency="urgent", deadline="2026-10-03T06:30:00"),
        # slack 10h / 2 = 5.0
        task("B", section="personal", urgency="high", deadline="2026-10-02T20:30:00"),
        # slack 10h / 1.5 = 6.67 (ties with A, personal loses to work)
        task("C", section="personal", urgency="medium", deadline="2026-10-02T20:30:00"),
    ]
    assert ids(rank(tasks, NOW, limit=5)) == ["B", "A", "C"]


def test_at_risk_tier_sorted_by_slack_including_negative():
    tasks = [
        task("E", urgency="urgent", deadline="2026-10-03T10:00:00"),               # slack 23.5h
        task("D", urgency="low", deadline="2026-10-02T12:00:00"),                   # slack 1.5h
        task("F", urgency="medium", est=120, deadline="2026-10-02T11:00:00"),       # slack -1h
    ]
    out = rank(tasks, NOW, limit=5)
    assert ids(out) == ["F", "D", "E"]
    assert [r["reason"] for r in out] == ["deadline_risk", "deadline_risk", "top_score"]


def test_no_deadline_ordered_by_urgency_weight():
    tasks = [
        task("I", section="leisure", urgency=None, effort="low"),
        task("H", urgency="low"),
        task("G", urgency="urgent"),
    ]
    assert ids(rank(tasks, NOW, limit=5)) == ["G", "H", "I"]


def test_no_deadline_never_outranks_a_task_with_deadline():
    tasks = [
        task("n_urgent", urgency="urgent"),                                   # no deadline
        task("n_high", urgency="high"),                                       # no deadline
        task("d_far", urgency="medium", deadline="2026-10-06T10:00:00"),      # ~4 days away
        task("d_near", urgency="low", deadline="2026-10-02T20:00:00"),        # ~10h away
    ]
    assert ids(rank(tasks, NOW, limit=10)) == ["d_near", "d_far", "n_urgent", "n_high"]


def test_inactive_tasks_excluded():
    tasks = [
        task("done", status="completed"),
        task("dropped", status="dropped"),
        task("blocked_status", status="blocked"),
        task("blocked_flag", blocked=True),
        task("live"),
    ]
    assert ids(rank(tasks, NOW, limit=10)) == ["live"]


def test_flexible_task_with_explicit_deadline():
    tasks = [
        task("s2", deadline="2026-10-02T18:00:00", explicit=True),   # 8h away -> rest
        task("s3", deadline="2026-10-02T09:30:00", explicit=True),   # 30 min late -> overdue, excluded
        task("s1", deadline="2026-10-02T10:05:00", explicit=True),   # pinned
    ]
    out = rank(tasks, NOW, limit=5)
    assert ids(out) == ["s1", "s2"]
    assert [r["reason"] for r in out] == ["pinned", "top_score"]


def test_overdue_excluded_but_pinned_grace_kept():
    tasks = [
        task("late", deadline="2026-10-02T09:59:00"),                          # 1 min late, no explicit time
        task("grace", deadline="2026-10-02T09:53:00", explicit=True),          # 7 min late, within +/- 8
        task("gone", deadline="2026-10-02T09:51:00", explicit=True),           # 9 min late, overdue
        task("tight", est=120, deadline="2026-10-02T11:00:00"),                # not overdue: slack -1h, still at risk
    ]
    out = rank(tasks, NOW, limit=10)
    assert ids(out) == ["grace", "tight"]
    assert [r["reason"] for r in out] == ["pinned", "deadline_risk"]


def test_energy_mode_at_risk_plus_effort_match():
    tasks = [
        task("X", effort="high", deadline="2026-10-02T12:00:00"),   # at risk
        task("Y", effort="low", urgency="low"),
        task("Z", effort="high", urgency="medium"),
        task("W", effort="medium", urgency="medium"),
    ]
    out = rank(tasks, NOW, energy="low")
    assert ids(out) == ["X", "Y"]
    assert out[1]["reason"] == "energy_match"


def test_energy_mode_pinned_first_and_max_two():
    tasks = [
        task("p", schedule_type="scheduled", start="2026-10-02T10:03:00", explicit=True),
        task("X", effort="high", deadline="2026-10-02T12:00:00"),
        task("Y", effort="low"),
    ]
    assert ids(rank(tasks, NOW, energy="low")) == ["p", "X"]


def test_energy_mode_without_at_risk_returns_single_match():
    tasks = [
        task("L", effort="low", urgency="medium"),
        task("H", effort="high", urgency="medium"),
    ]
    assert ids(rank(tasks, NOW, energy="high")) == ["H"]


def test_energy_mode_null_effort_is_neutral():
    tasks = [
        task("hi", effort="high"),
        task("none", effort=None),
    ]
    assert ids(rank(tasks, NOW, energy="low")) == ["none"]


def test_exclude_ids_and_limit():
    tasks = [
        task("A", section="work", urgency="urgent", deadline="2026-10-03T06:30:00"),
        task("B", section="personal", urgency="high", deadline="2026-10-02T20:30:00"),
        task("C", section="personal", urgency="medium", deadline="2026-10-02T20:30:00"),
    ]
    assert ids(rank(tasks, NOW, limit=1)) == ["B"]
    assert ids(rank(tasks, NOW, limit=5, exclude_ids=["B"])) == ["A", "C"]


def test_time_estimate_never_exposed():
    out = rank([task("A", est=90, deadline="2026-10-03T06:30:00")], NOW)
    assert "estimated_time_minutes" not in out[0]


def test_db_style_aware_timestamps_are_treated_as_wall_clock():
    # Supabase returns timestamptz as "+00:00" strings; the engine compares wall-clock
    out = rank([task("m", schedule_type="scheduled",
                     start="2026-10-02T10:05:00+00:00", explicit=True)], NOW)
    assert ids(out) == ["m"]