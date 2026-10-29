"""Phase 0 gate: the backend starts, routes are registered, auth basics hold.

Run first:  pytest -m gate
If anything here fails, stop and fix it before running any other test.
"""

import pytest

from tests.helpers import as_list

pytestmark = [pytest.mark.gate, pytest.mark.api]

PROTECTED = [
    ("GET", "/tasks", None),
    ("GET", "/tasks/dashboard", None),
    ("POST", "/agent/chat", {"messages": []}),
    ("POST", "/parse-task", {"text": "x"}),
]


def test_app_imports_and_core_routes_exist(app):
    paths = set(app.openapi()["paths"])
    assert "/health" in paths
    assert "/agent/chat" in paths
    assert any(p.startswith("/tasks") for p in paths), (
        "tasks router is not registered (check app.include_router(tasks_router) in main.py)"
    )


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_missing_token_is_rejected(client, method, path, body):
    response = client.request(method, path, json=body)
    assert response.status_code in (401, 403), f"{method} {path} -> {response.status_code}"


@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_garbage_token_is_rejected(client, method, path, body):
    response = client.request(
        method, path, json=body, headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code in (401, 403), f"{method} {path} -> {response.status_code}"


def test_valid_token_can_list_tasks(client, user_a):
    response = client.get("/tasks", headers=user_a.headers)
    assert response.status_code == 200
    assert isinstance(as_list(response.json()), list)


def test_valid_token_can_open_dashboard(client, user_a):
    response = client.get("/tasks/dashboard", headers=user_a.headers)
    assert response.status_code == 200
    assert isinstance(response.json(), dict)
