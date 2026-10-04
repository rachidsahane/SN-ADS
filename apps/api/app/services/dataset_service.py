"""Summary of the training data for the administrator (API_SPEC 6.7, simplified)."""

from datetime import datetime

from supabase import Client

from app.repositories import dataset_repo
from app.schemas.model import DatasetSummary
from app.services.backend import BACKEND_ERRORS, unavailable


def summary(db: Client) -> DatasetSummary:
    try:
        loaded_at = dataset_repo.first_loaded_at(db, source="seed")
        return DatasetSummary(
            seed_rows=dataset_repo.count_rows(db, source="seed"),
            agency_rows=dataset_repo.count_rows(db, source="agency"),
            holdout_rows=dataset_repo.count_rows(db, holdout=True),
            seed_loaded_at=datetime.fromisoformat(loaded_at) if loaded_at else None,
        )
    except BACKEND_ERRORS as error:
        raise unavailable(error, "dataset_summary") from None
