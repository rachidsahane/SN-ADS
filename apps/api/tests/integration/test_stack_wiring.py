"""The local Supabase stack as the api sees it (needs `make up`; hosts are compose service names).

Every test cleans what it creates. Only dummy addresses on example.test are used.
"""

import re
import secrets
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("require_stack")]

MAILPIT = "http://mailpit:8025"
SCHEMA_VERSION = re.compile(r"^\d{14}$")
VERIFY_LINK = "http://localhost:54321/auth/v1/verify?token="
SENDER = "no-reply@example.test"
TIMEOUT = 10.0


def _keyed(key: str, **extra: str) -> dict[str, str]:
    return {"apikey": key, "Authorization": f"Bearer {key}", **extra}


@pytest.fixture
def anon(stack_settings: Settings) -> dict[str, str]:
    return _keyed(stack_settings.supabase_anon_key.get_secret_value())


@pytest.fixture
def service(stack_settings: Settings) -> dict[str, str]:
    key = stack_settings.supabase_service_role_key.get_secret_value()
    if not key:
        pytest.fail("SUPABASE_SERVICE_ROLE_KEY is empty in the api container: run 'make env-local'")
    return _keyed(key)


@pytest.fixture
def http(stack_settings: Settings) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=stack_settings.supabase_url, timeout=TIMEOUT) as client:
        yield client


def _test_email() -> str:
    return f"phase1-{uuid.uuid4()}@example.test"


@contextmanager
def _auth_user(
    http: httpx.Client, service: dict[str, str], **body: Any
) -> Iterator[dict[str, Any]]:
    """Create a user through gotrue's admin API and always delete it afterwards."""
    response = http.post(
        "/auth/v1/admin/users", headers=service, json={"email": _test_email(), **body}
    )
    assert response.status_code == 200, response.text
    user = response.json()
    try:
        yield user
    finally:
        http.delete(f"/auth/v1/admin/users/{user['id']}", headers=service)


def test_kong_requires_an_api_key(http: httpx.Client) -> None:
    assert http.get("/rest/v1/profiles").status_code == 401


def test_the_anon_key_cannot_read_profiles(http: httpx.Client, anon: dict[str, str]) -> None:
    response = http.get("/rest/v1/profiles", headers=anon)
    assert response.status_code in (401, 403)
    assert response.json()["code"] == "42501"  # permission denied: anon has no table right


def test_gotrue_is_healthy_behind_kong(http: httpx.Client, anon: dict[str, str]) -> None:
    response = http.get("/auth/v1/health", headers=anon)
    assert response.status_code == 200
    assert response.json()["name"] == "GoTrue"


def test_public_signup_is_disabled(
    http: httpx.Client, anon: dict[str, str], service: dict[str, str]
) -> None:
    assert http.get("/auth/v1/settings", headers=anon).json()["disable_signup"] is True
    email = _test_email()
    response = http.post(
        "/auth/v1/signup",
        headers=anon,
        json={"email": email, "password": secrets.token_urlsafe(18)},
    )
    assert 400 <= response.status_code < 500
    users = http.get("/auth/v1/admin/users", headers=service, params={"per_page": 1000}).json()
    assert email not in [user["email"] for user in users["users"]]


def test_storage_is_reachable_with_the_service_key_and_not_leaking_to_anon(
    http: httpx.Client, anon: dict[str, str], service: dict[str, str]
) -> None:
    assert http.get("/storage/v1/bucket", headers=service).status_code == 200
    as_anon = http.get("/storage/v1/bucket", headers=anon)
    if as_anon.status_code == 200:  # buckets of later phases are private: none may be listed
        assert all(bucket["public"] for bucket in as_anon.json())
    else:
        assert 400 <= as_anon.status_code < 500


def test_a_user_created_by_gotrue_gets_a_marketer_profile_whatever_the_metadata(
    http: httpx.Client, service: dict[str, str]
) -> None:
    with _auth_user(
        http,
        service,
        email_confirm=True,
        user_metadata={"full_name": "Stack Test", "role": "admin"},
        app_metadata={"role": "admin"},
    ) as user:
        response = http.get("/rest/v1/profiles", headers=service, params={"id": f"eq.{user['id']}"})
        profiles = response.json()
        assert len(profiles) == 1
        assert profiles[0]["role"] == "marketer"
        assert profiles[0]["full_name"] == "Stack Test"
        assert profiles[0]["is_active"] is True
    after = http.get("/rest/v1/profiles", headers=service, params={"id": f"eq.{user['id']}"})
    assert after.json() == []  # deleted with the auth user (cascade)


def test_anon_can_read_only_the_schema_version(http: httpx.Client, anon: dict[str, str]) -> None:
    version = http.post("/rest/v1/rpc/schema_version", headers=anon, json={})
    assert version.status_code == 200
    assert SCHEMA_VERSION.match(version.json())
    forbidden = http.post("/rest/v1/rpc/is_admin", headers=anon, json={})
    assert forbidden.status_code in (401, 403)
    assert forbidden.json()["code"] == "42501"


def _messages_for(http_mail: httpx.Client, address: str) -> list[dict[str, Any]]:
    listing = http_mail.get("/api/v1/messages", params={"limit": 200}).json()
    return [
        message
        for message in listing["messages"]
        if address in [recipient["Address"] for recipient in message["To"]]
    ]


def test_an_invitation_reaches_mailpit_with_a_working_verify_link(
    http: httpx.Client, service: dict[str, str]
) -> None:
    email = _test_email()
    user_id = None
    with httpx.Client(base_url=MAILPIT, timeout=TIMEOUT) as mail:
        try:
            response = http.post("/auth/v1/invite", headers=service, json={"email": email})
            assert response.status_code == 200, response.text
            user_id = response.json()["id"]
            deadline = time.monotonic() + TIMEOUT
            found: list[dict[str, Any]] = []
            while not found and time.monotonic() < deadline:
                found = _messages_for(mail, email)
                if not found:
                    time.sleep(0.5)
            assert found, "no invitation e-mail reached Mailpit within 10 seconds"
            message = found[0]
            assert message["From"]["Address"] == SENDER
            body = mail.get(f"/api/v1/message/{message['ID']}").json()
            assert VERIFY_LINK in (body.get("Text") or "") + (body.get("HTML") or "")
        finally:
            ids = [m["ID"] for m in _messages_for(mail, email)]
            if ids:
                mail.request("DELETE", "/api/v1/messages", json={"IDs": ids})
            if user_id:
                http.delete(f"/auth/v1/admin/users/{user_id}", headers=service)


def test_the_real_readiness_probe_is_ready_with_the_right_key_and_not_without(
    stack_settings: Settings, make_jwt: Any
) -> None:
    with TestClient(create_app(stack_settings)) as client:
        response = client.get("/api/ready")
    assert response.status_code == 200
    body = response.json()
    assert SCHEMA_VERSION.match(body["schema_version"])
    assert body["checks"]["database"] == "ok"
    wrong = stack_settings.model_copy(update={"supabase_anon_key": SecretStr(make_jwt("anon"))})
    with TestClient(create_app(wrong)) as client:
        refused = client.get("/api/ready")
    assert refused.status_code == 503
    assert refused.json()["status"] == "not_ready"
