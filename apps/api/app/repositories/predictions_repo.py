"""Reads and writes of `public.predictions`, always with the user's own client (RLS: owner only)."""

import uuid
from typing import Any

from supabase import Client

LIST_COLUMNS = (
    "id,name,created_at,level:results->performance->>level,"
    "score:results->performance->>score,"
    "campaign_channel:inputs->>campaign_channel,campaign_type:inputs->>campaign_type,"
    "model_versions!model_version_id(version)"
)
DETAIL_COLUMNS = "id,name,created_at,results"


def insert(db: Client, row: dict[str, Any]) -> dict[str, Any]:
    """`row`: user_id, model_version_id, name, inputs, results."""
    return dict(db.table("predictions").insert(row).execute().data[0])


def list_own(db: Client, *, limit: int) -> list[dict[str, Any]]:
    rows = (
        db.table("predictions")
        .select(LIST_COLUMNS)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    return [dict(row) for row in rows]


def get(db: Client, prediction_id: uuid.UUID) -> dict[str, Any] | None:
    rows = (
        db.table("predictions")
        .select(DETAIL_COLUMNS)
        .eq("id", str(prediction_id))
        .limit(1)
        .execute()
        .data
    )
    return dict(rows[0]) if rows else None


def delete(db: Client, prediction_id: uuid.UUID) -> bool:
    """True when a row was deleted (RLS hides other users' rows: they count as missing)."""
    return bool(db.table("predictions").delete().eq("id", str(prediction_id)).execute().data)
