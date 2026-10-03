"""User administration against the real local stack (needs `make up`; hosts are service names).

The first three tests settle assumptions about gotrue that the design relies on (A1: the error code
of a banned sign-in, A2: what a banned user's old token and refresh token do, A3: `list_users`
paging). They do not depend on any phase 3 code. The others drive the real admin routes with real
tokens.

Accounts are `phase3-<uuid>@example.test`. Everything created is deleted in teardown (users,
profiles, Redis keys, Mailpit messages). The audit log is append-only by design: its rows stay.
"""

import base64
import contextlib
import json
import re
import secrets
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
import redis
from fastapi.testclient import TestClient

from app.config import Settings
from app.infra.profile_cache import profile_key
from app.infra.supabase_clients import get_anon_client, get_service_client
from app.main import create_app

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("require_stack")]

TIMEOUT = 10.0
MAILPIT = "http://mailpit:8025"
INVITATION_SUBJECT = "You have been invited to Soro Nua Campaign Predictor"
DISABLED = "Your account has been deactivated. Contact an administrator."
BAN = "876000h"
ADMIN_ROUTES = (
    ("GET", "/api/v1/admin/users"),
    ("POST", "/api/v1/admin/users/invite"),
    ("PATCH", f"/api/v1/admin/users/{uuid.UUID(int=0)}"),
    ("GET", "/api/v1/admin/audit-log"),
)


@dataclass
class Account:
    id: str
    email: str
    password: str
    full_name: str


class Lab:
    """Creates throwaway accounts through gotrue's admin API and removes everything afterwards."""

    def __init__(self, settings: Settings, cache: redis.Redis) -> None:
        self.settings = settings
        self.cache = cache
        self.service = get_service_client(settings)
        self.keys = {
            "anon": settings.supabase_anon_key.get_secret_value(),
            "service": settings.supabase_service_role_key.get_secret_value(),
        }
        self.http = httpx.Client(base_url=settings.supabase_url, timeout=TIMEOUT)
        self.mail = httpx.Client(base_url=MAILPIT, timeout=TIMEOUT)
        self.accounts: list[Account] = []
        self.emails: list[str] = []

    # -- accounts --

    def new_email(self) -> str:
        email = f"phase3-{uuid.uuid4()}@example.test"
        self.emails.append(email)
        return email

    def create(
        self, *, role: str = "marketer", full_name: str = "Phase Three", confirmed: bool = True
    ) -> Account:
        password = f"Zx9-{secrets.token_hex(12)}"
        email = self.new_email()
        created = self.service.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": confirmed,
                "user_metadata": {"full_name": full_name},
            }
        )
        assert created.user is not None
        account = Account(created.user.id, email, password, full_name)
        self.accounts.append(account)
        if role != "marketer":
            self.service.table("profiles").update({"role": role}).eq("id", account.id).execute()
        return account

    def password_grant(self, account: Account, password: str | None = None) -> httpx.Response:
        return self.http.post(
            "/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": self.keys["anon"]},
            json={"email": account.email, "password": password or account.password},
        )

    def sign_in(self, account: Account) -> str:
        response = self.password_grant(account)
        assert response.status_code == 200, response.text
        return str(response.json()["access_token"])

    def refresh_token_of(self, account: Account) -> str:
        response = self.password_grant(account)
        assert response.status_code == 200, response.text
        return str(response.json()["refresh_token"])

    def profile(self, user_id: str) -> dict[str, Any]:
        rows = self.service.table("profiles").select("*").eq("id", user_id).execute().data
        return dict(rows[0])

    def active_admins_except(self, ids: set[str]) -> list[str]:
        rows = (
            self.service.table("profiles")
            .select("id")
            .eq("role", "admin")
            .eq("is_active", True)
            .execute()
            .data
        )
        return [row["id"] for row in rows if row["id"] not in ids]

    # -- mail --

    def invitation_for(self, email: str) -> dict[str, Any]:
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            listing = self.mail.get("/api/v1/search", params={"query": f"to:{email}"}).json()
            if listing.get("messages"):
                return dict(self.mail.get(f"/api/v1/message/{listing['messages'][0]['ID']}").json())
            time.sleep(0.5)
        pytest.fail(f"no e-mail reached Mailpit for {email} within {TIMEOUT:.0f} seconds")

    # -- teardown --

    def close(self) -> None:
        ids = {account.id for account in self.accounts}
        for email in self.emails:
            rows = self.service.table("profiles").select("id").eq("email", email).execute().data
            ids.update(row["id"] for row in rows)
        for user_id in ids:
            self.cache.delete(profile_key(uuid.UUID(user_id)))
            with contextlib.suppress(Exception):  # teardown must go on
                self.service.auth.admin.delete_user(user_id)
        for email in self.emails:
            listing = self.mail.get("/api/v1/search", params={"query": f"to:{email}"}).json()
            message_ids = [message["ID"] for message in listing.get("messages", [])]
            if message_ids:
                self.mail.request("DELETE", "/api/v1/messages", json={"IDs": message_ids})
        self.http.close()
        self.mail.close()


@pytest.fixture(scope="module")
def jwt_ready(stack_settings: Settings) -> None:
    if not stack_settings.supabase_jwt_secret.get_secret_value():
        pytest.fail("SUPABASE_JWT_SECRET is empty in the api container: run 'make env-local'")


@pytest.fixture
def cache(stack_settings: Settings) -> Iterator[redis.Redis]:
    client = redis.Redis.from_url(
        stack_settings.redis_url.get_secret_value(), decode_responses=True, socket_timeout=5
    )
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def lab(stack_settings: Settings, cache: redis.Redis) -> Iterator[Lab]:
    laboratory = Lab(stack_settings, cache)
    try:
        yield laboratory
    finally:
        laboratory.close()


@pytest.fixture
def api(stack_settings: Settings, jwt_ready: None) -> Iterator[TestClient]:
    with TestClient(create_app(stack_settings)) as client:
        yield client


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _patch(api: TestClient, admin_token: str, user_id: str, body: dict[str, Any]) -> httpx.Response:
    return api.patch(f"/api/v1/admin/users/{user_id}", headers=_bearer(admin_token), json=body)


def _error_code(response: httpx.Response) -> str | None:
    body = response.json()
    return str(body.get("error_code") or body.get("code") or "") or None


# --- A1, A2, A3: what gotrue really does -------------------------------------------------------


def test_banned_user_cannot_sign_in_and_gotrue_reports_user_banned(lab: Lab) -> None:
    """A1. The web login screen classifies this answer by its `error_code`, never by status."""
    account = lab.create()
    lab.service.auth.admin.update_user_by_id(account.id, {"ban_duration": BAN})
    banned = lab.password_grant(account)
    assert banned.status_code in {400, 403}, banned.text
    assert banned.json()["error_code"] == "user_banned"
    # OBSERVED (probe of the local stack): gotrue answers user_banned BEFORE it checks the password,
    # so a wrong password on a banned account is told apart from a wrong password on any other
    # account. Spec contradiction C7 (SECURITY 4.4 identical failures vs E2E-AUTH-08): the web
    # login screen must decide with this fact in hand. A change here means gotrue changed.
    not_the_password = f"Wrong-{secrets.token_hex(8)}"
    wrong = lab.password_grant(account, password=not_the_password)
    assert wrong.json()["error_code"] == "user_banned"
    other = lab.create()
    assert lab.password_grant(other, password=not_the_password).json()["error_code"] == (
        "invalid_credentials"
    )
    lab.service.auth.admin.update_user_by_id(account.id, {"ban_duration": "none"})
    assert lab.password_grant(account).status_code == 200


def test_banned_users_access_token_and_refresh_token_with_gotrue(lab: Lab) -> None:
    """A2. gotrue refuses a banned user's access token on /user and its refresh token (SEC-07)."""
    account = lab.create()
    password_session = lab.password_grant(account).json()
    access, refresh = password_session["access_token"], password_session["refresh_token"]
    lab.service.auth.admin.update_user_by_id(account.id, {"ban_duration": BAN})
    on_user_endpoint = lab.http.get(
        "/auth/v1/user", headers={"apikey": lab.keys["anon"], "Authorization": f"Bearer {access}"}
    )
    # OBSERVED: gotrue itself refuses the old access token on /user (403 user_banned), so the web
    # middleware branch `getUser() -> user_banned -> /login?reason=disabled` is live (spec 2.B).
    assert on_user_endpoint.status_code == 403, on_user_endpoint.text
    assert on_user_endpoint.json()["error_code"] == "user_banned"
    refreshed = lab.http.post(
        "/auth/v1/token",
        params={"grant_type": "refresh_token"},
        headers={"apikey": lab.keys["anon"]},
        json={"refresh_token": refresh},
    )
    assert refreshed.status_code == 400, refreshed.text
    assert refreshed.json()["error_code"] == "user_banned"


def test_list_users_per_page_is_not_capped_below_what_the_loop_expects(lab: Lab) -> None:
    """A3. Three users are found with `per_page=200`; the paging loop ends on an EMPTY page."""
    made = {lab.create().id for _ in range(3)}
    seen: set[str] = set()
    pages = 0
    admin = lab.service.auth.admin
    while pages < 50:
        pages += 1
        users = admin.list_users(page=pages, per_page=200)
        if not users:
            break
        seen.update(user.id for user in users)
    else:  # pragma: no cover - would mean the loop never meets an empty page
        pytest.fail("list_users never returned an empty page")
    assert made <= seen


# --- the real routes ---------------------------------------------------------------------------


def test_invite_then_status_goes_invited_then_active(lab: Lab, api: TestClient) -> None:
    boss = lab.create(role="admin", full_name="Phase Boss")
    token = lab.sign_in(boss)
    email = lab.new_email()
    response = api.post(
        "/api/v1/admin/users/invite",
        headers=_bearer(token),
        json={"email": email.upper(), "full_name": "Phase Invitee", "role": "marketer"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["email"], body["status"], body["role"]) == (email, "invited", "marketer")
    assert body["is_active"] is True
    assert set(body) == {"id", "email", "full_name", "role", "is_active", "status", "created_at"}

    message = lab.invitation_for(email)
    assert message["Subject"] == INVITATION_SUBJECT
    found = re.search(
        r"token_hash=([0-9A-Za-z_-]+)&type=invite", message["HTML"].replace("&amp;", "&")
    )
    assert found, "the invitation e-mail has no token_hash link"
    assert "/auth/confirm?" in message["HTML"]

    listed = api.get("/api/v1/admin/users?limit=100", headers=_bearer(token)).json()["items"]
    assert next(u for u in listed if u["email"] == email)["status"] == "invited"

    session = (
        get_anon_client(lab.settings)
        .auth.verify_otp({"token_hash": found.group(1), "type": "invite"})
        .session
    )
    assert session is not None
    set_password = lab.http.put(
        "/auth/v1/user",
        headers={"apikey": lab.keys["anon"], "Authorization": f"Bearer {session.access_token}"},
        json={"password": f"Zx9-{secrets.token_hex(12)}"},
    )
    assert set_password.status_code == 200, set_password.text

    listed = api.get("/api/v1/admin/users?limit=100", headers=_bearer(token)).json()["items"]
    assert next(u for u in listed if u["email"] == email)["status"] == "active"


def test_deactivation_blocks_immediately(lab: Lab, api: TestClient, cache: redis.Redis) -> None:
    boss, target = lab.create(role="admin", full_name="Phase Boss"), lab.create()
    boss_token, target_token = lab.sign_in(boss), lab.sign_in(target)
    key = profile_key(uuid.UUID(target.id))
    assert api.get("/api/v1/me", headers=_bearer(target_token)).status_code == 200
    assert cache.get(key) is not None, "the first call must have filled the profile cache"

    off = _patch(api, boss_token, target.id, {"is_active": False})
    assert off.status_code == 200, off.text
    assert (off.json()["status"], off.json()["is_active"]) == ("deactivated", False)
    assert cache.get(key) is None, "the profile cache entry must be gone at once (API_SPEC 6.6)"
    refused = api.get("/api/v1/me", headers=_bearer(target_token))  # the OLD token, same second
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "ACCOUNT_DISABLED"
    assert refused.json()["error"]["message"] == DISABLED
    assert lab.password_grant(target).json()["error_code"] == "user_banned"
    assert lab.profile(target.id)["is_active"] is False

    on = _patch(api, boss_token, target.id, {"is_active": True})
    assert (on.status_code, on.json()["status"]) == (200, "active")
    fresh = lab.sign_in(target)
    assert api.get("/api/v1/me", headers=_bearer(fresh)).status_code == 200


def test_role_change_is_effective_without_waiting_60_seconds(lab: Lab, api: TestClient) -> None:
    boss, target = lab.create(role="admin", full_name="Phase Boss"), lab.create()
    boss_token, target_token = lab.sign_in(boss), lab.sign_in(target)
    probe = "/api/v1/admin/users?limit=1"
    assert api.get(probe, headers=_bearer(target_token)).status_code == 403  # caches "marketer"
    up = _patch(api, boss_token, target.id, {"role": "admin"})
    assert (up.status_code, up.json()["role"]) == (200, "admin")
    assert api.get(probe, headers=_bearer(target_token)).status_code == 200
    down = _patch(api, boss_token, target.id, {"role": "marketer"})
    assert (down.status_code, down.json()["role"]) == (200, "marketer")
    denied = api.get(probe, headers=_bearer(target_token))
    assert (denied.status_code, denied.json()["error"]["code"]) == (403, "FORBIDDEN")


def test_last_admin_guard_is_translated_from_the_real_database(lab: Lab) -> None:
    """The real PostgREST error shapes go through `from_postgrest` (never a SQL text, C3).

    LAST_ADMIN needs the target to be the ONLY active administrator, which a shared local database
    often is not: then the demotion must simply succeed (the guard is covered by pgTAP 030) and
    only the FORBIDDEN shape is checked, which does not depend on the data.
    """
    from postgrest.exceptions import APIError

    from app.api.errors import ErrorCode, from_postgrest
    from app.repositories.audit_repo import log_action
    from app.repositories.profiles_repo import update_profile

    only = lab.create(role="admin", full_name="Phase Only Admin")
    others = lab.active_admins_except({only.id})
    if others:
        update_profile(lab.service, uuid.UUID(only.id), {"role": "marketer"})
        assert lab.profile(only.id)["role"] == "marketer"
        update_profile(lab.service, uuid.UUID(only.id), {"role": "admin"})
    else:
        with pytest.raises(APIError) as refused:
            update_profile(lab.service, uuid.UUID(only.id), {"role": "marketer"})
        translated = from_postgrest(refused.value)
        assert translated is not None
        assert (translated.code, translated.status) == (ErrorCode.LAST_ADMIN, 409)
        assert translated.message == "At least one active administrator is required."
        assert "LAST_ADMIN" not in translated.message
        assert lab.profile(only.id)["role"] == "admin"

    marketer = lab.create()
    token = lab.sign_in(marketer)
    from app.infra.supabase_clients import get_user_client

    with pytest.raises(APIError) as forbidden:
        log_action(
            get_user_client(token, lab.settings),
            action="user.invited",
            target_type="user",
            target_id=marketer.id,
            metadata={},
        )
    translated = from_postgrest(forbidden.value)
    assert translated is not None
    assert (translated.code, translated.status) == (ErrorCode.FORBIDDEN, 403)


def test_audit_log_lists_the_actions_in_order_with_actor_embed(lab: Lab, api: TestClient) -> None:
    boss = lab.create(role="admin", full_name="Phase Boss")
    token = lab.sign_in(boss)
    email = lab.new_email()
    invited = api.post(
        "/api/v1/admin/users/invite",
        headers=_bearer(token),
        json={"email": email, "full_name": "Phase Invitee", "role": "marketer"},
    )
    assert invited.status_code == 201, invited.text
    target_id = invited.json()["id"]
    for body in ({"role": "admin"}, {"is_active": False}, {"is_active": True}):
        assert _patch(api, token, target_id, body).status_code == 200

    first = api.get("/api/v1/admin/audit-log?limit=100", headers=_bearer(token))
    assert first.status_code == 200, first.text
    ours = [e for e in first.json()["items"] if e["target_id"] == target_id]
    assert [e["action"] for e in ours] == [
        "user.reactivated",
        "user.deactivated",
        "user.role_changed",
        "user.invited",
    ]
    assert all(e["actor"] == {"id": boss.id, "full_name": "Phase Boss"} for e in ours)
    assert all(e["target_type"] == "user" for e in ours)
    assert ours[3]["metadata"] == {"email": email, "role": "marketer"}
    assert ours[2]["metadata"] == {"email": email, "from": "marketer", "to": "admin"}
    assert ours[1]["metadata"] == ours[0]["metadata"] == {"email": email}
    assert [e["created_at"] for e in ours] == sorted((e["created_at"] for e in ours), reverse=True)

    # Pagination: two entries per page, no overlap, strictly descending, until ours are found.
    seen: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(60):
        params = {"limit": "2", **({"cursor": cursor} if cursor else {})}
        page = api.get("/api/v1/admin/audit-log", params=params, headers=_bearer(token)).json()
        assert len(page["items"]) <= 2
        seen.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None or {e["id"] for e in ours} <= {e["id"] for e in seen}:
            break
    ids = [e["id"] for e in seen]
    assert len(ids) == len(set(ids)), "a page overlaps the previous one"
    assert ids == sorted(ids, reverse=True)
    assert {e["id"] for e in ours} <= set(ids)


def test_a_cursor_with_an_id_of_the_wrong_kind_is_a_400_not_a_database_error(
    lab: Lab, api: TestClient
) -> None:
    """A well-formed cursor whose id is not a uuid (users) or a bigint (audit) would be refused by
    PostgreSQL (22P02) and surface as a 503 plus an error report: it is a bad request."""
    token = lab.sign_in(lab.create(role="admin", full_name="Phase Cursor"))
    stamp = "2026-10-03T14:05:00.123456+00:00"
    wrong = {"users": "123", "audit-log": str(uuid.uuid4())}
    for route, row_id in wrong.items():
        payload = json.dumps({"c": stamp, "i": row_id})
        cursor = base64.urlsafe_b64encode(payload.encode()).decode()
        response = api.get(
            f"/api/v1/admin/{route}", params={"cursor": cursor}, headers=_bearer(token)
        )
        assert response.status_code == 400, (route, response.text)
        assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_marketer_token_gets_403_on_every_admin_route_and_service_key_gets_401(
    lab: Lab, api: TestClient
) -> None:
    token = lab.sign_in(lab.create())
    payload = {"email": lab.new_email(), "full_name": "Nobody", "role": "admin"}
    for method, path in ADMIN_ROUTES:
        body = payload if method == "POST" else {"is_active": False} if method == "PATCH" else None
        refused = api.request(method, path, headers=_bearer(token), json=body)
        assert refused.status_code == 403, (method, path, refused.text)
        assert refused.json()["error"]["code"] == "FORBIDDEN"
        for key in (lab.keys["service"], lab.keys["anon"]):
            unauthenticated = api.request(method, path, headers=_bearer(key), json=body)
            assert unauthenticated.status_code == 401, (method, path)
            assert unauthenticated.json()["error"]["code"] == "UNAUTHENTICATED"
    assert (
        lab.service.table("profiles").select("id").eq("email", payload["email"]).execute().data
        == []
    )


@pytest.mark.parametrize(
    "change",
    [{"is_active": False}, {"role": "marketer"}],
    ids=["deactivated", "demoted"],
)
def test_an_admin_with_a_stale_cached_role_cannot_invite(
    lab: Lab, api: TestClient, change: dict[str, Any]
) -> None:
    """The cache still says "admin" (60 s, or a failed invalidation) while the database no longer
    does. The invitation uses the service key, so the real database must refuse the actor."""
    stale = lab.create(role="admin", full_name="Phase Stale")
    lab.create(role="admin")  # a second active admin keeps the last-administrator guard quiet
    token = lab.sign_in(stale)
    assert api.get("/api/v1/admin/users?limit=1", headers=_bearer(token)).status_code == 200
    # Changed behind the cache's back (service client: the cache entry is NOT invalidated).
    lab.service.table("profiles").update(change).eq("id", stale.id).execute()
    email = lab.new_email()
    refused = api.post(
        "/api/v1/admin/users/invite",
        headers=_bearer(token),
        json={"email": email, "full_name": "Phase Nobody", "role": "admin"},
    )
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "FORBIDDEN")
    assert lab.service.table("profiles").select("id").eq("email", email).execute().data == []
    users = lab.service.auth.admin.list_users(page=1, per_page=200)
    assert all(user.email != email for user in users)
