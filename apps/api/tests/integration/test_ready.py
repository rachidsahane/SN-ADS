"""GET /api/ready (API_SPEC 6.1). No stack needed: the database check is overridden."""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.deps import get_database_check
from app.api.middleware import SECURITY_HEADERS
from app.config import Settings
from app.main import create_app
from app.services.readiness_service import DatabaseCheck

pytestmark = pytest.mark.integration

READY = DatabaseCheck(ok=True, schema_version="20261003120000", reason=None)
NOT_READY = DatabaseCheck(ok=False, schema_version=None, reason="connection_error")


@pytest.fixture
def ready_client(client: TestClient) -> TestClient:
    client.app.dependency_overrides[get_database_check] = lambda: READY  # type: ignore[attr-defined]
    return client


@pytest.fixture
def broken_client(client: TestClient) -> TestClient:
    client.app.dependency_overrides[get_database_check] = lambda: NOT_READY  # type: ignore[attr-defined]
    return client


def _log_entries(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    return [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]


def test_ready_returns_200_with_the_exact_documented_body(ready_client: TestClient) -> None:
    response = ready_client.get("/api/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok"},
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
        "checks": {"database": "error"},
        "release": "test-sha",
    }


def test_ready_needs_no_token(ready_client: TestClient) -> None:
    assert "authorization" not in ready_client.headers
    assert ready_client.get("/api/ready").status_code == 200


@pytest.mark.parametrize("failing", [False, True])
def test_ready_carries_a_request_id_and_the_security_headers(
    client: TestClient, failing: bool
) -> None:
    check = NOT_READY if failing else READY
    client.app.dependency_overrides[get_database_check] = lambda: check  # type: ignore[attr-defined]
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


def test_health_stays_200_while_the_database_is_down(broken_client: TestClient) -> None:
    assert broken_client.get("/api/ready").status_code == 503
    response = broken_client.get("/api/health")
    assert (response.status_code, response.json()["status"]) == (200, "ok")


def test_the_real_dependency_fails_closed_without_an_anon_key(settings: Settings) -> None:
    no_key = settings.model_copy(update={"supabase_anon_key": SecretStr("")})
    response = TestClient(create_app(no_key)).get("/api/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "error"}
    assert "schema_version" not in response.json()


def test_the_real_dependency_answers_503_when_the_database_host_is_unreachable(
    settings: Settings,
) -> None:
    unreachable = settings.model_copy(update={"supabase_url": "http://127.0.0.1:9"})
    response = TestClient(create_app(unreachable)).get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "error"},
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
