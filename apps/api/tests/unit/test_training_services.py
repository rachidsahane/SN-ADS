"""services: training job, training request, activation, model registry (repositories replaced)."""

import uuid
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from postgrest.exceptions import APIError

from app.api.errors import AppError, ErrorCode
from app.config import Settings
from app.ml.bundle import load_bundle
from app.schemas.user import CurrentUser
from app.services import activation_service, model_registry, training_job, training_request_service
from tests.data_factory import make_frame

VERSION_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER = CurrentUser(
    id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
    role="admin",
    access_token="t",  # noqa: S106
)
DB: Any = object()


class FakeVersions:
    """Records the status changes the job makes."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, can_start: bool = True) -> None:
        self.events: list[tuple[str, Any]] = []
        self.audit: list[dict[str, Any]] = []
        repo = training_job.versions
        monkeypatch.setattr(repo, "mark_running", lambda _db, _id: can_start)
        monkeypatch.setattr(
            repo, "mark_succeeded", lambda _db, _id, fields: self.events.append(("ok", fields))
        )
        monkeypatch.setattr(
            repo, "mark_failed", lambda _db, _id, message: self.events.append(("failed", message))
        )
        monkeypatch.setattr(repo, "get_requester", lambda _db, _id: str(USER.id))
        monkeypatch.setattr(
            training_job.audit_repo,
            "insert_system_entry",
            lambda _db, entry: self.audit.append(entry),
        )


def test_a_successful_job_stores_the_files_and_the_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeVersions(monkeypatch)
    monkeypatch.setattr(training_job.dataset_repo, "load_frame", lambda _db: make_frame())
    training_job.run_training_job(VERSION_ID, service_db=DB, model_dir=tmp_path)
    ((status, fields),) = fake.events
    assert status == "ok"
    assert fields["artifact_prefix"] == f"versions/{VERSION_ID}/"
    assert fields["train_row_count"] + fields["holdout_row_count"] == 800
    assert fields["metrics"]["overall_reliability"] == "good"
    assert load_bundle(tmp_path / "versions" / str(VERSION_ID)).model_version_id == str(VERSION_ID)
    assert [e["action"] for e in fake.audit] == ["model.training_succeeded"]
    assert fake.audit[0]["actor_id"] == str(USER.id)


def test_not_enough_rows_fails_with_the_readable_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeVersions(monkeypatch)
    monkeypatch.setattr(training_job.dataset_repo, "load_frame", lambda _db: make_frame(60))
    training_job.run_training_job(VERSION_ID, service_db=DB, model_dir=tmp_path)
    assert fake.events == [
        ("failed", "Not enough data: at least 200 training rows and 50 test rows are required.")
    ]
    assert [e["action"] for e in fake.audit] == ["model.training_failed"]


def test_an_unexpected_error_fails_with_a_reference_and_no_technical_detail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeVersions(monkeypatch)

    def boom(_db: Any) -> pd.DataFrame:
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(training_job.dataset_repo, "load_frame", boom)
    training_job.run_training_job(VERSION_ID, service_db=DB, model_dir=tmp_path)
    ((status, message),) = fake.events
    assert status == "failed"
    assert message.startswith("Training failed unexpectedly. Reference: ")
    assert "secret" not in message


def test_a_version_that_is_not_queued_any_more_is_left_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeVersions(monkeypatch, can_start=False)
    training_job.run_training_job(VERSION_ID, service_db=DB, model_dir=tmp_path)
    assert fake.events == [] and fake.audit == []


def test_start_up_fails_the_leftover_versions(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(training_job, "get_service_client", lambda _s: DB)
    monkeypatch.setattr(
        training_job.versions, "fail_in_progress", lambda _db, message: seen.append(message) or 1
    )
    training_job.fail_interrupted_versions(settings)
    assert seen == ["Training was interrupted."]


def test_start_up_cleanup_never_blocks_the_start(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    def down(_s: Settings) -> Any:
        raise RuntimeError("database down")

    monkeypatch.setattr(training_job, "get_service_client", down)
    training_job.fail_interrupted_versions(settings)  # does not raise


# --- request -------------------------------------------------------------------------------------


def test_a_request_queues_the_version_logs_it_and_starts_the_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[uuid.UUID] = []
    logged: list[dict[str, Any]] = []
    service = training_request_service
    monkeypatch.setattr(service.repo, "insert_queued", lambda _db, _user: VERSION_ID)
    monkeypatch.setattr(service.audit_service, "record", lambda _db, **kw: logged.append(kw))
    monkeypatch.setattr(service.model_version_service, "get_version", lambda _db, i: str(i))
    result = service.request_training(USER, DB, start=started.append)
    assert result == str(VERSION_ID)
    assert started == [VERSION_ID]
    assert logged[0]["action"] == "model.training_requested"


def test_a_second_request_while_one_is_in_progress_is_a_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refused(_db: Any, _user: Any) -> uuid.UUID:
        raise APIError({"message": "duplicate key", "code": "23505", "details": "", "hint": ""})

    monkeypatch.setattr(training_request_service.repo, "insert_queued", refused)
    started: list[uuid.UUID] = []
    with pytest.raises(AppError) as error:
        training_request_service.request_training(USER, DB, start=started.append)
    assert (error.value.status, error.value.code) == (409, ErrorCode.TRAINING_ALREADY_RUNNING)
    assert error.value.message == "A training run is already in progress."
    assert started == []


# --- activation ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("database_message", "status", "code"),
    [
        ("NOT_FOUND", 404, ErrorCode.NOT_FOUND),
        ("MODEL_NOT_ACTIVATABLE", 409, ErrorCode.MODEL_NOT_ACTIVATABLE),
        ("FORBIDDEN", 403, ErrorCode.FORBIDDEN),
    ],
)
def test_the_activation_refusals_of_the_database_become_standard_errors(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    database_message: str,
    status: int,
    code: ErrorCode,
) -> None:
    def refused(_db: Any, _id: uuid.UUID) -> None:
        raise APIError({"message": database_message, "code": "P0001", "details": "", "hint": ""})

    monkeypatch.setattr(activation_service.repo, "activate", refused)
    with pytest.raises(AppError) as error:
        activation_service.activate(DB, VERSION_ID, settings=settings)
    assert (error.value.status, error.value.code) == (status, code)


def test_activation_logs_it_and_reloads_the_model(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    logged: list[dict[str, Any]] = []
    refreshed: list[bool] = []

    class Registry:
        def refresh(self, *, force: bool = False) -> None:
            refreshed.append(force)

    monkeypatch.setattr(activation_service.repo, "activate", lambda _db, _id: None)
    monkeypatch.setattr(
        activation_service.audit_service, "record", lambda _db, **kw: logged.append(kw)
    )
    monkeypatch.setattr(activation_service, "get_registry", lambda _s: Registry())
    monkeypatch.setattr(
        activation_service.model_version_service, "get_version", lambda _db, i: str(i)
    )
    assert activation_service.activate(DB, VERSION_ID, settings=settings) == str(VERSION_ID)
    assert logged[0]["action"] == "model.activated"
    assert refreshed == [True]


# --- registry ------------------------------------------------------------------------------------


def test_the_registry_loads_lazily_and_reloads_when_the_active_version_changes(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, tmp_path: Path
) -> None:
    from app.ml.bundle import save_bundle
    from app.ml.training import train  # local: keeps the module imports light

    ids = ["aaaaaaaa-0000-0000-0000-000000000001", "aaaaaaaa-0000-0000-0000-000000000002"]
    for version in ids:
        save_bundle(
            train(make_frame(400), model_version_id=version), tmp_path / "versions" / version
        )
    active: list[str | None] = [None]
    monkeypatch.setattr(model_registry, "get_service_client", lambda _s: DB)
    monkeypatch.setattr(model_registry.model_versions_repo, "active_id", lambda _db: active[0])
    registry = model_registry.ModelRegistry(
        settings.model_copy(update={"model_dir": str(tmp_path)})
    )
    assert registry.current() is None
    active[0] = ids[0]
    assert registry.current() is None  # the pointer is only checked every 30 s...
    registry.refresh(force=True)  # ...unless an activation forces it
    first = registry.current()
    assert first is not None and first.version_id == ids[0]
    active[0] = ids[1]
    registry.refresh(force=True)
    second = registry.current()
    assert second is not None and second.version_id == ids[1]
    active[0] = None
    registry.refresh(force=True)
    assert registry.current() is None
