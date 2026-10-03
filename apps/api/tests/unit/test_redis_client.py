"""infra/redis_client.py: one lazily connected client with short timeouts, and a probe."""

from collections.abc import Iterator

import pytest
import redis
from pydantic import SecretStr

from app.config import Settings
from app.infra.redis_client import get_redis_client, ping
from tests.support import UNREACHABLE_REDIS


@pytest.fixture(autouse=True)
def fresh_client_cache() -> Iterator[None]:
    get_redis_client.cache_clear()  # type: ignore[attr-defined]
    yield
    get_redis_client.cache_clear()  # type: ignore[attr-defined]


def _kwargs(client: redis.Redis) -> dict[str, object]:
    return dict(client.connection_pool.connection_kwargs)


def test_the_client_has_short_timeouts_and_returns_text(settings: Settings) -> None:
    kwargs = _kwargs(get_redis_client(settings))
    assert kwargs["socket_connect_timeout"] == 2
    assert kwargs["socket_timeout"] == 5
    assert kwargs["decode_responses"] is True


def test_the_client_targets_the_configured_url(settings: Settings) -> None:
    custom = settings.model_copy(update={"redis_url": SecretStr("redis://cache.test:6390/3")})
    kwargs = _kwargs(get_redis_client(custom))
    assert (kwargs["host"], kwargs["port"], kwargs["db"]) == ("cache.test", 6390, 3)


def test_building_the_client_opens_no_connection(settings: Settings) -> None:
    # redis.test does not exist: a connection attempt would raise or hang.
    assert get_redis_client(settings) is not None


def test_the_client_is_cached(settings: Settings) -> None:
    assert get_redis_client(settings) is get_redis_client(settings)


def test_ping_failure_propagates_the_redis_error(settings: Settings) -> None:
    refused = settings.model_copy(update={"redis_url": SecretStr(UNREACHABLE_REDIS)})
    with pytest.raises(redis.exceptions.RedisError):
        ping(refused, timeout=0.5)


def test_ping_uses_its_own_short_lived_client_and_closes_it(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[object] = []
    original_close = redis.Redis.close

    def spy_close(self: redis.Redis) -> None:
        closed.append(self)
        original_close(self)

    monkeypatch.setattr(redis.Redis, "close", spy_close)
    refused = settings.model_copy(update={"redis_url": SecretStr(UNREACHABLE_REDIS)})
    with pytest.raises(redis.exceptions.RedisError):
        ping(refused, timeout=0.5)
    assert len(closed) == 1  # closed even though the probe failed
    assert closed[0] is not get_redis_client(refused)


def test_ping_applies_the_given_timeout_to_connect_and_read(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict[str, object]] = []
    original = redis.Redis.from_url

    def spy(url: str, **kwargs: object) -> redis.Redis:
        seen.append(kwargs)
        return original(url, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(redis.Redis, "from_url", staticmethod(spy))
    refused = settings.model_copy(update={"redis_url": SecretStr(UNREACHABLE_REDIS)})
    with pytest.raises(redis.exceptions.RedisError):
        ping(refused, timeout=1.5)
    (kwargs,) = seen
    assert kwargs["socket_connect_timeout"] == 1.5
    assert kwargs["socket_timeout"] == 1.5


def test_ping_default_timeout_is_two_seconds(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict[str, object]] = []
    original = redis.Redis.from_url

    def spy(url: str, **kwargs: object) -> redis.Redis:
        seen.append(kwargs)
        return original(url, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(redis.Redis, "from_url", staticmethod(spy))
    refused = settings.model_copy(update={"redis_url": SecretStr(UNREACHABLE_REDIS)})
    with pytest.raises(redis.exceptions.RedisError):
        ping(refused)
    assert seen[0]["socket_connect_timeout"] == 2.0
    assert seen[0]["socket_timeout"] == 2.0
