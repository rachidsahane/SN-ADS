"""Dataset summary, model versions and the active model (API_SPEC 6.5, 6.7, 6.8, simplified).

Same style as the other route tests: the real app and routes, the caller replaced by a known user,
and the repositories (the database) replaced by small doubles.
"""

import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.api.deps import get_current_user, get_user_db
from app.config import Settings
from app.main import create_app
from app.repositories import dataset_repo
from app.repositories import model_versions_repo as repo
from app.schemas.user import CurrentUser

pytestmark = pytest.mark.integration

ADMIN = CurrentUser(id=uuid.uuid4(), role="admin", access_token="admin-token")  # noqa: S106
MARKETER = CurrentUser(id=uuid.uuid4(), role="marketer", access_token="marketer-token")  # noqa: S106
VERSION_ID = str(uuid.uuid4())
TARGET_METRICS = {
    "mae": 0.07,
    "rmse": 0.08,
    "r2": -0.03,
    "baseline_mae": 0.07,
    "reliability": "low",
}
METRICS = {
    "click_through_rate": TARGET_METRICS,
    "conversion_rate": TARGET_METRICS,
    "website_visits": TARGET_METRICS,
    "overall_reliability": "low",
}
IMPORTANCE = {
    t: [{"field": "ad_spend", "share": 0.6}, {"field": "age", "share": 0.4}]
    for t in ("click_through_rate", "conversion_rate", "website_visits")
}


def _row(**changes: Any) -> dict[str, Any]:
    row = {
        "id": VERSION_ID,
        "version": 1,
        "status": "succeeded",
        "data_scope": "all",
        "is_active": False,
        "created_at": "2026-10-04T10:00:00+00:00",
        "finished_at": "2026-10-04T10:01:00+00:00",
        "requested_by": {"id": str(ADMIN.id), "full_name": "Boss Admin"},
        "metrics": METRICS,
        "global_importance": IMPORTANCE,
        "features_used": ["ad_spend", "age"],
        "train_row_count": 6400,
        "holdout_row_count": 1600,
        "error_message": None,
        "started_at": "2026-10-04T10:00:05+00:00",
        "activated_at": None,
    }
    return {**row, **changes}


Make = Callable[[CurrentUser], TestClient]


@pytest.fixture
def make_client(settings: Settings) -> Iterator[Make]:
    def make(user: CurrentUser) -> TestClient:
        app = create_app(settings)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_user_db] = lambda: object()
        return TestClient(app)

    yield make


def _error(response: Any, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    error: dict[str, Any] = response.json()["error"]
    assert error["code"] == code
    assert error["request_id"]
    return error


def test_dataset_summary_counts_the_rows(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    def count(_db: Any, *, source: str | None = None, holdout: bool | None = None) -> int:
        return {("seed", None): 8000, ("agency", None): 0, (None, True): 1603}[(source, holdout)]

    monkeypatch.setattr(dataset_repo, "count_rows", count)
    response = make_client(ADMIN).get("/api/v1/admin/dataset/summary")
    assert response.json() == {"seed_rows": 8000, "agency_rows": 0, "holdout_rows": 1603}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/admin/dataset/summary"),
        ("GET", "/api/v1/admin/model-versions"),
        ("POST", f"/api/v1/admin/model-versions/{VERSION_ID}/activate"),
    ],
)
def test_a_marketer_cannot_use_the_admin_routes(make_client: Make, method: str, path: str) -> None:
    _error(make_client(MARKETER).request(method, path, json={}), 403, "FORBIDDEN")


def test_the_list_and_the_detail_have_the_documented_shape(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(repo, "list_versions", lambda _db, limit: [_row(), _row(version=2)])
    monkeypatch.setattr(repo, "get_version", lambda _db, _id: _row())
    client = make_client(ADMIN)
    items = client.get("/api/v1/admin/model-versions").json()["items"]
    assert [i["version"] for i in items] == [1, 2]
    assert set(items[0]) == {
        "id", "version", "status", "data_scope", "is_active", "created_at", "finished_at",
        "requested_by",
    }  # fmt: skip
    detail = client.get(f"/api/v1/admin/model-versions/{VERSION_ID}").json()
    assert detail["metrics"]["overall_reliability"] == "low"
    assert detail["global_importance"]["website_visits"][0] == {"field": "ad_spend", "share": 0.6}
    assert detail["train_row_count"] == 6400


def test_an_unknown_or_malformed_version_is_a_404(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(repo, "get_version", lambda _db, _id: None)
    client = make_client(ADMIN)
    _error(client.get(f"/api/v1/admin/model-versions/{uuid.uuid4()}"), 404, "NOT_FOUND")
    _error(client.get("/api/v1/admin/model-versions/not-a-uuid"), 404, "NOT_FOUND")


def test_a_training_request_answers_202_and_runs_the_job_in_the_background(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[uuid.UUID] = []
    logged: list[str] = []
    monkeypatch.setattr(repo, "insert_queued", lambda _db, _user: uuid.UUID(VERSION_ID))
    monkeypatch.setattr(
        "app.api.admin.routes_models.run_in_background", lambda i, _s: ran.append(i)
    )
    monkeypatch.setattr(
        repo,
        "get_version",
        lambda _db, _id: _row(status="queued", metrics=None, global_importance=None),
    )
    monkeypatch.setattr(
        "app.repositories.audit_repo.log_action", lambda _db, **kw: logged.append(kw["action"])
    )
    response = make_client(ADMIN).post("/api/v1/admin/model-versions", json={"data_scope": "all"})
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "queued"
    assert ran == [uuid.UUID(VERSION_ID)]
    assert logged == ["model.training_requested"]


def test_a_second_training_is_a_409(make_client: Make, monkeypatch: pytest.MonkeyPatch) -> None:
    def refused(_db: Any, _user: Any) -> uuid.UUID:
        raise APIError({"message": "duplicate", "code": "23505", "details": "", "hint": ""})

    monkeypatch.setattr(repo, "insert_queued", refused)
    response = make_client(ADMIN).post("/api/v1/admin/model-versions", json={"data_scope": "all"})
    error = _error(response, 409, "TRAINING_ALREADY_RUNNING")
    assert error["message"] == "A training run is already in progress."


def test_a_training_request_refuses_unknown_fields(make_client: Make) -> None:
    response = make_client(ADMIN).post("/api/v1/admin/model-versions", json={"data_scope": "x"})
    _error(response, 422, "VALIDATION_ERROR")


def test_activation_returns_the_active_version(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(repo, "activate", lambda _db, _id: None)
    monkeypatch.setattr(repo, "get_version", lambda _db, _id: _row(is_active=True))
    monkeypatch.setattr("app.repositories.audit_repo.log_action", lambda _db, **_kw: None)
    monkeypatch.setattr("app.services.activation_service.get_registry", lambda _s: _NoRegistry())
    response = make_client(ADMIN).post(f"/api/v1/admin/model-versions/{VERSION_ID}/activate")
    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is True


class _NoRegistry:
    def refresh(self, *, force: bool = False) -> None:
        return None


def test_activating_a_failed_version_is_a_409(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refused(_db: Any, _id: uuid.UUID) -> None:
        raise APIError(
            {"message": "MODEL_NOT_ACTIVATABLE", "code": "P0001", "details": "", "hint": ""}
        )

    monkeypatch.setattr(repo, "activate", refused)
    response = make_client(ADMIN).post(f"/api/v1/admin/model-versions/{VERSION_ID}/activate")
    _error(response, 409, "MODEL_NOT_ACTIVATABLE")


def test_every_signed_in_user_reads_the_active_model(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    active = _row(is_active=True, activated_at="2026-10-04T10:02:00+00:00")
    monkeypatch.setattr(repo, "get_active", lambda _db: {k: active[k] for k in (
        "id", "version", "data_scope", "finished_at", "activated_at", "train_row_count",
        "holdout_row_count", "metrics", "global_importance")})  # fmt: skip
    body = make_client(MARKETER).get("/api/v1/model/active").json()
    assert body["version"] == 1
    assert body["reliability"] == "low"
    assert body["trained_at"] == "2026-10-04T10:01:00Z"
    assert body["metrics"]["click_through_rate"]["r2"] == -0.03
    assert body["global_importance"]["click_through_rate"][0]["field"] == "ad_spend"


def test_no_active_model_is_a_409(make_client: Make, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repo, "get_active", lambda _db: None)
    _error(make_client(MARKETER).get("/api/v1/model/active"), 409, "NO_ACTIVE_MODEL")
