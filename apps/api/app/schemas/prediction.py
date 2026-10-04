"""Campaign input, prediction result and form reference (API_SPEC 5.1, 5.2, 6.3, 6.4)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Channel = Literal["Social Media", "Email", "PPC", "SEO", "Referral"]
CampaignType = Literal["Awareness", "Consideration", "Conversion", "Retention"]
Gender = Literal["Male", "Female"]
Level = Literal["low", "medium", "high"]
OptionalText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
Count = Annotated[int, Field(ge=0, le=10_000_000)]


class CampaignInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_channel: Channel
    campaign_type: CampaignType
    ad_spend: float = Field(gt=0, le=10_000_000, allow_inf_nan=False)
    age: int = Field(ge=18, le=100)
    gender: Gender
    income: int = Field(ge=0, le=100_000_000)
    previous_purchases: int = Field(ge=0, le=10_000)
    loyalty_points: Count
    pages_per_visit: float = Field(ge=0, le=1000, allow_inf_nan=False)
    time_on_site: float = Field(ge=0, le=1440, allow_inf_nan=False)
    social_shares: Count
    email_opens: Count
    email_clicks: Count
    advertising_platform: OptionalText | None = None
    advertising_tool: OptionalText | None = None

    @field_validator("advertising_platform", "advertising_tool")
    @classmethod
    def _printable(cls, value: str | None) -> str | None:
        if value is not None and not value.isprintable():
            raise ValueError("Use printable characters only.")
        return value


class ModelRef(BaseModel):
    id: uuid.UUID
    version: int


class Predictions(BaseModel):
    click_through_rate: float
    conversion_rate: float
    website_visits: float


class Derived(BaseModel):
    estimated_leads: float
    estimated_cost_per_result: float | None


class Notes(BaseModel):
    click_through_rate: float
    estimated_leads: float
    estimated_cost_per_result: float


class Thresholds(BaseModel):
    low_below: float
    high_from: float


class Performance(BaseModel):
    score: float
    level: Level
    notes: Notes
    thresholds: Thresholds
    reference: Literal["campaign_type", "all_types"]


class Driver(BaseModel):
    field: str
    value: str | float | int | None
    contribution: float
    direction: Literal["up", "down"]


class Drivers(BaseModel):
    click_through_rate: list[Driver]
    conversion_rate: list[Driver]
    website_visits: list[Driver]


class Recommendation(BaseModel):
    lever: str
    from_value: str | float | int | None
    to_value: str | float | int | None
    score_gain: float
    new_score: float
    new_level: Level
    new_predictions: Predictions
    new_derived: Derived


class Recommendations(BaseModel):
    status: Literal["found", "none_significant"]
    items: list[Recommendation]


class PredictionWarning(BaseModel):
    code: Literal["LOW_MODEL_RELIABILITY", "OUT_OF_TRAINING_RANGE", "REFERENCE_FALLBACK"]
    field: str | None
    message: str


class PredictionResult(BaseModel):
    id: uuid.UUID | None
    created_at: datetime | None
    label: str | None
    model_version: ModelRef
    input: CampaignInput
    predictions: Predictions
    derived: Derived
    performance: Performance
    drivers: Drivers
    recommendations: Recommendations
    warnings: list[PredictionWarning]


class ReferenceOptions(BaseModel):
    currency: Literal["USD"]
    enums: dict[str, list[str]]
    limits: dict[str, dict[str, float]]
    training_ranges: dict[str, dict[str, float]]
    features_used: list[str]
    optional_categories: dict[str, list[str]]
    model_version: ModelRef | None


class EngagementDefaults(BaseModel):
    pages_per_visit: float
    time_on_site: float
    social_shares: int
    email_opens: int
    email_clicks: int
    basis: Literal["channel_and_type", "channel", "all"]


class SavePredictionRequest(BaseModel):
    """Only the campaign and a name are sent: the results are recomputed by the server."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    input: CampaignInput


class PredictionSummary(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    level: Level
    model_version: int


class PredictionList(BaseModel):
    items: list[PredictionSummary]
