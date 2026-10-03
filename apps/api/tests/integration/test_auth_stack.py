"""Real sign-in, real token, real profile, real Redis (needs `make up`; hosts are service names).

Users are `phase2-<uuid>@example.test`, created through gotrue's admin API and always deleted.
"""

import json
import secrets
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
import redis
from fastapi.testclient import TestClient

from app.config import Settings
from app.infra.profile_cache import profile_key
from app.main import create_app

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("require_stack")]

TIMEOUT = 10.0


@pytest.fixture(scope="module")
def jwt_ready(stack_settings: Settings) -> None:
    """The api container must hold the stack's JWT secret and issuer (phase 2 compose wiring)."""
    if not stack_settings.supabase_jwt_secret.get_secret_value():
        pytest.fail("SUPABASE_JWT_SECRET is empty in the api container: run 'make env-local'")
    if not stack_settings.supabase_jwt_issuer:
        pytest.fail("SUPABASE_JWT_ISSUER is empty in the api container")


@pytest.fixture
def keys(stack_settings: Settings) -> dict[str, str]:
    return {
        "anon": stack_settings.supabase_anon_key.get_secret_value(),
        "service": stack_settings.supabase_service_role_key.get_secret_value(),
    }


@pytest.fixture
def http(stack_settings: Settings) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=stack_settings.supabase_url, timeout=TIMEOUT) as client:
        yield client


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
def api(stack_settings: Settings, jwt_ready: None) -> Iterator[TestClient]:
    with TestClient(create_app(stack_settings)) as client:
        yield client


def _headers(key: str, token: str | None = None) -> dict[str, str]:
    return {"apikey": key, "Authorization": f"Bearer {token or key}"}


@contextmanager
def _user(
    http: httpx.Client, keys: dict[str, str], cache: redis.Redis, **attributes: Any
) -> Iterator[dict[str, Any]]:
    password = f"Zx9-{secrets.token_hex(12)}"
    body = {
        "email": f"phase2-{uuid.uuid4()}@example.test",
        "password": password,
        "email_confirm": True,
        "user_metadata": {"full_name": "Phase Two"},
        **attributes,
    }
    created = http.post("/auth/v1/admin/users", headers=_headers(keys["service"]), json=body)
    assert created.status_code == 200, created.text
    user = created.json() | {"password": password}
    try:
        yield user
    finally:
        cache.delete(profile_key(uuid.UUID(user["id"])))
        http.delete(f"/auth/v1/admin/users/{user['id']}", headers=_headers(keys["service"]))


def _sign_in(http: httpx.Client, keys: dict[str, str], user: dict[str, Any]) -> str:
    response = http.post(
        "/auth/v1/token",
        params={"grant_type": "password"},
        headers=_headers(keys["anon"]),
        json={"email": user["email"], "password": user["password"]},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_a_real_gotrue_token_gives_the_real_profile(
    api: TestClient, http: httpx.Client, keys: dict[str, str], cache: redis.Redis
) -> None:
    with _user(http, keys, cache) as user:
        token = _sign_in(http, keys, user)
        response = api.get("/api/v1/me", headers=_bearer(token))
        assert response.status_code == 200, response.text
        assert response.json() == {
            "id": user["id"],
            "email": user["email"],
            "full_name": "Phase Two",
            "role": "marketer",
            "is_active": True,
        }


def test_the_profile_is_cached_for_at_most_a_minute_without_personal_data(
    api: TestClient, http: httpx.Client, keys: dict[str, str], cache: redis.Redis
) -> None:
    with _user(http, keys, cache) as user:
        token = _sign_in(http, keys, user)
        assert api.get("/api/v1/me", headers=_bearer(token)).status_code == 200
        key = profile_key(uuid.UUID(user["id"]))
        assert key == f"auth:profile:{user['id']}"
        assert 0 < cache.ttl(key) <= 60
        stored = cache.get(key)
        assert stored is not None
        assert json.loads(stored) == {"role": "marketer", "is_active": True}
        assert user["email"] not in stored
        assert "Phase Two" not in stored


def test_a_deactivated_user_is_refused_once_the_cache_entry_is_gone(
    api: TestClient, http: httpx.Client, keys: dict[str, str], cache: redis.Redis
) -> None:
    with _user(http, keys, cache) as user:
        token = _sign_in(http, keys, user)
        assert api.get("/api/v1/me", headers=_bearer(token)).status_code == 200
        patched = http.patch(
            "/rest/v1/profiles",
            headers=_headers(keys["service"]) | {"Prefer": "return=representation"},
            params={"id": f"eq.{user['id']}"},
            json={"is_active": False},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()[0]["is_active"] is False
        cache.delete(profile_key(uuid.UUID(user["id"])))  # what the phase 3 deactivation will do
        response = api.get("/api/v1/me", headers=_bearer(token))
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"
        assert response.json()["error"]["message"] == (
            "Your account has been deactivated. Contact an administrator."
        )


def test_a_token_signed_with_another_secret_is_refused(
    api: TestClient, stack_settings: Settings, make_access_token: Any
) -> None:
    forged = make_access_token(key="other-" + "x" * 40, iss=stack_settings.supabase_jwt_issuer)
    response = api.get("/api/v1/me", headers=_bearer(forged))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_a_token_signed_with_the_real_secret_but_for_nobody_is_refused(
    api: TestClient, stack_settings: Settings, make_access_token: Any
) -> None:
    """Right secret and issuer, but role anon: the shape of the anon key."""
    token = make_access_token(
        key=stack_settings.supabase_jwt_secret.get_secret_value(),
        iss=stack_settings.supabase_jwt_issuer,
        role="anon",
        drop=("sub",),
    )
    assert api.get("/api/v1/me", headers=_bearer(token)).status_code == 401


def test_the_real_service_key_is_refused_as_bearer(api: TestClient, keys: dict[str, str]) -> None:
    response = api.get("/api/v1/me", headers=_bearer(keys["service"]))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_the_real_anon_key_is_refused_as_bearer(api: TestClient, keys: dict[str, str]) -> None:
    assert api.get("/api/v1/me", headers=_bearer(keys["anon"])).status_code == 401


def test_a_valid_token_of_a_user_whose_row_was_deleted_is_account_disabled(
    api: TestClient, http: httpx.Client, keys: dict[str, str], cache: redis.Redis
) -> None:
    with _user(http, keys, cache) as user:
        token = _sign_in(http, keys, user)
    # The user is gone (profile deleted with it) but the token is still valid for a while.
    response = api.get("/api/v1/me", headers=_bearer(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"


def test_the_real_readiness_probe_reports_the_cache(api: TestClient) -> None:
    response = api.get("/api/ready")
    assert response.status_code == 200, response.text
    assert response.json()["checks"] == {"database": "ok", "cache": "ok"}
