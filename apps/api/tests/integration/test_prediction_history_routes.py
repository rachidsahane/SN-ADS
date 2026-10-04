"""Saved predictions (API_SPEC 6.5): save, list, read, delete. The table is replaced by an
in-memory double that keeps the RLS rule (a row is visible to its owner only)."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_user_db
from app.config import Settings
from app.main import create_app
from app.ml.predictor import Predictor
from app.ml.training import train
from app.repositories import predictions_repo
from app.schemas.prediction import ModelRef
from app.schemas.user import CurrentUser
from app.services import prediction_service
from tests.data_factory import make_frame
from tests.unit.test_prediction import INPUT

pytestmark = pytest.mark.integration

MODEL = ModelRef(id=uuid.uuid4(), version=3)
ALICE = CurrentUser(id=uuid.uuid4(), role="marketer", access_token="alice")  # noqa: S106
BOB = CurrentUser(id=uuid.uuid4(), role="admin", access_token="bob")  # noqa: S106


class FakeDb:
    def __init__(self, user_id: uuid.UUID) -> None:
        self.user_id = user_id


@pytest.fixture(scope="module")
def predictor() -> Predictor:
    return Predictor(train(make_frame(), model_version_id=str(MODEL.id)))


@pytest.fixture
def world(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, predictor: Predictor
) -> Iterator[tuple[TestClient, dict[str, CurrentUser]]]:
    rows: list[dict[str, Any]] = []
    caller = {"user": ALICE}

    monkeypatch.setattr(prediction_service, "active_predictor", lambda _db, _s: (predictor, MODEL))

    def insert(db: FakeDb, row: dict[str, Any]) -> Any:
        assert row["user_id"] == str(db.user_id)  # the policy: you save as yourself
        saved = {
            **row,
            "id": str(uuid.uuid4()),
            "created_at": datetime.now(UTC).isoformat(),
            "level": row["results"]["performance"]["level"],
            "score": str(row["results"]["performance"]["score"]),  # the list reads it as text
            "campaign_channel": row["inputs"]["campaign_channel"],
            "campaign_type": row["inputs"]["campaign_type"],
            "model_versions": {"version": MODEL.version},
        }
        rows.append(saved)
        return saved

    def own(db: FakeDb) -> list[dict[str, Any]]:
        return [r for r in rows if r["user_id"] == str(db.user_id)]

    monkeypatch.setattr(predictions_repo, "insert", insert)
    monkeypatch.setattr(predictions_repo, "list_own", lambda db, limit: own(db)[::-1][:limit])
    monkeypatch.setattr(
        predictions_repo,
        "get",
        lambda db, pid: next((r for r in own(db) if r["id"] == str(pid)), None),
    )

    def delete(db: FakeDb, pid: uuid.UUID) -> bool:
        found = [r for r in own(db) if r["id"] == str(pid)]
        for row in found:
            rows.remove(row)
        return bool(found)

    monkeypatch.setattr(predictions_repo, "delete", delete)

    app = create_app(settings)
    app.dependency_overrides[get_current_user] = lambda: caller["user"]
    app.dependency_overrides[get_user_db] = lambda: FakeDb(caller["user"].id)
    client = TestClient(app)
    yield client, caller


def test_save_recomputes_on_the_server_then_read_back_identically(
    world: tuple[TestClient, dict[str, CurrentUser]],
) -> None:
    client, _ = world
    forged = {"name": "Spring push", "input": INPUT, "results": {"performance": {"score": 99}}}
    assert client.post("/api/v1/predictions", json=forged).status_code == 422  # extra="forbid"

    saved = client.post("/api/v1/predictions", json={"name": " Spring push ", "input": INPUT})
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["label"] == "Spring push" and body["id"] and body["created_at"]
    assert body["model_version"]["version"] == 3 and body["input"]["ad_spend"] == 5000

    listing = client.get("/api/v1/predictions").json()["items"]
    assert [(i["name"], i["model_version"], i["level"]) for i in listing] == [
        ("Spring push", 3, body["performance"]["level"])
    ]
    assert (listing[0]["campaign_channel"], listing[0]["campaign_type"]) == (
        "Social Media",
        "Awareness",
    )
    assert listing[0]["score"] == body["performance"]["score"]
    assert client.get(f"/api/v1/predictions/{body['id']}").json() == body


def test_a_name_is_required_and_bounded(world: tuple[TestClient, dict[str, CurrentUser]]) -> None:
    client, _ = world
    for name in ("", "   ", "x" * 101):
        response = client.post("/api/v1/predictions", json={"name": name, "input": INPUT})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_another_user_gets_404_even_an_administrator(
    world: tuple[TestClient, dict[str, CurrentUser]],
) -> None:
    client, caller = world
    saved = client.post("/api/v1/predictions", json={"name": "Mine", "input": INPUT}).json()
    caller["user"] = BOB
    assert client.get("/api/v1/predictions").json() == {"items": []}
    for response in (
        client.get(f"/api/v1/predictions/{saved['id']}"),
        client.delete(f"/api/v1/predictions/{saved['id']}"),
        client.get(f"/api/v1/predictions/{uuid.uuid4()}"),
    ):
        assert response.status_code == 404
        error = response.json()["error"]
        assert (error["code"], error["message"]) == ("NOT_FOUND", "Prediction not found.")
    caller["user"] = ALICE
    assert client.get(f"/api/v1/predictions/{saved['id']}").status_code == 200


def test_delete_removes_the_prediction(world: tuple[TestClient, dict[str, CurrentUser]]) -> None:
    client, _ = world
    saved = client.post("/api/v1/predictions", json={"name": "Temp", "input": INPUT}).json()
    assert client.delete(f"/api/v1/predictions/{saved['id']}").status_code == 204
    assert client.get(f"/api/v1/predictions/{saved['id']}").status_code == 404
    assert client.get("/api/v1/predictions").json() == {"items": []}
