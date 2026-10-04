"""Summary of the training data for the administrator (API_SPEC 6.7, simplified)."""

from supabase import Client

from app.repositories import dataset_repo
from app.schemas.model import DatasetSummary
from app.services.backend import BACKEND_ERRORS, unavailable


def summary(db: Client) -> DatasetSummary:
    try:
        return DatasetSummary(
            seed_rows=dataset_repo.count_rows(db, source="seed"),
            agency_rows=dataset_repo.count_rows(db, source="agency"),
            holdout_rows=dataset_repo.count_rows(db, holdout=True),
        )
    except BACKEND_ERRORS as error:
        raise unavailable(error, "dataset_summary") from None
