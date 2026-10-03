import json
import uuid
from typing import Any

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from app.api.errors import AppError, ErrorCode
from app.api.middleware import SECURITY_HEADERS
from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.integration


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ad_spend: float = Field(gt=0)


def _probe_router() -> APIRouter:
    router = APIRouter()

    @router.post("/api/v1/_probe")
    async def probe(payload: Payload) -> dict[str, float]:
        return {"ad_spend": payload.ad_spend}

    @router.get("/api/v1/_boom")
    async def boom() -> None:
        raise RuntimeError("database password is hunter2")

    @router.get("/api/v1/_app_error")
    async def app_error() -> None:
        raise AppError(ErrorCode.NO_ACTIVE_MODEL, 409, "No active model.")

    @router.get("/api/v1/_unavailable")
    async def unavailable() -> None:
        raise AppError(ErrorCode.SERVICE_UNAVAILABLE, 503, "Down.")

    @router.get("/api/v1/_item/{item_id}")
    async def item(item_id: uuid.UUID) -> str:
        return str(item_id)

    return router


@pytest.fixture
def probe_client(settings: Settings) -> TestClient:
    app = create_app(settings)
    app.include_router(_probe_router())
    return TestClient(app)


def test_health_returns_ok_and_the_release(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "release": "test-sha"}


def test_request_id_from_the_client_is_echoed(client: TestClient) -> None:
    sent = str(uuid.uuid4())
    assert client.get("/api/health", headers={"X-Request-ID": sent}).headers["X-Request-ID"] == sent


def test_invalid_request_id_is_replaced_by_a_generated_uuid(client: TestClient) -> None:
    received = client.get("/api/health", headers={"X-Request-ID": "not a uuid"}).headers[
        "X-Request-ID"
    ]
    assert received != "not a uuid"
    assert uuid.UUID(received)


def test_security_headers_are_present_on_success_and_on_errors(client: TestClient) -> None:
    for path in ("/api/health", "/api/nope"):
        response = client.get(path)
        for name, value in SECURITY_HEADERS.items():
            assert response.headers[name] == value


def test_unknown_route_uses_the_standard_error_format(client: TestClient) -> None:
    response = client.get("/api/nope")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["details"] == []
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_wrong_method_is_refused_in_the_standard_format(client: TestClient) -> None:
    response = client.post("/api/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_validation_error_follows_the_spec_example(probe_client: TestClient) -> None:
    response = probe_client.post("/api/v1/_probe", json={"ad_spend": -1})
    assert response.status_code == 422
    assert response.json()["error"]["details"] == [
        {"field": "ad_spend", "issue": "must_be_greater_than",
         "message": "Ad spend must be greater than 0."}
    ]  # fmt: skip


def test_unknown_field_is_refused(probe_client: TestClient) -> None:
    response = probe_client.post("/api/v1/_probe", json={"ad_spend": 1, "score": 9})
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["issue"] == "unknown_field"


def test_malformed_json_is_a_400(probe_client: TestClient) -> None:
    response = probe_client.post(
        "/api/v1/_probe", content=b"{nope", headers={"Content-Type": "application/json"}
    )
    assert (response.status_code, response.json()["error"]["code"]) == (400, "INVALID_REQUEST")


def test_invalid_path_identifier_is_a_404(probe_client: TestClient) -> None:
    response = probe_client.get("/api/v1/_item/not-a-uuid")
    assert (response.status_code, response.json()["error"]["code"]) == (404, "NOT_FOUND")


def test_app_error_is_rendered_with_its_code_and_status(probe_client: TestClient) -> None:
    response = probe_client.get("/api/v1/_app_error")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NO_ACTIVE_MODEL"


def test_unexpected_exception_returns_500_without_technical_detail(
    probe_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    response = probe_client.get("/api/v1/_boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "hunter2" not in response.text
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    entries = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]
    captured = next(e for e in entries if e["event"] == "unexpected_error")
    assert captured["route"] == "/api/v1/_boom"
    assert captured["request_id"] == response.headers["X-Request-ID"]


def test_service_unavailable_app_error_is_also_reported(
    probe_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    assert probe_client.get("/api/v1/_unavailable").status_code == 503
    assert "unexpected_error" in capsys.readouterr().out


def test_json_body_over_64_kb_is_refused_by_content_length(probe_client: TestClient) -> None:
    response = probe_client.post(
        "/api/v1/_probe", content=b"x" * 70_000, headers={"Content-Type": "application/json"}
    )
    assert (response.status_code, response.json()["error"]["code"]) == (413, "PAYLOAD_TOO_LARGE")


def test_streamed_json_body_over_64_kb_is_refused(probe_client: TestClient) -> None:
    def chunks() -> Any:
        yield b'{"ad_spend": 1, "pad": "'
        yield b"x" * 70_000
        yield b'"}'

    response = probe_client.post(
        "/api/v1/_probe", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert (response.status_code, response.json()["error"]["code"]) == (413, "PAYLOAD_TOO_LARGE")


def test_unsupported_content_type_is_a_415(probe_client: TestClient) -> None:
    response = probe_client.post(
        "/api/v1/_probe", content=b"ad_spend=1", headers={"Content-Type": "text/plain"}
    )
    assert (response.status_code, response.json()["error"]["code"]) == (
        415, "UNSUPPORTED_MEDIA_TYPE",
    )  # fmt: skip


def test_openapi_is_served_outside_production(client: TestClient) -> None:
    assert client.get("/api/openapi.json").status_code == 200


def test_openapi_is_disabled_in_production(settings: Settings) -> None:
    production = settings.model_copy(update={"app_env": "production"})
    assert TestClient(create_app(production)).get("/api/openapi.json").status_code == 404


def test_each_request_is_logged_as_json(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    client.get("/api/nope")
    entries = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]
    entry = next(e for e in entries if e["event"] == "request")
    assert (entry["method"], entry["path"], entry["status"]) == ("GET", "/api/nope", 404)
    assert "duration_ms" in entry
    assert entry["request_id"]


def test_request_log_uses_the_route_template_not_the_raw_path(
    probe_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    item_id = uuid.uuid4()
    probe_client.get(f"/api/v1/_item/{item_id}")
    entries = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]
    entry = next(e for e in entries if e["event"] == "request")
    assert entry["route"] == "/api/v1/_item/{item_id}"
    assert entry["path"] == f"/api/v1/_item/{item_id}"


def test_trailing_slash_is_not_redirected(client: TestClient) -> None:
    response = client.get("/api/health/", follow_redirects=False)
    assert response.status_code == 404
    assert "location" not in response.headers
