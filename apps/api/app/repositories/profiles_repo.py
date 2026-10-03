"""Reads of `public.profiles`. The client is given, never built here (CLAUDE 4.2): called with the
user's own client, RLS decides which rows are visible."""

import uuid

from supabase import Client

from app.schemas.user import Profile

PROFILE_COLUMNS = "id,email,full_name,role,is_active"


def get_profile(db: Client, user_id: uuid.UUID) -> Profile | None:
    """The profile of a user, or None when no row is visible (absent, or deactivated under RLS)."""
    rows = (
        db.table("profiles").select(PROFILE_COLUMNS).eq("id", str(user_id)).limit(1).execute().data
    )
    return Profile.model_validate(rows[0]) if rows else None
