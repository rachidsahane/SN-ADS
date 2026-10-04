"""Reads of the model versions: the list, one version, the active model."""

import uuid

from supabase import Client

from app.api.errors import AppError, ErrorCode
from app.repositories import model_versions_repo as repo
from app.schemas.model import ActiveModel, ModelVersion, ModelVersionDetail, ModelVersionList
from app.services.backend import BACKEND_ERRORS, unavailable

LIST_LIMIT = 50
NOT_FOUND_MESSAGE = "Model version not found."
NO_ACTIVE_MESSAGE = "No model is active yet. Ask an administrator to activate a version."


def list_versions(db: Client) -> ModelVersionList:
    try:
        rows = repo.list_versions(db, limit=LIST_LIMIT)
    except BACKEND_ERRORS as error:
        raise unavailable(error, "list_model_versions") from None
    return ModelVersionList(items=[ModelVersion.model_validate(row) for row in rows])


def get_version(db: Client, version_id: uuid.UUID) -> ModelVersionDetail:
    try:
        row = repo.get_version(db, version_id)
    except BACKEND_ERRORS as error:
        raise unavailable(error, "get_model_version", model_version_id=str(version_id)) from None
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND, 404, NOT_FOUND_MESSAGE)
    return ModelVersionDetail.model_validate(row)


def active_model(db: Client) -> ActiveModel:
    try:
        row = repo.get_active(db)
    except BACKEND_ERRORS as error:
        raise unavailable(error, "get_active_model") from None
    if row is None:
        raise AppError(ErrorCode.NO_ACTIVE_MODEL, 409, NO_ACTIVE_MESSAGE)
    row["trained_at"] = row.pop("finished_at")
    row["reliability"] = row["metrics"]["overall_reliability"]
    return ActiveModel.model_validate(row)
