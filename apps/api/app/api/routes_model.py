"""/api/v1/model/active: the active model's reliability and importance, for every signed-in user."""

from typing import Annotated

from fastapi import APIRouter, Depends
from supabase import Client

from app.api.deps import get_user_db
from app.schemas.common import ErrorResponse
from app.schemas.model import ActiveModel
from app.services import model_version_service

router = APIRouter(prefix="/model", tags=["model"])


@router.get(
    "/active",
    response_model=ActiveModel,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, invalid or expired token."},
        409: {"model": ErrorResponse, "description": "No model is active yet."},
        503: {"model": ErrorResponse, "description": "The database is unavailable."},
    },
    summary="Active model",
)
def active_model(db: Annotated[Client, Depends(get_user_db)]) -> ActiveModel:
    return model_version_service.active_model(db)
