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
SENDER = "no-reply@example.test"
WEB = "http://web:3000"
INVITE_SUBJECT = "You have been invited to Soro Nua Campaign Predictor"
RECOVERY_SUBJECT = "Reset your Soro Nua Campaign Predictor password"
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


def test_a_user_token_reaches_row_level_security_and_sees_only_its_own_profile(
    http: httpx.Client, anon: dict[str, str], service: dict[str, str]
) -> None:
    """A gotrue token must carry role=authenticated, or PostgREST rejects every user request."""
    password = f"Zx9-{secrets.token_hex(12)}"
    with (
        _auth_user(http, service, email_confirm=True, password=password) as me,
        _auth_user(http, service, email_confirm=True, password=password) as other,
    ):
        login = http.post(
            "/auth/v1/token",
            params={"grant_type": "password"},
            headers=anon,
            json={"email": me["email"], "password": password},
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        as_user = _keyed(anon["apikey"]) | {"Authorization": f"Bearer {token}"}

        rows = http.get("/rest/v1/profiles", headers=as_user)
        assert rows.status_code == 200, rows.text
        assert [row["id"] for row in rows.json()] == [me["id"]]
        assert other["id"] not in [row["id"] for row in rows.json()]

        escalation = http.patch(
            "/rest/v1/profiles",
            headers=as_user | {"Prefer": "return=representation"},
            params={"id": f"eq.{me['id']}"},
            json={"role": "admin"},
        )
        assert escalation.status_code == 200
        assert escalation.json() == []  # the update policy refuses self-modification


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


def _wait_for_mail(mail: httpx.Client, address: str) -> dict[str, Any]:
    deadline = time.monotonic() + TIMEOUT
    found: list[dict[str, Any]] = []
    while not found and time.monotonic() < deadline:
        found = _messages_for(mail, address)
        if not found:
            time.sleep(0.5)
    assert found, f"no e-mail reached Mailpit for {address} within {TIMEOUT:.0f} seconds"
    message = found[0]  # newest first
    body = mail.get(f"/api/v1/message/{message['ID']}").json()
    return {"summary": message, "body": body}


def _clean(mail: httpx.Client, address: str) -> None:
    ids = [m["ID"] for m in _messages_for(mail, address)]
    if ids:
        mail.request("DELETE", "/api/v1/messages", json={"IDs": ids})


def _confirm_link(html: str, kind: str, site_url: str) -> re.Match[str] | None:
    """The link of the e-mail: SITE_URL + /auth/confirm?token_hash=...&type=<kind>&next=..."""
    unescaped = html.replace("&amp;", "&")
    pattern = (
        re.escape(site_url)
        + r"/auth/confirm\?token_hash=[0-9A-Za-z_-]+&type="
        + kind
        + r"&next=/auth/set-password"
    )
    return re.search(pattern, unescaped)


def test_an_invitation_uses_the_web_template_and_the_confirm_link(
    http: httpx.Client, service: dict[str, str], stack_settings: Settings
) -> None:
    """Proves GOTRUE_MAILER_TEMPLATES_INVITE is fetched from `web` (phase 2, D-053)."""
    email = _test_email()
    user_id = None
    with httpx.Client(base_url=MAILPIT, timeout=TIMEOUT) as mail:
        try:
            response = http.post("/auth/v1/invite", headers=service, json={"email": email})
            assert response.status_code == 200, response.text
            user_id = response.json()["id"]
            received = _wait_for_mail(mail, email)
            assert received["summary"]["From"]["Address"] == SENDER
            assert received["summary"]["Subject"] == INVITE_SUBJECT
            html = received["body"].get("HTML") or ""
            assert _confirm_link(html, "invite", stack_settings.web_app_url), html
            assert "/auth/v1/verify" not in html  # not the default gotrue template any more
            assert "Set your password" in html
        finally:
            _clean(mail, email)
            if user_id:
                http.delete(f"/auth/v1/admin/users/{user_id}", headers=service)


def test_a_recovery_e_mail_uses_the_web_template_and_the_confirm_link(
    http: httpx.Client, anon: dict[str, str], service: dict[str, str], stack_settings: Settings
) -> None:
    with (
        httpx.Client(base_url=MAILPIT, timeout=TIMEOUT) as mail,
        _auth_user(http, service, email_confirm=True) as user,
    ):
        try:
            response = http.post("/auth/v1/recover", headers=anon, json={"email": user["email"]})
            assert response.status_code == 200, response.text
            received = _wait_for_mail(mail, user["email"])
            assert received["summary"]["Subject"] == RECOVERY_SUBJECT
            html = received["body"].get("HTML") or ""
            assert _confirm_link(html, "recovery", stack_settings.web_app_url), html
            assert "/auth/v1/verify" not in html
            assert "Set a new password" in html
        finally:
            _clean(mail, user["email"])


@pytest.mark.parametrize("template", ["invite", "recovery"])
def test_the_mail_templates_are_served_by_web_without_a_session(template: str) -> None:
    """gotrue fetches them at send time, with no cookie: the session middleware must let them by."""
    response = httpx.get(
        f"{WEB}/auth-templates/{template}.html", follow_redirects=False, timeout=TIMEOUT
    )
    assert response.status_code == 200
    assert "{{ .TokenHash }}" in response.text
    assert "{{ .SiteURL }}" in response.text
    assert "{{ .RedirectTo }}" not in response.text


def test_the_real_readiness_probe_is_ready_with_the_right_key_and_not_without(
    stack_settings: Settings, make_jwt: Any
) -> None:
    with TestClient(create_app(stack_settings)) as client:
        response = client.get("/api/ready")
    assert response.status_code == 200
    body = response.json()
    assert SCHEMA_VERSION.match(body["schema_version"])
    assert body["checks"] == {"database": "ok", "cache": "ok"}
    wrong = stack_settings.model_copy(update={"supabase_anon_key": SecretStr(make_jwt("anon"))})
    with TestClient(create_app(wrong)) as client:
        refused = client.get("/api/ready")
    assert refused.status_code == 503
    assert refused.json()["status"] == "not_ready"
