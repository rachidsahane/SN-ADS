"""Audit log: write an entry as the administrator, list the entries (API_SPEC 6.9, D-084).

The business action is already done when the entry is written, so a failed write is reported and
never fails or undoes it.
"""

from collections.abc import Mapping
from typing import Final

import httpx
from postgrest.exceptions import APIError
from supabase import Client

from app.api.errors import UNAVAILABLE_MESSAGE, AppError, ErrorCode
from app.infra.observability import capture
from app.infra.pagination import Page, encode_cursor, require_cursor_id
from app.repositories import audit_repo
from app.schemas.audit import AuditAction, AuditLogPage, AuditTargetType

_BACKEND_ERRORS: Final = (httpx.HTTPError, httpx.InvalidURL, APIError)


def record(
    db: Client,
    *,
    action: AuditAction,
    target_type: AuditTargetType,
    target_id: str,
    metadata: Mapping[str, object],
) -> bool:
    """Write one entry as the caller (`log_audit`). Never raises; False when the write failed.

    The report carries the action and the target id, never the metadata (it may hold an e-mail).
    """
    try:
        audit_repo.log_action(
            db, action=action, target_type=target_type, target_id=target_id, metadata=metadata
        )
    except _BACKEND_ERRORS as error:
        capture(error, operation="audit_write", action=action, target_id=target_id)
        return False
    return True


def list_audit(db: Client, *, page: Page) -> AuditLogPage:
    """The entries newest first. One row more than the limit is read to know if a page follows."""
    require_cursor_id(page.after, "int")
    try:
        entries = audit_repo.list_entries(db, limit=page.limit + 1, after=page.after)
    except _BACKEND_ERRORS as error:
        capture(error, operation="list_audit")
        raise AppError(ErrorCode.SERVICE_UNAVAILABLE, 503, UNAVAILABLE_MESSAGE) from None
    items = entries[: page.limit]
    next_cursor = None
    if len(entries) > page.limit:
        last = items[-1]
        next_cursor = encode_cursor(last.created_at, last.id)
    return AuditLogPage(items=items, next_cursor=next_cursor)
