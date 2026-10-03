"""api/deps.py: bearer extraction, current user, per-request user client, cache dependencies.

Phase 3 adds `require_admin` (403 FORBIDDEN unless an active administrator) and `get_page`.
"""

import inspect
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import SecretStr

from app.api.deps import (
    get_bearer_token,
    get_cache_check,
    get_current_user,
    get_page,
    get_profile_cache,
    get_user_db,
    require_admin,
)
from app.api.errors import AppError, ErrorCode
from app.config import Settings
from app.infra.observability import configure_logging
from app.infra.pagination import DEFAULT_PAGE_SIZE, Cursor, Page, encode_cursor
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


# --- phase 3: require_admin ---------------------------------------------------------------------

TARGET = uuid.uuid4()
CREATED_AT = datetime(2026, 10, 3, 14, 5, 0, 123456, tzinfo=UTC)


def _request(method: str = "PATCH") -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "method": method,
        "path": f"/api/v1/admin/users/{TARGET}",
        "path_params": {"user_id": str(TARGET)},
        "route": object(),
        "headers": [],
    }
    return Request(scope)


def test_require_admin_is_a_plain_function_so_that_fastapi_runs_it_in_the_thread_pool() -> None:
    assert not inspect.iscoroutinefunction(require_admin)
    assert not inspect.iscoroutinefunction(get_page)


def test_require_admin_lets_an_administrator_through() -> None:
    admin = CurrentUser(id=uuid.uuid4(), role="admin", access_token="admin-token-value")  # noqa: S106
    assert require_admin(request=_request(), user=admin) == admin


def test_require_admin_refuses_a_marketer_with_403_forbidden() -> None:
    marketer = CurrentUser(id=uuid.uuid4(), role="marketer", access_token="m-token-value")  # noqa: S106
    with pytest.raises(AppError) as error:
        require_admin(request=_request(), user=marketer)
    assert (error.value.code, error.value.status) == (ErrorCode.FORBIDDEN, 403)
    assert error.value.message == "You do not have permission to do this."


def test_a_refused_attempt_is_logged_once_with_the_user_and_the_route_and_no_token(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    token = "m-token-" + uuid.uuid4().hex
    marketer = CurrentUser(id=uuid.uuid4(), role="marketer", access_token=token)
    with pytest.raises(AppError):
        require_admin(request=_request(), user=marketer)
    out = capsys.readouterr().out
    entries = [json.loads(x) for x in out.splitlines() if x.startswith("{")]
    (denied,) = [e for e in entries if e["event"] == "admin_access_denied"]
    assert denied["level"] == "warning"
    assert denied["user_id"] == str(marketer.id)
    assert "/api/v1/admin/users/{user_id}" in denied.values()
    assert "PATCH" in denied.values()
    assert str(TARGET) not in out  # the route is logged as a template
    assert token not in out


def test_an_administrator_leaves_no_access_denied_log(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    admin = CurrentUser(id=uuid.uuid4(), role="admin", access_token="admin-token-value")  # noqa: S106
    require_admin(request=_request(), user=admin)
    assert "admin_access_denied" not in capsys.readouterr().out


# --- phase 3: get_page --------------------------------------------------------------------------


def test_get_page_defaults_to_50_items_and_no_cursor() -> None:
    assert get_page() == Page(limit=DEFAULT_PAGE_SIZE, after=None) == Page(limit=50, after=None)


def test_get_page_decodes_the_cursor() -> None:
    raw = encode_cursor(CREATED_AT, 42)
    page = get_page(limit=10, cursor=raw)
    assert page == Page(
        limit=10, after=Cursor(created_at="2026-10-03T14:05:00.123456+00:00", id="42")
    )


def test_get_page_refuses_an_undecodable_cursor_with_a_400() -> None:
    with pytest.raises(AppError) as error:
        get_page(limit=10, cursor="garbage")
    assert (error.value.code, error.value.status) == (ErrorCode.INVALID_REQUEST, 400)
    assert error.value.details[0].field == "cursor"
