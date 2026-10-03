"""JSON logging and error reporting.

Before phase 16 errors are only logged locally. Phase 16 plugs Sentry into `init_observability`
and `capture` without touching their callers.
"""

import logging
import sys
import uuid
from collections.abc import Mapping
from typing import Any, Final

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

from app.config import Settings
from app.infra.request_context import get_request_id, get_user_id

REDACTED: Final = "[redacted]"
SENSITIVE_KEYS: Final = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "service_role_key",
        "jwt",
        "email",
        "full_name",
    }
)
NOISY_LIBRARIES: Final = ("httpx", "httpcore", "asyncio")
_HANDLER_MARK: Final = "_soronua_json_handler"
_MAX_REDACTION_DEPTH: Final = 5


def _redact(value: Any, depth: int = 0) -> Any:  # arbitrary log payloads: any type is intended
    if isinstance(value, Mapping) and depth < _MAX_REDACTION_DEPTH:
        return {
            key: REDACTED if str(key).lower() in SENSITIVE_KEYS else _redact(item, depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple) and depth < _MAX_REDACTION_DEPTH:
        return [_redact(item, depth + 1) for item in value]
    return value


def _redact_processor(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    return {
        key: REDACTED if str(key).lower() in SENSITIVE_KEYS else _redact(value)
        for key, value in event_dict.items()
    }


def _request_context_processor(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    request_id, user_id = get_request_id(), get_user_id()
    if request_id and "request_id" not in event_dict:
        event_dict["request_id"] = request_id
    if user_id and "user_id" not in event_dict:
        event_dict["user_id"] = user_id
    return event_dict


def _static_fields(settings: Settings) -> Processor:
    fields = {
        "service": settings.service_name,
        "environment": settings.app_env,
        "release": settings.app_release,
    }

    def processor(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
        for key, value in fields.items():
            event_dict.setdefault(key, value)
        return event_dict

    return processor


class StdoutHandler(logging.Handler):
    """Writes to whatever `sys.stdout` is at emit time (container logs, and test capture)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stdout.write(self.format(record) + "\n")
            sys.stdout.flush()
        except Exception:  # logging must never raise: standard handler contract
            self.handleError(record)


def configure_logging(settings: Settings) -> None:
    """Send every log (ours, uvicorn's, libraries') to stdout as one JSON object per line."""
    shared: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        _static_fields(settings),
        _request_context_processor,
        _redact_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    handler = StdoutHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
    )
    setattr(handler, _HANDLER_MARK, True)
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not getattr(h, _HANDLER_MARK, False)]
    root.addHandler(handler)
    root.setLevel(settings.log_level)
    for name in ("uvicorn", "uvicorn.error"):
        library_logger = logging.getLogger(name)
        library_logger.handlers.clear()
        library_logger.propagate = True
    access_logger = logging.getLogger("uvicorn.access")  # replaced by the request log
    access_logger.handlers.clear()
    access_logger.propagate = False
    for name in NOISY_LIBRARIES:  # their INFO lines contain full URLs, i.e. query values
        logging.getLogger(name).setLevel(max(logging.WARNING, root.level))


def init_observability(settings: Settings) -> None:
    """Configure logging. Sentry is added here in phase 16 (DSN from `settings.sentry_dsn`)."""
    configure_logging(settings)


def get_logger(name: str = "app") -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name)


def capture(exc: BaseException, **context: object) -> str:
    """Report an unexpected exception and return its reference (event id).

    `context` carries business identifiers (route, model_version_id...), never personal data;
    sensitive keys are redacted anyway.
    """
    event_id = uuid.uuid4().hex
    get_logger("app.errors").error(
        "unexpected_error",
        event_id=event_id,
        error_type=type(exc).__name__,
        exc_info=exc,
        **context,
    )
    return event_id
