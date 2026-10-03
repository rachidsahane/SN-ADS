import base64
import json
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TEST_SUPABASE_URL = "http://supabase.test"
TEST_ANON_KEY = "test-only-anon"
TEST_SERVICE_KEY = "test-only-service"


@pytest.fixture
def settings() -> Settings:
    # Supabase values are explicit: otherwise they would come from the container environment.
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="local",
        service_name="api",
        app_release="test-sha",
        log_level="DEBUG",
        supabase_url=TEST_SUPABASE_URL,
        supabase_anon_key=TEST_ANON_KEY,
        supabase_service_role_key=TEST_SERVICE_KEY,
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
