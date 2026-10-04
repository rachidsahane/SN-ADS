"""/api/v1/admin/model-versions: list, train, read and activate (API_SPEC 6.8, simplified)."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, ConfigDict
from supabase import Client

from app.api.deps import get_current_user, get_settings, get_user_db
from app.config import Settings
from app.schemas.common import ErrorResponse
from app.schemas.model import DataScope, ModelVersionDetail, ModelVersionList
from app.schemas.user import CurrentUser
from app.services import activation_service, model_version_service, training_request_service
from app.services.training_job import run_in_background

router = APIRouter(prefix="/model-versions", tags=["admin-models"])

_COMMON: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired token."},
    403: {"model": ErrorResponse, "description": "The caller is not an active administrator."},
    503: {"model": ErrorResponse, "description": "The database is unavailable."},
}
_NOT_FOUND = {"model": ErrorResponse, "description": "Model version not found."}


class TrainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_scope: DataScope = "all"


@router.get("", response_model=ModelVersionList, responses=_COMMON, summary="List versions")
def list_versions(db: Annotated[Client, Depends(get_user_db)]) -> ModelVersionList:
    return model_version_service.list_versions(db)


@router.post(
    "",
    status_code=202,
    response_model=ModelVersionDetail,
    responses={
        **_COMMON,
        409: {"model": ErrorResponse, "description": "A training run is already in progress."},
        422: {"model": ErrorResponse, "description": "Not enough agency data (agency_only)."},
    },
    summary="Train a new version",
)
def train_version(
    body: TrainRequest,
    background: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_user_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ModelVersionDetail:
    def start(version_id: uuid.UUID) -> None:
        background.add_task(run_in_background, version_id, settings, body.data_scope)

    return training_request_service.request_training(
        user, db, data_scope=body.data_scope, start=start
    )


@router.get(
    "/{version_id}",
    response_model=ModelVersionDetail,
    responses={**_COMMON, 404: _NOT_FOUND},
    summary="Read a version",
)
def read_version(
    version_id: uuid.UUID, db: Annotated[Client, Depends(get_user_db)]
) -> ModelVersionDetail:
    return model_version_service.get_version(db, version_id)


@router.post(
    "/{version_id}/activate",
    response_model=ModelVersionDetail,
    responses={
        **_COMMON,
        404: _NOT_FOUND,
        409: {"model": ErrorResponse, "description": "The version did not succeed."},
    },
    summary="Activate a version",
)
def activate_version(
    version_id: uuid.UUID,
    db: Annotated[Client, Depends(get_user_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ModelVersionDetail:
    return activation_service.activate(db, version_id, settings=settings)
