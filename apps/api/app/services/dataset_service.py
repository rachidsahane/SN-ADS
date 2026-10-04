"""Summary of the training data and import of an agency CSV file (API_SPEC 6.7, simplified)."""

import uuid
from datetime import datetime
from typing import Final

from postgrest.exceptions import APIError
from supabase import Client

from app.api.errors import AppError, ErrorCode
from app.domain.csv_validation import MAX_LISTED_ISSUES, validate_csv
from app.domain.holdout import is_holdout
from app.repositories import dataset_repo
from app.schemas.common import ErrorDetail
from app.schemas.model import DatasetSummary, DatasetUploadResult
from app.services import audit_service
from app.services.backend import BACKEND_ERRORS, unavailable

SOURCE: Final = "agency"
BATCH_SIZE: Final = 1000
UNIQUE_VIOLATION: Final = "23505"
ALREADY_IMPORTED_MESSAGE: Final = "This file has already been imported."
CONCURRENT_IMPORT_MESSAGE: Final = (
    "Some campaign numbers were imported while this file was being processed. "
    "Upload the file again."
)
FILE_NAME_LENGTH: Final = 100


def summary(db: Client) -> DatasetSummary:
    try:
        seed_loaded_at = dataset_repo.first_loaded_at(db, source="seed")
        agency_loaded_at = dataset_repo.first_loaded_at(db, source=SOURCE)
        return DatasetSummary(
            seed_rows=dataset_repo.count_rows(db, source="seed"),
            agency_rows=dataset_repo.count_rows(db, source=SOURCE),
            holdout_rows=dataset_repo.count_rows(db, holdout=True),
            seed_loaded_at=datetime.fromisoformat(seed_loaded_at) if seed_loaded_at else None,
            agency_loaded_at=datetime.fromisoformat(agency_loaded_at) if agency_loaded_at else None,
        )
    except BACKEND_ERRORS as error:
        raise unavailable(error, "dataset_summary") from None


def _errors_message(total: int) -> str:
    noun = "error" if total == 1 else "errors"
    tail = f" The first {MAX_LISTED_ISSUES} are listed." if total > MAX_LISTED_ISSUES else ""
    return f"The file contains {total:,} {noun}.{tail}"


def _clean_file_name(name: str | None) -> str:
    """The name shown in the audit log: no folders, at most 100 characters."""
    base = (name or "file.csv").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return (base or "file.csv")[:FILE_NAME_LENGTH]


def import_agency_csv(db: Client, *, content: bytes, file_name: str | None) -> DatasetUploadResult:
    """Validate the whole file, then add its rows as source 'agency' with the caller's own client
    (RLS lets administrators insert agency rows only). A file with a problem adds nothing."""
    try:
        existing = dataset_repo.agency_external_ids(db)
    except BACKEND_ERRORS as error:
        raise unavailable(error, "dataset_upload") from None
    checked = validate_csv(content, existing)
    if checked.already_imported:
        raise AppError(ErrorCode.DUPLICATE_UPLOAD, 409, ALREADY_IMPORTED_MESSAGE)
    if checked.total_issues:
        details = [
            ErrorDetail(row=i.row, column=i.column, field=None, issue="invalid", message=i.message)
            for i in checked.issues
        ]
        raise AppError(
            ErrorCode.CSV_INVALID, 422, _errors_message(checked.total_issues), details=details
        )

    rows = [
        {**row, "source": SOURCE, "is_holdout": is_holdout(SOURCE, int(str(row["external_id"])))}
        for row in checked.rows
    ]
    try:
        for start in range(0, len(rows), BATCH_SIZE):
            dataset_repo.add_rows(db, rows[start : start + BATCH_SIZE])
        total = dataset_repo.count_rows(db, source=SOURCE)
    except APIError as error:
        if error.code == UNIQUE_VIOLATION:
            raise AppError(
                ErrorCode.DUPLICATE_EXTERNAL_ID, 409, CONCURRENT_IMPORT_MESSAGE
            ) from None
        raise unavailable(error, "dataset_upload") from None
    except BACKEND_ERRORS as error:
        raise unavailable(error, "dataset_upload") from None
    audit_service.record(
        db,
        action="upload.accepted",
        target_type="upload",
        target_id=str(uuid.uuid4()),
        metadata={"file_name": _clean_file_name(file_name), "row_count": len(rows)},
    )
    return DatasetUploadResult(rows_imported=len(rows), agency_rows_total=total)
