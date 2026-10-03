"""The audit log as the administrator reads it (API_SPEC 6.9, DATA_MODEL 4.6)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

# The ten actions of the `check` constraint of `audit_log` (DATA_MODEL 4.6), verbatim.
AuditAction = Literal[
    "user.invited",
    "user.role_changed",
    "user.deactivated",
    "user.reactivated",
    "upload.accepted",
    "upload.failed",
    "model.training_requested",
    "model.training_succeeded",
    "model.training_failed",
    "model.activated",
]
AuditTargetType = Literal["user", "upload", "model_version"]


class AuditActor(BaseModel):
    id: uuid.UUID
    full_name: str


class AuditEntry(BaseModel):
    id: int
    created_at: datetime
    actor: AuditActor | None  # null when the author is the system (or no longer exists)
    action: AuditAction
    target_type: AuditTargetType
    target_id: str
    # Any: the content depends on the action (user e-mail, role change, file name...).
    metadata: dict[str, Any]


class AuditLogPage(BaseModel):
    items: list[AuditEntry]
    next_cursor: str | None
