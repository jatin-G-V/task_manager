"""Readable time text that the backend writes into replies."""

import re
from datetime import timedelta

import pytest

from app.services.taskfmt import clock, day_word, when_text
from app.services.timeutil import now_local

pytestmark = pytest.mark.logic


def at(days, hour, minute=0):
    return (now_local() + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)


def test_clock_handles_midnight_noon_and_afternoon():
    assert clock(at(1, 0, 5)) == "12:05 AM"
    assert clock(at(1, 12, 0)) == "12:00 PM"
    assert clock(at(1, 13, 30)) == "1:30 PM"
    assert clock(at(1, 9, 0)) == "9:00 AM"


def test_day_word():
    assert day_word(at(0, 15)) == "today"
    assert day_word(at(1, 15)) == "tomorrow"
    assert day_word(at(-1, 15)) == "yesterday"
    assert re.fullmatch(r"[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}", day_word(at(5, 15)))


def test_exact_time():
    task = {"schedule_type": "scheduled", "has_explicit_time": True,
            "scheduled_start": at(1, 10).isoformat()}
    assert when_text(task) == "tomorrow at 10:00 AM"


def test_deadline_with_and_without_a_clock_time():
    d = at(1, 17).isoformat()
    assert when_text({"schedule_type": "flexible", "deadline": d, "has_explicit_time": True}) == "due tomorrow at 5:00 PM"
    assert when_text({"schedule_type": "flexible", "deadline": d, "has_explicit_time": False}) == "due tomorrow"


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ((1, 0, 0), (1, 23, 59), "tomorrow"),                       # whole day
        ((1, 18, 0), (1, 23, 59), "tomorrow after 6:00 PM"),        # open-ended evening
        ((1, 17, 0), (1, 21, 0), "tomorrow, 5:00 PM-9:00 PM"),      # bounded window
    ],
)
def test_vague_windows(start, end, expected):
    task = {"schedule_type": "scheduled", "has_explicit_time": False,
            "scheduled_start": at(*start).isoformat(), "scheduled_end": at(*end).isoformat()}
    assert when_text(task) == expected


def test_multi_day_window_and_window_without_end():
    multi = {"schedule_type": "scheduled", "has_explicit_time": False,
             "scheduled_start": at(1, 0, 0).isoformat(), "scheduled_end": at(4, 23, 59).isoformat()}
    assert when_text(multi).startswith("by ")

    no_end = {"schedule_type": "scheduled", "has_explicit_time": False,
              "scheduled_start": at(1, 9).isoformat()}
    assert when_text(no_end) == "tomorrow"


def test_no_time_at_all_gives_none():
    assert when_text({"schedule_type": "flexible"}) is None
