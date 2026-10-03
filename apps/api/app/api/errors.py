"""Standard error format (docs/API_SPEC.md section 3) and the handlers that produce it."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from typing import Any, Final

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.infra.observability import capture
from app.infra.request_context import get_request_id, route_template
from app.schemas.common import ErrorBody, ErrorDetail, ErrorResponse


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"  # noqa: S105  # error code, not a credential
    FORBIDDEN = "FORBIDDEN"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    NOT_FOUND = "NOT_FOUND"
    NO_ACTIVE_MODEL = "NO_ACTIVE_MODEL"
    TRAINING_ALREADY_RUNNING = "TRAINING_ALREADY_RUNNING"
    DUPLICATE_UPLOAD = "DUPLICATE_UPLOAD"
    DUPLICATE_EXTERNAL_ID = "DUPLICATE_EXTERNAL_ID"
    MODEL_NOT_ACTIVATABLE = "MODEL_NOT_ACTIVATABLE"
    ACTIVE_VERSION_CHANGED = "ACTIVE_VERSION_CHANGED"
    EMAIL_ALREADY_REGISTERED = "EMAIL_ALREADY_REGISTERED"
    LAST_ADMIN = "LAST_ADMIN"
    SELF_ACTION_FORBIDDEN = "SELF_ACTION_FORBIDDEN"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CSV_INVALID = "CSV_INVALID"
    NOT_ENOUGH_DATA = "NOT_ENOUGH_DATA"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


# HTTP status of every code (API_SPEC section 3). A unit test keeps this table in sync.
ERROR_STATUS: Final[Mapping[ErrorCode, int]] = {
    ErrorCode.INVALID_REQUEST: 400,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.ACCOUNT_DISABLED: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.NO_ACTIVE_MODEL: 409,
    ErrorCode.TRAINING_ALREADY_RUNNING: 409,
    ErrorCode.DUPLICATE_UPLOAD: 409,
    ErrorCode.DUPLICATE_EXTERNAL_ID: 409,
    ErrorCode.MODEL_NOT_ACTIVATABLE: 409,
    ErrorCode.ACTIVE_VERSION_CHANGED: 409,
    ErrorCode.EMAIL_ALREADY_REGISTERED: 409,
    ErrorCode.LAST_ADMIN: 409,
    ErrorCode.SELF_ACTION_FORBIDDEN: 409,
    ErrorCode.PAYLOAD_TOO_LARGE: 413,
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: 415,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.CSV_INVALID: 422,
    ErrorCode.NOT_ENOUGH_DATA: 422,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
}

INTERNAL_ERROR_MESSAGE: Final = "Something went wrong on our side. Please try again."
UNAVAILABLE_MESSAGE: Final = (
    "The service is temporarily unavailable. Please try again in a few minutes."
)


class AppError(Exception):
    """Expected, business-level failure. `message` is shown to the user as is."""

    def __init__(
        self,
        code: ErrorCode,
        status: int,
        message: str,
        details: Sequence[ErrorDetail] = (),
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message
        self.details = list(details)
        self.headers = dict(headers) if headers else None


class PayloadTooLargeError(HTTPException):
    """Raised while a body is being read. Must derive from fastapi.HTTPException: FastAPI turns
    any other exception raised during body parsing into a generic 400."""

    def __init__(self, message: str) -> None:
        super().__init__(status_code=413, detail=message)
        self.message = message


def error_response(
    status: int,
    code: ErrorCode,
    message: str,
    details: Sequence[ErrorDetail] = (),
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code.value, message=message, details=list(details), request_id=get_request_id()
        )
    )
    return JSONResponse(
        status_code=status,
        content=body.model_dump(mode="json", exclude_none=True),
        headers=dict(headers) if headers else None,
    )


def internal_error_response(exc: BaseException, *, route: str | None) -> JSONResponse:
    """500 for an unexpected exception: report it, show no technical detail."""
    capture(exc, route=route)
    return error_response(500, ErrorCode.INTERNAL_ERROR, INTERNAL_ERROR_MESSAGE)


# --- validation errors -------------------------------------------------------------------------

_ISSUE_BY_TYPE: Final[Mapping[str, str]] = {
    "missing": "required",
    "extra_forbidden": "unknown_field",
    "greater_than": "must_be_greater_than",
    "greater_than_equal": "must_be_at_least",
    "less_than": "must_be_less_than",
    "less_than_equal": "must_be_at_most",
    "string_too_short": "too_short",
    "string_too_long": "too_long",
    "enum": "invalid_choice",
    "literal_error": "invalid_choice",
    "string_pattern_mismatch": "invalid_format",
}
_PAGINATION_PARAMS: Final = frozenset({"limit", "cursor"})


@dataclass(frozen=True)
class TranslatedValidation:
    status: int
    code: ErrorCode
    message: str
    details: list[ErrorDetail]


def _number(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _field_path(loc: Sequence[object]) -> str | None:
    parts = [str(part) for part in loc[1:]]
    return ".".join(parts) if parts else (str(loc[0]) if loc else None)


def _issue(error_type: str) -> str:
    if error_type in _ISSUE_BY_TYPE:
        return _ISSUE_BY_TYPE[error_type]
    if error_type.endswith(("_type", "_parsing", "_from_str")):
        return "invalid_type"
    return "invalid"


def _message(label: str, error_type: str, ctx: Mapping[str, Any]) -> str:
    rules: dict[str, str] = {
        "missing": f"{label} is required.",
        "extra_forbidden": f"{label} is not an accepted field.",
        "greater_than": f"{label} must be greater than {_number(ctx.get('gt'))}.",
        "greater_than_equal": f"{label} must be at least {_number(ctx.get('ge'))}.",
        "less_than": f"{label} must be less than {_number(ctx.get('lt'))}.",
        "less_than_equal": f"{label} must be at most {_number(ctx.get('le'))}.",
        "string_too_short": f"{label} must have at least {ctx.get('min_length')} characters.",
        "string_too_long": f"{label} must have at most {ctx.get('max_length')} characters.",
        "enum": f"{label} must be one of: {ctx.get('expected')}.",
        "literal_error": f"{label} must be one of: {ctx.get('expected')}.",
    }
    return rules.get(error_type, f"{label} is not valid.")


def _detail(error: Mapping[str, Any]) -> ErrorDetail:
    field = _field_path(error["loc"])
    last = str(error["loc"][-1]) if error["loc"] else "value"
    label = last.replace("_", " ").capitalize()
    return ErrorDetail(
        field=field,
        issue=_issue(error["type"]),
        message=_message(label, error["type"], error.get("ctx") or {}),
    )


def translate_validation_errors(errors: Sequence[Mapping[str, Any]]) -> TranslatedValidation:
    """Map Pydantic errors to the API contract. Never copies the rejected input."""
    if any(error["type"] == "json_invalid" for error in errors):
        message = "The request body is not valid JSON."
        return TranslatedValidation(400, ErrorCode.INVALID_REQUEST, message, [])
    if errors and all(error["loc"] and error["loc"][0] == "path" for error in errors):
        return TranslatedValidation(404, ErrorCode.NOT_FOUND, "Resource not found.", [])
    details = [_detail(error) for error in errors]
    if all(
        len(error["loc"]) > 1
        and error["loc"][0] == "query"
        and error["loc"][1] in _PAGINATION_PARAMS
        for error in errors
    ):
        message = "The pagination parameters are invalid."
        return TranslatedValidation(400, ErrorCode.INVALID_REQUEST, message, details)
    return TranslatedValidation(
        422, ErrorCode.VALIDATION_ERROR, "Some fields are invalid.", details
    )


# --- handlers ----------------------------------------------------------------------------------


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):  # pragma: no cover - guaranteed by registration
        raise exc
    if exc.status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        capture(exc, route=route_template(request.scope), error_code=exc.code.value)
    return error_response(exc.status, exc.code, exc.message, exc.details, exc.headers)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):  # pragma: no cover
        raise exc
    translated = translate_validation_errors(exc.errors())
    return error_response(
        translated.status, translated.code, translated.message, translated.details
    )


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):  # pragma: no cover
        raise exc
    status = exc.status_code
    if isinstance(exc, PayloadTooLargeError):
        return error_response(413, ErrorCode.PAYLOAD_TOO_LARGE, exc.message)
    if status == HTTPStatus.NOT_FOUND:
        return error_response(404, ErrorCode.NOT_FOUND, "The requested resource was not found.")
    if status == HTTPStatus.METHOD_NOT_ALLOWED:
        return error_response(
            405, ErrorCode.INVALID_REQUEST, "This method is not allowed here.", headers=exc.headers
        )
    if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        capture(exc, route=route_template(request.scope))
        return error_response(status, ErrorCode.INTERNAL_ERROR, INTERNAL_ERROR_MESSAGE)
    return error_response(
        status,
        ErrorCode.INVALID_REQUEST,
        "The request could not be processed.",
        headers=exc.headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Unexpected exceptions are handled by `RequestContextMiddleware` (see middleware.py)."""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
