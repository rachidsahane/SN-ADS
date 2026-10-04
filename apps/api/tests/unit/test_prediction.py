"""Prediction: input bounds, factors, warnings, recommendations and the simulation (LLD 6.x)."""

import uuid
from typing import Any

import pandas as pd
import pytest
from pydantic import ValidationError

from app.api.errors import AppError
from app.domain.dataset_schema import CATEGORICAL, LIMITS
from app.domain.explanations import top_drivers
from app.domain.recommendations import Candidate, build_candidates, pick_best
from app.domain.warnings import build_warnings
from app.ml.bundle import ModelBundle
from app.ml.predictor import Predictor
from app.ml.training import train
from app.schemas.prediction import CampaignInput, ModelRef
from app.services import prediction_service
from tests.data_factory import make_frame

MODEL = ModelRef(id=uuid.UUID("11111111-1111-1111-1111-111111111111"), version=1)
INPUT: dict[str, Any] = {
    "campaign_channel": "Social Media",
    "campaign_type": "Awareness",
    "ad_spend": 5000,
    "age": 35,
    "gender": "Female",
    "income": 60000,
    "previous_purchases": 2,
    "loyalty_points": 1000,
    "pages_per_visit": 5.5,
    "time_on_site": 7.5,
    "social_shares": 50,
    "email_opens": 9,
    "email_clicks": 4,
}


@pytest.fixture(scope="module")
def predictor() -> Predictor:
    bundle: ModelBundle = train(make_frame(), model_version_id=str(MODEL.id))
    return Predictor(bundle)


# --- input ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("field", list(LIMITS))
def test_every_bound_of_the_form_is_enforced(field: str) -> None:
    bounds = LIMITS[field]
    low = bounds.get("min", bounds.get("min_exclusive"))
    assert low is not None
    outside = [low] if "min_exclusive" in bounds else [low - 1]
    for value in [*outside, bounds["max"] + 1]:
        with pytest.raises(ValidationError):
            CampaignInput.model_validate({**INPUT, field: value})
    CampaignInput.model_validate({**INPUT, field: bounds["max"]})


def test_unknown_fields_and_bad_enums_are_refused() -> None:
    for bad in ({"colour": "red"}, {"campaign_channel": "Radio"}, {"advertising_tool": " "}):
        with pytest.raises(ValidationError):
            CampaignInput.model_validate({**INPUT, **bad})


# --- pure functions ------------------------------------------------------------------------------


def test_top_drivers_keep_five_fields_largest_first() -> None:
    series = pd.Series({"a": 0.1, "b": -0.5, "c": 0.0, "d": 0.3, "e": -0.2, "f": 0.05})
    result = top_drivers(series, {"b": 7})
    assert [d["field"] for d in result] == ["b", "d", "e", "a", "f"]
    assert result[0] == {"field": "b", "value": 7, "contribution": -0.5, "direction": "down"}
    assert result[1]["direction"] == "up"


def test_warnings() -> None:
    ranges = {"ad_spend": {"min": 100.0, "max": 9000.0}, "age": {"min": 18.0, "max": 70.0}}
    found = build_warnings(
        reliability="low",
        values={"ad_spend": 9500, "age": 30},
        ranges=ranges,
        reference_fallback=True,
    )
    assert [(w["code"], w["field"]) for w in found] == [
        ("LOW_MODEL_RELIABILITY", None),
        ("OUT_OF_TRAINING_RANGE", "ad_spend"),
        ("REFERENCE_FALLBACK", None),
    ]
    assert (
        build_warnings(
            reliability="good",
            values={"ad_spend": 100, "age": 70},
            ranges=ranges,
            reference_fallback=False,
        )
        == []
    )


def test_candidates_change_one_lever_at_a_time() -> None:
    values = {**INPUT, "advertising_platform": None, "advertising_tool": None}
    candidates = build_candidates(values, {})
    levers = [c.lever for c in candidates]
    assert levers.count("ad_spend") == 10
    assert levers.count("campaign_channel") == 4
    assert levers.count("campaign_type") == 3
    assert levers.count("age") == 4  # 35 is in the 35-44 band: 40 is left out
    assert levers.count("gender") == 1
    assert levers.count("previous_purchases") == 4  # 0, 3, 6, 9 (the current 2 is not among them)
    assert "advertising_platform" not in levers
    for candidate in candidates:
        changed = [k for k, v in candidate.inputs.items() if v != values[k]]
        assert changed == [candidate.lever]


def test_a_spend_above_the_maximum_is_not_proposed() -> None:
    candidates = build_candidates({**INPUT, "ad_spend": 9_000_000}, {})
    spends = [c.to_value for c in candidates if c.lever == "ad_spend"]
    assert max(spends) <= 10_000_000
    assert len(spends) == 6  # x0.5 to x0.9 and x1.1; x1.2 and above would exceed the bound


def test_recommendations_keep_the_best_of_each_lever_with_a_gain_of_five_points() -> None:
    def candidate(lever: str, value: int) -> Candidate:
        return Candidate(lever, 0, value, {})

    candidates = [
        candidate("ad_spend", 1),
        candidate("ad_spend", 2),
        candidate("age", 1),
        candidate("gender", 1),
        candidate("income", 1),
        candidate("loyalty_points", 1),
    ]
    scores = [60.0, 70.0, 66.0, 54.9, 66.0, 90.0]
    # base 50: ad_spend best +20 (index 1), age +16, income +16 (tie: table order), gender +4.9
    # (below 5), loyalty +40; only three are kept
    assert pick_best(candidates, scores, 50.0) == [(5, 40.0), (1, 20.0), (2, 16.0)]
    assert pick_best(candidates, [50.0, 54.9, 50, 50, 50, 50], 50.0) == []


# --- simulation ----------------------------------------------------------------------------------


def test_simulate_returns_every_part_of_the_result(predictor: Predictor) -> None:
    result = prediction_service.simulate(predictor, MODEL, CampaignInput.model_validate(INPUT))
    assert result.id is None and result.label is None
    assert 0 <= result.predictions.click_through_rate <= 1
    assert result.predictions.website_visits >= 0
    leads = result.derived.estimated_leads
    cost = result.derived.estimated_cost_per_result
    assert (cost is None) == (leads == 0)
    assert 0 <= result.performance.score <= 100
    assert result.performance.level in {"low", "medium", "high"}
    assert result.performance.reference == "campaign_type"
    averages = result.performance.averages
    assert averages is not None  # the dataset mean of each figure, shown under the figures
    assert 0 <= averages.click_through_rate <= 1 and averages.website_visits >= 0
    for drivers in (result.drivers.click_through_rate, result.drivers.website_visits):
        assert 1 <= len(drivers) <= 5
    assert len(result.recommendations.items) <= 3
    found = bool(result.recommendations.items)
    assert result.recommendations.status == ("found" if found else "none_significant")
    for item in result.recommendations.items:
        assert item.score_gain >= 5.0
        assert item.new_score == pytest.approx(result.performance.score + item.score_gain, abs=0.11)


def test_simulate_advises_what_the_training_signal_rewards(predictor: Predictor) -> None:
    """Conversion rate grows with previous purchases and click-through with Email."""
    result = prediction_service.simulate(predictor, MODEL, CampaignInput.model_validate(INPUT))
    items = result.recommendations.items
    assert (items[0].lever, items[0].to_value) == ("previous_purchases", 9)
    assert [i.score_gain for i in items] == sorted((i.score_gain for i in items), reverse=True)
    emailed = prediction_service.simulate(
        predictor, MODEL, CampaignInput.model_validate({**INPUT, "campaign_channel": "Email"})
    )
    assert emailed.predictions.click_through_rate > result.predictions.click_through_rate
    assert all(i.lever != "campaign_channel" for i in emailed.recommendations.items)


def test_out_of_range_values_raise_a_warning(predictor: Predictor) -> None:
    result = prediction_service.simulate(
        predictor, MODEL, CampaignInput.model_validate({**INPUT, "ad_spend": 9_999_999})
    )
    assert ("OUT_OF_TRAINING_RANGE", "ad_spend") in [(w.code, w.field) for w in result.warnings]


def test_a_field_used_by_the_model_is_required() -> None:
    bundle = train(make_frame(optional=True), model_version_id=str(MODEL.id))
    with pytest.raises(AppError) as error:
        prediction_service.simulate(Predictor(bundle), MODEL, CampaignInput.model_validate(INPUT))
    assert error.value.status == 422
    assert error.value.details[0].field == "advertising_platform"
    result = prediction_service.simulate(
        Predictor(bundle),
        MODEL,
        CampaignInput.model_validate({**INPUT, "advertising_platform": "Alpha"}),
    )
    assert result.input.advertising_platform == "Alpha"


def test_the_schema_enums_match_the_dataset_enums() -> None:
    from typing import get_args

    from app.schemas import prediction

    assert get_args(prediction.Channel) == CATEGORICAL["campaign_channel"]
    assert get_args(prediction.CampaignType) == CATEGORICAL["campaign_type"]
    assert get_args(prediction.Gender) == CATEGORICAL["gender"]
