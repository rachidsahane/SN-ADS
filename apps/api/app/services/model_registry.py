"""The active Predictor, loaded lazily from the model volume and reloaded when the active version
changes. Closed list of service-key holders (ARCHITECTURE 2.5): it reads the pointer with the
service client because the callers are all users."""

import threading
import time
from functools import lru_cache
from pathlib import Path

from app.config import Settings
from app.infra.supabase_clients import get_service_client
from app.ml.bundle import load_bundle
from app.ml.predictor import Predictor
from app.repositories import model_versions_repo

CHECK_EVERY_SECONDS = 30.0


class ModelRegistry:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._predictor: Predictor | None = None
        self._checked_at = float("-inf")
        self._lock = threading.Lock()

    def current(self) -> Predictor | None:
        """The active predictor, or None when no version is active."""
        self.refresh()
        return self._predictor

    def refresh(self, *, force: bool = False) -> None:
        with self._lock:
            if not force and time.monotonic() - self._checked_at < CHECK_EVERY_SECONDS:
                return
            active = model_versions_repo.active_id(get_service_client(self._settings))
            if active is None:
                self._predictor = None
            elif force or self._predictor is None or self._predictor.version_id != active:
                directory = Path(self._settings.model_dir) / "versions" / active
                self._predictor = Predictor(load_bundle(directory))
            self._checked_at = time.monotonic()


@lru_cache(maxsize=1)
def get_registry(settings: Settings) -> ModelRegistry:
    return ModelRegistry(settings)
