"""Fixtures of the integration tests that need the real local stack (`make up`)."""

import httpx
import pytest

from app.config import Settings, load_settings


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
