"""Backend failures shared by the services: what counts as "the database is down", and the 503."""

from typing import Final

import httpx
from postgrest.exceptions import APIError

from app.api.errors import UNAVAILABLE_MESSAGE, AppError, ErrorCode
from app.infra.observability import capture

BACKEND_ERRORS: Final = (httpx.HTTPError, httpx.InvalidURL, APIError)


def unavailable(error: BaseException, operation: str, **ids: str) -> AppError:
    """Report the failure (operation and ids only), build the 503."""
    capture(error, operation=operation, **ids)
    return AppError(ErrorCode.SERVICE_UNAVAILABLE, 503, UNAVAILABLE_MESSAGE)
