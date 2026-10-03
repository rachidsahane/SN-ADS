"""FastAPI dependencies: settings, readiness probes and authentication.

`require_admin` (phase 3) and `rate_limit` (phase 9) arrive with their first consumers.
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.config import Settings
from app.infra.auth import unauthenticated
from app.infra.profile_cache import ProfileCache
from app.infra.redis_client import get_redis_client
from app.infra.supabase_clients import get_user_client
from app.schemas.user import CurrentUser
from app.services.auth_service import authenticate
from app.services.readiness_service import CacheCheck, DatabaseCheck, check_cache, check_database

# auto_error=False is mandatory: FastAPI's own 403 would break the standard error format.
_bearer = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_database_check(settings: Annotated[Settings, Depends(get_settings)]) -> DatabaseCheck:
    """Probe the database. Synchronous on purpose: FastAPI runs it in its thread pool."""
    return check_database(settings)


def get_cache_check(settings: Annotated[Settings, Depends(get_settings)]) -> CacheCheck:
    """Probe Redis (thread pool, like the database probe). Never raises."""
    return check_cache(settings)


def get_profile_cache(settings: Annotated[Settings, Depends(get_settings)]) -> ProfileCache:
    return ProfileCache(get_redis_client(settings))


def get_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    """The raw bearer token. Missing, non-Bearer or blank is UNAUTHENTICATED (401)."""
    if credentials is None or not credentials.credentials.strip():
        raise unauthenticated()
    return credentials.credentials


def get_current_user(
    token: Annotated[str, Depends(get_bearer_token)],
    settings: Annotated[Settings, Depends(get_settings)],
    cache: Annotated[ProfileCache, Depends(get_profile_cache)],
) -> CurrentUser:
    """Verify the token and the account. Synchronous: it may query the database (thread pool)."""
    return authenticate(token, settings=settings, cache=cache)


def get_user_db(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Client:
    """A database client that carries the caller's token: RLS applies (CLAUDE 3.5)."""
    return get_user_client(user.access_token, settings)
