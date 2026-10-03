from typing import Any

from app.api.errors import ERROR_STATUS, ErrorCode, translate_validation_errors

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
