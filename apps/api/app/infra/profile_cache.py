"""Role and activity of a user, cached for 60 seconds (ARCHITECTURE 2.6, API_SPEC 2).

Only `role` and `is_active` are stored: Redis is a third party in the cloud (Upstash), so neither
the e-mail nor the name ever goes there. An outage degrades to "read the database" and never
fails a request; `invalidate` is the exception: a deactivation must know the stale entry is gone.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Final

import redis

from app.infra.observability import get_logger
from app.infra.redis_client import CACHE_ERRORS
from app.schemas.user import AppRole

PROFILE_TTL_SECONDS: Final = 60
_ROLES: Final = frozenset({"marketer", "admin"})

logger = get_logger("app.profile_cache")


def profile_key(user_id: uuid.UUID) -> str:
    return f"auth:profile:{user_id}"


@dataclass(frozen=True)
class CachedProfile:
    role: AppRole
    is_active: bool


def _decode(raw: str | None) -> CachedProfile | None:
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    role, is_active = data.get("role"), data.get("is_active")
    if not isinstance(role, str) or role not in _ROLES or not isinstance(is_active, bool):
        return None
    return CachedProfile(role="admin" if role == "admin" else "marketer", is_active=is_active)


class ProfileCache:
    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    def get(self, user_id: uuid.UUID) -> CachedProfile | None:
        """The cached profile, or None on a miss, a corrupt entry or a Redis outage."""
        try:
            raw = self._client.get(profile_key(user_id))
        except CACHE_ERRORS as error:
            logger.warning(
                "profile_cache_unavailable", operation="get", error_type=type(error).__name__
            )
            return None
        profile = _decode(raw if isinstance(raw, str) else None)
        if raw is not None and profile is None:
            logger.warning("profile_cache_unavailable", operation="get", error_type="BadEntry")
        return profile

    def set(
        self,
        user_id: uuid.UUID,
        profile: CachedProfile,
        ttl_seconds: int = PROFILE_TTL_SECONDS,
    ) -> None:
        payload = json.dumps({"role": profile.role, "is_active": profile.is_active})
        try:
            self._client.set(profile_key(user_id), payload, ex=ttl_seconds)
        except CACHE_ERRORS as error:
            logger.warning(
                "profile_cache_unavailable", operation="set", error_type=type(error).__name__
            )

    def invalidate(self, user_id: uuid.UUID) -> None:
        """Remove the entry. A Redis failure is NOT swallowed (phase 3 deactivation, SEC-07)."""
        self._client.delete(profile_key(user_id))
