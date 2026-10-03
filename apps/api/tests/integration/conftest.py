"""Fixtures of the integration tests that need the real local stack (`make up`)."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_profile_cache, get_user_db
from app.config import Settings, load_settings
from app.infra.profile_cache import CachedProfile
from app.main import create_app
from tests.support import AdminWorld, ProfileServer, make_admin_world


@pytest.fixture(scope="session")
def stack_settings() -> Settings:
    """Settings of the api container: it already points at supabase-kong and holds the keys."""
    return load_settings()


@pytest.fixture(scope="session")
def require_stack(stack_settings: Settings) -> None:
    """Fail loudly (never skip: CLAUDE 4.4) when the Supabase stack is not up."""
    anon = stack_settings.supabase_anon_key.get_secret_value()
    problem = "Local Supabase stack is not reachable: run 'make up' first"
    if not anon:
        pytest.fail(f"{problem} (SUPABASE_ANON_KEY is empty: run 'make env-local' first)")
    try:
        response = httpx.get(
            f"{stack_settings.supabase_url}/auth/v1/health",
            headers={"apikey": anon, "Authorization": f"Bearer {anon}"},
            timeout=5.0,
        )
    except httpx.HTTPError:
        pytest.fail(problem)
    if response.status_code != 200:
        pytest.fail(problem)


# --- Phase 3: the admin routes without the stack ----------------------------------------------


@dataclass
class AdminEnv:
    """The real app, real token verification, and doubles behind it: the profile cache is a fake
    Redis, the caller's database client is `FakeUserDb`, the service client is `FakeServiceClient`.
    `headers_for` signs a token and primes the 60 s profile cache the way a first call would."""

    client: TestClient
    world: AdminWorld
    profile_server: ProfileServer
    make_access_token: Callable[..., str]

    def headers_for(
        self, user_id: str | uuid.UUID, *, role: str = "admin", is_active: bool = True
    ) -> dict[str, str]:
        profile = CachedProfile("admin" if role == "admin" else "marketer", is_active)
        self.world.cache.set(uuid.UUID(str(user_id)), profile)
        return {"Authorization": f"Bearer {self.make_access_token(sub=user_id)}"}

    @property
    def admin_headers(self) -> dict[str, str]:
        return self.headers_for(self.world.admin.id)


@pytest.fixture
def admin_env(
    monkeypatch: pytest.MonkeyPatch,
    auth_settings: Settings,
    profile_server: ProfileServer,
    make_access_token: Callable[..., str],
) -> AdminEnv:
    world = make_admin_world()
    monkeypatch.setattr(
        "app.services.user_admin_service.get_service_client", lambda *_a, **_k: world.service
    )
    app = create_app(auth_settings)
    app.dependency_overrides[get_profile_cache] = lambda: world.cache
    app.dependency_overrides[get_user_db] = lambda: world.db
    return AdminEnv(TestClient(app), world, profile_server, make_access_token)
