"""/api/v1/admin/users: list, invite, change role, deactivate and reactivate (API_SPEC 6.6)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from supabase import Client

from app.api.deps import get_current_user, get_page, get_profile_cache, get_settings, get_user_db
from app.config import Settings
from app.infra.pagination import Page
from app.infra.profile_cache import ProfileCache
from app.schemas.common import ErrorResponse
from app.schemas.user import (
    AdminUser,
    AdminUserPage,
    CurrentUser,
    InviteUserRequest,
    UpdateUserRequest,
)
from app.services import user_admin_service

router = APIRouter(prefix="/users", tags=["admin-users"])

_UNAUTHENTICATED = {"model": ErrorResponse, "description": "Missing, invalid or expired token."}
_FORBIDDEN = {"model": ErrorResponse, "description": "The caller is not an active administrator."}
_UNAVAILABLE = {"model": ErrorResponse, "description": "The database or Auth is unavailable."}


@router.get(
    "",
    response_model=AdminUserPage,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid pagination parameters."},
        401: _UNAUTHENTICATED,
        403: _FORBIDDEN,
        503: _UNAVAILABLE,
    },
    summary="List users",
)
def list_users(
    db: Annotated[Client, Depends(get_user_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    page: Annotated[Page, Depends(get_page)],
) -> AdminUserPage:
    return user_admin_service.list_users(db, settings=settings, page=page)


@router.post(
    "/invite",
    status_code=201,
    response_model=AdminUser,
    responses={
        401: _UNAUTHENTICATED,
        403: _FORBIDDEN,
        409: {"model": ErrorResponse, "description": "A user with this e-mail already exists."},
        422: {"model": ErrorResponse, "description": "Some fields are invalid."},
        429: {"model": ErrorResponse, "description": "Too many invitation e-mails."},
        503: _UNAVAILABLE,
    },
    summary="Invite a user",
)
def invite_user(
    payload: InviteUserRequest,
    actor: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_user_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminUser:
    return user_admin_service.invite_user(actor, db, payload, settings=settings)


@router.patch(
    "/{user_id}",
    response_model=AdminUser,
    responses={
        401: _UNAUTHENTICATED,
        403: _FORBIDDEN,
        404: {"model": ErrorResponse, "description": "No such user."},
        409: {
            "model": ErrorResponse,
            "description": "Own account (SELF_ACTION_FORBIDDEN) or last admin (LAST_ADMIN).",
        },
        422: {"model": ErrorResponse, "description": "Some fields are invalid."},
        503: _UNAVAILABLE,
    },
    summary="Update a user",
)
def update_user(  # noqa: PLR0913  # one FastAPI dependency per collaborator
    user_id: uuid.UUID,
    payload: UpdateUserRequest,
    actor: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_user_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    cache: Annotated[ProfileCache, Depends(get_profile_cache)],
) -> AdminUser:
    return user_admin_service.update_user(
        actor, db, user_id, payload, settings=settings, cache=cache
    )
