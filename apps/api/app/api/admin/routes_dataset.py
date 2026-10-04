"""/api/v1/admin/dataset/summary: how many rows the models learn from (API_SPEC 6.7, simplified)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from supabase import Client

from app.api.deps import get_user_db
from app.schemas.common import ErrorResponse
from app.schemas.model import DatasetSummary
from app.services import dataset_service

router = APIRouter(prefix="/dataset", tags=["admin-dataset"])


@router.get(
    "/summary",
    response_model=DatasetSummary,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, invalid or expired token."},
        403: {"model": ErrorResponse, "description": "The caller is not an active administrator."},
        503: {"model": ErrorResponse, "description": "The database is unavailable."},
    },
    summary="Dataset summary",
)
def dataset_summary(db: Annotated[Client, Depends(get_user_db)]) -> DatasetSummary:
    return dataset_service.summary(db)
