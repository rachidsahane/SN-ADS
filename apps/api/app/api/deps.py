"""FastAPI dependencies. Authentication and rate limiting arrive in later phases."""

from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings
from app.services.readiness_service import DatabaseCheck, check_database


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_database_check(settings: Annotated[Settings, Depends(get_settings)]) -> DatabaseCheck:
    """Probe the database. Synchronous on purpose: FastAPI runs it in its thread pool."""
    return check_database(settings)
