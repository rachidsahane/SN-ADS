import base64
import json
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app
from tests.support import (
    JWT_ISSUER,
    JWT_SECRET,
    WEB_APP_URL,
    FakeRedis,
    ProfileServer,
)

TEST_SUPABASE_URL = "http://supabase.test"
TEST_ANON_KEY = "test-only-anon"
TEST_SERVICE_KEY = "test-only-service"


@pytest.fixture
def settings() -> Settings:
    # Supabase values are explicit: otherwise they would come from the container environment.
    # Phase 2: the JWT secret/issuer, Redis address and site URL are explicit too (the Redis host
    # does not exist: a test that really needs Redis overrides the dependency).
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="local",
        service_name="api",
        app_release="test-sha",
        log_level="DEBUG",
        supabase_url=TEST_SUPABASE_URL,
        supabase_anon_key=TEST_ANON_KEY,
        supabase_service_role_key=TEST_SERVICE_KEY,
        supabase_jwt_secret=JWT_SECRET,
        supabase_jwt_issuer=JWT_ISSUER,
        redis_url="redis://redis.test:6379/0",
        web_app_url=WEB_APP_URL,
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@pytest.fixture
def make_jwt() -> Callable[[str], str]:
    """Build a fake, unsigned-looking JWT at run time.

    supabase-py 2.10 refuses a key that does not look like `a.b.c`. The value is assembled here
    instead of being a literal so that secret scanners never see a token-shaped constant.
    """

    def build(role: str) -> str:
        header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        payload = _b64url(json.dumps({"role": role, "iss": "test-only"}).encode())
        return f"{header}.{payload}.test-signature-not-a-secret"

    return build


# --- Phase 2: tokens, Redis and PostgREST doubles ---------------------------------------------

MakeAccessToken = Callable[..., str]


@pytest.fixture
def make_access_token() -> MakeAccessToken:
    """Sign an access token like gotrue does (HS256, aud/iss/role claims). Every claim can be
    changed or dropped to build a forged token. Nothing here is a real secret."""

    def build(  # noqa: PLR0913
        *,
        sub: uuid.UUID | str | None = None,
        role: str | None = "authenticated",
        aud: str | None = "authenticated",
        iss: str | None = JWT_ISSUER,
        expires_in: int | None = 3600,
        issued_in: int = 0,
        key: str | None = JWT_SECRET,
        algorithm: str = "HS256",
        drop: tuple[str, ...] = (),
        extra: dict[str, Any] | None = None,
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": str(sub) if sub is not None else str(uuid.uuid4()),
            "role": role,
            "aud": aud,
            "iss": iss,
            "iat": now + issued_in,
            "email": "someone@example.test",
            "session_id": str(uuid.uuid4()),
        }
        if expires_in is not None:
            claims["exp"] = now + expires_in
        claims.update(extra or {})
        payload = {k: v for k, v in claims.items() if k not in drop and v is not None}
        return jwt.encode(payload, key, algorithm=algorithm)

    return build


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def profile_server() -> Iterator[ProfileServer]:
    server = ProfileServer()
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def auth_settings(settings: Settings, profile_server: ProfileServer, make_jwt: Any) -> Settings:
    """Settings whose Supabase URL is the in-process PostgREST (keys must look like JWTs)."""
    return settings.model_copy(
        update={
            "supabase_url": profile_server.url,
            "supabase_anon_key": SecretStr(make_jwt("anon")),
            "supabase_service_role_key": SecretStr(make_jwt("service_role")),
        }
    )
