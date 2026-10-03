"""GET /api/v1/me: the signed-in user (API_SPEC 6.2)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from supabase import Client

from app.api.deps import get_current_user, get_user_db
from app.schemas.common import ErrorResponse
from app.schemas.user import CurrentUser, MeResponse
from app.services.auth_service import get_me

router = APIRouter(tags=["me"])


@router.get(
    "/me",
    response_model=MeResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, invalid or expired token."},
        403: {"model": ErrorResponse, "description": "The account is deactivated."},
        503: {"model": ErrorResponse, "description": "The database is unavailable."},
    },
    summary="Current user",
)
def me(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_user_db)],
) -> MeResponse:
    return MeResponse.model_validate(get_me(user, db=db).model_dump())
