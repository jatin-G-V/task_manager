from datetime import datetime, timedelta
from typing import Optional

from app.services.timeutil import to_local


# Dominance window around an explicitly scheduled start: start - 8 min .. start + 8 min.
# Both ends are included. (Name kept as PINNED_WINDOW_MIN for compatibility.)
PINNED_WINDOW_MIN = 8
AT_RISK_SLACK_HOURS = 3
SLACK_CAP_HOURS = 168
DEFAULT_ESTIMATE_MIN = 30
TIE_EPS = 0.25
MAX_MOOD_PICKS = 2

URGENCY_WEIGHT = {
    None: 0.75,
    "low": 1.0,
    "medium": 1.5,
    "high": 2.0,
    "urgent": 3.0,
}

SECTION_ORDER = {
    "work": 0,
    "personal": 1,
    "leisure": 2,
}

EFFORT_LEVEL = {
    "low": 0,
    "medium": 1,
    "high": 2,
}

# Blocking is controlled only by the is_blocked flag (see _build_entry),
# not by a status value.
INACTIVE_STATUSES = {
    "completed",
    "dropped",
}


def _dt(value) -> Optional[datetime]:
    """Stored timestamp -> naive local wall-clock datetime."""
    if not value:
        return None

    return to_local(value).replace(tzinfo=None)


def _in_pinned_window(
    moment: datetime,
    now: datetime,
) -> bool:
    """True from moment - 8 min to moment + 8 min, both ends included."""
    return abs(now - moment) <= timedelta(
        minutes=PINNED_WINDOW_MIN
    )


class _Entry:
    __slots__ = (
        "task",
        "pinned",
        "pin_time",
        "due",
        "slack",
        "weight",
        "reason",
    )

    def __init__(
        self,
        task,
        pinned,
        pin_time,
        due,
        slack,
        weight,
    ):
        self.task = task
        self.pinned = pinned
        self.pin_time = pin_time
        self.due = due
        self.slack = slack
        self.weight = weight
        self.reason = None

    @property
    def at_risk(self) -> bool:
        return (
            self.due is not None
            and self.slack <= AT_RISK_SLACK_HOURS
        )

    @property
    def score(self) -> float:
        return self.slack / self.weight


def _build_entry(
    task: dict,
    now: datetime,
) -> Optional[_Entry]:

    if task.get("status") in INACTIVE_STATUSES or task.get("is_blocked"):
        return None

    schedule_type = task.get("schedule_type")
    explicit = bool(task.get("has_explicit_time"))

    start = _dt(task.get("scheduled_start"))
    end = _dt(task.get("scheduled_end"))
    deadline = _dt(task.get("deadline"))

    weight = URGENCY_WEIGHT.get(
        task.get("urgency"),
        URGENCY_WEIGHT[None],
    )

    pinned = False
    pin_time = None
    due = None

    if schedule_type == "scheduled" and start:

        if explicit:
            # Explicitly scheduled task:
            # eligible (and dominant) only inside its +/- 8 minute window.
            if not _in_pinned_window(start, now):
                return None

            return _Entry(
                task,
                True,
                start,
                None,
                SLACK_CAP_HOURS,
                weight,
            )

        # Vague window:
        # eligible only while the window is open.
        if now < start:
            return None

        if end and now > end:
            return None

        due = end

    else:
        # Flexible / bare topic:
        # deadline is the only time signal.
        due = deadline

        if (
            explicit
            and deadline
            and _in_pinned_window(deadline, now)
        ):
            pinned = True
            pin_time = deadline

    # Due time already passed -> overdue.
    if due is not None and due < now and not pinned:
        return None

    if due is None:
        slack = SLACK_CAP_HOURS

    else:
        estimate = (
            task.get("estimated_time_minutes")
            or DEFAULT_ESTIMATE_MIN
        )

        slack = (
            (due - now).total_seconds() / 3600
            - estimate / 60
        )

        slack = min(
            slack,
            SLACK_CAP_HOURS,
        )

    return _Entry(
        task,
        pinned,
        pin_time,
        due,
        slack,
        weight,
    )


def _rest_key(e: _Entry):
    # Tasks with no deadline/window end come after every task
    # that has one.
    return (
        e.due is None,
        round(e.score / TIE_EPS),
        SECTION_ORDER.get(
            e.task.get("section"),
            3,
        ),
        str(
            e.task.get("created_at")
            or ""
        ),
    )


def _present(e: _Entry) -> dict:
    t = e.task

    # estimated_time_minutes is deliberately NOT returned.
    return {
    "id": t.get("id"),
    "title": t.get("title"),
    "section": t.get("section") or "personal",
    "brief": t.get("brief"),

    "effort": t.get("effort"),
    "urgency": t.get("urgency"),
    "schedule_type": t.get("schedule_type"),
    "deadline": t.get("deadline"),
    "scheduled_start": t.get("scheduled_start"),
    "scheduled_end": t.get("scheduled_end"),
    "has_explicit_time": t.get("has_explicit_time"),

    "is_recurring": bool(t.get("is_recurring")),
    "recurrence": t.get("recurrence"),
    "recurrence_end": t.get("recurrence_end"),

    "is_blocked": bool(t.get("is_blocked")),
    "reason": e.reason,
}


def _order(entries: list):
    """Split eligible entries into the three tiers and sort each tier.

    Single source of truth: rank() and build_dashboard() both use it, so the
    Suggested Focus and the first item of the ranked list cannot disagree.
    Tier order: pinned (happening now) -> at risk -> everything else.
    """
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

    return pinned, at_risk, rest


def rank(
    tasks: list,
    now: datetime,
    limit: int = 3,
    energy: Optional[str] = None,
    exclude_ids=(),
) -> list:
    """Return the recommended tasks, best first.

    energy=None  -> normal ranking, top `limit`.

    energy=low|medium|high -> pinned tasks, the most at-risk task,
    and one task whose effort best matches the user's stated energy.
    """

    excluded = {
        str(i)
        for i in exclude_ids
    }

    entries = []

    for task in tasks:

        if str(task.get("id")) in excluded:
            continue

        entry = _build_entry(
            task,
            now,
        )

        if entry:
            entries.append(entry)

    pinned, at_risk, rest = _order(entries)

    if energy is None:

        picks = (
            pinned
            + at_risk
            + rest
        )[:limit]

        return [
            _present(e)
            for e in picks
        ]

    # --------------------------------------------------------
    # MOOD / ENERGY MODE
    # --------------------------------------------------------

    target = EFFORT_LEVEL[energy]

    picks = list(pinned)

    if at_risk:
        picks.append(at_risk[0])

    pool = (
        at_risk[1:]
        + rest
    )

    if pool:

        def effort_distance(item):
            idx, e = item

            level = EFFORT_LEVEL.get(
                e.task.get("effort")
            )

            distance = (
                1
                if level is None
                else abs(level - target)
            )

            return (
                distance,
                idx,
            )

        _, best = min(
            enumerate(pool),
            key=effort_distance,
        )

        best.reason = "energy_match"

        picks.append(best)

    return [
        _present(e)
        for e in picks[:MAX_MOOD_PICKS]
    ]


def next_scheduled(
    tasks: list,
    now: datetime,
    exclude_ids=(),
) -> Optional[dict]:
    """Return the next future exact-time commitment, or None.

    ``now`` and stored timestamps are compared as local wall-clock values,
    matching rank(). A meeting at exactly the pinned-window boundary belongs
    to Suggested Focus, so Upcoming Schedule starts strictly after it.
    """
    excluded = {str(task_id) for task_id in exclude_ids}
    threshold = now + timedelta(minutes=PINNED_WINDOW_MIN)

    eligible = []
    for task in tasks:
        start = _dt(task.get("scheduled_start"))
        if (
            task.get("schedule_type") != "scheduled"
            or not task.get("has_explicit_time")
            or start is None
            or start <= threshold
            or task.get("status") in INACTIVE_STATUSES
            or task.get("is_blocked")
            or str(task.get("id")) in excluded
        ):
            continue

        end = _dt(task.get("scheduled_end"))
        created = _dt(task.get("created_at"))
        eligible.append((
            (
                start,
                end is None,
                end or datetime.max,
                created or datetime.max,
                str(task.get("id") or ""),
            ),
            task,
        ))

    if not eligible:
        return None

    eligible.sort(key=lambda item: item[0])
    return eligible[0][1]


# ============================================================
# DASHBOARD
# ============================================================

def build_dashboard(
    tasks: list,
    now: datetime,
    energy: Optional[str] = None,
) -> dict:

    active_entries = []

    for task in tasks:
        if task.get("status") in INACTIVE_STATUSES:
            continue

        entry = _build_entry(
            task,
            now,
        )

        if entry:
            active_entries.append(entry)

    active_ids = {e.task["id"] for e in active_entries}

    # --------------------------------------------------------
    # OVERDUE
    # A task that is still eligible (including the pinned grace window
    # after a meeting starts) is never overdue.
    # --------------------------------------------------------

    overdue_entries = []

    for task in tasks:
        if task.get("status") in INACTIVE_STATUSES:
            continue

        if task["id"] in active_ids:
            continue

        schedule_type = task.get("schedule_type")
        explicit = bool(
            task.get("has_explicit_time")
        )

        start = _dt(
            task.get("scheduled_start")
        )

        end = _dt(
            task.get("scheduled_end")
        )

        deadline = _dt(
            task.get("deadline")
        )

        due = None

        if schedule_type == "scheduled" and start:
            if explicit:
                due = start
            else:
                due = end or start
        else:
            due = deadline

        if due is not None and due < now:
            overdue_entries.append(
                (
                    task,
                    due,
                )
            )

    overdue_entries.sort(
        key=lambda item: item[1]
    )

    overdue = [
        _build_overdue_entry(task)
        for task, _ in overdue_entries
    ]

    # --------------------------------------------------------
    # UPCOMING
    # --------------------------------------------------------

    overdue_ids = {t["id"] for t, _ in overdue_entries}

    upcoming_tasks = [
        t for t in tasks
        if t.get("status") not in INACTIVE_STATUSES
        and t["id"] not in overdue_ids
        and t["id"] not in active_ids
    ]
    upcoming_tasks.sort(
        key=lambda t: _dt(t.get("scheduled_start") or t.get("deadline"))
        or datetime.max
    )

    upcoming = [
        {**_build_overdue_entry(t), "reason": "upcoming"}
        for t in upcoming_tasks
    ]

    # Dashboard helpers. `upcoming` is sorted by time, nearest first.
    # Blocked tasks stay in `upcoming` (so the sections still list them)
    # but are never offered as the "next" task.
    selectable = [u for u in upcoming if not u["is_blocked"]]

    # option A: nearest upcoming task of any kind
    next_upcoming = selectable[0] if selectable else None

    # option B: nearest upcoming task that has an exact time
    focus_pick = rank(tasks, now=now, limit=1, energy=energy)
    focus_ids = [focus_pick[0]["id"]] if focus_pick else []
    next_explicit_task = next_scheduled(tasks, now, exclude_ids=focus_ids)
    next_upcoming_explicit = (
        {**_build_overdue_entry(next_explicit_task), "reason": "upcoming"}
        if next_explicit_task else None
    )

    # --------------------------------------------------------
    # RANKED / AT RISK / LATER  (same order as rank())
    # --------------------------------------------------------

    pinned_entries, at_risk_entries, later_entries = _order(active_entries)

    ranked_entries = pinned_entries + at_risk_entries + later_entries

    ranked = [_present(e) for e in ranked_entries]
    at_risk = [_present(e) for e in at_risk_entries]
    later = [_present(e) for e in later_entries]

    # --------------------------------------------------------
    # DUE TODAY: eligible tasks that have a time today
    # (overdue and upcoming tasks are not counted here)
    # --------------------------------------------------------

    def _has_time_today(task: dict) -> bool:
        moments = [
            _dt(task.get("deadline")),
            _dt(task.get("scheduled_start")),
            _dt(task.get("scheduled_end")),
        ]

        return any(
            m is not None and m.date() == now.date()
            for m in moments
        )

    due_today = [
        _present(e)
        for e in ranked_entries
        if _has_time_today(e.task)
    ]

    # --------------------------------------------------------
    # SUGGESTED
    # --------------------------------------------------------

    suggested = rank(
        tasks,
        now=now,
        limit=3,
        energy=energy,
    )

    # Main dashboard recommendation: ONE task, never affected by energy / mood.
    top = rank(tasks, now=now, limit=1)
    focus = top[0] if top else None

    # --------------------------------------------------------
    # COUNTS
    # --------------------------------------------------------

    counts = {
        "overdue": len(overdue),
        "due_today": len(due_today),
        "at_risk": len(at_risk),
        "later": len(later),
        "upcoming": len(upcoming),
    }

    return {
        "focus": focus,
        "suggested": suggested,
        "ranked": ranked,
        "overdue": overdue,
        "later": later,
        "upcoming": upcoming,
        "next_upcoming": next_upcoming,
        "next_upcoming_explicit": next_upcoming_explicit,
        "due_today": due_today,
        "at_risk": at_risk,
        "counts": counts,
    }


def _build_overdue_entry(
    task: dict,
) -> dict:
    """
    Present an overdue task using the same public task shape.
    """

    return {
    "id": task.get("id"),
    "title": task.get("title"),
    "section": task.get("section") or "personal",
    "brief": task.get("brief"),

    "effort": task.get("effort"),
    "urgency": task.get("urgency"),
    "schedule_type": task.get("schedule_type"),
    "deadline": task.get("deadline"),
    "scheduled_start": task.get("scheduled_start"),
    "scheduled_end": task.get("scheduled_end"),
    "has_explicit_time": task.get("has_explicit_time"),

    "is_recurring": bool(task.get("is_recurring")),
    "recurrence": task.get("recurrence"),
    "recurrence_end": task.get("recurrence_end"),

    "is_blocked": bool(task.get("is_blocked")),
    "reason": "deadline_risk",
}
