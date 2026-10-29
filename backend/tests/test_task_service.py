import pytest

from app.services import task_service


def test_get_task_returns_none_for_non_uuid_without_querying_database(monkeypatch):
    class UnexpectedDatabaseCall:
        def table(self, *_args, **_kwargs):
            pytest.fail("get_task must reject non-UUID ids before querying Supabase")

    monkeypatch.setattr(task_service, "supabase", UnexpectedDatabaseCall())

    assert task_service.get_task("user-id", "call amit") is None
