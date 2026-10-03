"""Liveness (/health) and readiness (/ready) probes. Both are public."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_database_check, get_settings
from app.config import Settings
from app.schemas.common import HealthResponse, ReadyChecks, ReadyResponse
from app.services.readiness_service import DatabaseCheck

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", release=settings.app_release)


@router.get(
    "/ready",
    response_model=ReadyResponse,
    response_model_exclude_none=True,
    responses={503: {"model": ReadyResponse, "description": "A backing service is not ready."}},
    summary="Readiness probe",
)
def ready(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[DatabaseCheck, Depends(get_database_check)],
) -> ReadyResponse:
    """The 503 body has the same schema as the 200 one (API_SPEC 6.1), not the error format."""
    if not database.ok:
        response.status_code = 503
        return ReadyResponse(
            status="not_ready",
            checks=ReadyChecks(database="error"),
            release=settings.app_release,
        )
    return ReadyResponse(
        status="ready",
        checks=ReadyChecks(database="ok"),
        schema_version=database.schema_version,
        release=settings.app_release,
    )
