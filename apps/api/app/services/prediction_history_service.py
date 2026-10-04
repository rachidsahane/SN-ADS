"""Saved predictions: save (recomputed here, never trusted from the browser), list, read, delete."""

import uuid
from typing import Any

from supabase import Client

from app.api.errors import AppError, ErrorCode
from app.config import Settings
from app.repositories import predictions_repo as repo
from app.schemas.prediction import (
    PredictionList,
    PredictionResult,
    PredictionSummary,
    SavePredictionRequest,
)
from app.schemas.user import CurrentUser
from app.services import prediction_service
from app.services.backend import BACKEND_ERRORS, unavailable

LIST_LIMIT = 50
NOT_FOUND_MESSAGE = "Prediction not found."


def _result(row: dict[str, Any]) -> PredictionResult:
    """The frozen results, completed with the identity of the saved row."""
    data = {
        **row["results"],
        "id": row["id"],
        "created_at": row["created_at"],
        "label": row["name"],
    }
    return PredictionResult.model_validate(data)


def save(
    user: CurrentUser, db: Client, settings: Settings, request: SavePredictionRequest
) -> PredictionResult:
    predictor, model = prediction_service.require_predictor(db, settings)
    result = prediction_service.simulate(predictor, model, request.input)
    try:
        row = repo.insert(
            db,
            {
                "user_id": str(user.id),
                "model_version_id": str(model.id),
                "name": request.name,
                "inputs": request.input.model_dump(mode="json"),
                "results": result.model_dump(mode="json"),
            },
        )
    except BACKEND_ERRORS as error:
        raise unavailable(error, "save_prediction") from None
    return _result({**row, "results": result.model_dump(mode="json")})


def list_own(db: Client) -> PredictionList:
    try:
        rows = repo.list_own(db, limit=LIST_LIMIT)
    except BACKEND_ERRORS as error:
        raise unavailable(error, "list_predictions") from None
    return PredictionList(
        items=[
            PredictionSummary(
                id=row["id"],
                name=row["name"],
                created_at=row["created_at"],
                level=row["level"],
                model_version=row["model_versions"]["version"],
            )
            for row in rows
        ]
    )


def get(db: Client, prediction_id: uuid.UUID) -> PredictionResult:
    try:
        row = repo.get(db, prediction_id)
    except BACKEND_ERRORS as error:
        raise unavailable(error, "get_prediction", prediction_id=str(prediction_id)) from None
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND, 404, NOT_FOUND_MESSAGE)
    return _result(row)


def delete(db: Client, prediction_id: uuid.UUID) -> None:
    try:
        deleted = repo.delete(db, prediction_id)
    except BACKEND_ERRORS as error:
        raise unavailable(error, "delete_prediction", prediction_id=str(prediction_id)) from None
    if not deleted:
        raise AppError(ErrorCode.NOT_FOUND, 404, NOT_FOUND_MESSAGE)
