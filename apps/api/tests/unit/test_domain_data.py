"""domain: holdout, features, scoring, engagement defaults (LLD 5.2, 5.3, 6.3 to 6.5)."""

import numpy as np
import pandas as pd
import pytest

from app.domain.engagement_defaults import build_engagement_defaults, defaults_for
from app.domain.features import OTHER, FeatureSpec, build_feature_spec, encode, training_ranges
from app.domain.holdout import is_holdout
from app.domain.scoring import (
    ReferenceArrays,
    ScoringReference,
    build_scoring_reference,
    level_for,
    percentile_rank,
    score_campaign,
)
from tests.data_factory import make_frame


def test_holdout_is_deterministic_and_about_a_fifth() -> None:
    flags = [is_holdout("seed", i) for i in range(8000, 16000)]
    assert flags == [is_holdout("seed", i) for i in range(8000, 16000)]
    assert 0.17 < sum(flags) / len(flags) < 0.23
    # the source is part of the hash
    assert any(is_holdout("seed", i) != is_holdout("agency", i) for i in range(8000, 8100))


def test_constant_optional_fields_are_left_out() -> None:
    spec = build_feature_spec(make_frame())
    assert len(spec.columns) == 10 + 5 + 4 + 2
    assert spec.optional_categories == {}
    assert "advertising_platform" not in spec.features_used


def test_optional_field_with_two_values_is_used_with_an_other_bucket() -> None:
    train = make_frame(optional=True)
    spec = build_feature_spec(train)
    assert spec.optional_categories["advertising_platform"] == ("Alpha", "Beta", OTHER)
    unknown = train.head(2).copy()
    unknown["advertising_platform"] = ["Alpha", "Brand new"]
    encoded = encode(unknown, spec)
    assert list(encoded.columns) == list(spec.columns)
    assert encoded[f"advertising_platform={OTHER}"].tolist() == [0.0, 1.0]


def test_encoding_is_one_hot_in_the_frozen_order_and_spec_round_trips() -> None:
    frame = make_frame(50)
    spec = build_feature_spec(frame)
    encoded = encode(frame, spec)
    channels = [c for c in spec.columns if c.startswith("campaign_channel=")]
    assert (encoded[channels].sum(axis=1) == 1).all()
    assert FeatureSpec.from_dict(spec.to_dict()) == spec
    ranges = training_ranges(frame, spec)
    assert ranges["age"]["min"] == frame["age"].min()


def test_percentile_rank_counts_ties_as_half() -> None:
    ref = np.array([1.0, 2.0, 2.0, 3.0])
    assert percentile_rank(0.5, ref) == 0.0
    assert percentile_rank(2.0, ref) == 50.0
    assert percentile_rank(9.0, ref) == 100.0


def _reference() -> ScoringReference:
    return build_scoring_reference(make_frame(600))


def test_scoring_reference_round_trips_through_json_with_infinite_costs() -> None:
    reference = _reference()
    again = ScoringReference.from_dict(reference.to_dict())
    assert again.low_below == reference.low_below
    assert np.array_equal(
        again.all_types.estimated_cost_per_result, reference.all_types.estimated_cost_per_result
    )
    arrays = ReferenceArrays.from_dict(
        {
            "click_through_rate": [0.1],
            "estimated_leads": [0.0],
            "estimated_cost_per_result": [None],
            "n": 1,
        }
    )
    assert np.isinf(arrays.estimated_cost_per_result[0])


def test_score_and_level_follow_the_terciles() -> None:
    reference = _reference()
    assert reference.low_below < reference.high_from
    best = score_campaign(1.0, 1e9, 0.01, "Awareness", reference)
    worst = score_campaign(0.0, 0.0, None, "Awareness", reference)
    assert best.score > 90
    assert worst.score < 10
    assert worst.cost_note == 0.0
    assert level_for(best.score, reference) == "high"
    assert level_for(worst.score, reference) == "low"
    assert level_for(reference.low_below, reference) == "medium"


def test_a_type_with_fewer_than_30_rows_falls_back_to_all_types() -> None:
    frame = make_frame(300)
    frame.loc[frame.index[:10], "campaign_type"] = "Rare"
    reference = build_scoring_reference(frame)
    assert score_campaign(0.1, 5.0, 10.0, "Rare", reference).reference_fallback
    assert not score_campaign(0.1, 5.0, 10.0, "Awareness", reference).reference_fallback


def test_engagement_defaults_use_channel_and_type_then_channel_then_all() -> None:
    frame = make_frame(600)
    defaults = build_engagement_defaults(frame)
    assert defaults_for(defaults, "Email", "Awareness")["basis"] == "channel_and_type"
    assert defaults_for(defaults, "Email", "Nothing")["basis"] == "channel"
    result = defaults_for(defaults, "Nothing", "Nothing")
    assert result["basis"] == "all"
    assert isinstance(result["pages_per_visit"], float)
    assert result["email_opens"] == float(round(result["email_opens"]))
    assert result["n"] == len(frame)


@pytest.mark.parametrize("name", ["by_channel_type", "by_channel", "all"])
def test_engagement_defaults_have_the_three_levels(name: str) -> None:
    assert name in build_engagement_defaults(pd.DataFrame(make_frame(100)))
