"""Keyset pagination: opaque cursors made of `created_at` and `id` (LLD 2, API_SPEC 6.4, D-081).

The decoded cursor ends up inside a PostgREST `or` filter, so it is an injection surface: only a
timestamp and an id of a strict shape are accepted. Anything else is a 400 that never echoes the
input.
"""

import base64
import binascii
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

from app.api.errors import AppError, ErrorCode
from app.schemas.common import ErrorDetail

DEFAULT_PAGE_SIZE: Final = 50
MAX_PAGE_SIZE: Final = 100

# ASCII only and matched with `fullmatch`: `\d` also matches other scripts' digits and `$` also
# matches before a trailing newline, and none of that may reach a PostgREST filter.
_TIMESTAMP: Final = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})", re.ASCII
)
_ROW_ID: Final = re.compile(r"[0-9a-fA-F-]{1,36}|[0-9]{1,19}", re.ASCII)
_BIGINT_MAX: Final = 2**63 - 1
_KEYS: Final = frozenset({"c", "i"})
_INVALID_MESSAGE: Final = "The pagination parameters are invalid."


@dataclass(frozen=True)
class Cursor:
    created_at: str  # ISO 8601 with offset and full microsecond precision
    id: str  # uuid text (profiles) or digits (audit_log.id)


@dataclass(frozen=True)
class Page:
    limit: int
    after: Cursor | None


def _invalid() -> AppError:
    return AppError(
        ErrorCode.INVALID_REQUEST,
        400,
        _INVALID_MESSAGE,
        [ErrorDetail(field="cursor", issue="invalid_format", message="The cursor is not valid.")],
    )


def encode_cursor(created_at: datetime, row_id: uuid.UUID | int | str) -> str:
    payload = json.dumps({"c": created_at.isoformat(), "i": str(row_id)}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _parse(raw: str) -> dict[str, object] | None:
    try:
        data = json.loads(base64.b64decode(raw.encode("ascii"), altchars=b"-_", validate=True))
    except (ValueError, binascii.Error, UnicodeError):
        return None
    return data if isinstance(data, dict) else None


def _valid_timestamp(value: str) -> bool:
    if not _TIMESTAMP.fullmatch(value):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def decode_cursor(raw: str) -> Cursor:
    data = _parse(raw)
    if data is None or set(data) != _KEYS:
        raise _invalid()
    created_at, row_id = data["c"], data["i"]
    if (
        not isinstance(created_at, str)
        or not isinstance(row_id, str)
        or not _valid_timestamp(created_at)
        or not _ROW_ID.fullmatch(row_id)
    ):
        raise _invalid()
    return Cursor(created_at=created_at, id=row_id)


IdKind = Literal["uuid", "int"]


def _id_has_kind(row_id: str, kind: IdKind) -> bool:
    if kind == "int":
        return row_id.isascii() and row_id.isdigit() and int(row_id) <= _BIGINT_MAX
    try:
        return str(uuid.UUID(row_id)) == row_id.lower()  # canonical text, as PostgreSQL wants it
    except ValueError:
        return False


def require_cursor_id(cursor: Cursor | None, kind: IdKind) -> None:
    """The id of the cursor must have the type of the column it is compared with (`uuid` for
    profiles, `int` for the audit log): otherwise the database refuses the filter and the caller
    would get a 503 for what is a bad request. Same 400 as an undecodable cursor."""
    if cursor is not None and not _id_has_kind(cursor.id, kind):
        raise _invalid()


def keyset_filter(cursor: Cursor) -> str:
    """PostgREST `or` expression selecting the rows strictly after `cursor` in
    (created_at desc, id desc) order."""
    c, i = cursor.created_at, cursor.id
    return f"created_at.lt.{c},and(created_at.eq.{c},id.lt.{i})"
