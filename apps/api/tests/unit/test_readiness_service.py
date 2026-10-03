"""services/readiness_service.py: database probe through the public schema_version() function."""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
import redis
from pydantic import SecretStr

from app.config import Settings
from app.infra.observability import configure_logging
from app.services.readiness_service import CacheCheck, DatabaseCheck, check_cache, check_database

Handler = Callable[[httpx.Request], httpx.Response]
SCHEMA_VERSION = "20261003120000"


def _transport(handler: Handler, seen: list[httpx.Request] | None = None) -> httpx.MockTransport:
    def record(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return handler(request)

    return httpx.MockTransport(record)


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=SCHEMA_VERSION)


def test_database_is_ready_when_the_function_returns_a_migration_number(
    settings: Settings,
) -> None:
    result = check_database(settings, transport=_transport(_ok))
    assert result == DatabaseCheck(ok=True, schema_version=SCHEMA_VERSION, reason=None)


def test_the_probe_calls_the_rpc_with_the_anon_key_only(settings: Settings) -> None:
    seen: list[httpx.Request] = []
    check_database(settings, transport=_transport(_ok, seen))
    (request,) = seen
    assert request.method == "POST"
    assert str(request.url) == "http://supabase.test/rest/v1/rpc/schema_version"
    assert request.headers["apikey"] == "test-only-anon"
    assert request.headers["authorization"] == "Bearer test-only-anon"
    assert json.loads(request.content) == {}


def test_the_service_key_is_never_sent_whatever_the_outcome(settings: Settings) -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200 if len(seen) % 2 else 503, json=SCHEMA_VERSION)

    for _ in range(2):
        check_database(settings, transport=_transport(answer, seen))
    assert len(seen) == 2
    for request in seen:
        assert all("test-only-service" not in value for value in request.headers.values())
        assert b"test-only-service" not in request.content
        assert "test-only-service" not in str(request.url)


@pytest.mark.parametrize(
    "payload",
    [
        "abc",
        "",
        123,
        {},
        None,
        "2026100312000",
        "202610031200001",
        "2026100312000a",
        [SCHEMA_VERSION],
    ],
)
def test_an_invalid_payload_means_not_ready(settings: Settings, payload: Any) -> None:
    result = check_database(
        settings, transport=_transport(lambda _: httpx.Response(200, json=payload))
    )
    assert result == DatabaseCheck(ok=False, schema_version=None, reason="bad_payload")


def test_a_body_that_is_not_json_means_not_ready(settings: Settings) -> None:
    result = check_database(
        settings, transport=_transport(lambda _: httpx.Response(200, content=b"<html>oops"))
    )
    assert result == DatabaseCheck(ok=False, schema_version=None, reason="bad_payload")


@pytest.mark.parametrize("status", [401, 404, 500, 503])
def test_an_http_error_is_reported_with_its_status(settings: Settings, status: int) -> None:
    # 404 is PostgREST's PGRST202: the migrations are not applied yet.
    result = check_database(
        settings, transport=_transport(lambda _: httpx.Response(status, json={"code": "x"}))
    )
    assert result == DatabaseCheck(ok=False, schema_version=None, reason=f"http_{status}")


def test_a_connection_failure_is_reported(settings: Settings) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    result = check_database(settings, transport=_transport(refuse))
    assert result == DatabaseCheck(ok=False, schema_version=None, reason="connection_error")


def test_an_unusable_database_url_fails_closed_instead_of_raising(settings: Settings) -> None:
    # Settings accepts "http://host:abc"; httpx raises InvalidURL, which is not an HTTPError.
    # The probe must still answer "not ready" and never leak a 500.
    broken = settings.model_copy(update={"supabase_url": "http://host:abc"})
    result = check_database(broken, transport=_transport(_ok))
    assert result == DatabaseCheck(ok=False, schema_version=None, reason="connection_error")


def test_a_timeout_is_reported(settings: Settings) -> None:
    def hang(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    result = check_database(settings, transport=_transport(hang))
    assert result == DatabaseCheck(ok=False, schema_version=None, reason="timeout")


def test_a_missing_anon_key_fails_closed_without_any_request(settings: Settings) -> None:
    seen: list[httpx.Request] = []
    empty = settings.model_copy(update={"supabase_anon_key": SecretStr("")})
    result = check_database(empty, transport=_transport(_ok, seen))
    assert result == DatabaseCheck(ok=False, schema_version=None, reason="missing_key")
    assert seen == []


def test_the_failure_is_logged_without_key_url_or_response_body(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    body = {"message": "internal-detail-must-not-leak"}
    check_database(settings, transport=_transport(lambda _: httpx.Response(503, json=body)))
    out = capsys.readouterr().out
    entries = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    entry = next(e for e in entries if e["event"] == "readiness_failed")
    assert (entry["level"], entry["check"], entry["reason"]) == ("warning", "database", "http_503")
    assert "test-only-anon" not in out
    assert "test-only-service" not in out
    assert "supabase.test" not in out
    assert "internal-detail-must-not-leak" not in out


def test_a_healthy_probe_logs_nothing_at_warning_level(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    check_database(settings, transport=_transport(_ok))
    assert "readiness_failed" not in capsys.readouterr().out


# --- Phase 2: cache (Redis) probe ---

REDIS_PASSWORD = "pw-" + "q" * 12


def _redis_settings(settings: Settings) -> Settings:
    url = f"redis://:{REDIS_PASSWORD}@redis-host.test:6379/0"
    return settings.model_copy(update={"redis_url": SecretStr(url)})


def _failing(error: Exception) -> Callable[..., None]:
    def pinger(*_: object, **__: object) -> None:
        raise error

    return pinger


def _healthy(*_: object, **__: object) -> None:
    return None


def test_the_cache_is_ready_when_redis_answers_the_ping(settings: Settings) -> None:
    assert check_cache(settings, pinger=_healthy) == CacheCheck(ok=True, reason=None)


def test_the_probe_pings_with_the_settings(settings: Settings) -> None:
    seen: list[tuple[object, ...]] = []

    def pinger(*args: object, **_: object) -> None:
        seen.append(args)

    check_cache(settings, pinger=pinger)
    assert seen == [(settings,)]


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (redis.exceptions.TimeoutError("slow"), "timeout"),
        (redis.exceptions.ConnectionError("refused"), "connection_error"),
        (redis.exceptions.ResponseError("-ERR bad"), "bad_response"),
    ],
)
def test_a_cache_failure_gives_its_reason(
    settings: Settings, error: Exception, reason: str
) -> None:
    assert check_cache(settings, pinger=_failing(error)) == CacheCheck(ok=False, reason=reason)


def test_the_real_probe_fails_closed_when_redis_is_unreachable(settings: Settings) -> None:
    unreachable = settings.model_copy(update={"redis_url": SecretStr("redis://127.0.0.1:9/0")})
    result = check_cache(unreachable)
    assert result.ok is False
    assert result.reason in {"timeout", "connection_error"}


def test_the_cache_failure_is_logged_without_password_or_address(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    configured = _redis_settings(settings)
    check_cache(configured, pinger=_failing(redis.exceptions.ConnectionError(REDIS_PASSWORD)))
    out = capsys.readouterr().out
    entries = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    entry = next(e for e in entries if e["event"] == "readiness_failed")
    assert (entry["level"], entry["check"], entry["reason"]) == (
        "warning",
        "cache",
        "connection_error",
    )
    assert REDIS_PASSWORD not in out
    assert "redis-host.test" not in out


def test_a_healthy_cache_probe_logs_nothing_at_warning_level(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    check_cache(settings, pinger=_healthy)
    assert "readiness_failed" not in capsys.readouterr().out
