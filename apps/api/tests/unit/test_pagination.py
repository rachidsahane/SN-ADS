"""infra/pagination.py: keyset cursors (LLD 2, API_SPEC 6.4, D-081).

The decoded cursor is put into a PostgREST `or` filter, so it is an injection surface: only a
timestamp and an id of a strict shape are accepted, everything else is a 400 that never echoes the
input.
"""

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.api.errors import AppError, ErrorCode
from app.infra.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    Cursor,
    Page,
    decode_cursor,
    encode_cursor,
    keyset_filter,
    require_cursor_id,
)

STAMP = datetime(2026, 10, 3, 14, 5, 0, 123456, tzinfo=UTC)
STAMP_TEXT = "2026-10-03T14:05:00.123456+00:00"
ROW_ID = uuid.UUID("2f1c5b0e-7d0a-4b8e-9a53-6a1d3c0f9e11")


def _raw(payload: object) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _refusal(raw: str) -> AppError:
    with pytest.raises(AppError) as error:
        decode_cursor(raw)
    return error.value


# --- constants and shapes ----------------------------------------------------------------------


def test_the_page_sizes_are_50_by_default_and_100_at_most() -> None:
    assert (DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE) == (50, 100)


def test_a_cursor_and_a_page_are_immutable_values() -> None:
    cursor = Cursor(created_at=STAMP_TEXT, id="7")
    page = Page(limit=10, after=cursor)
    assert page == Page(limit=10, after=Cursor(created_at=STAMP_TEXT, id="7"))
    with pytest.raises(AttributeError):
        cursor.id = "8"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        page.limit = 20  # type: ignore[misc]


# --- encoding ----------------------------------------------------------------------------------


def test_a_cursor_survives_a_round_trip_with_its_microseconds() -> None:
    cursor = decode_cursor(encode_cursor(STAMP, ROW_ID))
    assert cursor == Cursor(created_at=STAMP_TEXT, id=str(ROW_ID))


def test_the_microsecond_is_never_rounded_away() -> None:
    stamp = STAMP.replace(microsecond=1)
    assert decode_cursor(encode_cursor(stamp, 7)).created_at == "2026-10-03T14:05:00.000001+00:00"


def test_a_numeric_id_is_kept_as_digits() -> None:
    assert decode_cursor(encode_cursor(STAMP, 42)) == Cursor(created_at=STAMP_TEXT, id="42")
    assert decode_cursor(encode_cursor(STAMP, "9007199254740993")).id == "9007199254740993"


def test_another_utc_offset_is_kept_as_given() -> None:
    stamp = STAMP.astimezone(timezone(timedelta(hours=2)))
    assert decode_cursor(encode_cursor(stamp, 1)).created_at == "2026-10-03T16:05:00.123456+02:00"


def test_the_encoded_form_is_padded_base64url_of_a_json_object_with_keys_c_and_i() -> None:
    raw = encode_cursor(STAMP, ROW_ID)
    assert len(raw) % 4 == 0
    assert set(raw) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=")
    assert json.loads(base64.urlsafe_b64decode(raw)) == {"c": STAMP_TEXT, "i": str(ROW_ID)}


def test_the_keyset_filter_is_the_documented_postgrest_expression() -> None:
    cursor = Cursor(created_at=STAMP_TEXT, id="42")
    assert keyset_filter(cursor) == (
        f"created_at.lt.{STAMP_TEXT},and(created_at.eq.{STAMP_TEXT},id.lt.42)"
    )


# --- accepted ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("created_at", "row_id"),
    [
        ("2026-10-03T14:05:00Z", "1"),
        ("2026-10-03T14:05:00.5Z", "9223372036854775807"),
        ("2026-10-03T14:05:00+00:00", str(ROW_ID)),
        ("2026-10-03T14:05:00.123456-05:30", "0a1B-2c3D"),
    ],
)
def test_well_formed_values_are_accepted(created_at: str, row_id: str) -> None:
    assert decode_cursor(_raw({"c": created_at, "i": row_id})) == Cursor(created_at, row_id)


# --- refused -----------------------------------------------------------------------------------

HOSTILE: list[tuple[str, str]] = [
    ("empty", ""),
    ("not base64", "not base64!!"),
    ("not json", base64.urlsafe_b64encode(b"hello").decode()),
    ("json list", _raw([STAMP_TEXT, "1"])),
    ("json string", _raw(STAMP_TEXT)),
    ("json null", _raw(None)),
    ("extra key", _raw({"c": STAMP_TEXT, "i": "1", "x": "2"})),
    ("missing id", _raw({"c": STAMP_TEXT})),
    ("missing timestamp", _raw({"i": "1"})),
    ("naive timestamp", _raw({"c": "2026-10-03T14:05:00.123456", "i": "1"})),
    ("date only", _raw({"c": "2026-10-03", "i": "1"})),
    ("impossible date", _raw({"c": "2026-13-45T25:61:00+00:00", "i": "1"})),
    ("comma in timestamp", _raw({"c": "2026-10-03T14:05:00,123456+00:00", "i": "1"})),
    ("filter in timestamp", _raw({"c": "2026-10-03T14:05:00+00:00,or(id.gt.0)", "i": "1"})),
    ("over-long fraction", _raw({"c": "2026-10-03T14:05:00." + "1" * 50 + "+00:00", "i": "1"})),
    ("filter in id", _raw({"c": STAMP_TEXT, "i": "1),id.gt.0"})),
    ("dot in id", _raw({"c": STAMP_TEXT, "i": "1.5"})),
    ("parenthesis in id", _raw({"c": STAMP_TEXT, "i": "(1)"})),
    ("space in id", _raw({"c": STAMP_TEXT, "i": "1 2"})),
    ("over-long id", _raw({"c": STAMP_TEXT, "i": "1" * 40})),
    ("empty id", _raw({"c": STAMP_TEXT, "i": ""})),
    ("id is a number", _raw({"c": STAMP_TEXT, "i": 5})),
    ("timestamp is a number", _raw({"c": 5, "i": "1"})),
    # `$` matches before a trailing newline and `\\d` matches any Unicode digit: neither may reach
    # the PostgREST filter.
    ("newline after id", _raw({"c": STAMP_TEXT, "i": "5\n"})),
    ("newline after uuid", _raw({"c": STAMP_TEXT, "i": str(ROW_ID) + "\n"})),
    ("non-ascii digit in id", _raw({"c": STAMP_TEXT, "i": "\u0663"})),
    ("non-ascii digit in timestamp", _raw({"c": "\u0662026-10-03T14:05:00Z", "i": "1"})),
    ("newline after timestamp", _raw({"c": "2026-10-03T14:05:00Z\n", "i": "1"})),
]


@pytest.mark.parametrize("raw", [raw for _, raw in HOSTILE], ids=[name for name, _ in HOSTILE])
def test_a_malformed_or_hostile_cursor_is_a_400_that_does_not_echo_it(raw: str) -> None:
    error = _refusal(raw)
    assert (error.code, error.status) == (ErrorCode.INVALID_REQUEST, 400)
    assert error.message == "The pagination parameters are invalid."
    (detail,) = error.details
    assert (detail.field, detail.issue) == ("cursor", "invalid_format")
    assert detail.message == "The cursor is not valid."
    if raw:
        assert raw not in repr(error.details) + error.message


# --- the kind of id depends on the table: a well-formed cursor of the wrong kind is a 400 ------


def _cursor(row_id: str) -> Cursor:
    return Cursor(created_at=STAMP_TEXT, id=row_id)


@pytest.mark.parametrize(
    ("kind", "row_id"),
    [
        ("uuid", str(ROW_ID)),
        ("uuid", str(ROW_ID).upper()),
        ("int", "1"),
        ("int", "9223372036854775807"),
    ],
)
def test_an_id_of_the_expected_kind_passes(kind: str, row_id: str) -> None:
    require_cursor_id(_cursor(row_id), kind)  # type: ignore[arg-type]


def test_no_cursor_is_always_fine() -> None:
    require_cursor_id(None, "uuid")
    require_cursor_id(None, "int")


@pytest.mark.parametrize(
    ("kind", "row_id"),
    [
        ("uuid", "123"),
        ("uuid", "abc-def"),
        ("uuid", "----"),
        ("uuid", str(ROW_ID).replace("-", "", 1)),  # hyphens must sit where uuid text puts them
        ("uuid", "1-2-3-4-5-6-7-8-9-a-b-c-d-e-f-0-1-2-3-4-5-6-7-8"),
        ("int", str(ROW_ID)),
        ("int", "abc"),
        ("int", "9223372036854775808"),  # one above bigint
        ("int", "9999999999999999999"),
    ],
)
def test_an_id_of_the_wrong_kind_is_the_same_400_that_does_not_echo_it(
    kind: str, row_id: str
) -> None:
    with pytest.raises(AppError) as error:
        require_cursor_id(_cursor(row_id), kind)  # type: ignore[arg-type]
    assert (error.value.code, error.value.status) == (ErrorCode.INVALID_REQUEST, 400)
    (detail,) = error.value.details
    assert (detail.field, detail.issue) == ("cursor", "invalid_format")
    assert row_id not in repr(error.value.details) + error.value.message
