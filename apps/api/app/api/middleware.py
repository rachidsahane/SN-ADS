"""Request id, JSON request log, security headers, body-size and media-type guards.

Written as pure ASGI middleware (not BaseHTTPMiddleware) so that context variables, error
responses and headers behave the same for every response, including a 500.
"""

import time
import uuid
from dataclasses import dataclass
from typing import Final, Literal

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import (
    ErrorCode,
    PayloadTooLargeError,
    error_response,
    internal_error_response,
)
from app.infra.observability import get_logger
from app.infra.request_context import bind_context, reset_context, route_template

REQUEST_ID_HEADER: Final = "X-Request-ID"
MAX_JSON_BODY_BYTES: Final = 64 * 1024
MULTIPART_OVERHEAD_BYTES: Final = 64 * 1024
BODY_METHODS: Final = frozenset({"POST", "PUT", "PATCH"})
QUIET_PATHS: Final = frozenset({"/api/health", "/api/ready"})
MAX_LOGGED_PATH: Final = 200
SERVER_ERROR: Final = 500

SECURITY_HEADERS: Final[dict[str, str]] = {
    "Strict-Transport-Security": "max-age=31536000",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}

logger = get_logger("app.request")


def resolve_request_id(candidate: str | None) -> str:
    """Reuse a client-supplied UUID, otherwise generate one. Never echo anything else."""
    if candidate:
        try:
            return str(uuid.UUID(candidate.strip()))
        except ValueError:
            pass
    return str(uuid.uuid4())


@dataclass
class _ResponseState:
    status: int = SERVER_ERROR
    started: bool = False


class RequestContextMiddleware:
    """Outermost middleware: owns the request id, the request log and the 500 fallback."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = resolve_request_id(Headers(scope=scope).get(REQUEST_ID_HEADER))
        token = bind_context(request_id=request_id)
        state = _ResponseState()
        started_at = time.perf_counter()

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                state.status, state.started = message["status"], True
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        try:
            await self._run(scope, receive, send_with_headers, state)
        finally:
            self._log(scope, state.status, time.perf_counter() - started_at)
            reset_context(token)

    async def _run(self, scope: Scope, receive: Receive, send: Send, state: _ResponseState) -> None:
        try:
            await self.app(scope, receive, send)
        except ClientDisconnect:
            logger.info("client_disconnected")
        except Exception as exc:
            if state.started:
                raise
            await internal_error_response(exc, route=route_template(scope))(scope, receive, send)

    @staticmethod
    def _log(scope: Scope, status: int, elapsed: float) -> None:
        path = str(scope.get("path", ""))[:MAX_LOGGED_PATH]
        log = logger.error if status >= SERVER_ERROR else logger.info
        if path in QUIET_PATHS and status < SERVER_ERROR:
            log = logger.debug
        log(
            "request",
            method=scope.get("method"),
            path=path,
            route=route_template(scope),
            status=status,
            duration_ms=round(elapsed * 1000, 1),
        )


MediaKind = Literal["json", "multipart"]


def _media_kind(content_type: str | None) -> MediaKind | None:
    essence = (content_type or "").split(";")[0].strip().lower()
    if essence == "application/json" or essence.endswith("+json"):
        return "json"
    if essence == "multipart/form-data":
        return "multipart"
    return None


class RequestGuardMiddleware:
    """Refuse unsupported media types (415) and oversized bodies (413) before any parsing."""

    def __init__(self, app: ASGIApp, *, max_upload_bytes: int) -> None:
        self.app = app
        self.max_upload_bytes = max_upload_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in BODY_METHODS:
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        length_header = headers.get("content-length")
        has_body = "transfer-encoding" in headers or length_header not in (None, "0")
        if not has_body:
            await self.app(scope, receive, send)
            return
        kind = _media_kind(headers.get("content-type"))
        if kind is None:
            message = "Unsupported content type. Send application/json."
            response = error_response(415, ErrorCode.UNSUPPORTED_MEDIA_TYPE, message)
            await response(scope, receive, send)
            return
        limit = MAX_JSON_BODY_BYTES
        message = "The request body is too large (64 KB maximum)."
        if kind == "multipart":
            limit = self.max_upload_bytes + MULTIPART_OVERHEAD_BYTES
            message = (
                f"The file is too large ({self.max_upload_bytes // (1024 * 1024)} MB maximum)."
            )
        if length_header is not None and length_header.isdigit() and int(length_header) > limit:
            response = error_response(413, ErrorCode.PAYLOAD_TOO_LARGE, message)
            await response(scope, receive, send)
            return
        await self.app(scope, self._limited(receive, limit, message), send)

    @staticmethod
    def _limited(receive: Receive, limit: int, error_message: str) -> Receive:
        """Count streamed bytes too: a client can omit or lie about Content-Length."""
        total = 0

        async def limited_receive() -> Message:
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > limit:
                    raise PayloadTooLargeError(error_message)
            return message

        return limited_receive
