"""Duplicate check, step 1: the cheap rules that choose which open tasks the judge will see.
(The LLM judge itself is measured in tests/agent/test_dedupe_judge.py.)"""

from datetime import timedelta

import pytest

from app.services.timeutil import now_local

pytestmark = pytest.mark.logic


@pytest.fixture
def dd(settings):
    from app.services import dedupe
    return dedupe


def day(offset, hour=10):
    return (now_local() + timedelta(days=offset)).replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


def new(title, offset=None):
    return {"title": title, "deadline": day(offset) if offset is not None else None}


def old(title, offset=None, **kw):
    return {"id": title, "title": title, "deadline": day(offset) if offset is not None else None, **kw}


def titles(result):
    return [t["title"] for t in result]


def test_word_normalisation_ignores_case_order_punctuation_and_filler(dd):
    assert dd._words("Call Amit!") == dd._words("amit  CALL")
    assert dd._words("Go to the gym tonight") == dd._words("gym")


def test_same_day_tasks_are_candidates_even_when_titles_differ(dd):
    result = dd.shortlist(new("Buy milk", 1), [old("Draft architecture", 1)])
    assert titles(result) == ["Draft architecture"]


def test_other_day_tasks_need_a_near_identical_title(dd):
    unrelated = old("Draft architecture", 3)
    partly_alike = old("Call supplier", 3)
    near_identical = old("Review the budget sheet", 3)

    result = dd.shortlist(new("Review budget sheet", 1), [unrelated, partly_alike, near_identical])

    assert titles(result) == ["Review the budget sheet"]


def test_undated_tasks_can_belong_to_any_day(dd):
    assert titles(dd.shortlist(new("Buy milk", 2), [old("Buy groceries")])) == ["Buy groceries"]
    assert titles(dd.shortlist(new("Buy milk"), [old("Buy groceries", 5)])) == ["Buy groceries"]


def test_same_day_candidates_come_first_then_best_title_match(dd):
    same_day_weak = old("Draft architecture", 1)
    other_day_strong = old("Review the budget sheet", 4)
    same_day_strong = old("Review budget sheet", 1)

    result = dd.shortlist(new("Review budget sheet", 1), [other_day_strong, same_day_weak, same_day_strong])

    assert titles(result) == ["Review budget sheet", "Draft architecture", "Review the budget sheet"]


def test_at_most_eight_candidates(dd):
    many = [old(f"Task number {i}", 1) for i in range(12)]
    assert len(dd.shortlist(new("Something else", 1), many)) == 8


def test_no_open_tasks_means_no_candidates(dd):
    assert dd.shortlist(new("Buy milk", 1), []) == []
