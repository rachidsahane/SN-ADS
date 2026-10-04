"""Predictions (API_SPEC 6.4, 6.5): the simulation, then the user's own saved predictions."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from supabase import Client

from app.api.deps import get_current_user, get_settings, get_user_db
from app.config import Settings
from app.schemas.common import ErrorResponse
from app.schemas.prediction import (
    CampaignInput,
    PredictionList,
    PredictionResult,
    SavePredictionRequest,
)
from app.schemas.user import CurrentUser
from app.services import prediction_history_service, prediction_service

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post(
    "/simulate",
    response_model=PredictionResult,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, invalid or expired token."},
        409: {"model": ErrorResponse, "description": "No model is active yet."},
        422: {"model": ErrorResponse, "description": "Invalid campaign."},
        503: {"model": ErrorResponse, "description": "The database is unavailable."},
    },
    summary="Simulate a campaign",
)
def simulate(
    campaign: CampaignInput,
    db: Annotated[Client, Depends(get_user_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PredictionResult:
    predictor, model = prediction_service.require_predictor(db, settings)
    return prediction_service.simulate(predictor, model, campaign)


_NOT_FOUND = {"model": ErrorResponse, "description": "Prediction not found (or not yours)."}
_AUTH = {"model": ErrorResponse, "description": "Missing, invalid or expired token."}


@router.post(
    "",
    status_code=201,
    response_model=PredictionResult,
    responses={
        401: _AUTH,
        409: {"model": ErrorResponse, "description": "No model is active yet."},
        422: {"model": ErrorResponse, "description": "Invalid campaign or name."},
        503: {"model": ErrorResponse, "description": "The database is unavailable."},
    },
    summary="Save a prediction (recomputed by the server)",
)
def save_prediction(
    body: SavePredictionRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_user_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PredictionResult:
    return prediction_history_service.save(user, db, settings, body)


@router.get(
    "",
    response_model=PredictionList,
    responses={401: _AUTH},
    summary="My latest 50 predictions",
)
def list_predictions(db: Annotated[Client, Depends(get_user_db)]) -> PredictionList:
    return prediction_history_service.list_own(db)


@router.get(
    "/{prediction_id}",
    response_model=PredictionResult,
    responses={401: _AUTH, 404: _NOT_FOUND},
    summary="Read one of my predictions",
)
def read_prediction(
    prediction_id: uuid.UUID, db: Annotated[Client, Depends(get_user_db)]
) -> PredictionResult:
    return prediction_history_service.get(db, prediction_id)


@router.delete(
    "/{prediction_id}",
    status_code=204,
    responses={401: _AUTH, 404: _NOT_FOUND},
    summary="Delete one of my predictions",
)
def delete_prediction(
    prediction_id: uuid.UUID, db: Annotated[Client, Depends(get_user_db)]
) -> Response:
    prediction_history_service.delete(db, prediction_id)
    return Response(status_code=204)
