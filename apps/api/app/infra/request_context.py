"""Per-request context (request id, user id) read by the logs and, later, by Sentry."""

from collections.abc import Mapping
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any


@dataclass
class RequestContext:
    """Mutable on purpose: a value set in a worker thread stays visible to the middleware."""

    request_id: str | None = None
    user_id: str | None = None


_current: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def bind_context(
    request_id: str | None = None, user_id: str | None = None
) -> Token[RequestContext | None]:
    return _current.set(RequestContext(request_id=request_id, user_id=user_id))


def reset_context(token: Token[RequestContext | None]) -> None:
    _current.reset(token)


def get_request_id() -> str | None:
    context = _current.get()
    return context.request_id if context else None


def get_user_id() -> str | None:
    context = _current.get()
    return context.user_id if context else None


def set_user_id(user_id: str | None) -> None:
    """Attach the authenticated user (UUID only) to the current request, if there is one."""
    context = _current.get()
    if context is not None:
        context.user_id = user_id


def route_template(scope: Mapping[str, Any]) -> str | None:
    """Matched route as a template (`/api/v1/predictions/{prediction_id}`), None if unmatched.

    Rebuilt from the real path: with FastAPI 0.142 `scope["route"].path` loses the outer
    `/api` prefix of nested routers. Templates keep log and Sentry cardinality low.
    """
    if scope.get("route") is None:
        return None
    path = str(scope.get("path", ""))
    for name, value in scope.get("path_params", {}).items():
        path = path.replace(f"/{value}", f"/{{{name}}}", 1)
    return path
