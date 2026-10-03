"""GET /api/ready (API_SPEC 6.1). No stack needed: the database check is overridden."""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.deps import get_cache_check, get_database_check
from app.api.middleware import SECURITY_HEADERS
from app.config import Settings
from app.main import create_app
from app.services.readiness_service import CacheCheck, DatabaseCheck

pytestmark = pytest.mark.integration

READY = DatabaseCheck(ok=True, schema_version="20261003120000", reason=None)
NOT_READY = DatabaseCheck(ok=False, schema_version=None, reason="connection_error")
CACHE_OK = CacheCheck(ok=True, reason=None)
CACHE_DOWN = CacheCheck(ok=False, reason="connection_error")


def _override(client: TestClient, database: DatabaseCheck, cache: CacheCheck) -> TestClient:
    overrides = client.app.dependency_overrides  # type: ignore[attr-defined]
    overrides[get_database_check] = lambda: database
    overrides[get_cache_check] = lambda: cache
    return client


@pytest.fixture
def ready_client(client: TestClient) -> TestClient:
    return _override(client, READY, CACHE_OK)


@pytest.fixture
def broken_client(client: TestClient) -> TestClient:
    """Database down, cache fine."""
    return _override(client, NOT_READY, CACHE_OK)


@pytest.fixture
def cache_down_client(client: TestClient) -> TestClient:
    return _override(client, READY, CACHE_DOWN)


def _log_entries(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    return [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]


def test_ready_returns_200_with_the_exact_documented_body(ready_client: TestClient) -> None:
    response = ready_client.get("/api/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "cache": "ok"},
        "schema_version": "20261003120000",
        "release": "test-sha",
    }


def test_ready_returns_503_with_the_same_schema_and_no_error_body(
    broken_client: TestClient,
) -> None:
    response = broken_client.get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "error", "cache": "ok"},
        "release": "test-sha",
    }


def test_ready_returns_503_when_only_the_cache_is_down(cache_down_client: TestClient) -> None:
    response = cache_down_client.get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "ok", "cache": "error"},
        "release": "test-sha",
    }
    assert "schema_version" not in response.json()


def test_ready_shows_both_failures_when_both_are_down(client: TestClient) -> None:
    _override(client, NOT_READY, CACHE_DOWN)
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "error", "cache": "error"},
        "release": "test-sha",
    }


def test_a_cache_failure_leaks_no_detail_in_the_body(cache_down_client: TestClient) -> None:
    assert "connection_error" not in cache_down_client.get("/api/ready").text


def test_ready_needs_no_token(ready_client: TestClient) -> None:
    assert "authorization" not in ready_client.headers
    assert ready_client.get("/api/ready").status_code == 200


@pytest.mark.parametrize("failing", [False, True])
def test_ready_carries_a_request_id_and_the_security_headers(
    client: TestClient, failing: bool
) -> None:
    _override(client, NOT_READY if failing else READY, CACHE_DOWN if failing else CACHE_OK)
    response = client.get("/api/ready")
    assert response.headers["X-Request-ID"]
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value


def test_ready_refuses_other_methods_in_the_standard_error_format(
    ready_client: TestClient,
) -> None:
    response = ready_client.post("/api/ready")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_a_successful_probe_is_logged_at_debug_level_only(
    ready_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    ready_client.get("/api/ready")
    entry = next(e for e in _log_entries(capsys) if e["event"] == "request")
    assert (entry["path"], entry["status"], entry["level"]) == ("/api/ready", 200, "debug")


def test_a_failed_probe_is_logged_above_debug_level(
    broken_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    # The request middleware logs every 5xx as an error (QUIET_PATHS only silences successes).
    broken_client.get("/api/ready")
    entry = next(e for e in _log_entries(capsys) if e["event"] == "request")
    assert (entry["path"], entry["status"]) == ("/api/ready", 503)
    assert entry["level"] != "debug"


def test_a_cache_failure_is_logged_above_debug_level(
    cache_down_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    cache_down_client.get("/api/ready")
    entry = next(e for e in _log_entries(capsys) if e["event"] == "request")
    assert (entry["path"], entry["status"]) == ("/api/ready", 503)
    assert entry["level"] != "debug"


def test_health_stays_200_while_the_database_is_down(broken_client: TestClient) -> None:
    assert broken_client.get("/api/ready").status_code == 503
    response = broken_client.get("/api/health")
    assert (response.status_code, response.json()["status"]) == (200, "ok")


def test_health_stays_200_while_the_cache_is_down(cache_down_client: TestClient) -> None:
    assert cache_down_client.get("/api/ready").status_code == 503
    response = cache_down_client.get("/api/health")
    assert (response.status_code, response.json()["status"]) == (200, "ok")


def _with_healthy_cache(settings: Settings) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_cache_check] = lambda: CACHE_OK
    return TestClient(app)


def test_the_real_dependency_fails_closed_without_an_anon_key(settings: Settings) -> None:
    no_key = settings.model_copy(update={"supabase_anon_key": SecretStr("")})
    response = _with_healthy_cache(no_key).get("/api/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "error", "cache": "ok"}
    assert "schema_version" not in response.json()


def test_the_real_dependency_answers_503_when_the_database_host_is_unreachable(
    settings: Settings,
) -> None:
    unreachable = settings.model_copy(update={"supabase_url": "http://127.0.0.1:9"})
    response = _with_healthy_cache(unreachable).get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "error", "cache": "ok"},
        "release": "test-sha",
    }


def test_the_real_cache_dependency_answers_503_when_redis_is_unreachable(
    settings: Settings,
) -> None:
    app = create_app(settings.model_copy(update={"redis_url": SecretStr("redis://127.0.0.1:9/0")}))
    app.dependency_overrides[get_database_check] = lambda: READY
    response = TestClient(app).get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "ok", "cache": "error"},
        "release": "test-sha",
    }


def test_openapi_documents_the_ready_response(client: TestClient) -> None:
    spec = client.get("/api/openapi.json").json()
    assert {"ReadyResponse", "ReadyChecks"} <= set(spec["components"]["schemas"])
    responses = spec["paths"]["/api/ready"]["get"]["responses"]
    assert responses["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ReadyResponse"
    )
    assert responses["503"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ReadyResponse"
    )
