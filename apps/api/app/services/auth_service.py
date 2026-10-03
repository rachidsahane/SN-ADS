"""From an access token to the current user (API_SPEC 2), and the read behind GET /me.

The token is verified without any network call; role and activity then come from the Redis cache
(60 s) or, on a miss, from the database read with the USER's token. A deactivated account and a
missing profile are indistinguishable under RLS and both end as ACCOUNT_DISABLED (403). A Redis
outage degrades to a database read; a database outage is a 503 (CL-17).
"""

import uuid
from typing import Final

import httpx
from postgrest.exceptions import APIError
from supabase import Client

from app.api.errors import UNAVAILABLE_MESSAGE, AppError, ErrorCode
from app.config import Settings
from app.infra.auth import verify_access_token
from app.infra.observability import capture
from app.infra.profile_cache import CachedProfile, ProfileCache
from app.infra.request_context import set_user_id
from app.infra.supabase_clients import get_user_client
from app.repositories.profiles_repo import get_profile
from app.schemas.user import CurrentUser, Profile

DISABLED_MESSAGE: Final = "Your account has been deactivated. Contact an administrator."
_DATABASE_ERRORS: Final = (httpx.HTTPError, httpx.InvalidURL, APIError)


def _disabled() -> AppError:
    return AppError(ErrorCode.ACCOUNT_DISABLED, 403, DISABLED_MESSAGE)


def _read_profile(db: Client, user_id: uuid.UUID) -> Profile | None:
    """Read the profile; a database failure is reported once and becomes a 503."""
    try:
        return get_profile(db, user_id)
    except _DATABASE_ERRORS as error:
        capture(error, operation="read_profile")
        raise AppError(ErrorCode.SERVICE_UNAVAILABLE, 503, UNAVAILABLE_MESSAGE) from None


def authenticate(access_token: str, *, settings: Settings, cache: ProfileCache) -> CurrentUser:
    claims = verify_access_token(access_token, settings)
    set_user_id(str(claims.user_id))  # every later log line and error report carries the user
    cached = cache.get(claims.user_id)
    if cached is None:
        profile = _read_profile(get_user_client(access_token, settings), claims.user_id)
        if profile is None:
            raise _disabled()  # not cached: absent and deactivated look the same under RLS
        cached = CachedProfile(role=profile.role, is_active=profile.is_active)
        cache.set(claims.user_id, cached)
    if not cached.is_active:
        raise _disabled()
    return CurrentUser(id=claims.user_id, role=cached.role, access_token=access_token)


def get_me(user: CurrentUser, *, db: Client) -> Profile:
    """The full profile, always read from the database (the cache holds role and activity only)."""
    profile = _read_profile(db, user.id)
    if profile is None or not profile.is_active:
        raise _disabled()
    return profile
