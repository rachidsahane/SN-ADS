"""Readiness of the backing services behind GET /api/ready (API_SPEC 6.1).

Phase 1 checks the database only. The probe calls the public `schema_version()` function through
PostgREST with the anon key: it never uses the service-role key (ARCHITECTURE 2.5). An expected
outage is a warning in the log, not an exception reported to Sentry.
"""

import re
from dataclasses import dataclass
from typing import Final

import httpx

from app.config import Settings
from app.infra.observability import get_logger

PROBE_TIMEOUT_SECONDS: Final = 2.0
SCHEMA_VERSION_PATH: Final = "/rest/v1/rpc/schema_version"
_MIGRATION_NUMBER: Final = re.compile(r"[0-9]{14}")

logger = get_logger("app.readiness")


@dataclass(frozen=True)
class DatabaseCheck:
    ok: bool
    schema_version: str | None
    reason: str | None  # missing_key | timeout | connection_error | http_<status> | bad_payload


def _failed(reason: str) -> DatabaseCheck:
    logger.warning("readiness_failed", check="database", reason=reason)
    return DatabaseCheck(ok=False, schema_version=None, reason=reason)


def _read_version(response: httpx.Response) -> DatabaseCheck:
    if response.status_code != httpx.codes.OK:
        return _failed(f"http_{response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        return _failed("bad_payload")
    if not isinstance(payload, str) or not _MIGRATION_NUMBER.fullmatch(payload):
        return _failed("bad_payload")
    return DatabaseCheck(ok=True, schema_version=payload, reason=None)


def check_database(
    settings: Settings, *, transport: httpx.BaseTransport | None = None
) -> DatabaseCheck:
    """Ask the database for its schema number. Fails closed on any problem."""
    anon = settings.supabase_anon_key.get_secret_value()
    if not anon:
        return _failed("missing_key")
    try:
        with httpx.Client(
            base_url=settings.supabase_url, timeout=PROBE_TIMEOUT_SECONDS, transport=transport
        ) as client:
            response = client.post(
                SCHEMA_VERSION_PATH,
                json={},
                headers={"apikey": anon, "Authorization": f"Bearer {anon}"},
            )
    except httpx.TimeoutException:
        return _failed("timeout")
    except (httpx.HTTPError, httpx.InvalidURL):
        # InvalidURL (e.g. a non-numeric port that Settings lets through) is no HTTPError.
        return _failed("connection_error")
    return _read_version(response)
