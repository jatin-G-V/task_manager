"""Duplicate check, step 2: how good is the LLM judge? (real Groq calls)

Run on purpose:   pytest -m agent tests/agent/test_dedupe_judge.py -s

It sends 30 labelled pairs, one every 5 seconds (Groq's free tier allows about 8,000 tokens
per minute) and prints a table. Thresholds are a starting point: run once to get your
baseline, then tighten them.
"""

import time
from datetime import timedelta

import pytest

from app.services.timeutil import now_local

pytestmark = pytest.mark.agent

PAUSE_SECONDS = 5
MIN_DETECTION_RATE = 0.80       # duplicates and part-of items the judge catches
MAX_FALSE_POSITIVES = 1         # unrelated pairs it wrongly links (out of 15)


def _day(offset, hhmm):
    hour, minute = map(int, hhmm.split(":"))
    return (now_local() + timedelta(days=offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)


def exact(title, day, hhmm, minutes=30):
    start = _day(day, hhmm)
    return {"title": title, "schedule_type": "scheduled", "has_explicit_time": True, "deadline": None,
            "scheduled_start": start.isoformat(),
            "scheduled_end": (start + timedelta(minutes=minutes)).isoformat()}


def deadline(title, day, hhmm):
    return {"title": title, "schedule_type": "flexible", "has_explicit_time": True,
            "deadline": _day(day, hhmm).isoformat(), "scheduled_start": None, "scheduled_end": None}


def window(title, day, start, end):
    return {"title": title, "schedule_type": "scheduled", "has_explicit_time": False, "deadline": None,
            "scheduled_start": _day(day, start).isoformat(), "scheduled_end": _day(day, end).isoformat()}


def undated(title):
    return {"title": title, "schedule_type": "flexible", "has_explicit_time": False, "deadline": None,
            "scheduled_start": None, "scheduled_end": None}


def cases():
    return [
        # ---- duplicates (same activity, different wording) ----
        ("report", "duplicate", deadline("Send in the report", 3, "17:00"), deadline("Submit the report", 3, "17:00")),
        ("meeting notes", "duplicate", deadline("Share the meeting notes", 3, "17:00"), deadline("Send meeting notes", 3, "17:00")),
        ("checklist", "duplicate", exact("Check the onboarding checklist", 1, "15:00"), exact("Review onboarding checklist", 1, "15:00")),
        ("electricity bill", "duplicate", deadline("Pay the electricity bill", 4, "23:59"), deadline("Pay electricity bill", 4, "23:59")),
        ("call mom", "duplicate", window("Call mom tonight", 0, "18:00", "23:59"), window("Phone mom this evening", 0, "17:00", "21:00")),
        ("buy milk", "duplicate", window("Buy milk tomorrow", 1, "00:00", "23:59"), undated("Buy milk")),
        ("dentist", "duplicate", undated("Book dentist appointment"), undated("Schedule a dentist appointment")),
        ("login bug", "duplicate", deadline("Fix the login bug", 1, "11:00"), deadline("Resolve login bug", 1, "11:00")),
        ("plants", "duplicate", window("Water the plants tomorrow morning", 1, "06:00", "12:00"), undated("Water plants")),
        ("guitar", "duplicate", exact("Practice guitar tonight", 0, "20:00", 20), exact("Guitar practice", 0, "20:00", 20)),
        # ---- part-of (a small item inside a bigger task) ----
        ("milk in groceries", "part_of", window("Buy milk tomorrow", 1, "00:00", "23:59"), undated("Buy groceries")),
        ("hotel in trip", "part_of", undated("Book hotel"), undated("Plan Goa trip")),
        ("cake in party", "part_of", undated("Buy a cake"), undated("Organize Mom's birthday party")),
        ("charger in packing", "part_of", undated("Pack the charger"), undated("Pack for the trip")),
        ("slide in presentation", "part_of", undated("Add a budget slide"), undated("Prepare the client presentation")),
        # ---- unrelated pairs the judge must NOT link ----
        ("demo supplies vs rehearsal", None, window("Buy demo supplies tomorrow afternoon", 1, "12:00", "17:00"), exact("Rehearse the client demo", 1, "17:00")),
        ("send vs review report", None, deadline("Send the report", 3, "17:00"), deadline("Review the report", 3, "17:00")),
        ("call vs email Amit", None, exact("Call Amit", 1, "16:00"), undated("Email Amit")),
        ("supplier call vs proposal", None, exact("Call the supplier", 1, "14:30"), exact("Review supplier proposal", 1, "14:00", 60)),
        ("guitar vs piano", None, exact("Practice guitar", 0, "20:00", 20), exact("Practice piano", 0, "20:00", 20)),
        ("electricity vs internet bill", None, deadline("Pay the electricity bill", 4, "23:59"), deadline("Pay the internet bill", 4, "23:59")),
        ("tax return vs expense report", None, deadline("Submit the tax return", 5, "17:00"), deadline("Submit the expense report", 5, "17:00")),
        ("gift vs call mom", None, deadline("Buy a birthday gift for Mom", 3, "18:00"), window("Call Mom tonight", 0, "18:00", "23:59")),
        ("resume vs linkedin", None, undated("Update the resume"), undated("Update the LinkedIn profile")),
        ("goa vs quarterly review", None, undated("Plan Goa trip"), undated("Plan the quarterly review")),
        ("read vs write chapter", None, window("Read a chapter tonight", 0, "18:00", "23:59"), undated("Write a chapter summary")),
        ("kitchen vs garage", None, undated("Clean the kitchen"), undated("Clean the garage")),
        ("slides vs architecture", None, deadline("Prepare the slides", 4, "12:00"), deadline("Draft architecture for the migration", 4, "12:00")),
        ("sprint review vs planning", None, exact("Schedule the sprint review", 2, "11:00"), exact("Sprint planning meeting", 1, "11:00")),
        ("return vs buy a book", None, undated("Return the library book"), undated("Buy a book")),
    ]


@pytest.fixture
def judge_setup(settings, monkeypatch):
    from app.services import dedupe

    errors = []
    completions = dedupe.groq_client.chat.completions
    original = completions.create

    def recording(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        except Exception as exc:  # judge() swallows it and treats it as "no match"
            errors.append(repr(exc)[:160])
            raise

    monkeypatch.setattr(completions, "create", recording)
    return dedupe, errors


def test_judge_accuracy_on_labelled_pairs(judge_setup):
    dedupe, errors = judge_setup
    rows = []

    for label, expected, new, existing in cases():
        result = dedupe.judge(new, [existing])
        got = result["relation"] if result else None
        rows.append((label, expected, got))
        time.sleep(PAUSE_SECONDS)

    positives = [r for r in rows if r[1] is not None]
    negatives = [r for r in rows if r[1] is None]
    detected = [r for r in positives if r[2] is not None]
    exact_relation = [r for r in positives if r[2] == r[1]]
    false_positives = [r for r in negatives if r[2] is not None]

    print("\n  case                          expected    got")
    for label, expected, got in rows:
        mark = "  " if expected == got else "!!"
        print(f"{mark}{label:30s}{str(expected):12s}{got}")
    print(
        f"\n  detected {len(detected)}/{len(positives)}   exact relation {len(exact_relation)}/{len(positives)}"
        f"   false positives {len(false_positives)}/{len(negatives)}"
    )

    assert not errors, f"{len(errors)} Groq calls failed (rate limit?), so results are not valid: {errors[:2]}"
    assert len(false_positives) <= MAX_FALSE_POSITIVES, [r[0] for r in false_positives]
    assert len(detected) / len(positives) >= MIN_DETECTION_RATE, [r[0] for r in positives if r[2] is None]
