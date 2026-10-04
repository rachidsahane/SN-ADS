"""Simulation and form reference routes (API_SPEC 6.3, 6.4): real app and routes, the caller
replaced by a known user, the active model replaced by a small trained one."""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_user_db
from app.config import Settings
from app.main import create_app
from app.ml.predictor import Predictor
from app.ml.training import train
from app.schemas.prediction import ModelRef
from app.schemas.user import CurrentUser
from app.services import prediction_service
from tests.data_factory import make_frame
from tests.unit.test_prediction import INPUT

pytestmark = pytest.mark.integration

USER = CurrentUser(id=uuid.uuid4(), role="marketer", access_token="user-token")  # noqa: S106
MODEL = ModelRef(id=uuid.uuid4(), version=2)


@pytest.fixture(scope="module")
def predictor() -> Predictor:
    return Predictor(train(make_frame(), model_version_id=str(MODEL.id)))


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_user_db] = lambda: object()
    yield TestClient(app)


@pytest.fixture
def active(monkeypatch: pytest.MonkeyPatch, predictor: Predictor) -> None:
    monkeypatch.setattr(prediction_service, "active_predictor", lambda _db, _s: (predictor, MODEL))


@pytest.fixture
def none_active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prediction_service, "active_predictor", lambda _db, _s: None)


def _error(response: Any, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    error: dict[str, Any] = response.json()["error"]
    assert error["code"] == code
    assert error["request_id"]
    return error


@pytest.mark.usefixtures("active")
def test_simulate_returns_the_documented_result(client: TestClient) -> None:
    response = client.post("/api/v1/predictions/simulate", json=INPUT)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "id", "created_at", "label", "model_version", "input", "predictions", "derived",
        "performance", "drivers", "recommendations", "warnings",
    }  # fmt: skip
    assert body["id"] is None and body["model_version"] == {"id": str(MODEL.id), "version": 2}
    assert body["input"]["ad_spend"] == 5000
    assert set(body["performance"]["notes"]) == {
        "click_through_rate",
        "estimated_leads",
        "estimated_cost_per_result",
    }
    assert len(body["drivers"]["website_visits"]) == 5


@pytest.mark.usefixtures("active")
def test_simulate_refuses_unknown_fields_and_out_of_bounds_values(client: TestClient) -> None:
    for bad in ({"colour": "red"}, {"ad_spend": 0}, {"age": 17}, {"campaign_type": "Radio"}):
        error = _error(
            client.post("/api/v1/predictions/simulate", json={**INPUT, **bad}),
            422,
            "VALIDATION_ERROR",
        )
        assert error["details"]


@pytest.mark.usefixtures("none_active")
def test_without_an_active_model_simulate_is_a_409_and_options_still_answer(
    client: TestClient,
) -> None:
    _error(client.post("/api/v1/predictions/simulate", json=INPUT), 409, "NO_ACTIVE_MODEL")
    _error(
        client.get(
            "/api/v1/reference/engagement-defaults",
            params={"campaign_channel": "Email", "campaign_type": "Conversion"},
        ),
        409,
        "NO_ACTIVE_MODEL",
    )
    options = client.get("/api/v1/reference/options").json()
    assert options["model_version"] is None and options["training_ranges"] == {}
    assert options["enums"]["gender"] == ["Male", "Female"]


@pytest.mark.usefixtures("active")
def test_options_and_engagement_defaults_come_from_the_active_model(client: TestClient) -> None:
    options = client.get("/api/v1/reference/options").json()
    assert options["model_version"]["version"] == 2
    assert options["limits"]["age"] == {"min": 18, "max": 100}
    assert set(options["training_ranges"]) >= {"ad_spend", "age"}
    assert "campaign_channel" in options["features_used"]
    defaults = client.get(
        "/api/v1/reference/engagement-defaults",
        params={"campaign_channel": "Email", "campaign_type": "Conversion"},
    ).json()
    assert defaults["basis"] == "channel_and_type"
    assert set(defaults) == {
        "pages_per_visit", "time_on_site", "social_shares", "email_opens", "email_clicks", "basis",
    }  # fmt: skip
    _error(
        client.get(
            "/api/v1/reference/engagement-defaults",
            params={"campaign_channel": "Radio", "campaign_type": "Conversion"},
        ),
        422,
        "VALIDATION_ERROR",
    )
