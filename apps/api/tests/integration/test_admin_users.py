"""/api/v1/admin/users* (API_SPEC 6.6): list, invite, change role, deactivate, reactivate.

No stack: the real app and real token verification; `AdminEnv` puts doubles behind it (fake Redis,
`FakeUserDb` as the admin's database client, `FakeServiceClient` as gotrue's admin API). The real
stack is covered by test_admin_users_stack.py.
"""

import json
import uuid
from typing import Any

import httpx
import pytest
from gotrue.errors import AuthApiError
from postgrest.exceptions import APIError

from app.api.middleware import SECURITY_HEADERS
from app.infra.profile_cache import CachedProfile, profile_key
from tests.integration.conftest import AdminEnv
from tests.support import log_entries

pytestmark = pytest.mark.integration

USERS = "/api/v1/admin/users"
INVITE = "/api/v1/admin/users/invite"
AUDIT = "/api/v1/admin/audit-log"
SOMEONE = uuid.UUID("00000000-0000-4000-8000-000000000000")
FIELDS = {"id", "email", "full_name", "role", "is_active", "status", "created_at"}
UNAVAILABLE = "The service is temporarily unavailable. Please try again in a few minutes."
DISABLED = "Your account has been deactivated. Contact an administrator."
INVITATION = {"email": "awa@example.test", "full_name": "Awa N.", "role": "marketer"}

ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", USERS, None),
    ("POST", INVITE, INVITATION),
    ("PATCH", f"{USERS}/{SOMEONE}", {"role": "admin"}),
    ("GET", AUDIT, None),
]
ROUTE_IDS = ["list", "invite", "update", "audit"]


def _assert_error(response: httpx.Response, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    error: dict[str, Any] = response.json()["error"]
    assert error["code"] == code
    assert error["request_id"]
    assert isinstance(error["message"], str)
    assert isinstance(error["details"], list)
    return error


# --- who may call: the matrix of every admin route ---------------------------------------------


@pytest.mark.parametrize(("method", "url", "body"), ROUTES, ids=ROUTE_IDS)
def test_no_authorization_header_is_unauthenticated(
    admin_env: AdminEnv, method: str, url: str, body: dict[str, Any] | None
) -> None:
    response = admin_env.client.request(method, url, json=body)
    _assert_error(response, 401, "UNAUTHENTICATED")
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(("method", "url", "body"), ROUTES, ids=ROUTE_IDS)
def test_an_expired_token_is_token_expired(
    admin_env: AdminEnv, method: str, url: str, body: dict[str, Any] | None
) -> None:
    token = admin_env.make_access_token(sub=admin_env.world.admin.id, expires_in=-3600)
    response = admin_env.client.request(
        method, url, json=body, headers={"Authorization": f"Bearer {token}"}
    )
    _assert_error(response, 401, "TOKEN_EXPIRED")


@pytest.mark.parametrize(("method", "url", "body"), ROUTES, ids=ROUTE_IDS)
def test_a_marketer_is_forbidden_in_the_standard_format_and_nothing_is_touched(
    admin_env: AdminEnv, method: str, url: str, body: dict[str, Any] | None
) -> None:
    headers = admin_env.headers_for(uuid.uuid4(), role="marketer")
    response = admin_env.client.request(method, url, json=body, headers=headers)
    error = _assert_error(response, 403, "FORBIDDEN")
    assert error["message"] == "You do not have permission to do this."
    assert response.headers["X-Request-ID"] == error["request_id"]
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value
    assert response.headers["Cache-Control"] == "no-store"
    assert admin_env.world.db.calls == []
    assert admin_env.world.service.calls == []
    assert admin_env.world.events == []


@pytest.mark.parametrize(("method", "url", "body"), ROUTES, ids=ROUTE_IDS)
def test_a_deactivated_admin_is_refused_with_the_deactivation_message(
    admin_env: AdminEnv, method: str, url: str, body: dict[str, Any] | None
) -> None:
    headers = admin_env.headers_for(admin_env.world.admin.id, is_active=False)
    response = admin_env.client.request(method, url, json=body, headers=headers)
    error = _assert_error(response, 403, "ACCOUNT_DISABLED")
    assert error["message"] == DISABLED
    assert admin_env.world.db.calls == []


def test_the_guard_runs_before_validation_so_a_marketer_learns_nothing(admin_env: AdminEnv) -> None:
    """No existence leak (SEC-01/02): 403 even for a bad id, a bad body or a bad page.

    (A body that is not even JSON is refused with a 400 while FastAPI reads it, before any
    dependency runs; that answer says nothing about users.)
    """
    headers = admin_env.headers_for(uuid.uuid4(), role="marketer")
    client = admin_env.client
    assert (
        client.patch(f"{USERS}/not-a-uuid", json={"role": "admin"}, headers=headers).status_code
        == 403
    )
    assert (
        client.patch(f"{USERS}/{SOMEONE}", json={"nonsense": 1}, headers=headers).status_code == 403
    )
    assert client.get(f"{USERS}?limit=0&cursor=garbage", headers=headers).status_code == 403
    assert client.post(INVITE, json={"email": "x"}, headers=headers).status_code == 403


def test_a_bad_path_id_is_a_404_for_an_admin(admin_env: AdminEnv) -> None:
    response = admin_env.client.patch(
        f"{USERS}/not-a-uuid", json={"role": "admin"}, headers=admin_env.admin_headers
    )
    _assert_error(response, 404, "NOT_FOUND")


# --- GET /admin/users --------------------------------------------------------------------------


def _seed_three(env: AdminEnv) -> None:
    env.world.service.seed("one@example.test", confirmed=False, full_name="One")
    env.world.service.seed("two@example.test", is_active=False, full_name="Two")


def test_the_list_has_the_documented_shape_newest_first_with_the_three_statuses(
    admin_env: AdminEnv,
) -> None:
    _seed_three(admin_env)
    response = admin_env.client.get(USERS, headers=admin_env.admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"items", "next_cursor"}
    assert body["next_cursor"] is None
    assert all(set(item) == FIELDS for item in body["items"])
    assert [(i["email"], i["status"]) for i in body["items"]] == [
        ("two@example.test", "deactivated"),
        ("one@example.test", "invited"),
        (admin_env.world.admin.email, "active"),
    ]
    assert body["items"][0]["is_active"] is False
    assert body["items"][0]["created_at"] > body["items"][1]["created_at"]


def test_the_list_pages_follow_the_cursor_without_gap_or_duplicate(admin_env: AdminEnv) -> None:
    _seed_three(admin_env)
    first = admin_env.client.get(f"{USERS}?limit=2", headers=admin_env.admin_headers).json()
    assert len(first["items"]) == 2
    assert isinstance(first["next_cursor"], str)
    second = admin_env.client.get(
        USERS,
        params={"limit": "2", "cursor": first["next_cursor"]},
        headers=admin_env.admin_headers,
    ).json()
    assert len(second["items"]) == 1
    assert second["next_cursor"] is None
    ids = [item["id"] for item in first["items"] + second["items"]]
    assert len(set(ids)) == 3


def test_the_largest_page_size_is_accepted(admin_env: AdminEnv) -> None:
    assert (
        admin_env.client.get(f"{USERS}?limit=100", headers=admin_env.admin_headers).status_code
        == 200
    )


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=101", "limit=-1", "limit=abc", "cursor=garbage", "cursor=" + "x" * 513],
)
def test_a_bad_page_parameter_is_a_400_with_details_and_no_echo(
    admin_env: AdminEnv, query: str
) -> None:
    response = admin_env.client.get(f"{USERS}?{query}", headers=admin_env.admin_headers)
    error = _assert_error(response, 400, "INVALID_REQUEST")
    assert error["message"] == "The pagination parameters are invalid."
    assert error["details"]
    value = query.split("=")[1]
    if value.isalpha():
        assert value not in response.text


def test_the_list_reads_with_the_admin_client_not_the_service_client(admin_env: AdminEnv) -> None:
    admin_env.client.get(USERS, headers=admin_env.admin_headers)
    assert admin_env.world.db.calls_named("profiles.select")
    assert admin_env.world.service.calls_named("profile_update") == []


def test_a_gotrue_outage_on_the_list_is_a_503_in_the_standard_format(admin_env: AdminEnv) -> None:
    admin_env.world.service.errors["list_users"] = httpx.ConnectError("down")
    error = _assert_error(
        admin_env.client.get(USERS, headers=admin_env.admin_headers), 503, "SERVICE_UNAVAILABLE"
    )
    assert error["message"] == UNAVAILABLE


# --- POST /admin/users/invite ------------------------------------------------------------------


def test_an_invitation_is_a_201_with_the_invited_user_and_an_audit_entry(
    admin_env: AdminEnv,
) -> None:
    response = admin_env.client.post(
        INVITE,
        json={**INVITATION, "email": "  Awa@Example.TEST "},
        headers=admin_env.admin_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == FIELDS
    assert (body["email"], body["full_name"], body["role"]) == (
        "awa@example.test",
        "Awa N.",
        "marketer",
    )
    assert (body["status"], body["is_active"]) == ("invited", True)
    (entry,) = admin_env.world.db.audit
    assert (entry["action"], entry["target_id"]) == ("user.invited", body["id"])
    assert entry["actor_id"] == admin_env.world.admin.id
    assert entry["metadata"] == {"email": "awa@example.test", "role": "marketer"}


def test_an_admin_invitation_returns_the_admin_role(admin_env: AdminEnv) -> None:
    response = admin_env.client.post(
        INVITE, json={**INVITATION, "role": "admin"}, headers=admin_env.admin_headers
    )
    assert (response.status_code, response.json()["role"]) == (201, "admin")


def test_an_email_that_already_exists_is_a_409(admin_env: AdminEnv) -> None:
    admin_env.world.service.seed("awa@example.test", confirmed=False)
    response = admin_env.client.post(INVITE, json=INVITATION, headers=admin_env.admin_headers)
    error = _assert_error(response, 409, "EMAIL_ALREADY_REGISTERED")
    assert error["message"] == "A user with this email already exists."
    assert admin_env.world.service.calls_named("invite") == []


@pytest.mark.parametrize(
    ("changes", "field", "issues"),
    [
        ({"email": "not-an-email"}, "email", {"invalid_format"}),
        ({"email": "a" * 250 + "@x.test"}, "email", {"too_long"}),
        ({"full_name": ""}, "full_name", {"too_short", "invalid"}),
        ({"role": "owner"}, "role", {"invalid_choice"}),
        ({"is_active": False}, "is_active", {"unknown_field"}),
        ({"role": None}, "role", {"invalid_choice"}),
    ],
    ids=["email", "long_email", "empty_name", "role", "extra_field", "null_role"],
)
def test_an_invalid_invitation_is_a_422_that_names_the_field_and_never_echoes_it(
    admin_env: AdminEnv, changes: dict[str, Any], field: str, issues: set[str]
) -> None:
    response = admin_env.client.post(
        INVITE, json={**INVITATION, **changes}, headers=admin_env.admin_headers
    )
    error = _assert_error(response, 422, "VALIDATION_ERROR")
    assert error["message"] == "Some fields are invalid."
    (detail,) = error["details"]
    assert detail["field"] == field
    assert detail["issue"] in issues
    for value in changes.values():
        if isinstance(value, str) and len(value) > 3:
            assert value not in response.text
    assert admin_env.world.events == []


def test_a_missing_field_is_reported_as_required(admin_env: AdminEnv) -> None:
    for field in ("email", "full_name", "role"):
        body = {k: v for k, v in INVITATION.items() if k != field}
        response = admin_env.client.post(INVITE, json=body, headers=admin_env.admin_headers)
        error = _assert_error(response, 422, "VALIDATION_ERROR")
        assert [(d["field"], d["issue"]) for d in error["details"]] == [(field, "required")]


def test_a_body_that_is_not_json_is_a_400(admin_env: AdminEnv) -> None:
    response = admin_env.client.post(
        INVITE,
        content="{not json",
        headers={**admin_env.admin_headers, "Content-Type": "application/json"},
    )
    _assert_error(response, 400, "INVALID_REQUEST")


def test_a_body_over_64_kb_is_a_413(admin_env: AdminEnv) -> None:
    padding = "a" * 70_000
    response = admin_env.client.post(
        INVITE,
        content=json.dumps({**INVITATION, "full_name": padding}),
        headers={**admin_env.admin_headers, "Content-Type": "application/json"},
    )
    _assert_error(response, 413, "PAYLOAD_TOO_LARGE")


def test_gotrue_rate_limit_is_a_429_with_retry_after(admin_env: AdminEnv) -> None:
    admin_env.world.service.errors["invite_user_by_email"] = AuthApiError(  # type: ignore[arg-type]
        "email rate limit exceeded", 429, "over_email_send_rate_limit"
    )
    response = admin_env.client.post(INVITE, json=INVITATION, headers=admin_env.admin_headers)
    _assert_error(response, 429, "RATE_LIMITED")
    assert response.headers["Retry-After"] == "60"


# --- PATCH /admin/users/{id} -------------------------------------------------------------------


def _target(env: AdminEnv, **changes: Any) -> str:
    return env.world.service.seed("target@example.test", full_name="Target", **changes).id


def test_a_role_change_is_a_200_with_the_updated_user_and_an_audit_entry(
    admin_env: AdminEnv,
) -> None:
    target = _target(admin_env)
    response = admin_env.client.patch(
        f"{USERS}/{target}", json={"role": "admin"}, headers=admin_env.admin_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == FIELDS
    assert (body["id"], body["role"], body["status"]) == (target, "admin", "active")
    (entry,) = admin_env.world.db.audit
    assert entry["action"] == "user.role_changed"
    assert entry["metadata"] == {"email": "target@example.test", "from": "marketer", "to": "admin"}


def test_a_deactivation_bans_clears_the_cache_and_a_reactivation_undoes_it(
    admin_env: AdminEnv,
) -> None:
    target = _target(admin_env)
    admin_env.world.cache.set(uuid.UUID(target), CachedProfile("marketer", True))
    off = admin_env.client.patch(
        f"{USERS}/{target}", json={"is_active": False}, headers=admin_env.admin_headers
    )
    assert (off.status_code, off.json()["status"], off.json()["is_active"]) == (
        200,
        "deactivated",
        False,
    )
    assert admin_env.world.service.calls_named("ban") == [("ban", target, "876000h")]
    assert profile_key(uuid.UUID(target)) not in admin_env.world.redis.data
    on = admin_env.client.patch(
        f"{USERS}/{target}", json={"is_active": True}, headers=admin_env.admin_headers
    )
    assert (on.status_code, on.json()["status"]) == (200, "active")
    assert admin_env.world.service.calls_named("ban")[-1] == ("ban", target, "none")
    assert [e["action"] for e in admin_env.world.db.audit] == [
        "user.deactivated",
        "user.reactivated",
    ]


def test_a_deactivated_admin_is_refused_on_his_very_next_call(admin_env: AdminEnv) -> None:
    """E2E-AUTH-08 / E2E-SESS-03 on the API side. A second administrator is deactivated by the
    first; his 60 s profile cache entry is cleared at once, so the database (RLS hides his row) is
    asked and answers: deactivated."""
    other = admin_env.world.service.seed("second@example.test", role="admin", full_name="Second")
    other_headers = admin_env.headers_for(other.id)
    assert admin_env.client.get(USERS, headers=other_headers).status_code == 200  # cache hit
    off = admin_env.client.patch(
        f"{USERS}/{other.id}", json={"is_active": False}, headers=admin_env.admin_headers
    )
    assert off.status_code == 200, off.text
    refused = admin_env.client.get(USERS, headers=other_headers)  # the same, still valid token
    error = _assert_error(refused, 403, "ACCOUNT_DISABLED")
    assert error["message"] == DISABLED
    assert any(r.method == "GET" for r in admin_env.profile_server.requests)


def test_changing_the_own_account_is_a_409_for_every_field(admin_env: AdminEnv) -> None:
    me = admin_env.world.admin.id
    for body in ({"role": "marketer"}, {"is_active": False}, {"full_name": "Boss"}):
        response = admin_env.client.patch(
            f"{USERS}/{me}", json=body, headers=admin_env.admin_headers
        )
        error = _assert_error(response, 409, "SELF_ACTION_FORBIDDEN")
        assert error["message"] == "You cannot change your own account."
    assert admin_env.world.service.calls == []


def test_an_unknown_user_is_a_404(admin_env: AdminEnv) -> None:
    response = admin_env.client.patch(
        f"{USERS}/{uuid.uuid4()}", json={"role": "admin"}, headers=admin_env.admin_headers
    )
    error = _assert_error(response, 404, "NOT_FOUND")
    assert error["message"] == "User not found."


def test_the_last_administrator_guard_of_the_database_is_a_409(admin_env: AdminEnv) -> None:
    target = _target(admin_env, role="admin")
    admin_env.world.db.errors["profiles.update"] = APIError(
        {"message": "LAST_ADMIN", "code": "P0001", "details": "SQL detail", "hint": ""}
    )
    response = admin_env.client.patch(
        f"{USERS}/{target}", json={"role": "marketer"}, headers=admin_env.admin_headers
    )
    error = _assert_error(response, 409, "LAST_ADMIN")
    assert error["message"] == "At least one active administrator is required."
    assert "SQL" not in response.text
    assert admin_env.world.events == []


@pytest.mark.parametrize("body", [{}, {"role": None}, {"role": None, "is_active": None}])
def test_an_empty_update_is_a_422(admin_env: AdminEnv, body: dict[str, Any]) -> None:
    response = admin_env.client.patch(
        f"{USERS}/{_target(admin_env)}", json=body, headers=admin_env.admin_headers
    )
    error = _assert_error(response, 422, "VALIDATION_ERROR")
    assert [(d["field"], d["issue"]) for d in error["details"]] == [("body", "required")]
    assert error["details"][0]["message"] == (
        "Provide at least one field to update: role, is_active or full_name."
    )


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"is_active": "false"}, "is_active"),
        ({"is_active": 0}, "is_active"),
        ({"role": "owner"}, "role"),
        ({"email": "x@y.test"}, "email"),
        ({"full_name": ""}, "full_name"),
    ],
)
def test_an_invalid_update_is_a_422_naming_the_field(
    admin_env: AdminEnv, body: dict[str, Any], field: str
) -> None:
    response = admin_env.client.patch(
        f"{USERS}/{_target(admin_env)}", json=body, headers=admin_env.admin_headers
    )
    error = _assert_error(response, 422, "VALIDATION_ERROR")
    assert {d["field"] for d in error["details"]} == {field}


def test_a_database_outage_on_an_update_is_a_503_in_the_standard_format(
    admin_env: AdminEnv,
) -> None:
    target = _target(admin_env)
    admin_env.world.db.errors["profiles.select"] = httpx.ConnectError("down")
    response = admin_env.client.patch(
        f"{USERS}/{target}", json={"role": "admin"}, headers=admin_env.admin_headers
    )
    error = _assert_error(response, 503, "SERVICE_UNAVAILABLE")
    assert error["message"] == UNAVAILABLE


def test_the_request_log_of_an_update_carries_the_user_id_and_nothing_personal(
    admin_env: AdminEnv, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _target(admin_env)
    headers = admin_env.admin_headers
    admin_env.client.patch(f"{USERS}/{target}", json={"role": "admin"}, headers=headers)
    out = capsys.readouterr().out
    entry = next(e for e in log_entries(out) if e["event"] == "request" and e["method"] == "PATCH")
    assert entry["user_id"] == admin_env.world.admin.id
    assert entry["status"] == 200
    assert entry["route"] == "/api/v1/admin/users/{user_id}"
    assert headers["Authorization"].removeprefix("Bearer ") not in out
    assert "target@example.test" not in out
    assert "Target" not in out


def test_a_refused_admin_call_is_logged_as_a_warning_without_the_token(
    admin_env: AdminEnv, capsys: pytest.CaptureFixture[str]
) -> None:
    headers = admin_env.headers_for(uuid.uuid4(), role="marketer")
    admin_env.client.get(USERS, headers=headers)
    out = capsys.readouterr().out
    assert [e["level"] for e in log_entries(out) if e["event"] == "admin_access_denied"] == [
        "warning"
    ]
    assert headers["Authorization"].removeprefix("Bearer ") not in out
