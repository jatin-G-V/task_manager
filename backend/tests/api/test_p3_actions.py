"""Phase 3: what complete / update / delete really do to the database, and who may do them.

Run:  pytest tests/api/test_p3_actions.py

Everything is checked on the stored row (service role), not on the response text.
Tests marked "FINDING" probe behaviour that looks wrong in the current code; if one fails
it is a real bug to fix, not a broken test.
"""

import logging
import uuid
from datetime import timedelta

import pytest

from tests.helpers import (
    as_list, db_row, db_rows, past_iso, recurring_overrides, unique_title,
)

pytestmark = pytest.mark.api


def complete(client, user, task_id):
    return client.post(f"/tasks/{task_id}/complete", headers=user.headers)


def patch(client, user, task_id, body):
    return client.patch(f"/tasks/{task_id}", headers=user.headers, json=body)


def delete(client, user, task_id):
    return client.delete(f"/tasks/{task_id}", headers=user.headers)


# ============================================================================
# Complete
# ============================================================================

def test_complete_sets_status_and_timestamp_and_creates_nothing_else(client, user_a, seed_task, admin):
    task = seed_task(user_a)

    response = complete(client, user_a, task["id"])

    assert response.status_code == 200
    row = db_row(admin, task["id"])
    assert row["status"] == "completed" and row["completed_at"]
    assert len(db_rows(admin, user_a.id, task["title"])) == 1


def test_completed_task_leaves_the_active_list_and_appears_in_history(client, user_a, seed_task):
    task = seed_task(user_a)
    complete(client, user_a, task["id"])

    active = {t["id"] for t in as_list(client.get("/tasks?limit=200", headers=user_a.headers).json())}
    history = {t["id"] for t in as_list(
        client.get("/tasks?status=completed&limit=200", headers=user_a.headers).json())}

    assert task["id"] not in active
    assert task["id"] in history


def test_completing_twice_changes_nothing(client, user_a, seed_task, admin):
    task = seed_task(user_a)
    complete(client, user_a, task["id"])
    first = db_row(admin, task["id"])["completed_at"]

    again = complete(client, user_a, task["id"])

    assert again.status_code == 200
    assert db_row(admin, task["id"])["completed_at"] == first
    assert len(db_rows(admin, user_a.id, task["title"])) == 1


def test_completing_an_unknown_task_is_404(client, user_a):
    assert complete(client, user_a, str(uuid.uuid4())).status_code == 404


def test_FINDING_completing_a_malformed_id_is_not_a_server_error(client, user_a):
    # get/patch already answer 404 for a malformed id; complete and delete should too
    assert complete(client, user_a, "call-amit").status_code in (404, 422)


# ============================================================================
# Delete
# ============================================================================

def test_delete_removes_the_row_and_a_second_delete_is_404(client, user_a, seed_task, admin):
    task = seed_task(user_a)

    first = delete(client, user_a, task["id"])

    assert first.status_code == 200 and first.json()["deleted"] is True
    assert db_row(admin, task["id"]) is None
    assert delete(client, user_a, task["id"]).status_code == 404


def test_FINDING_deleting_a_malformed_id_is_not_a_server_error(client, user_a):
    assert delete(client, user_a, "call-amit").status_code in (404, 422)


# ============================================================================
# Update
# ============================================================================

def test_update_changes_only_the_requested_field(client, user_a, seed_task, admin):
    task = seed_task(user_a, urgency="medium", effort="low", section="work", brief="keep me")

    response = patch(client, user_a, task["id"], {"urgency": "high"})

    assert response.status_code == 200
    row = db_row(admin, task["id"])
    assert row["urgency"] == "high"
    for field in ("title", "effort", "section", "brief", "deadline", "status", "user_id"):
        assert row[field] == task[field], field


def test_update_can_empty_an_optional_field(client, user_a, seed_task, admin):
    task = seed_task(user_a, brief="to be removed")

    assert patch(client, user_a, task["id"], {"brief": None}).status_code == 200

    row = db_row(admin, task["id"])
    assert row["brief"] is None and row["title"] == task["title"]


def test_update_cannot_hand_the_task_to_another_user(client, user_a, user_b, seed_task, admin):
    task = seed_task(user_a)

    patch(client, user_a, task["id"], {"user_id": user_b.id})  # refused or ignored, never applied

    assert db_row(admin, task["id"])["user_id"] == user_a.id


def test_update_rejects_an_invalid_enum_value(client, user_a, seed_task, admin):
    task = seed_task(user_a, urgency="medium")

    response = patch(client, user_a, task["id"], {"urgency": "extreme"})

    assert response.status_code in (400, 422)
    assert db_row(admin, task["id"])["urgency"] == "medium"


def test_update_rejects_a_deadline_in_the_past(client, user_a, seed_task, admin):
    task = seed_task(user_a)

    response = patch(client, user_a, task["id"], {"deadline": past_iso(2)})

    assert response.status_code == 400 and "past" in response.json()["detail"].lower()
    assert db_row(admin, task["id"])["deadline"] == task["deadline"]


def test_an_overdue_task_can_still_be_renamed(client, user_a, seed_task, admin):
    task = seed_task(user_a)
    admin.table("tasks").update({"deadline": past_iso(24)}).eq("id", task["id"]).execute()

    response = patch(client, user_a, task["id"], {"title": unique_title("renamed")})

    assert response.status_code == 200


def test_switching_to_scheduled_without_a_start_is_rejected(client, user_a, seed_task, admin):
    task = seed_task(user_a)  # flexible, has a deadline

    response = patch(client, user_a, task["id"], {"schedule_type": "scheduled"})

    assert response.status_code == 400
    assert db_row(admin, task["id"])["schedule_type"] == "flexible"


def test_update_duration_keeps_the_estimate_in_sync(client, user_a, seed_task, admin):
    task = seed_task(user_a)

    assert patch(client, user_a, task["id"], {"duration": 45}).status_code == 200

    row = db_row(admin, task["id"])
    assert row["duration"] == 45 and row["estimated_time_minutes"] == 45


def test_update_rejects_a_zero_duration(client, user_a, seed_task, admin):
    task = seed_task(user_a)

    assert patch(client, user_a, task["id"], {"duration": 0}).status_code in (400, 422)
    assert db_row(admin, task["id"])["duration"] is None


def test_recurrence_pattern_must_match_the_scheduled_date(client, user_a, seed_task, admin):
    overrides, start = recurring_overrides()
    task = seed_task(user_a, **overrides)
    wrong_day = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"][(start.weekday() + 3) % 7]

    response = patch(client, user_a, task["id"], {"recurrence": f"FREQ=WEEKLY;BYDAY={wrong_day}"})

    assert response.status_code == 400
    assert db_row(admin, task["id"])["recurrence"] == overrides["recurrence"]


# ============================================================================
# Recurring tasks: completing one creates the next
# ============================================================================

def _series(admin, user, title):
    rows = db_rows(admin, user.id, title)
    return ([r for r in rows if r["status"] == "completed"],
            [r for r in rows if r["status"] == "pending"])


def test_completing_a_recurring_task_creates_exactly_one_next_occurrence(client, user_a, seed_task, admin):
    from app.services.timeutil import to_local

    overrides, start = recurring_overrides()
    task = seed_task(user_a, **overrides)

    assert complete(client, user_a, task["id"]).status_code == 200

    done, pending = _series(admin, user_a, overrides["title"])
    assert len(done) == 1 and len(pending) == 1
    nxt = pending[0]
    nxt_start = to_local(nxt["scheduled_start"])
    assert nxt_start > to_local(task["scheduled_start"])                 # a later date, not the same one again
    assert (nxt_start - to_local(task["scheduled_start"])) <= timedelta(days=14)
    assert nxt_start.weekday() == start.weekday()                        # same weekday
    assert (nxt_start.hour, nxt_start.minute) == (start.hour, start.minute)
    assert nxt["is_recurring"] is True and nxt["recurrence"] == overrides["recurrence"]
    assert nxt["is_blocked"] is False and nxt["completed_at"] is None
    assert nxt["scheduled_end"] and to_local(nxt["scheduled_end"]) - nxt_start == timedelta(minutes=20)


def test_completing_the_same_recurring_task_again_does_not_duplicate_the_next_one(client, user_a, seed_task, admin):
    overrides, _ = recurring_overrides()
    task = seed_task(user_a, **overrides)

    complete(client, user_a, task["id"])
    complete(client, user_a, task["id"])

    done, pending = _series(admin, user_a, overrides["title"])
    assert len(done) == 1 and len(pending) == 1


def test_a_database_error_never_blocks_completion_and_a_retry_heals_the_series(
    client, user_a, seed_task, admin, monkeypatch, caplog
):
    from postgrest.exceptions import APIError
    from app.services import task_service

    overrides, _ = recurring_overrides()
    task = seed_task(user_a, **overrides)
    real = task_service._ensure_next_occurrence

    def failing(*args, **kwargs):
        raise APIError({"message": "injected failure", "code": "XX000"})

    monkeypatch.setattr(task_service, "_ensure_next_occurrence", failing)
    caplog.set_level(logging.ERROR)

    response = complete(client, user_a, task["id"])

    assert response.status_code == 200                                   # the user's action succeeded
    done, pending = _series(admin, user_a, overrides["title"])
    assert len(done) == 1 and pending == []
    assert any("next occurrence" in record.getMessage() for record in caplog.records)  # and it was logged

    monkeypatch.setattr(task_service, "_ensure_next_occurrence", real)
    assert complete(client, user_a, task["id"]).status_code == 200       # retry
    done, pending = _series(admin, user_a, overrides["title"])
    assert len(done) == 1 and len(pending) == 1


def test_a_series_stops_after_its_end_date(client, user_a, seed_task, admin):
    overrides, start = recurring_overrides()
    overrides["recurrence_end"] = (start + timedelta(days=3)).isoformat()  # before the next weekly date
    task = seed_task(user_a, **overrides)

    complete(client, user_a, task["id"])

    done, pending = _series(admin, user_a, overrides["title"])
    assert len(done) == 1 and pending == []


# ============================================================================
# Security: another user's task through the real routes
# ============================================================================

@pytest.fixture
def others_task(user_b, seed_task):
    return seed_task(user_b, title=unique_title("b"))


def test_another_user_cannot_update_my_task(client, user_a, others_task, admin):
    response = patch(client, user_a, others_task["id"], {"title": "HACKED"})

    assert response.status_code == 404
    assert db_row(admin, others_task["id"])["title"] == others_task["title"]


def test_another_user_cannot_complete_my_task(client, user_a, others_task, admin):
    response = complete(client, user_a, others_task["id"])

    assert response.status_code == 404
    assert db_row(admin, others_task["id"])["status"] == "pending"


def test_another_user_cannot_delete_my_task(client, user_a, others_task, admin):
    response = delete(client, user_a, others_task["id"])

    assert response.status_code == 404
    assert db_row(admin, others_task["id"]) is not None
