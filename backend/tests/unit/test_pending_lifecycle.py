"""Lifecycle rules for the in-memory agent decisions."""

import time

import pytest

pytestmark = pytest.mark.logic

USER_A = "pending-lifecycle-user-a"
USER_B = "pending-lifecycle-user-b"


@pytest.fixture
def pending_modules(settings, monkeypatch):
    from app.services import agent_tools
    from app import main

    agent_tools._pending.clear()
    agent_tools._delete_pending.clear()
    monkeypatch.setattr(main, "run_agent", lambda user_id, messages: ("ok", False))

    yield main, agent_tools

    agent_tools._pending.clear()
    agent_tools._delete_pending.clear()


def waiting_duplicate(title="Call Amit", expires=None):
    return {
        "expires": expires if expires is not None else time.time() + 600,
        "queue": [{
            "kind": "duplicate",
            "relation": "duplicate",
            "title": title,
            "new_when": None,
            "raw": title,
            "parsed": {"title": title},
            "target": {"id": "existing-task", "title": title, "when": None},
        }],
    }


def waiting_delete(title="Call Amit"):
    return {
        "expires": time.time() + 600,
        "task_ids": ["11111111-1111-1111-1111-111111111111"],
        "titles": [title],
    }


def chat(main, messages, user_id=USER_A):
    return main.agent_chat(main.ChatRequest(messages=messages), user_id=user_id)


def test_fresh_chat_clears_both_pending_stores_for_that_user(pending_modules):
    main, tools = pending_modules
    tools._pending[USER_A] = waiting_duplicate()
    tools._delete_pending[USER_A] = waiting_delete()

    chat(main, [{"role": "user", "content": "Something new"}])

    assert USER_A not in tools._pending
    assert USER_A not in tools._delete_pending


def test_resolve_pending_without_state_returns_existing_plain_reply(pending_modules):
    _, tools = pending_modules

    result = tools.resolve_pending(USER_A, {"choice": "keep_existing"})

    assert result["status"] == "nothing_pending"
    assert result["reply"] == "There's nothing waiting for a decision. Tell me the task you'd like to add."


def test_delete_confirmation_without_matching_request_deletes_nothing(pending_modules, monkeypatch):
    _, tools = pending_modules
    deleted = []
    monkeypatch.setattr(tools.task_service, "delete_tasks", lambda *args: deleted.append(args))

    result = tools.delete_task(USER_A, {"confirmation": "confirm"})

    assert result["status"] == "not_confirmed"
    assert deleted == []


def test_expired_pending_decision_is_not_applied(pending_modules, monkeypatch):
    _, tools = pending_modules
    tools._pending[USER_A] = waiting_duplicate(expires=time.time() - 1)
    added = []
    monkeypatch.setattr(tools.task_service, "create_task", lambda *args, **kwargs: added.append(args))

    result = tools.resolve_pending(USER_A, {"choice": "add_separate"})

    assert result["status"] == "nothing_pending"
    assert added == []
    assert USER_A not in tools._pending


def test_assistant_in_transcript_preserves_pending_confirmation(pending_modules):
    main, tools = pending_modules
    tools._pending[USER_A] = waiting_duplicate()
    tools._delete_pending[USER_A] = waiting_delete()

    chat(main, [
        {"role": "assistant", "content": "There is a duplicate. Keep it or add anyway?"},
        {"role": "user", "content": "Keep it"},
    ])

    assert USER_A in tools._pending
    assert USER_A in tools._delete_pending
    result = tools.resolve_pending(USER_A, {"choice": "keep_existing"})
    assert result["status"] == "resolved"


def test_fresh_chat_clears_only_the_requesting_users_state(pending_modules):
    main, tools = pending_modules
    tools._pending[USER_A] = waiting_duplicate("A decision")
    tools._delete_pending[USER_A] = waiting_delete("A delete")
    tools._pending[USER_B] = waiting_duplicate("B decision")
    tools._delete_pending[USER_B] = waiting_delete("B delete")

    chat(main, [{"role": "user", "content": "A new request"}], user_id=USER_A)

    assert USER_A not in tools._pending
    assert USER_A not in tools._delete_pending
    assert tools._pending[USER_B]["queue"][0]["title"] == "B decision"
    assert tools._delete_pending[USER_B]["titles"] == ["B delete"]


def test_new_pending_question_from_fresh_chat_survives_next_request(pending_modules, monkeypatch):
    main, tools = pending_modules

    def create_question(user_id, messages):
        tools._pending[user_id] = waiting_duplicate("New question")
        return "A duplicate question", False

    monkeypatch.setattr(main, "run_agent", create_question)
    chat(main, [{"role": "user", "content": "Add the task"}])
    assert tools._pending[USER_A]["queue"][0]["title"] == "New question"

    monkeypatch.setattr(main, "run_agent", lambda user_id, messages: ("resolved", False))
    chat(main, [
        {"role": "user", "content": "Add the task"},
        {"role": "assistant", "content": "A duplicate question"},
        {"role": "user", "content": "Add it anyway"},
    ])

    assert tools._pending[USER_A]["queue"][0]["title"] == "New question"
