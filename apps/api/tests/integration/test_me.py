"""GET /api/v1/me (API_SPEC 2 and 6.2).

No stack: real token signing, in-process PostgREST, fake Redis.
"""

import json
import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.api.middleware import SECURITY_HEADERS
from app.config import Settings
from app.infra.profile_cache import CachedProfile, ProfileCache, profile_key
from app.main import create_app
from tests.support import OTHER_JWT_SECRET, FakeRedis, ProfileServer

pytestmark = pytest.mark.integration

MakeToken = Callable[..., str]
URL = "/api/v1/me"
ME_FIELDS = {"id", "email", "full_name", "role", "is_active"}
DISABLED = "Your account has been deactivated. Contact an administrator."


@pytest.fixture
def me_client(auth_settings: Settings, fake_redis: FakeRedis) -> TestClient:
    from app.api.deps import get_profile_cache

    app = create_app(auth_settings)
    cache = ProfileCache(fake_redis)  # type: ignore[arg-type]
    app.dependency_overrides[get_profile_cache] = lambda: cache
    return TestClient(app)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- success ----------------------------------------------------------------------------------


def test_me_returns_the_exact_documented_body(
    me_client: TestClient, profile_server: ProfileServer, make_access_token: MakeToken
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(
        user_id, email="awa@example.test", full_name="Awa N.", role="marketer"
    )
    response = me_client.get(URL, headers=_bearer(make_access_token(sub=user_id)))
    assert response.status_code == 200
    assert response.json() == {
        "id": str(user_id),
        "email": "awa@example.test",
        "full_name": "Awa N.",
        "role": "marketer",
        "is_active": True,
    }
    assert set(response.json()) == ME_FIELDS


def test_an_admin_sees_the_admin_role(
    me_client: TestClient, profile_server: ProfileServer, make_access_token: MakeToken
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, role="admin")
    body = me_client.get(URL, headers=_bearer(make_access_token(sub=user_id))).json()
    assert body["role"] == "admin"


def test_me_reads_the_database_with_the_user_token_never_the_service_key(
    me_client: TestClient,
    profile_server: ProfileServer,
    make_access_token: MakeToken,
    auth_settings: Settings,
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id)
    token = make_access_token(sub=user_id)
    me_client.get(URL, headers=_bearer(token))
    assert profile_server.requests
    service = auth_settings.supabase_service_role_key.get_secret_value()
    for request in profile_server.requests:
        assert request.headers["authorization"] == f"Bearer {token}"
        assert service not in request.headers.values()


def test_me_always_reads_the_profile_even_when_the_cache_is_warm(
    me_client: TestClient,
    profile_server: ProfileServer,
    fake_redis: FakeRedis,
    make_access_token: MakeToken,
) -> None:
    """The cache keeps role and is_active only: the name and e-mail come from the database."""
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, full_name="Fresh Name")
    ProfileCache(fake_redis).set(user_id, CachedProfile("marketer", True))  # type: ignore[arg-type]
    body = me_client.get(URL, headers=_bearer(make_access_token(sub=user_id))).json()
    assert body["full_name"] == "Fresh Name"
    assert len(profile_server.requests) == 1


def test_the_first_call_fills_the_cache_without_personal_data(
    me_client: TestClient,
    profile_server: ProfileServer,
    fake_redis: FakeRedis,
    make_access_token: MakeToken,
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, email="awa@example.test", full_name="Awa N.")
    me_client.get(URL, headers=_bearer(make_access_token(sub=user_id)))
    stored = fake_redis.data[profile_key(user_id)]
    assert json.loads(stored) == {"role": "marketer", "is_active": True}
    assert fake_redis.ttl(profile_key(user_id)) == 60


def test_me_still_works_when_redis_is_down(
    auth_settings: Settings,
    profile_server: ProfileServer,
    make_access_token: MakeToken,
) -> None:
    import redis

    from app.api.deps import get_profile_cache

    app = create_app(auth_settings)
    down = ProfileCache(
        FakeRedis(error=redis.exceptions.ConnectionError("down"))  # type: ignore[arg-type]
    )
    app.dependency_overrides[get_profile_cache] = lambda: down
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id)
    response = TestClient(app).get(URL, headers=_bearer(make_access_token(sub=user_id)))
    assert response.status_code == 200


def test_unknown_query_parameters_are_ignored(
    me_client: TestClient, profile_server: ProfileServer, make_access_token: MakeToken
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id)
    response = me_client.get(
        URL,
        params={"role": "admin", "user_id": str(uuid.uuid4())},
        headers=_bearer(make_access_token(sub=user_id)),
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(user_id)
    assert response.json()["role"] == "marketer"


# --- 401 --------------------------------------------------------------------------------------


def _assert_401(response: object, code: str) -> None:
    assert response.status_code == 401  # type: ignore[attr-defined]
    body = response.json()  # type: ignore[attr-defined]
    assert body["error"]["code"] == code
    assert body["error"]["request_id"]
    assert response.headers["WWW-Authenticate"] == "Bearer"  # type: ignore[attr-defined]


def test_no_header_is_unauthenticated(me_client: TestClient, profile_server: ProfileServer) -> None:
    response = me_client.get(URL)
    _assert_401(response, "UNAUTHENTICATED")
    assert response.json()["error"]["message"] == "Authentication is required. Please sign in."
    assert profile_server.requests == []


@pytest.mark.parametrize(
    "header", ["Basic dXNlcjpwYXNz", "Bearer", "Bearer ", "Token abc", "abc.def.ghi", "bearer"]
)
def test_a_header_that_is_not_a_bearer_token_is_unauthenticated(
    me_client: TestClient, header: str
) -> None:
    _assert_401(me_client.get(URL, headers={"Authorization": header}), "UNAUTHENTICATED")


def test_a_garbage_bearer_token_is_unauthenticated(me_client: TestClient) -> None:
    _assert_401(me_client.get(URL, headers=_bearer("garbage")), "UNAUTHENTICATED")


def test_an_expired_token_is_token_expired(
    me_client: TestClient, profile_server: ProfileServer, make_access_token: MakeToken
) -> None:
    response = me_client.get(URL, headers=_bearer(make_access_token(expires_in=-3600)))
    _assert_401(response, "TOKEN_EXPIRED")
    assert response.json()["error"]["message"] == "Your session has expired. Please sign in again."
    assert profile_server.requests == []


def test_a_token_signed_with_another_secret_is_unauthenticated(
    me_client: TestClient, profile_server: ProfileServer, make_access_token: MakeToken
) -> None:
    response = me_client.get(URL, headers=_bearer(make_access_token(key=OTHER_JWT_SECRET)))
    _assert_401(response, "UNAUTHENTICATED")
    assert profile_server.requests == []


@pytest.mark.parametrize("role", ["anon", "service_role"])
def test_the_anon_and_service_keys_are_unauthenticated_as_bearer(
    me_client: TestClient, profile_server: ProfileServer, make_access_token: MakeToken, role: str
) -> None:
    key = make_access_token(role=role, drop=("sub", "session_id"), expires_in=10 * 365 * 86400)
    _assert_401(me_client.get(URL, headers=_bearer(key)), "UNAUTHENTICATED")
    assert profile_server.requests == []


def test_alg_none_is_unauthenticated(me_client: TestClient, make_access_token: MakeToken) -> None:
    forged = make_access_token(key=None, algorithm="none")
    _assert_401(me_client.get(URL, headers=_bearer(forged)), "UNAUTHENTICATED")


def test_a_token_from_another_environment_is_unauthenticated(
    me_client: TestClient, make_access_token: MakeToken
) -> None:
    other = make_access_token(iss="https://production.example.test/auth/v1")
    _assert_401(me_client.get(URL, headers=_bearer(other)), "UNAUTHENTICATED")


# --- 403 --------------------------------------------------------------------------------------


@pytest.mark.parametrize("cached", [False, True])
def test_a_deactivated_or_missing_profile_is_account_disabled(
    me_client: TestClient,
    profile_server: ProfileServer,
    fake_redis: FakeRedis,
    make_access_token: MakeToken,
    cached: bool,
) -> None:
    user_id = uuid.uuid4()
    if cached:
        ProfileCache(fake_redis).set(user_id, CachedProfile("marketer", False))  # type: ignore[arg-type]
    response = me_client.get(URL, headers=_bearer(make_access_token(sub=user_id)))
    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "ACCOUNT_DISABLED"
    assert error["message"] == DISABLED
    assert error["request_id"]


def test_an_inactive_row_is_account_disabled(
    me_client: TestClient, profile_server: ProfileServer, make_access_token: MakeToken
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, is_active=False)
    response = me_client.get(URL, headers=_bearer(make_access_token(sub=user_id)))
    assert (response.status_code, response.json()["error"]["code"]) == (403, "ACCOUNT_DISABLED")


# --- 503 --------------------------------------------------------------------------------------


def test_a_database_failure_is_a_standard_503_without_technical_detail(
    me_client: TestClient, profile_server: ProfileServer, make_access_token: MakeToken
) -> None:
    profile_server.status = 500
    response = me_client.get(URL, headers=_bearer(make_access_token()))
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "SERVICE_UNAVAILABLE"
    assert "internal-detail" not in response.text
    assert "XX000" not in response.text


# --- cross-cutting ----------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", ["ok", "no_token", "expired", "disabled"])
def test_every_response_has_a_request_id_the_security_headers_and_no_store(
    me_client: TestClient,
    profile_server: ProfileServer,
    make_access_token: MakeToken,
    scenario: str,
) -> None:
    user_id = uuid.uuid4()
    if scenario == "ok":
        profile_server.add_profile(user_id)
    headers = {
        "ok": _bearer(make_access_token(sub=user_id)),
        "no_token": {},
        "expired": _bearer(make_access_token(expires_in=-3600)),
        "disabled": _bearer(make_access_token(sub=user_id)),
    }[scenario]
    response = me_client.get(URL, headers=headers)
    assert response.headers["X-Request-ID"]
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value
    assert response.headers["Cache-Control"] == "no-store"


def test_the_request_log_of_an_authenticated_call_carries_the_user_id_and_nothing_personal(
    me_client: TestClient,
    profile_server: ProfileServer,
    make_access_token: MakeToken,
    capsys: pytest.CaptureFixture[str],
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, email="private@example.test", full_name="Private Name")
    token = make_access_token(sub=user_id)
    me_client.get(URL, headers=_bearer(token))
    out = capsys.readouterr()
    lines = [json.loads(x) for x in out.out.splitlines() if x.startswith("{")]
    entry = next(e for e in lines if e["event"] == "request" and e["path"] == URL)
    assert entry["user_id"] == str(user_id)
    assert entry["status"] == 200
    assert token not in out.out
    assert "private@example.test" not in out.out
    assert "Private Name" not in out.out


def test_the_request_log_of_a_refused_call_has_no_user_id(
    me_client: TestClient, make_access_token: MakeToken, capsys: pytest.CaptureFixture[str]
) -> None:
    token = make_access_token(key=OTHER_JWT_SECRET)
    me_client.get(URL, headers=_bearer(token))
    out = capsys.readouterr().out
    entries = [json.loads(x) for x in out.splitlines() if x.startswith("{")]
    entry = next(e for e in entries if e["event"] == "request")
    assert entry["status"] == 401
    assert "user_id" not in entry
    assert token not in out


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_other_methods_are_405_invalid_request_with_the_allow_header(
    me_client: TestClient, make_access_token: MakeToken, method: str
) -> None:
    """API_SPEC 3.1: a method not allowed on an existing route is 405 INVALID_REQUEST + Allow."""
    response = getattr(me_client, method)(URL, headers=_bearer(make_access_token()))
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert response.json()["error"]["request_id"]
    assert "GET" in response.headers["Allow"]


def test_a_role_in_the_query_or_a_body_cannot_change_the_answer(
    me_client: TestClient, profile_server: ProfileServer, make_access_token: MakeToken
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, role="marketer")
    response = me_client.get(
        URL,
        params={"role": "admin"},
        headers={**_bearer(make_access_token(sub=user_id, extra={"user_role": "admin"}))},
    )
    assert response.json()["role"] == "marketer"


# --- OpenAPI ----------------------------------------------------------------------------------


def test_openapi_documents_the_bearer_scheme_and_the_me_response(client: TestClient) -> None:
    spec = client.get("/api/openapi.json").json()
    schemes = spec["components"]["securitySchemes"]
    assert "BearerAuth" in schemes
    assert schemes["BearerAuth"]["type"] == "http"
    assert schemes["BearerAuth"]["scheme"] == "bearer"
    assert "MeResponse" in spec["components"]["schemas"]
    operation = spec["paths"]["/api/v1/me"]["get"]
    ok = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert ok["$ref"].endswith("/MeResponse")
    assert {"BearerAuth": []} in operation["security"]
    assert set(spec["components"]["schemas"]["MeResponse"]["properties"]) == ME_FIELDS
    assert spec["components"]["schemas"]["MeResponse"].get("additionalProperties") is False
