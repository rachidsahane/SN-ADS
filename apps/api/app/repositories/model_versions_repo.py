"""Reads and writes of `public.model_versions`. The client is given, never built here (CLAUDE 4.2):
the user's own client for requests, reads and activation; the service client (training job only)
for status changes."""

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from supabase import Client

LIST_COLUMNS = (
    "id,version,status,data_scope,is_active,created_at,finished_at,"
    "requested_by:profiles!requested_by(id,full_name)"
)
DETAIL_COLUMNS = (
    f"{LIST_COLUMNS},metrics,global_importance,features_used,train_row_count,"
    "holdout_row_count,error_message,started_at,activated_at"
)
ACTIVE_COLUMNS = (
    "id,version,data_scope,finished_at,activated_at,train_row_count,holdout_row_count,"
    "metrics,global_importance"
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def insert_queued(db: Client, user_id: uuid.UUID) -> uuid.UUID:
    """Queue a version as the caller (RLS: administrator, status queued). Returns its id."""
    rows = db.table("model_versions").insert({"requested_by": str(user_id)}).execute().data
    return uuid.UUID(rows[0]["id"])


def list_versions(db: Client, *, limit: int) -> list[dict[str, Any]]:
    rows = (
        db.table("model_versions")
        .select(LIST_COLUMNS)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    return [dict(row) for row in rows]


def get_version(db: Client, version_id: uuid.UUID) -> dict[str, Any] | None:
    rows = (
        db.table("model_versions")
        .select(DETAIL_COLUMNS)
        .eq("id", str(version_id))
        .limit(1)
        .execute()
        .data
    )
    return dict(rows[0]) if rows else None


def get_active(db: Client) -> dict[str, Any] | None:
    rows = db.table("model_versions").select(ACTIVE_COLUMNS).eq("is_active", True).execute().data
    return dict(rows[0]) if rows else None


def active_ref(db: Client) -> tuple[str, int] | None:
    """Id and number of the active version, as the caller (RLS)."""
    rows = (
        db.table("model_versions")
        .select("id,version")
        .eq("is_active", True)
        .limit(1)
        .execute()
        .data
    )
    return (str(rows[0]["id"]), int(rows[0]["version"])) if rows else None


def active_id(db: Client) -> str | None:
    rows = db.table("model_versions").select("id").eq("is_active", True).limit(1).execute().data
    return str(rows[0]["id"]) if rows else None


def activate(db: Client, version_id: uuid.UUID) -> None:
    """Switch the active version atomically (`activate_model_version`, administrators only)."""
    db.rpc("activate_model_version", {"p_id": str(version_id)}).execute()


# --- status changes made by the training job (service client) -----------------------------------


def mark_running(db: Client, version_id: uuid.UUID) -> bool:
    """queued -> running; False when the version is not queued any more."""
    rows = (
        db.table("model_versions")
        .update({"status": "running", "started_at": _now()})
        .eq("id", str(version_id))
        .eq("status", "queued")
        .execute()
        .data
    )
    return bool(rows)


def mark_succeeded(db: Client, version_id: uuid.UUID, fields: Mapping[str, Any]) -> None:
    db.table("model_versions").update({**fields, "status": "succeeded", "finished_at": _now()}).eq(
        "id", str(version_id)
    ).execute()


def mark_failed(db: Client, version_id: uuid.UUID, message: str) -> None:
    db.table("model_versions").update(
        {"status": "failed", "error_message": message, "finished_at": _now()}
    ).eq("id", str(version_id)).execute()


def fail_in_progress(db: Client, message: str) -> int:
    """Start-up cleanup: every queued or running version is failed. Returns how many."""
    rows = (
        db.table("model_versions")
        .update({"status": "failed", "error_message": message, "finished_at": _now()})
        .in_("status", ["queued", "running"])
        .execute()
        .data
    )
    return len(rows)


def get_requester(db: Client, version_id: uuid.UUID) -> str | None:
    rows = (
        db.table("model_versions")
        .select("requested_by")
        .eq("id", str(version_id))
        .limit(1)
        .execute()
        .data
    )
    return rows[0]["requested_by"] if rows else None


# --- demo command (service client): train and activate without an administrator session ---------


def insert_system_queued(db: Client) -> uuid.UUID:
    rows = db.table("model_versions").insert({}).execute().data
    return uuid.UUID(rows[0]["id"])


def latest_succeeded_id(db: Client) -> uuid.UUID | None:
    rows = (
        db.table("model_versions")
        .select("id")
        .eq("status", "succeeded")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return uuid.UUID(rows[0]["id"]) if rows else None


def set_active(db: Client, version_id: uuid.UUID) -> None:
    """No other version is active when this is called (the unique index would refuse it)."""
    db.table("model_versions").update({"is_active": True, "activated_at": _now()}).eq(
        "id", str(version_id)
    ).execute()
