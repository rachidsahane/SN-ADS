"""services/auth_service.py: from an access token to the current user, and the /me read.

The profile is read with the user's own token (RLS) from an in-process PostgREST; Redis is a fake.
"""

import json
import uuid
from collections.abc import Callable, Iterator

import pytest
import redis

from app.api.errors import AppError, ErrorCode
from app.config import Settings
from app.infra.observability import configure_logging
from app.infra.profile_cache import CachedProfile, ProfileCache, profile_key
from app.infra.request_context import bind_context, get_user_id, reset_context
from app.infra.supabase_clients import get_user_client
from app.schemas.user import CurrentUser, Profile
from app.services.auth_service import authenticate, get_me
from tests.support import UNREACHABLE_URL, FakeRedis, ProfileServer

MakeToken = Callable[..., str]
DISABLED_MESSAGE = "Your account has been deactivated. Contact an administrator."
UNAVAILABLE = "The service is temporarily unavailable. Please try again in a few minutes."


@pytest.fixture
def cache(fake_redis: FakeRedis) -> ProfileCache:
    return ProfileCache(fake_redis)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def request_scope() -> Iterator[None]:
    """A request context, like the middleware opens one (user id is attached to it)."""
    token = bind_context(request_id=str(uuid.uuid4()))
    yield
    reset_context(token)


def _refusal(token: str, settings: Settings, cache: ProfileCache) -> AppError:
    with pytest.raises(AppError) as error:
        authenticate(token, settings=settings, cache=cache)
    return error.value


# --- authenticate: cache ----------------------------------------------------------------------


def test_a_cache_hit_needs_no_database_call(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    make_access_token: MakeToken,
) -> None:
    user_id = uuid.uuid4()
    cache.set(user_id, CachedProfile("admin", True))
    token = make_access_token(sub=user_id)
    user = authenticate(token, settings=auth_settings, cache=cache)
    assert user == CurrentUser(id=user_id, role="admin", access_token=token)
    assert profile_server.requests == []


def test_a_cache_miss_reads_the_profile_with_the_user_token_then_fills_the_cache(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    fake_redis: FakeRedis,
    make_access_token: MakeToken,
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, role="admin")
    token = make_access_token(sub=user_id)
    user = authenticate(token, settings=auth_settings, cache=cache)
    assert (user.id, user.role, user.access_token) == (user_id, "admin", token)
    (request,) = profile_server.requests
    assert request.headers["authorization"] == f"Bearer {token}"
    assert request.query["id"] == [f"eq.{user_id}"]
    assert cache.get(user_id) == CachedProfile("admin", True)
    assert fake_redis.ttl(profile_key(user_id)) == 60


def test_the_cached_entry_holds_no_personal_data(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    fake_redis: FakeRedis,
    make_access_token: MakeToken,
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, email="private@example.test", full_name="Private Name")
    authenticate(make_access_token(sub=user_id), settings=auth_settings, cache=cache)
    stored = fake_redis.data[profile_key(user_id)]
    assert json.loads(stored) == {"role": "marketer", "is_active": True}
    assert "private" not in stored.lower()


def test_the_service_key_is_never_used_to_read_a_profile(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    make_access_token: MakeToken,
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id)
    authenticate(make_access_token(sub=user_id), settings=auth_settings, cache=cache)
    service = auth_settings.supabase_service_role_key.get_secret_value()
    for request in profile_server.requests:
        assert service not in request.headers.values()


# --- authenticate: deactivated or missing account (SEC-07) ------------------------------------


def test_a_missing_profile_is_account_disabled_not_404(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    make_access_token: MakeToken,
) -> None:
    """RLS returns no row for a deactivated user: 'not found' and 'inactive' look the same."""
    refusal = _refusal(make_access_token(), auth_settings, cache)
    assert refusal.code is ErrorCode.ACCOUNT_DISABLED
    assert refusal.status == 403
    assert refusal.message == DISABLED_MESSAGE


def test_an_inactive_profile_is_account_disabled(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    make_access_token: MakeToken,
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, is_active=False)
    refusal = _refusal(make_access_token(sub=user_id), auth_settings, cache)
    assert (refusal.code, refusal.status) == (ErrorCode.ACCOUNT_DISABLED, 403)
    assert refusal.message == DISABLED_MESSAGE


def test_an_inactive_profile_is_cached_and_refused_again_without_the_database(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    make_access_token: MakeToken,
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, is_active=False)
    token = make_access_token(sub=user_id)
    _refusal(token, auth_settings, cache)
    assert cache.get(user_id) == CachedProfile("marketer", False)
    calls_after_first = len(profile_server.requests)
    assert _refusal(token, auth_settings, cache).code is ErrorCode.ACCOUNT_DISABLED
    assert len(profile_server.requests) == calls_after_first


def test_a_missing_profile_is_not_cached(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    fake_redis: FakeRedis,
    make_access_token: MakeToken,
) -> None:
    user_id = uuid.uuid4()
    _refusal(make_access_token(sub=user_id), auth_settings, cache)
    assert cache.get(user_id) is None
    assert fake_redis.data == {}


def test_reactivation_is_seen_as_soon_as_the_entry_is_invalidated(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    make_access_token: MakeToken,
) -> None:
    user_id = uuid.uuid4()
    row = profile_server.add_profile(user_id, is_active=False)
    token = make_access_token(sub=user_id)
    _refusal(token, auth_settings, cache)
    row["is_active"] = True
    cache.invalidate(user_id)
    assert authenticate(token, settings=auth_settings, cache=cache).id == user_id


# --- authenticate: invalid token --------------------------------------------------------------


def test_an_invalid_token_is_refused_before_any_io(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    fake_redis: FakeRedis,
    make_access_token: MakeToken,
) -> None:
    refusal = _refusal(make_access_token(role="anon"), auth_settings, cache)
    assert refusal.code is ErrorCode.UNAUTHENTICATED
    expired = _refusal(make_access_token(expires_in=-3600), auth_settings, cache)
    assert expired.code is ErrorCode.TOKEN_EXPIRED
    assert profile_server.requests == []
    assert fake_redis.calls == []
    assert get_user_id() is None  # nothing is attached to the context for a token we refused


# --- authenticate: request context ------------------------------------------------------------


def test_the_user_id_is_attached_to_the_request_context(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    make_access_token: MakeToken,
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id)
    authenticate(make_access_token(sub=user_id), settings=auth_settings, cache=cache)
    assert get_user_id() == str(user_id)


def test_the_user_id_is_attached_before_the_profile_lookup(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    make_access_token: MakeToken,
) -> None:
    """So that the logs and the error report of a failing lookup already carry the user."""
    user_id = uuid.uuid4()
    profile_server.status = 500
    _refusal(make_access_token(sub=user_id), auth_settings, cache)
    assert get_user_id() == str(user_id)


# --- authenticate: degraded Redis -------------------------------------------------------------


@pytest.mark.parametrize(
    "error", [redis.exceptions.ConnectionError("down"), redis.exceptions.TimeoutError("slow")]
)
def test_a_redis_outage_falls_back_to_the_database_and_the_request_succeeds(
    auth_settings: Settings,
    profile_server: ProfileServer,
    fake_redis: FakeRedis,
    make_access_token: MakeToken,
    error: Exception,
) -> None:
    fake_redis.error = error
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, role="admin")
    user = authenticate(
        make_access_token(sub=user_id),
        settings=auth_settings,
        cache=ProfileCache(fake_redis),  # type: ignore[arg-type]
    )
    assert (user.id, user.role) == (user_id, "admin")
    assert len(profile_server.requests) == 1


def test_a_redis_outage_does_not_hide_a_deactivated_account(
    auth_settings: Settings,
    profile_server: ProfileServer,
    fake_redis: FakeRedis,
    make_access_token: MakeToken,
) -> None:
    fake_redis.error = redis.exceptions.ConnectionError("down")
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, is_active=False)
    refusal = _refusal(
        make_access_token(sub=user_id),
        auth_settings,
        ProfileCache(fake_redis),  # type: ignore[arg-type]
    )
    assert refusal.code is ErrorCode.ACCOUNT_DISABLED


# --- authenticate: database outage ------------------------------------------------------------


def _entries(out: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


def test_a_database_error_is_a_503_and_is_reported_without_personal_data(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    make_access_token: MakeToken,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(auth_settings)
    user_id = uuid.uuid4()
    profile_server.status = 500
    token = make_access_token(sub=user_id)
    refusal = _refusal(token, auth_settings, cache)
    assert (refusal.code, refusal.status) == (ErrorCode.SERVICE_UNAVAILABLE, 503)
    assert refusal.message == UNAVAILABLE
    out = capsys.readouterr().out
    reported = [e for e in _entries(out) if e["event"] == "unexpected_error"]
    assert reported, "the database failure must be reported with capture()"
    assert reported[0]["user_id"] == str(user_id)
    assert token not in out
    assert "internal-detail" not in refusal.message
    assert "someone@example.test" not in out


def test_an_unreachable_database_is_a_503(
    auth_settings: Settings, cache: ProfileCache, make_access_token: MakeToken
) -> None:
    unreachable = auth_settings.model_copy(update={"supabase_url": UNREACHABLE_URL})
    refusal = _refusal(make_access_token(), unreachable, cache)
    assert (refusal.code, refusal.status) == (ErrorCode.SERVICE_UNAVAILABLE, 503)


def test_nothing_is_cached_when_the_database_fails(
    auth_settings: Settings,
    profile_server: ProfileServer,
    cache: ProfileCache,
    fake_redis: FakeRedis,
    make_access_token: MakeToken,
) -> None:
    profile_server.status = 500
    _refusal(make_access_token(), auth_settings, cache)
    assert fake_redis.data == {}


# --- get_me -----------------------------------------------------------------------------------


def test_get_me_returns_the_full_profile_read_with_the_user_token(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(
        user_id, email="awa@example.test", full_name="Awa N.", role="marketer"
    )
    user = CurrentUser(id=user_id, role="marketer", access_token="user-token-value")  # noqa: S106
    profile = get_me(user, db=get_user_client(user.access_token, auth_settings))
    assert profile == Profile(
        id=user_id, email="awa@example.test", full_name="Awa N.", role="marketer", is_active=True
    )
    (request,) = profile_server.requests
    assert request.headers["authorization"] == "Bearer user-token-value"


def test_get_me_of_a_profile_that_vanished_is_account_disabled(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    user = CurrentUser(id=uuid.uuid4(), role="marketer", access_token="user-token-value")  # noqa: S106
    with pytest.raises(AppError) as error:
        get_me(user, db=get_user_client(user.access_token, auth_settings))
    assert (error.value.code, error.value.status) == (ErrorCode.ACCOUNT_DISABLED, 403)
