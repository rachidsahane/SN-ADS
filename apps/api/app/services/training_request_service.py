"""Request a training: queue the version as the administrator, then start the job."""

import uuid
from collections.abc import Callable

from postgrest.exceptions import APIError
from supabase import Client

from app.api.errors import AppError, ErrorCode
from app.repositories import model_versions_repo as repo
from app.schemas.model import ModelVersionDetail
from app.schemas.user import CurrentUser
from app.services import audit_service, model_version_service
from app.services.backend import BACKEND_ERRORS, unavailable

ALREADY_RUNNING_MESSAGE = "A training run is already in progress."
UNIQUE_VIOLATION = "23505"


def request_training(
    user: CurrentUser, db: Client, *, start: Callable[[uuid.UUID], None]
) -> ModelVersionDetail:
    """409 when a training is already queued or running (unique index of the table)."""
    try:
        version_id = repo.insert_queued(db, user.id)
    except APIError as error:
        if error.code == UNIQUE_VIOLATION:
            raise AppError(
                ErrorCode.TRAINING_ALREADY_RUNNING, 409, ALREADY_RUNNING_MESSAGE
            ) from None
        raise unavailable(error, "request_training") from None
    except BACKEND_ERRORS as error:
        raise unavailable(error, "request_training") from None
    audit_service.record(
        db,
        action="model.training_requested",
        target_type="model_version",
        target_id=str(version_id),
        metadata={"data_scope": "all"},
    )
    start(version_id)
    return model_version_service.get_version(db, version_id)
