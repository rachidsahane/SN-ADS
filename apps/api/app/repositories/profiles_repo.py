"""Reads of `public.profiles`. The client is given, never built here (CLAUDE 4.2): called with the
user's own client, RLS decides which rows are visible."""

import uuid
from collections.abc import Mapping

from supabase import Client

from app.infra.pagination import Cursor, keyset_filter
from app.schemas.user import Profile, ProfileRecord

PROFILE_COLUMNS = "id,email,full_name,role,is_active"
ADMIN_USER_COLUMNS = "id,email,full_name,role,is_active,created_at"


def get_profile(db: Client, user_id: uuid.UUID) -> Profile | None:
    """The profile of a user, or None when no row is visible (absent, or deactivated under RLS)."""
    rows = (
        db.table("profiles").select(PROFILE_COLUMNS).eq("id", str(user_id)).limit(1).execute().data
    )
    return Profile.model_validate(rows[0]) if rows else None


def get_profile_record(db: Client, user_id: uuid.UUID) -> ProfileRecord | None:
    """The profile with its creation date, or None when no row is visible."""
    rows = (
        db.table("profiles")
        .select(ADMIN_USER_COLUMNS)
        .eq("id", str(user_id))
        .limit(1)
        .execute()
        .data
    )
    return ProfileRecord.model_validate(rows[0]) if rows else None


def find_profile_by_email(db: Client, email: str) -> ProfileRecord | None:
    """The profile with this (lower-case) e-mail, whatever its state, or None."""
    rows = (
        db.table("profiles").select(ADMIN_USER_COLUMNS).eq("email", email).limit(1).execute().data
    )
    return ProfileRecord.model_validate(rows[0]) if rows else None


def list_profile_records(db: Client, *, limit: int, after: Cursor | None) -> list[ProfileRecord]:
    """Profiles newest first (`created_at`, then `id` as tie-break), after the cursor if any."""
    query = (
        db.table("profiles")
        .select(ADMIN_USER_COLUMNS)
        .order("created_at", desc=True)
        .order("id", desc=True)
        .limit(limit)
    )
    if after is not None:
        query = query.or_(keyset_filter(after))
    return [ProfileRecord.model_validate(row) for row in query.execute().data]


def update_profile(
    db: Client, user_id: uuid.UUID, changes: Mapping[str, object]
) -> ProfileRecord | None:
    """Update the given columns in ONE statement. None when no row changed: RLS refused the
    update (own row, not an administrator) or the row is gone. Database errors are not caught."""
    rows = db.table("profiles").update(dict(changes)).eq("id", str(user_id)).execute().data
    return ProfileRecord.model_validate(rows[0]) if rows else None
