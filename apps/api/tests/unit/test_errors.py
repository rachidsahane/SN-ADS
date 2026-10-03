from typing import Any

import pytest
from postgrest.exceptions import APIError

from app.api.errors import (
    EMAIL_EXISTS_MESSAGE,
    ERROR_STATUS,
    FORBIDDEN_MESSAGE,
    LAST_ADMIN_MESSAGE,
    SELF_ACTION_MESSAGE,
    USER_NOT_FOUND_MESSAGE,
    ErrorCode,
    from_postgrest,
    translate_validation_errors,
)

SPEC_SECTION_3 = {
    "INVALID_REQUEST": 400, "UNAUTHENTICATED": 401, "TOKEN_EXPIRED": 401, "FORBIDDEN": 403,
    "ACCOUNT_DISABLED": 403, "NOT_FOUND": 404, "NO_ACTIVE_MODEL": 409,
    "TRAINING_ALREADY_RUNNING": 409, "DUPLICATE_UPLOAD": 409, "DUPLICATE_EXTERNAL_ID": 409,
    "MODEL_NOT_ACTIVATABLE": 409, "ACTIVE_VERSION_CHANGED": 409, "EMAIL_ALREADY_REGISTERED": 409,
    "LAST_ADMIN": 409, "SELF_ACTION_FORBIDDEN": 409, "PAYLOAD_TOO_LARGE": 413,
    "UNSUPPORTED_MEDIA_TYPE": 415, "VALIDATION_ERROR": 422, "CSV_INVALID": 422,
    "NOT_ENOUGH_DATA": 422, "RATE_LIMITED": 429, "INTERNAL_ERROR": 500,
    "SERVICE_UNAVAILABLE": 503,
}  # fmt: skip


def error(kind: str, loc: tuple[str | int, ...], **ctx: Any) -> dict[str, Any]:
    return {"type": kind, "loc": loc, "msg": "x", "input": "SECRET", "ctx": ctx}


def test_error_codes_and_statuses_match_the_api_spec() -> None:
    assert {code.value: status for code, status in ERROR_STATUS.items()} == SPEC_SECTION_3
    assert set(ErrorCode) == set(ERROR_STATUS)


def test_greater_than_message_matches_the_spec_example() -> None:
    result = translate_validation_errors([error("greater_than", ("body", "ad_spend"), gt=0.0)])
    assert result.status == 422
    assert result.code is ErrorCode.VALIDATION_ERROR
    assert result.message == "Some fields are invalid."
    detail = result.details[0]
    assert (detail.field, detail.issue) == ("ad_spend", "must_be_greater_than")
    assert detail.message == "Ad spend must be greater than 0."


def test_unknown_field_is_reported_as_unknown_field() -> None:
    result = translate_validation_errors([error("extra_forbidden", ("body", "score"))])
    assert result.details[0].issue == "unknown_field"


def test_rejected_input_is_never_copied_into_the_response() -> None:
    result = translate_validation_errors([error("int_parsing", ("body", "age"))])
    assert "SECRET" not in repr(result)


def test_malformed_json_is_a_400() -> None:
    result = translate_validation_errors([error("json_invalid", ("body", 1))])
    assert (result.status, result.code) == (400, ErrorCode.INVALID_REQUEST)


def test_invalid_path_parameter_is_a_404() -> None:
    result = translate_validation_errors([error("uuid_parsing", ("path", "id"))])
    assert (result.status, result.code) == (404, ErrorCode.NOT_FOUND)


def test_invalid_pagination_parameter_is_a_400() -> None:
    result = translate_validation_errors([error("less_than_equal", ("query", "limit"), le=100)])
    assert (result.status, result.code) == (400, ErrorCode.INVALID_REQUEST)


def test_other_invalid_query_parameter_is_a_422() -> None:
    result = translate_validation_errors(
        [error("enum", ("query", "campaign_channel"), expected="'A'")]
    )
    assert result.status == 422


# --- phase 3: PostgREST errors with a business code (LLD 2) ------------------------------------


def _postgrest_error(message: str | None, code: str | None = "P0001") -> APIError:
    body: dict[str, Any] = {"details": "", "hint": ""}
    if message is not None:
        body["message"] = message
    if code is not None:
        body["code"] = code
    return APIError(body)


def test_the_phase_3_messages_are_the_documented_texts() -> None:
    assert LAST_ADMIN_MESSAGE == "At least one active administrator is required."
    assert FORBIDDEN_MESSAGE == "You do not have permission to do this."
    assert SELF_ACTION_MESSAGE == "You cannot change your own account."
    assert EMAIL_EXISTS_MESSAGE == "A user with this email already exists."
    assert USER_NOT_FOUND_MESSAGE == "User not found."


def test_the_last_admin_trigger_error_becomes_a_409() -> None:
    translated = from_postgrest(_postgrest_error("LAST_ADMIN"))
    assert translated is not None
    assert (translated.code, translated.status) == (ErrorCode.LAST_ADMIN, 409)
    assert translated.message == "At least one active administrator is required."


def test_the_forbidden_error_of_log_audit_becomes_a_403() -> None:
    translated = from_postgrest(_postgrest_error("FORBIDDEN"))
    assert translated is not None
    assert (translated.code, translated.status) == (ErrorCode.FORBIDDEN, 403)
    assert translated.message == "You do not have permission to do this."


@pytest.mark.parametrize(
    "error",
    [
        _postgrest_error("SOMETHING_ELSE"),
        _postgrest_error("last_admin"),
        _postgrest_error("LAST_ADMIN", code="23505"),
        _postgrest_error("LAST_ADMIN", code="42501"),
        _postgrest_error("LAST_ADMIN", code=None),
        _postgrest_error(None),
    ],
)
def test_any_other_postgrest_error_is_left_to_the_caller(error: APIError) -> None:
    assert from_postgrest(error) is None


def test_a_translated_error_never_carries_the_database_text() -> None:
    error = APIError(
        {"message": "LAST_ADMIN", "code": "P0001", "details": "SELECT secret FROM x", "hint": "h"}
    )
    translated = from_postgrest(error)
    assert translated is not None
    assert "SELECT" not in repr(translated.message) + repr(translated.details)
