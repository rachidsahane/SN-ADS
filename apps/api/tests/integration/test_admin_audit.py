"""GET /api/v1/admin/audit-log (API_SPEC 6.9) and the OpenAPI contract of the admin routes.

No stack: see test_admin_users.py for the doubles.
"""

import base64
import json
import uuid
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import AdminEnv

pytestmark = pytest.mark.integration

AUDIT = "/api/v1/admin/audit-log"
ENTRY_FIELDS = {"id", "created_at", "actor", "action", "target_type", "target_id", "metadata"}


def _seed(env: AdminEnv, count: int, *, same_time: str | None = None) -> list[int]:
    ids = []
    for number in range(count):
        row = env.world.db.add_audit(
            action="user.invited",
            target_id=f"target-{number}",
            actor_id=env.world.admin.id if number % 2 == 0 else None,
            metadata={"email": f"u{number}@example.test", "role": "marketer"},
            created_at=same_time,
        )
        ids.append(row["id"])
    return ids


def _error(response: httpx.Response, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    error: dict[str, Any] = response.json()["error"]
    assert error["code"] == code
    assert error["request_id"]
    return error


def test_the_log_has_the_documented_shape_with_the_actor_or_null(admin_env: AdminEnv) -> None:
    _seed(admin_env, 2)
    response = admin_env.client.get(AUDIT, headers=admin_env.admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"items", "next_cursor"}
    assert body["next_cursor"] is None
    newest, oldest = body["items"]
    assert set(newest) == set(oldest) == ENTRY_FIELDS
    assert newest["target_id"] == "target-1"
    assert newest["actor"] is None  # serialised as null, not omitted
    assert oldest["actor"] == {"id": admin_env.world.admin.id, "full_name": "Boss Admin"}
    assert (oldest["action"], oldest["target_type"]) == ("user.invited", "user")
    assert oldest["metadata"] == {"email": "u0@example.test", "role": "marketer"}
    assert newest["created_at"] > oldest["created_at"]


def test_an_empty_log_is_an_empty_list(admin_env: AdminEnv) -> None:
    response = admin_env.client.get(AUDIT, headers=admin_env.admin_headers)
    assert response.json() == {"items": [], "next_cursor": None}


def test_the_pages_follow_the_cursor_without_gap_or_duplicate_even_on_equal_dates(
    admin_env: AdminEnv,
) -> None:
    ids = _seed(admin_env, 5, same_time="2026-10-03T12:00:00.000001+00:00")
    seen: list[int] = []
    cursor: str | None = None
    for _ in range(5):
        params = {"limit": "2", **({"cursor": cursor} if cursor else {})}
        page = admin_env.client.get(AUDIT, params=params, headers=admin_env.admin_headers).json()
        assert len(page["items"]) <= 2
        seen.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == sorted(ids, reverse=True)


def test_exactly_the_limit_of_entries_has_no_next_cursor(admin_env: AdminEnv) -> None:
    _seed(admin_env, 2)
    page = admin_env.client.get(f"{AUDIT}?limit=2", headers=admin_env.admin_headers).json()
    assert (len(page["items"]), page["next_cursor"]) == (2, None)


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=101", "limit=abc", "cursor=garbage", "cursor=" + "y" * 513]
)
def test_a_bad_page_parameter_is_a_400(admin_env: AdminEnv, query: str) -> None:
    response = admin_env.client.get(f"{AUDIT}?{query}", headers=admin_env.admin_headers)
    error = _error(response, 400, "INVALID_REQUEST")
    assert error["details"]
    assert error["message"] == "The pagination parameters are invalid."


@pytest.mark.parametrize("row_id", ["abc-def", "2f1c5b0e-7d0a-4b8e-9a53-6a1d3c0f9e11", "9" * 19])
def test_a_well_formed_cursor_with_an_id_that_is_not_a_bigint_is_a_400_not_a_503(
    admin_env: AdminEnv, row_id: str
) -> None:
    """The database would refuse the id (22P02 / 22003): the cursor is checked before it is used."""
    payload = json.dumps({"c": "2026-10-03T14:05:00.123456+00:00", "i": row_id})
    cursor = base64.urlsafe_b64encode(payload.encode()).decode()
    response = admin_env.client.get(
        AUDIT, params={"cursor": cursor}, headers=admin_env.admin_headers
    )
    _error(response, 400, "INVALID_REQUEST")
    assert admin_env.world.db.calls_named("audit_log.select") == []


def test_a_marketer_cannot_read_the_log(admin_env: AdminEnv) -> None:
    _seed(admin_env, 1)
    headers = admin_env.headers_for(uuid.uuid4(), role="marketer")
    response = admin_env.client.get(AUDIT, headers=headers)
    _error(response, 403, "FORBIDDEN")
    assert "target-0" not in response.text
    assert admin_env.world.db.calls == []


def test_a_database_outage_on_the_log_is_a_503(admin_env: AdminEnv) -> None:
    admin_env.world.db.errors["audit_log.select"] = httpx.ConnectError("down")
    response = admin_env.client.get(AUDIT, headers=admin_env.admin_headers)
    error = _error(response, 503, "SERVICE_UNAVAILABLE")
    assert error["message"] == (
        "The service is temporarily unavailable. Please try again in a few minutes."
    )


def test_the_actions_of_the_routes_show_up_in_the_log_newest_first(admin_env: AdminEnv) -> None:
    """A round trip through the real routes: invite, change a role, deactivate, then read."""
    client, headers = admin_env.client, admin_env.admin_headers
    invited = client.post(
        "/api/v1/admin/users/invite",
        json={"email": "awa@example.test", "full_name": "Awa N.", "role": "marketer"},
        headers=headers,
    ).json()
    for body in ({"role": "admin"}, {"is_active": False}):
        assert (
            client.patch(
                f"/api/v1/admin/users/{invited['id']}", json=body, headers=headers
            ).status_code
            == 200
        )
    items = client.get(AUDIT, headers=headers).json()["items"]
    assert [item["action"] for item in items] == [
        "user.deactivated",
        "user.role_changed",
        "user.invited",
    ]
    assert {item["target_id"] for item in items} == {invited["id"]}
    assert all(item["actor"]["full_name"] == "Boss Admin" for item in items)


# --- OpenAPI -----------------------------------------------------------------------------------


@pytest.fixture
def spec(client: TestClient) -> dict[str, Any]:
    document: dict[str, Any] = client.get("/api/openapi.json").json()
    return document


def test_openapi_declares_the_four_admin_operations_with_bearer_auth(spec: dict[str, Any]) -> None:
    declared = {
        ("GET", "/api/v1/admin/users"),
        ("POST", "/api/v1/admin/users/invite"),
        ("PATCH", "/api/v1/admin/users/{user_id}"),
        ("GET", "/api/v1/admin/audit-log"),
    }
    for method, path in declared:
        operation = spec["paths"][path][method.lower()]
        assert {"BearerAuth": []} in operation["security"], (method, path)
        assert {"401", "403", "503"} <= set(operation["responses"]), (method, path)


def test_openapi_declares_the_admin_schemas(spec: dict[str, Any]) -> None:
    schemas = spec["components"]["schemas"]
    for name in (
        "AdminUser",
        "AdminUserPage",
        "InviteUserRequest",
        "UpdateUserRequest",
        "AuditLogPage",
        "AuditEntry",
    ):
        assert name in schemas, name
    assert set(schemas["AdminUser"]["properties"]) == {
        "id", "email", "full_name", "role", "is_active", "status", "created_at"
    }  # fmt: skip
    assert set(schemas["AuditEntry"]["properties"]) == ENTRY_FIELDS
    assert schemas["InviteUserRequest"].get("additionalProperties") is False
    assert schemas["UpdateUserRequest"].get("additionalProperties") is False


def test_openapi_documents_the_status_codes_of_the_mutations(spec: dict[str, Any]) -> None:
    invite = spec["paths"]["/api/v1/admin/users/invite"]["post"]["responses"]
    assert {"201", "409", "422"} <= set(invite)
    update = spec["paths"]["/api/v1/admin/users/{user_id}"]["patch"]["responses"]
    assert {"200", "404", "409", "422"} <= set(update)
    listing = spec["paths"]["/api/v1/admin/users"]["get"]
    assert {parameter["name"] for parameter in listing["parameters"]} == {"limit", "cursor"}
