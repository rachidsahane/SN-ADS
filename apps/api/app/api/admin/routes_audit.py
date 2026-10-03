"""/api/v1/admin/audit-log: who did what, newest first (API_SPEC 6.9)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from supabase import Client

from app.api.deps import get_page, get_user_db
from app.infra.pagination import Page
from app.schemas.audit import AuditLogPage
from app.schemas.common import ErrorResponse
from app.services import audit_service

router = APIRouter(prefix="/audit-log", tags=["admin-audit"])


@router.get(
    "",
    response_model=AuditLogPage,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid pagination parameters."},
        401: {"model": ErrorResponse, "description": "Missing, invalid or expired token."},
        403: {"model": ErrorResponse, "description": "The caller is not an active administrator."},
        503: {"model": ErrorResponse, "description": "The database is unavailable."},
    },
    summary="Audit log",
)
def audit_log(
    db: Annotated[Client, Depends(get_user_db)],
    page: Annotated[Page, Depends(get_page)],
) -> AuditLogPage:
    return audit_service.list_audit(db, page=page)
