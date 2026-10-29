"""Shared fixtures for the Sorted validation suite.

Safety rules built in:
- Nothing that touches Supabase runs unless backend/.env.test exists and contains
  SORTED_TEST_ENV=1, so the suite can never silently use your normal .env.
- Tests create their own throw-away users and delete only those users' rows.
- Heavy imports (supabase, the app) are lazy, so `pytest --collect-only` always works.
"""

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.test"

# Tables that hold per-user rows. Add more (for example a completion log) if you have them.
USER_TABLES = ("tasks", "user_profile")


@dataclass
class Settings:
    url: str
    anon_key: str
    service_key: str


@dataclass
class Account:
    id: str
    email: str
    token: str
    client: object  # supabase client signed in as this user (RLS applies to it)

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}


def _first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


@pytest.fixture(scope="session")
def settings() -> Settings:
    from dotenv import load_dotenv

    if not ENV_FILE.exists():
        pytest.exit(
            f"Missing {ENV_FILE}. Copy .env.test.example to .env.test and fill it in.",
            returncode=2,
        )

    load_dotenv(ENV_FILE, override=True)

    if os.environ.get("SORTED_TEST_ENV") != "1":
        pytest.exit(
            "SORTED_TEST_ENV=1 is missing from .env.test. Refusing to run against another environment.",
            returncode=2,
        )

    found = Settings(
        url=os.environ.get("SUPABASE_URL", "").strip(),
        anon_key=_first_env("SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY"),
        service_key=_first_env(
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_SERVICE_KEY",
            "SUPABASE_SECRET_KEY",
        ),
    )

    missing = [name for name, value in vars(found).items() if not value]
    if missing:
        pytest.exit(f".env.test is missing: {', '.join(missing)}", returncode=2)

    return found


@pytest.fixture(scope="session")
def admin(settings):
    """Service-role client. Used only to create/delete test users and to verify DB state."""
    from supabase import create_client

    return create_client(settings.url, settings.service_key)


def _make_account(admin, settings: Settings, label: str) -> Account:
    from supabase import create_client

    email = f"sorted-test-{label}-{uuid.uuid4().hex[:8]}@example.com"
    password = f"Test-{uuid.uuid4().hex}"

    created = admin.auth.admin.create_user(
        {"email": email, "password": password, "email_confirm": True}
    )
    user_id = created.user.id

    client = create_client(settings.url, settings.anon_key)
    signed_in = client.auth.sign_in_with_password({"email": email, "password": password})

    return Account(
        id=user_id,
        email=email,
        token=signed_in.session.access_token,
        client=client,
    )


@pytest.fixture(scope="session")
def accounts(admin, settings):
    pair = (_make_account(admin, settings, "a"), _make_account(admin, settings, "b"))
    yield pair

    ids = [account.id for account in pair]

    for table in USER_TABLES:
        try:
            admin.table(table).delete().in_("user_id", ids).execute()
        except Exception as exc:
            print(f"WARNING: could not clean table {table}: {exc}")

    for user_id in ids:
        try:
            admin.auth.admin.delete_user(user_id)
        except Exception as exc:
            print(f"WARNING: could not delete test user {user_id}: {exc}")


@pytest.fixture(scope="session")
def user_a(accounts) -> Account:
    return accounts[0]


@pytest.fixture(scope="session")
def user_b(accounts) -> Account:
    return accounts[1]


@pytest.fixture(scope="session")
def app(settings):
    """The FastAPI app, but only after proving its database client points at the TEST project.

    Without this check a mis-set .env could make the backend write to your real data.
    """
    from urllib.parse import urlparse

    from app.main import app as fastapi_app
    from app.db.supabase_client import supabase

    test_host = urlparse(settings.url).netloc
    seen = [
        str(getattr(supabase, "supabase_url", "")),
        str(getattr(getattr(supabase, "postgrest", None), "base_url", "")),
    ]

    if not test_host or not any(test_host in value for value in seen):
        pytest.exit(
            "SAFETY STOP: the backend's database client does not point at the TEST project.\n"
            f"  test project host : {test_host}\n"
            f"  backend client saw: {seen}\n"
            "Check app/db/supabase_client.py (env variable names, load_dotenv(override=...)).",
            returncode=2,
        )

    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def seed_task(app):
    """Create a task directly through task_service (skips the parser on purpose)."""
    from app.services import task_service
    from tests.helpers import task_payload

    def _seed(account: Account, **overrides) -> dict:
        return task_service.create_task(account.id, task_payload(**overrides))

    return _seed
