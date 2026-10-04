"""Activate a succeeded version (demo: no comparison, no verdict)."""

import uuid

from postgrest.exceptions import APIError
from supabase import Client

from app.api.errors import from_postgrest
from app.config import Settings
from app.infra.observability import capture
from app.repositories import model_versions_repo as repo
from app.schemas.model import ModelVersionDetail
from app.services import audit_service, model_version_service
from app.services.backend import BACKEND_ERRORS, unavailable
from app.services.model_registry import get_registry


def activate(db: Client, version_id: uuid.UUID, *, settings: Settings) -> ModelVersionDetail:
    """The database switches the active version atomically and refuses a version that did not
    succeed (409) or does not exist (404)."""
    try:
        repo.activate(db, version_id)
    except APIError as error:
        business = from_postgrest(error)
        if business is not None:
            raise business from None
        raise unavailable(error, "activate_model", model_version_id=str(version_id)) from None
    except BACKEND_ERRORS as error:
        raise unavailable(error, "activate_model", model_version_id=str(version_id)) from None
    audit_service.record(
        db,
        action="model.activated",
        target_type="model_version",
        target_id=str(version_id),
        metadata={},
    )
    try:
        get_registry(settings).refresh(force=True)
    except Exception as error:  # the pointer moved; the files are checked on next use
        capture(error, operation="registry_refresh", model_version_id=str(version_id))
    return model_version_service.get_version(db, version_id)
