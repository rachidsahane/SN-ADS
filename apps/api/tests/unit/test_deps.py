"""api/deps.py: bearer extraction, current user, per-request user client, cache dependencies.

`require_admin` is not part of phase 2 (its first consumer, /api/v1/admin/*, is phase 3).
"""

import inspect
import uuid
from collections.abc import Callable

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import SecretStr

from app.api.deps import (
    get_bearer_token,
    get_cache_check,
    get_current_user,
    get_profile_cache,
    get_user_db,
)
from app.api.errors import AppError, ErrorCode
from app.config import Settings
from app.infra.profile_cache import CachedProfile, ProfileCache
from app.schemas.user import CurrentUser
from app.services.readiness_service import CacheCheck
from tests.support import UNREACHABLE_REDIS, FakeRedis

MakeToken = Callable[..., str]


def _credentials(value: str, scheme: str = "Bearer") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme=scheme, credentials=value)


# --- get_bearer_token -------------------------------------------------------------------------


def test_the_bearer_token_is_returned_as_is() -> None:
    assert get_bearer_token(_credentials("abc.def.ghi")) == "abc.def.ghi"


@pytest.mark.parametrize("credentials", [None, _credentials(""), _credentials("   ")])
def test_a_missing_or_blank_token_is_unauthenticated_in_the_standard_format(
    credentials: HTTPAuthorizationCredentials | None,
) -> None:
    with pytest.raises(AppError) as error:
        get_bearer_token(credentials)
    assert error.value.code is ErrorCode.UNAUTHENTICATED
    assert error.value.status == 401
    assert error.value.message == "Authentication is required. Please sign in."
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


# --- get_current_user -------------------------------------------------------------------------


def test_get_current_user_is_a_plain_function_so_that_fastapi_runs_it_in_the_thread_pool() -> None:
    assert not inspect.iscoroutinefunction(get_current_user)
    assert not inspect.iscoroutinefunction(get_user_db)
    assert not inspect.iscoroutinefunction(get_cache_check)


def test_get_current_user_returns_the_user_of_a_valid_token(
    auth_settings: Settings, make_access_token: MakeToken, fake_redis: FakeRedis
) -> None:
    user_id = uuid.uuid4()
    cache = ProfileCache(fake_redis)  # type: ignore[arg-type]
    cache.set(user_id, CachedProfile("admin", True))
    token = make_access_token(sub=user_id)
    user = get_current_user(token=token, settings=auth_settings, cache=cache)
    assert user == CurrentUser(id=user_id, role="admin", access_token=token)


def test_get_current_user_refuses_a_forged_token(
    auth_settings: Settings, make_access_token: MakeToken, fake_redis: FakeRedis
) -> None:
    cache = ProfileCache(fake_redis)  # type: ignore[arg-type]
    with pytest.raises(AppError) as error:
        get_current_user(
            token=make_access_token(role="service_role"), settings=auth_settings, cache=cache
        )
    assert error.value.code is ErrorCode.UNAUTHENTICATED


# --- get_user_db ------------------------------------------------------------------------------


def test_the_user_db_client_carries_the_user_token_and_never_the_service_key(
    auth_settings: Settings,
) -> None:
    user = CurrentUser(id=uuid.uuid4(), role="marketer", access_token="user-token-value")  # noqa: S106
    client = get_user_db(user=user, settings=auth_settings)
    headers = {name.lower(): value for name, value in client.postgrest.session.headers.items()}
    assert headers["authorization"] == "Bearer user-token-value"
    assert headers["apikey"] == auth_settings.supabase_anon_key.get_secret_value()
    assert auth_settings.supabase_service_role_key.get_secret_value() not in headers.values()


def test_two_requests_never_share_a_user_db_client(auth_settings: Settings) -> None:
    user = CurrentUser(id=uuid.uuid4(), role="marketer", access_token="user-token-value")  # noqa: S106
    assert get_user_db(user=user, settings=auth_settings) is not get_user_db(
        user=user, settings=auth_settings
    )


# --- cache dependencies -----------------------------------------------------------------------


def test_get_profile_cache_builds_a_profile_cache(settings: Settings) -> None:
    assert isinstance(get_profile_cache(settings=settings), ProfileCache)


def test_get_cache_check_probes_redis_for_real_and_never_raises(settings: Settings) -> None:
    down = settings.model_copy(update={"redis_url": SecretStr(UNREACHABLE_REDIS)})
    result = get_cache_check(settings=down)
    assert isinstance(result, CacheCheck)
    assert result.ok is False
    assert result.reason in {"timeout", "connection_error", "bad_response"}
