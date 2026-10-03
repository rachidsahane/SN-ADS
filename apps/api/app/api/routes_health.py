"""Liveness probe. Public, no dependency on any backing service."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_settings
from app.config import Settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", release=settings.app_release)
