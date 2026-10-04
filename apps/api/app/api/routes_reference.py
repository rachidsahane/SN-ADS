"""Form reference: options and pre-filled engagement values (API_SPEC 6.3)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from supabase import Client

from app.api.deps import get_settings, get_user_db
from app.config import Settings
from app.schemas.common import ErrorResponse
from app.schemas.prediction import CampaignType, Channel, EngagementDefaults, ReferenceOptions
from app.services import prediction_service

router = APIRouter(prefix="/reference", tags=["reference"])
_errors: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired token."},
    503: {"model": ErrorResponse, "description": "The database is unavailable."},
}


@router.get("/options", response_model=ReferenceOptions, responses=_errors, summary="Form options")
def options(
    db: Annotated[Client, Depends(get_user_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReferenceOptions:
    return prediction_service.reference_options(db, settings)


@router.get(
    "/engagement-defaults",
    response_model=EngagementDefaults,
    responses={**_errors, 409: {"model": ErrorResponse, "description": "No model is active yet."}},
    summary="Pre-filled engagement values",
)
def engagement_defaults(
    campaign_channel: Channel,
    campaign_type: CampaignType,
    db: Annotated[Client, Depends(get_user_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EngagementDefaults:
    predictor, _ = prediction_service.require_predictor(db, settings)
    return prediction_service.engagement_defaults(predictor, campaign_channel, campaign_type)
