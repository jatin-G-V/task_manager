"""Questions waiting for an answer (duplicate / clash / delete confirmation) belong to ONE user.

Another user can never see, answer, cancel or trigger them, and an expired one is never applied.
No database or LLM is used: the delete call is replaced by a recorder.
"""

import time

import pytest

pytestmark = pytest.mark.logic

TASK_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def tools(settings, monkeypatch):
    from app.services import agent_tools

    agent_tools._pending.clear()
    agent_tools._delete_pending.clear()

    deleted = []

    def fake_delete(user_id, ids):
        deleted.append((user_id, list(ids)))
        return [{"id": task_id, "title": "Buy milk"} for task_id in ids]

    monkeypatch.setattr(agent_tools.task_service, "delete_tasks", fake_delete)

    yield agent_tools, deleted

    agent_tools._pending.clear()
    agent_tools._delete_pending.clear()


def waiting_delete(expires_in=600):
    return {"expires": time.time() + expires_in, "task_ids": [TASK_ID], "titles": ["Buy milk"]}


def waiting_duplicate(title="Call Amit"):
    return {
        "expires": time.time() + 600,
        "queue": [{
            "kind": "duplicate", "relation": "duplicate", "title": title, "new_when": None,
            "raw": title, "parsed": {"title": title},
            "target": {"id": "t1", "title": "Call Amit", "when": None},
        }],
    }


# ---- delete confirmation -----------------------------------------------------

def test_the_owner_can_confirm_their_own_delete(tools):
    t, deleted = tools
    t._delete_pending["user-a"] = waiting_delete()

    result = t.delete_task("user-a", {"confirmation": "confirm"})

    assert result["status"] == "deleted"
    assert deleted == [("user-a", [TASK_ID])]


def test_another_user_cannot_confirm_my_delete(tools):
    t, deleted = tools
    t._delete_pending["user-a"] = waiting_delete()

    result = t.delete_task("user-b", {"confirmation": "confirm"})

    assert result["status"] == "not_confirmed"
    assert deleted == []
    assert "user-a" in t._delete_pending          # A's question is still waiting


def test_another_user_cannot_cancel_my_delete(tools):
    t, deleted = tools
    t._delete_pending["user-a"] = waiting_delete()

    t.delete_task("user-b", {"confirmation": "cancel"})

    assert "user-a" in t._delete_pending and deleted == []


def test_an_expired_delete_confirmation_is_never_applied(tools):
    t, deleted = tools
    t._delete_pending["user-a"] = waiting_delete(expires_in=-1)

    result = t.delete_task("user-a", {"confirmation": "confirm"})

    assert result["status"] == "not_confirmed" and deleted == []


# ---- duplicate / clash questions ---------------------------------------------

def test_another_user_cannot_answer_my_pending_question(tools):
    t, _ = tools
    t._pending["user-a"] = waiting_duplicate()

    result = t.resolve_pending("user-b", {"choice": "keep_existing"})

    assert result["status"] == "nothing_pending"
    assert len(t._pending["user-a"]["queue"]) == 1


def test_two_users_have_independent_questions(tools):
    t, _ = tools
    t._pending["user-a"] = waiting_duplicate("Call Amit")
    t._pending["user-b"] = waiting_duplicate("Pay the bill")

    result = t.resolve_pending("user-a", {"choice": "keep_existing"})

    assert result["status"] == "resolved"
    assert "user-a" not in t._pending
    assert t._pending["user-b"]["queue"][0]["title"] == "Pay the bill"


def test_with_nothing_pending_the_reply_is_plain_and_changes_nothing(tools):
    t, _ = tools

    result = t.resolve_pending("user-a", {"choice": "keep_existing"})

    assert result["status"] == "nothing_pending"
    assert "nothing waiting" in result["reply"].lower() or "no longer" in result["reply"].lower()
