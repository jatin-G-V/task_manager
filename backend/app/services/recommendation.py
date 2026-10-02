"""
JT-C6 recommendation engine.

Pure functions only: no database, no clock. `now` is always passed in so the
engine is deterministic and testable (and the timezone fix lives in one place).

All datetimes are compared as wall-clock values: tzinfo is dropped from stored
strings and `now` must be a naive datetime in the user's local time.

Pipeline
  0. eligibility   : drop completed / dropped / blocked / overdue (due time already
                     passed), vague windows that have not started or already ended,
                     meetings outside their pinned window
  1. pinned        : explicit-time tasks within +/- PINNED_WINDOW_MIN of their time
  2. at-risk       : slack <= AT_RISK_SLACK_HOURS (negative slack included)
  3. everything else: score = slack / urgency weight, lower = sooner
  Ties (within TIE_EPS of score) are broken by section, then by older created_at.
"""

from datetime import datetime, timedelta
from typing import Optional

PINNED_WINDOW_MIN = 8
AT_RISK_SLACK_HOURS = 3
SLACK_CAP_HOURS = 168          # tasks with no deadline are treated as 7 days away
DEFAULT_ESTIMATE_MIN = 30      # used only when estimated_time_minutes is null
TIE_EPS = 0.25
MAX_MOOD_PICKS = 2

URGENCY_WEIGHT = {
    None: 0.75,
    "low": 1.0,
    "medium": 1.5,
    "high": 2.0,
    "urgent": 3.0,
}
SECTION_ORDER = {"work": 0, "personal": 1, "leisure": 2}
EFFORT_LEVEL = {"low": 0, "medium": 1, "high": 2}

INACTIVE_STATUSES = {"completed", "dropped", "blocked"}


def _dt(value) -> Optional[datetime]:
    if not value:
        return None
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt.replace(tzinfo=None)


def _in_pinned_window(moment: datetime, now: datetime) -> bool:
    return abs(now - moment) <= timedelta(minutes=PINNED_WINDOW_MIN)


class _Entry:
    __slots__ = ("task", "pinned", "pin_time", "due", "slack", "weight", "reason")

    def __init__(self, task, pinned, pin_time, due, slack, weight):
        self.task = task
        self.pinned = pinned
        self.pin_time = pin_time
        self.due = due
        self.slack = slack
        self.weight = weight
        self.reason = None

    @property
    def at_risk(self) -> bool:
        return self.due is not None and self.slack <= AT_RISK_SLACK_HOURS

    @property
    def score(self) -> float:
        return self.slack / self.weight


def _build_entry(task: dict, now: datetime) -> Optional[_Entry]:
    if task.get("status") in INACTIVE_STATUSES or task.get("is_blocked"):
        return None

    schedule_type = task.get("schedule_type")
    explicit = bool(task.get("has_explicit_time"))
    start = _dt(task.get("scheduled_start"))
    end = _dt(task.get("scheduled_end"))
    deadline = _dt(task.get("deadline"))
    weight = URGENCY_WEIGHT.get(task.get("urgency"), URGENCY_WEIGHT[None])

    pinned = False
    pin_time = None
    due = None

    if schedule_type == "scheduled" and start:
        if explicit:
            # meeting-like: recommended only inside its pinned window.
            # Before it: not yet relevant. After it: missed (overdue list).
            if not _in_pinned_window(start, now):
                return None
            return _Entry(task, True, start, None, SLACK_CAP_HOURS, weight)

        # vague window ("tomorrow", "tonight"): eligible only while it is open
        if now < start:
            return None
        if end and now > end:
            return None
        due = end
    else:
        # flexible (or bare topic): deadline is the only time signal
        due = deadline
        if explicit and deadline and _in_pinned_window(deadline, now):
            pinned = True
            pin_time = deadline

    # due time already passed -> overdue: not recommended (it belongs in the overdue list).
    # A pinned task keeps its +/- 8 min grace window around its explicit time.
    if due is not None and due < now and not pinned:
        return None

    if due is None:
        slack = SLACK_CAP_HOURS
    else:
        estimate = task.get("estimated_time_minutes") or DEFAULT_ESTIMATE_MIN
        slack = (due - now).total_seconds() / 3600 - estimate / 60
        slack = min(slack, SLACK_CAP_HOURS)

    return _Entry(task, pinned, pin_time, due, slack, weight)


def _rest_key(e: _Entry):
    # tasks with no deadline/window end always come after every task that has one;
    # among themselves they are ordered by urgency weight (same slack, so score = 168/weight)
    return (
        e.due is None,
        round(e.score / TIE_EPS),
        SECTION_ORDER.get(e.task.get("section"), 3),
        str(e.task.get("created_at") or ""),
    )


def _present(e: _Entry) -> dict:
    t = e.task
    # estimated_time_minutes is deliberately NOT returned: it must never reach the user
    return {
        "id": t.get("id"),
        "title": t.get("title"),
        "section": t.get("section"),
        "effort": t.get("effort"),
        "urgency": t.get("urgency"),
        "schedule_type": t.get("schedule_type"),
        "deadline": t.get("deadline"),
        "scheduled_start": t.get("scheduled_start"),
        "scheduled_end": t.get("scheduled_end"),
        "has_explicit_time": t.get("has_explicit_time"),
        "reason": e.reason,
    }


def rank(
    tasks: list,
    now: datetime,
    limit: int = 3,
    energy: Optional[str] = None,
    exclude_ids=(),
) -> list:
    """Return the recommended tasks, best first.

    energy=None  -> normal ranking, top `limit`.
    energy=low|medium|high -> pinned tasks, the most at-risk task, and one task whose
    effort best matches the user's stated energy (max MAX_MOOD_PICKS in total).
    """
    excluded = {str(i) for i in exclude_ids}

    entries = []
    for task in tasks:
        if str(task.get("id")) in excluded:
            continue
        entry = _build_entry(task, now)
        if entry:
            entries.append(entry)

    pinned = sorted(
        (e for e in entries if e.pinned),
        key=lambda e: (e.pin_time, -e.weight),
    )
    at_risk = sorted(
        (e for e in entries if not e.pinned and e.at_risk),
        key=lambda e: (e.slack, -e.weight),
    )
    rest = sorted(
        (e for e in entries if not e.pinned and not e.at_risk),
        key=_rest_key,
    )

    for e in pinned:
        e.reason = "pinned"
    for e in at_risk:
        e.reason = "deadline_risk"
    for e in rest:
        e.reason = "top_score"

    if energy is None:
        picks = (pinned + at_risk + rest)[:limit]
        return [_present(e) for e in picks]

    # ----- mood / energy mode -----
    target = EFFORT_LEVEL[energy]
    picks = list(pinned)

    if at_risk:
        picks.append(at_risk[0])

    pool = at_risk[1:] + rest
    if pool:
        def effort_distance(item):
            idx, e = item
            level = EFFORT_LEVEL.get(e.task.get("effort"))
            distance = 1 if level is None else abs(level - target)
            return (distance, idx)

        _, best = min(enumerate(pool), key=effort_distance)
        best.reason = "energy_match"
        picks.append(best)

    return [_present(e) for e in picks[:MAX_MOOD_PICKS]]