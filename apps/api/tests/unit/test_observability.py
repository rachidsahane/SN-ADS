import json
import logging
from typing import Any

import pytest

from app.config import Settings
from app.infra.observability import capture, configure_logging, get_logger
from app.infra.request_context import bind_context, reset_context


def lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    out = capsys.readouterr().out
    return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


def test_logs_are_json_with_service_environment_and_release(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    get_logger("test").info("hello", answer=42)
    (entry,) = lines(capsys)
    assert entry["event"] == "hello"
    assert entry["answer"] == 42
    assert entry["level"] == "info"
    assert (entry["service"], entry["environment"], entry["release"]) == (
        "api",
        "local",
        "test-sha",
    )
    assert entry["timestamp"].endswith("Z")


def test_logs_carry_request_and_user_ids(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    token = bind_context(request_id="req-1", user_id="user-1")
    get_logger("test").info("inside")
    reset_context(token)
    (entry,) = lines(capsys)
    assert (entry["request_id"], entry["user_id"]) == ("req-1", "user-1")


def test_sensitive_values_are_redacted_at_any_depth(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    get_logger("test").info("x", email="a@b.c", nested={"Authorization": "Bearer abc", "ok": 1})
    (entry,) = lines(capsys)
    assert entry["email"] == "[redacted]"
    assert entry["nested"] == {"Authorization": "[redacted]", "ok": 1}


def test_capture_returns_a_reference_and_logs_the_error_with_context(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    try:
        raise ValueError("boom")
    except ValueError as exc:
        reference = capture(
            exc, route="/api/x", model_version_id="mv-1", authorization="Bearer abc"
        )
    (entry,) = lines(capsys)
    assert len(reference) == 32
    assert entry["event"] == "unexpected_error"
    assert entry["event_id"] == reference
    assert entry["error_type"] == "ValueError"
    assert entry["route"] == "/api/x"
    assert entry["model_version_id"] == "mv-1"
    assert entry["authorization"] == "[redacted]"
    assert "ValueError: boom" in entry["exception"]
    assert entry["level"] == "error"


def test_configuring_twice_does_not_duplicate_log_lines(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    configure_logging(settings)
    get_logger("test").info("once")
    assert len(lines(capsys)) == 1


def test_standard_library_and_uvicorn_logs_are_json_too(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    logging.getLogger("uvicorn.error").warning("from uvicorn")
    (entry,) = lines(capsys)
    assert entry["event"] == "from uvicorn"
    assert entry["service"] == "api"


def test_uvicorn_access_log_is_silenced_in_favour_of_the_request_log(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    logging.getLogger("uvicorn.access").info("GET / 200")
    assert lines(capsys) == []


def test_http_client_libraries_do_not_log_urls_at_info(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    logging.getLogger("httpx").info("HTTP Request: GET http://x/?email=eq.a@b.c")
    assert lines(capsys) == []
