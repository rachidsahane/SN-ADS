"""/api/v1/admin/dataset: the summary of the rows the models learn from and the import of an agency
CSV file (API_SPEC 6.7, simplified)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, UploadFile
from supabase import Client

from app.api.deps import get_settings, get_user_db
from app.api.errors import AppError, ErrorCode
from app.config import Settings
from app.schemas.common import ErrorResponse
from app.schemas.model import DatasetSummary, DatasetUploadResult
from app.services import dataset_service

router = APIRouter(prefix="/dataset", tags=["admin-dataset"])

# Browsers label a CSV differently (Excel on Windows says application/vnd.ms-excel).
CSV_CONTENT_TYPES = frozenset(
    {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"}
)
NOT_CSV_MESSAGE = "Only CSV files are accepted."

_COMMON: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired token."},
    403: {"model": ErrorResponse, "description": "The caller is not an active administrator."},
    503: {"model": ErrorResponse, "description": "The database is unavailable."},
}


@router.get(
    "/summary",
    response_model=DatasetSummary,
    responses=_COMMON,
    summary="Dataset summary",
)
def dataset_summary(db: Annotated[Client, Depends(get_user_db)]) -> DatasetSummary:
    return dataset_service.summary(db)


@router.post(
    "/upload",
    status_code=201,
    response_model=DatasetUploadResult,
    responses={
        **_COMMON,
        409: {"model": ErrorResponse, "description": "The file has already been imported."},
        413: {"model": ErrorResponse, "description": "The file is too large."},
        415: {"model": ErrorResponse, "description": "The file is not a CSV file."},
        422: {"model": ErrorResponse, "description": "The file has problems (CSV_INVALID)."},
    },
    summary="Import an agency CSV file",
)
def upload_dataset(
    file: UploadFile,
    db: Annotated[Client, Depends(get_user_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetUploadResult:
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    name = file.filename or ""
    if content_type not in CSV_CONTENT_TYPES or not name.lower().endswith(".csv"):
        raise AppError(ErrorCode.UNSUPPORTED_MEDIA_TYPE, 415, NOT_CSV_MESSAGE)
    content = file.file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes // (1024 * 1024)
        raise AppError(
            ErrorCode.PAYLOAD_TOO_LARGE, 413, f"The file is too large ({limit_mb} MB maximum)."
        )
    return dataset_service.import_agency_csv(db, content=content, file_name=name)
