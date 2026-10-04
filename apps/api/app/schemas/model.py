"""Model versions, the active model and the dataset summary (API_SPEC 6.5, 6.7, 6.8, simplified)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

TrainingStatus = Literal["queued", "running", "succeeded", "failed"]
Reliability = Literal["low", "moderate", "good"]
DataScope = Literal["all", "agency_only"]


class TargetMetrics(BaseModel):
    mae: float
    rmse: float
    r2: float
    baseline_mae: float
    reliability: Reliability


class ModelMetrics(BaseModel):
    click_through_rate: TargetMetrics
    conversion_rate: TargetMetrics
    website_visits: TargetMetrics
    overall_reliability: Reliability


class ImportanceShare(BaseModel):
    field: str
    share: float


class GlobalImportance(BaseModel):
    click_through_rate: list[ImportanceShare]
    conversion_rate: list[ImportanceShare]
    website_visits: list[ImportanceShare]


class Requester(BaseModel):
    id: uuid.UUID
    full_name: str


class ModelVersion(BaseModel):
    """One row of the list."""

    id: uuid.UUID
    version: int
    status: TrainingStatus
    data_scope: DataScope
    is_active: bool
    created_at: datetime
    finished_at: datetime | None
    requested_by: Requester | None


class ModelVersionDetail(ModelVersion):
    metrics: ModelMetrics | None
    global_importance: GlobalImportance | None
    features_used: list[str] | None
    train_row_count: int | None
    holdout_row_count: int | None
    error_message: str | None
    started_at: datetime | None
    activated_at: datetime | None


class ModelVersionList(BaseModel):
    items: list[ModelVersion]


class ActiveModel(BaseModel):
    """GET /api/v1/model/active, readable by every signed-in user."""

    id: uuid.UUID
    version: int
    data_scope: DataScope
    trained_at: datetime | None
    activated_at: datetime | None
    train_row_count: int | None
    holdout_row_count: int | None
    reliability: Reliability
    metrics: ModelMetrics
    global_importance: GlobalImportance


class DatasetSummary(BaseModel):
    seed_rows: int
    agency_rows: int
    holdout_rows: int
    seed_loaded_at: datetime | None = None  # when the starting dataset was loaded
    agency_loaded_at: datetime | None = None  # when the first agency rows were imported


class DatasetUploadResult(BaseModel):
    """201 of POST /api/v1/admin/dataset/upload."""

    rows_imported: int
    agency_rows_total: int
