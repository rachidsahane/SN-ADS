"""Writes and reads of `public.audit_log`, always with the caller's own client (RLS applies).

Entries are written through the `log_audit` function (administrators only, the actor is taken from
the token), never by a direct insert.
"""

from collections.abc import Mapping

from postgrest.types import ReturnMethod
from supabase import Client

from app.infra.pagination import Cursor, keyset_filter
from app.schemas.audit import AuditEntry

AUDIT_COLUMNS = (
    "id,created_at,action,target_type,target_id,metadata,actor:profiles!actor_id(id,full_name)"
)


def log_action(
    db: Client,
    *,
    action: str,
    target_type: str,
    target_id: str,
    metadata: Mapping[str, object],
) -> None:
    """Write one audit entry as the caller. Database errors are not caught."""
    db.rpc(
        "log_audit",
        {
            "p_action": action,
            "p_target_type": target_type,
            "p_target_id": target_id,
            "p_metadata": dict(metadata),
        },
    ).execute()


def list_entries(db: Client, *, limit: int, after: Cursor | None) -> list[AuditEntry]:
    """Entries newest first (`created_at`, then `id`), with the author's id and name."""
    query = (
        db.table("audit_log")
        .select(AUDIT_COLUMNS)
        .order("created_at", desc=True)
        .order("id", desc=True)
        .limit(limit)
    )
    if after is not None:
        query = query.or_(keyset_filter(after))
    return [AuditEntry.model_validate(row) for row in query.execute().data]


def insert_system_entry(db: Client, entry: Mapping[str, object]) -> None:
    """Write one entry with the service client (training job: no administrator token there).
    `entry` holds actor_id, action, target_type, target_id and metadata."""
    db.table("audit_log").insert(dict(entry), returning=ReturnMethod.minimal).execute()
