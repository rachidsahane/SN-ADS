"""infra/profile_cache.py: role and activity of a user, 60 s, key auth:profile:<uuid>.

Only `role` and `is_active` are stored: Upstash is a third party (no e-mail, no name).
"""

import json
import uuid

import pytest
import redis

from app.config import Settings
from app.infra.observability import configure_logging
from app.infra.profile_cache import (
    PROFILE_TTL_SECONDS,
    CachedProfile,
    ProfileCache,
    profile_key,
)
from tests.support import FakeRedis

USER_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")


@pytest.fixture
def cache(fake_redis: FakeRedis) -> ProfileCache:
    return ProfileCache(fake_redis)  # type: ignore[arg-type]


def _down() -> FakeRedis:
    return FakeRedis(error=redis.exceptions.ConnectionError("redis is down"))


def test_the_ttl_is_sixty_seconds() -> None:
    assert PROFILE_TTL_SECONDS == 60


def test_the_key_format() -> None:
    assert profile_key(USER_ID) == "auth:profile:11111111-2222-3333-4444-555555555555"


def test_a_miss_returns_none(cache: ProfileCache) -> None:
    assert cache.get(USER_ID) is None


@pytest.mark.parametrize(
    "profile",
    [
        CachedProfile("marketer", True),
        CachedProfile("admin", True),
        CachedProfile("marketer", False),
    ],
)
def test_set_then_get_round_trips(cache: ProfileCache, profile: CachedProfile) -> None:
    cache.set(USER_ID, profile)
    assert cache.get(USER_ID) == profile


def test_cached_profiles_are_immutable() -> None:
    profile = CachedProfile("admin", True)
    with pytest.raises(AttributeError):
        profile.role = "marketer"  # type: ignore[misc]


def test_the_entry_expires_after_sixty_seconds_by_default(
    cache: ProfileCache, fake_redis: FakeRedis
) -> None:
    cache.set(USER_ID, CachedProfile("marketer", True))
    assert fake_redis.ttl(profile_key(USER_ID)) == 60


def test_the_ttl_can_be_shortened(cache: ProfileCache, fake_redis: FakeRedis) -> None:
    cache.set(USER_ID, CachedProfile("marketer", True), ttl_seconds=5)
    assert fake_redis.ttl(profile_key(USER_ID)) == 5


def test_the_stored_json_has_exactly_role_and_is_active(
    cache: ProfileCache, fake_redis: FakeRedis
) -> None:
    cache.set(USER_ID, CachedProfile("admin", False))
    raw = fake_redis.data[profile_key(USER_ID)]
    assert json.loads(raw) == {"role": "admin", "is_active": False}


def test_nothing_personal_is_stored(cache: ProfileCache, fake_redis: FakeRedis) -> None:
    cache.set(USER_ID, CachedProfile("marketer", True))
    raw = fake_redis.data[profile_key(USER_ID)]
    assert "@" not in raw
    assert "email" not in raw
    assert "name" not in raw


def test_an_inactive_profile_is_cached_too(cache: ProfileCache) -> None:
    cache.set(USER_ID, CachedProfile("marketer", False))
    assert cache.get(USER_ID) == CachedProfile("marketer", False)


def test_users_do_not_share_entries(cache: ProfileCache) -> None:
    other = uuid.uuid4()
    cache.set(USER_ID, CachedProfile("admin", True))
    cache.set(other, CachedProfile("marketer", True))
    assert cache.get(USER_ID) == CachedProfile("admin", True)
    assert cache.get(other) == CachedProfile("marketer", True)


@pytest.mark.parametrize(
    "garbage",
    [
        "not json",
        "",
        "null",
        "[]",
        '"marketer"',
        "{}",
        '{"role": "marketer"}',
        '{"is_active": true}',
        '{"role": "superuser", "is_active": true}',
        '{"role": "admin", "is_active": "yes"}',
        '{"role": 1, "is_active": true}',
    ],
)
def test_a_corrupt_or_unexpected_entry_is_a_miss(
    cache: ProfileCache, fake_redis: FakeRedis, garbage: str
) -> None:
    fake_redis.data[profile_key(USER_ID)] = garbage
    assert cache.get(USER_ID) is None


# --- invalidation -----------------------------------------------------------------------------


def test_invalidate_deletes_the_entry(cache: ProfileCache, fake_redis: FakeRedis) -> None:
    cache.set(USER_ID, CachedProfile("marketer", True))
    cache.invalidate(USER_ID)
    assert cache.get(USER_ID) is None
    assert profile_key(USER_ID) not in fake_redis.data


def test_invalidating_a_missing_entry_is_fine(cache: ProfileCache) -> None:
    cache.invalidate(USER_ID)


def test_invalidate_only_touches_one_user(cache: ProfileCache) -> None:
    other = uuid.uuid4()
    cache.set(USER_ID, CachedProfile("marketer", True))
    cache.set(other, CachedProfile("marketer", True))
    cache.invalidate(USER_ID)
    assert cache.get(other) is not None


def test_invalidate_propagates_a_redis_failure() -> None:
    """A deactivation must know that the stale entry could not be removed (SEC-07)."""
    with pytest.raises(redis.exceptions.RedisError):
        ProfileCache(_down()).invalidate(USER_ID)  # type: ignore[arg-type]


# --- degraded mode ----------------------------------------------------------------------------


def test_a_redis_failure_on_get_is_a_miss_with_a_warning(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    assert ProfileCache(_down()).get(USER_ID) is None  # type: ignore[arg-type]
    entries = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]
    entry = next(e for e in entries if e["event"] == "profile_cache_unavailable")
    assert entry["level"] == "warning"


def test_a_redis_failure_on_set_is_swallowed_with_a_warning(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    ProfileCache(_down()).set(USER_ID, CachedProfile("marketer", True))  # type: ignore[arg-type]
    entries = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]
    assert any(e["event"] == "profile_cache_unavailable" for e in entries)


@pytest.mark.parametrize(
    "error",
    [redis.exceptions.TimeoutError("slow"), redis.exceptions.ConnectionError("down")],
)
def test_timeouts_and_connection_errors_are_both_degraded_not_raised(
    cache: ProfileCache, fake_redis: FakeRedis, error: Exception
) -> None:
    fake_redis.error = error
    assert cache.get(USER_ID) is None
    cache.set(USER_ID, CachedProfile("marketer", True))
