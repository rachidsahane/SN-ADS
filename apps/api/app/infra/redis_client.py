"""The only place that builds Redis clients (Upstash in the cloud, a container locally).

`redis` is imported under `app/infra/` only. The cache is an accelerator, never a dependency of a
request: callers treat `CACHE_ERRORS` as "the cache is unavailable".
"""

from functools import lru_cache
from typing import Final

import redis

from app.config import Settings, get_settings

CONNECT_TIMEOUT_SECONDS: Final = 2
READ_TIMEOUT_SECONDS: Final = 5
# Everything a Redis call can raise when the server is down, slow or misconfigured (a malformed URL
# raises ValueError). Exposed so that other layers do not import `redis` to catch it.
CACHE_ERRORS: Final = (redis.RedisError, OSError, ValueError)


@lru_cache(maxsize=1)
def get_redis_client(settings: Settings | None = None) -> redis.Redis:
    """One lazily connected client: building it opens no connection."""
    settings = settings or get_settings()
    return redis.Redis.from_url(
        settings.redis_url.get_secret_value(),
        socket_connect_timeout=CONNECT_TIMEOUT_SECONDS,
        socket_timeout=READ_TIMEOUT_SECONDS,
        decode_responses=True,
    )


def ping(settings: Settings | None = None, *, timeout: float = 2.0) -> None:
    """Probe Redis with a short-lived client (own timeouts, always closed). Raises on failure."""
    settings = settings or get_settings()
    client = redis.Redis.from_url(
        settings.redis_url.get_secret_value(),
        socket_connect_timeout=timeout,
        socket_timeout=timeout,
        decode_responses=True,
    )
    try:
        if not client.ping():
            raise redis.ResponseError("unexpected answer to PING")
    finally:
        client.close()  # type: ignore[no-untyped-call]


def classify_cache_error(error: BaseException) -> str:
    """`timeout`, `connection_error` or `bad_response`. The message is unused."""
    if isinstance(error, redis.TimeoutError | TimeoutError):
        return "timeout"
    if isinstance(error, redis.ConnectionError | OSError | ValueError):
        return "connection_error"
    return "bad_response"
