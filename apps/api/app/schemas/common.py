"""Schemas shared by all routes: health and the standard error body (API_SPEC section 3)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    release: str


class ReadyChecks(BaseModel):
    """One entry per backing service. Unchecked services are omitted (None): `model` is filled in
    phase 8."""

    model_config = ConfigDict(extra="forbid")

    database: Literal["ok", "error"]
    cache: Literal["ok", "error"] | None = None
    model: Literal["ok", "none_active", "error"] | None = None


class ReadyResponse(BaseModel):
    """Body of GET /api/ready, for 200 and 503 alike."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_ready"]
    checks: ReadyChecks
    schema_version: str | None = None
    release: str


class ErrorDetail(BaseModel):
    """One problem. CSV imports also fill `row` and `column`."""

    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    row: int | None = None
    column: str | None = None
    issue: str
    message: str


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: list[ErrorDetail]
    request_id: str | None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody
