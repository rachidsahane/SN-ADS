"""Training of one version, run in the api process by a FastAPI background task (demo: no queue,
no separate worker). Closed list of service-key holders (ARCHITECTURE 2.5): this module reads the
dataset and writes the version status with the service client."""

import uuid
from pathlib import Path
from typing import Any

from supabase import Client

from app.config import Settings
from app.infra.observability import capture, get_logger
from app.infra.supabase_clients import get_service_client
from app.ml.bundle import save_bundle
from app.ml.training import NotEnoughDataError, train
from app.repositories import audit_repo, dataset_repo
from app.repositories import model_versions_repo as versions

INTERRUPTED_MESSAGE = "Training was interrupted."
UNEXPECTED_MESSAGE = "Training failed unexpectedly. Reference: {reference}"


def _audit(db: Client, version_id: uuid.UUID, action: str, metadata: dict[str, Any]) -> None:
    """Best effort: the version status is already final, a failed entry is only reported."""
    try:
        entry = {
            "actor_id": versions.get_requester(db, version_id),
            "action": action,
            "target_type": "model_version",
            "target_id": str(version_id),
            "metadata": metadata,
        }
        audit_repo.insert_system_entry(db, entry)
    except Exception as error:
        capture(error, operation="audit_write", action=action, model_version_id=str(version_id))


def run_training_job(version_id: uuid.UUID, *, service_db: Client, model_dir: Path) -> None:
    """queued -> running -> succeeded | failed. Never raises: a failure becomes `failed`."""
    try:
        if not versions.mark_running(service_db, version_id):
            return  # already handled
        frame = dataset_repo.load_frame(service_db)
        bundle = train(frame, model_version_id=str(version_id))
        prefix = f"versions/{version_id}/"
        save_bundle(bundle, model_dir / "versions" / str(version_id))
        versions.mark_succeeded(
            service_db,
            version_id,
            {
                "metrics": bundle.metrics,
                "global_importance": bundle.global_importance,
                "features_used": bundle.spec.features_used,
                "train_row_count": int((~frame["is_holdout"]).sum()),
                "holdout_row_count": int(frame["is_holdout"].sum()),
                "artifact_prefix": prefix,
            },
        )
        _audit(service_db, version_id, "model.training_succeeded", {})
    except NotEnoughDataError as error:
        _fail(service_db, version_id, str(error))
    except Exception as error:
        reference = capture(error, operation="training_job", model_version_id=str(version_id))
        _fail(service_db, version_id, UNEXPECTED_MESSAGE.format(reference=reference))


def _fail(service_db: Client, version_id: uuid.UUID, message: str) -> None:
    try:
        versions.mark_failed(service_db, version_id, message)
    except Exception as error:
        capture(error, operation="mark_failed", model_version_id=str(version_id))
        return
    _audit(service_db, version_id, "model.training_failed", {"reason": message})


def run_in_background(version_id: uuid.UUID, settings: Settings) -> None:
    """Entry point of the background task."""
    run_training_job(
        version_id, service_db=get_service_client(settings), model_dir=Path(settings.model_dir)
    )


def fail_interrupted_versions(settings: Settings) -> None:
    """At start-up no training can still be running: fail the leftovers."""
    try:
        count = versions.fail_in_progress(get_service_client(settings), INTERRUPTED_MESSAGE)
    except Exception as error:
        get_logger("app.training").warning(
            "startup_cleanup_skipped", error_type=type(error).__name__
        )
        return
    if count:
        get_logger("app.training").warning("training_interrupted", count=count)
