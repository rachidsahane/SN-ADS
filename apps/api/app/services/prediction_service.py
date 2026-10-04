"""Simulation of one campaign: three figures, derived figures, score, factors and advice
(LLD 6.1 to 6.8). Nothing is stored."""

import uuid
from typing import Any

import pandas as pd
from supabase import Client

from app.api.errors import AppError, ErrorCode
from app.config import Settings
from app.domain.dataset_schema import CATEGORICAL, ENGAGEMENT, LIMITS, NUMERIC, OPTIONAL, TARGETS
from app.domain.derived_metrics import estimated_cost_per_result, estimated_leads
from app.domain.engagement_defaults import defaults_for
from app.domain.explanations import top_drivers
from app.domain.recommendations import build_candidates, pick_best
from app.domain.scoring import PerformanceScore, ScoringReference, level_for, score_campaign
from app.domain.warnings import build_warnings
from app.ml.predictor import Predictor
from app.repositories import model_versions_repo as repo
from app.schemas.common import ErrorDetail
from app.schemas.prediction import (
    CampaignInput,
    EngagementDefaults,
    ModelRef,
    PredictionResult,
    ReferenceOptions,
)
from app.services.backend import BACKEND_ERRORS, unavailable
from app.services.model_registry import get_registry
from app.services.model_version_service import NO_ACTIVE_MESSAGE

CAMPAIGN_FIELDS = (*CATEGORICAL, *NUMERIC, *OPTIONAL)
MISSING_FIELD_MESSAGE = "This field is required by the active model."


def active_predictor(db: Client, settings: Settings) -> tuple[Predictor, ModelRef] | None:
    """The active predictor and its version, or None. The pointer is read as the caller; the
    registry is reloaded at once when it is behind."""
    try:
        ref = repo.active_ref(db)
        if ref is None:
            return None
        registry = get_registry(settings)
        predictor = registry.current()
        if predictor is None or predictor.version_id != ref[0]:
            registry.refresh(force=True)
            predictor = registry.current()
    except BACKEND_ERRORS as error:
        raise unavailable(error, "active_predictor") from None
    if predictor is None or predictor.version_id != ref[0]:
        return None
    return predictor, ModelRef(id=uuid.UUID(ref[0]), version=ref[1])


def require_predictor(db: Client, settings: Settings) -> tuple[Predictor, ModelRef]:
    active = active_predictor(db, settings)
    if active is None:
        raise AppError(ErrorCode.NO_ACTIVE_MODEL, 409, NO_ACTIVE_MESSAGE)
    return active


def reference_options(db: Client, settings: Settings) -> ReferenceOptions:
    """The form description; without an active model the page shows a banner (no error)."""
    active = active_predictor(db, settings)
    bundle = active[0].bundle if active else None
    spec = bundle.spec if bundle else None
    return ReferenceOptions(
        currency="USD",
        enums={name: list(values) for name, values in CATEGORICAL.items()},
        limits={name: dict(bounds) for name, bounds in LIMITS.items()},
        training_ranges=bundle.training_ranges if bundle else {},
        features_used=spec.features_used if spec else [],
        optional_categories={
            name: [v for v in spec.optional_categories.get(name, ()) if not v.startswith("__")]
            for name in OPTIONAL
        }
        if spec
        else {},
        model_version=active[1] if active else None,
    )


def engagement_defaults(
    predictor: Predictor, campaign_channel: str, campaign_type: str
) -> EngagementDefaults:
    found = defaults_for(predictor.bundle.engagement_defaults, campaign_channel, campaign_type)
    return EngagementDefaults(**{name: found[name] for name in ENGAGEMENT}, basis=found["basis"])


def _frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=list(CAMPAIGN_FIELDS))
    frame[list(OPTIONAL)] = frame[list(OPTIONAL)].fillna("")
    return frame


def _figures(
    predicted: dict[str, float], ad_spend: float, campaign_type: str, reference: ScoringReference
) -> tuple[dict[str, float], dict[str, float | None], PerformanceScore]:
    leads = estimated_leads(predicted["website_visits"], predicted["conversion_rate"])
    cost = estimated_cost_per_result(ad_spend, leads)
    score = score_campaign(predicted["click_through_rate"], leads, cost, campaign_type, reference)
    shown = {
        "click_through_rate": round(predicted["click_through_rate"], 4),
        "conversion_rate": round(predicted["conversion_rate"], 4),
        "website_visits": round(predicted["website_visits"], 2),
    }
    derived = {
        "estimated_leads": round(leads, 2),
        "estimated_cost_per_result": None if cost is None else round(cost, 2),
    }
    return shown, derived, score


def simulate(predictor: Predictor, model: ModelRef, campaign: CampaignInput) -> PredictionResult:
    bundle = predictor.bundle
    values = campaign.model_dump()
    for name in bundle.spec.optional_categories:  # the model uses this field: it is required
        if values[name] is None:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                422,
                MISSING_FIELD_MESSAGE,
                [ErrorDetail(field=name, issue="required", message=MISSING_FIELD_MESSAGE)],
            )
    candidates = build_candidates(values, bundle.spec.optional_categories)
    rows = [values, *(c.inputs for c in candidates)]
    frame = _frame(rows)
    batch = predictor.predict(frame)  # the input and every variant, in one batch
    reference = bundle.scoring_reference
    figures = [
        _figures(
            {t: float(batch[t][i]) for t in TARGETS},
            float(row["ad_spend"]),
            str(row["campaign_type"]),
            reference,
        )
        for i, row in enumerate(rows)
    ]
    shown, derived, score = figures[0]
    picked = pick_best(candidates, [f[2].score for f in figures[1:]], score.score)
    contributions = predictor.contributions(frame.iloc[[0]])
    items = []
    for index, gain in picked:
        c_shown, c_derived, c_score = figures[index + 1]
        candidate = candidates[index]
        items.append(
            {
                "lever": candidate.lever,
                "from_value": candidate.from_value,
                "to_value": candidate.to_value,
                "score_gain": gain,
                "new_score": c_score.score,
                "new_level": level_for(c_score.score, reference),
                "new_predictions": c_shown,
                "new_derived": c_derived,
            }
        )
    return PredictionResult.model_validate(
        {
            "id": None,
            "created_at": None,
            "label": None,
            "model_version": model,
            "input": campaign,
            "predictions": shown,
            "derived": derived,
            "performance": {
                "score": score.score,
                "level": level_for(score.score, reference),
                "notes": {
                    "click_through_rate": round(score.ctr_note, 1),
                    "estimated_leads": round(score.leads_note, 1),
                    "estimated_cost_per_result": round(score.cost_note, 1),
                },
                "thresholds": {"low_below": reference.low_below, "high_from": reference.high_from},
                "reference": "all_types" if score.reference_fallback else "campaign_type",
                "averages": bundle.target_means,
            },
            "drivers": {t: top_drivers(contributions[t].iloc[0], values) for t in TARGETS},
            "recommendations": {
                "status": "found" if items else "none_significant",
                "items": items,
            },
            "warnings": build_warnings(
                reliability=bundle.metrics["overall_reliability"],
                values=values,
                ranges=bundle.training_ranges,
                reference_fallback=score.reference_fallback,
            ),
        }
    )
