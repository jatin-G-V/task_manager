"""Phase 1 security invariants. Zero tolerance: one failure here is a blocker.

Run:  pytest -m security

Covers (a) the backend API and (b) Supabase row-level security directly, so a bug
in either layer is caught. Tests for the update/complete/delete routes are added
once routers/tasks.py has been reviewed.
"""

import pytest

from tests.helpers import as_list, contains_text, unique_title

pytestmark = [pytest.mark.security, pytest.mark.api]


@pytest.fixture
def two_users_with_tasks(user_a, user_b, seed_task):
    mine = [seed_task(user_a, title=unique_title("a")) for _ in range(2)]
    theirs = seed_task(user_b, title=unique_title("b"))
    return mine, theirs


# ---- backend API ----------------------------------------------------------

def test_list_returns_only_own_tasks(client, user_a, two_users_with_tasks):
    mine, theirs = two_users_with_tasks
    data = client.get("/tasks", headers=user_a.headers).json()
    ids = {task["id"] for task in as_list(data)}

    assert {task["id"] for task in mine} <= ids
    assert theirs["id"] not in ids
    assert not contains_text(data, theirs["title"])


def test_get_other_users_task_is_hidden(client, user_a, two_users_with_tasks):
    _, theirs = two_users_with_tasks
    response = client.get(f"/tasks/{theirs['id']}", headers=user_a.headers)

    assert response.status_code in (403, 404)
    assert not contains_text(response.json(), theirs["title"])


def test_dashboard_contains_only_own_tasks(client, user_a, two_users_with_tasks):
    mine, theirs = two_users_with_tasks
    data = client.get("/tasks/dashboard", headers=user_a.headers).json()

    assert not contains_text(data, theirs["title"])
    assert contains_text(data, mine[0]["title"])


# ---- row-level security, straight against the database --------------------

def test_rls_user_sees_only_own_rows(user_a, two_users_with_tasks):
    rows = user_a.client.table("tasks").select("id,user_id").execute().data
    assert rows, "user A should see their own tasks"
    assert all(row["user_id"] == user_a.id for row in rows)


def test_rls_cannot_read_other_users_task(user_a, two_users_with_tasks):
    _, theirs = two_users_with_tasks
    rows = user_a.client.table("tasks").select("id").eq("id", theirs["id"]).execute().data
    assert rows == []


def test_rls_cannot_update_other_users_task(user_a, admin, two_users_with_tasks):
    _, theirs = two_users_with_tasks
    try:
        user_a.client.table("tasks").update({"title": "HACKED"}).eq("id", theirs["id"]).execute()
    except Exception:
        pass  # raising is also an acceptable way to refuse

    after = admin.table("tasks").select("title").eq("id", theirs["id"]).execute().data
    assert after and after[0]["title"] == theirs["title"]


def test_rls_cannot_delete_other_users_task(user_a, admin, two_users_with_tasks):
    _, theirs = two_users_with_tasks
    try:
        user_a.client.table("tasks").delete().eq("id", theirs["id"]).execute()
    except Exception:
        pass

    after = admin.table("tasks").select("id").eq("id", theirs["id"]).execute().data
    assert after, "user B's task was deleted by user A"


def test_rls_cannot_insert_row_for_another_user(user_a, user_b, admin):
    title = unique_title("planted")
    try:
        user_a.client.table("tasks").insert(
            {"user_id": user_b.id, "title": title, "section": "work", "status": "pending"}
        ).execute()
    except Exception:
        pass

    planted = admin.table("tasks").select("id").eq("title", title).execute().data
    assert planted == [], "user A planted a task in user B's account"
