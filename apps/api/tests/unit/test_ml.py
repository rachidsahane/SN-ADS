"""ml: training, evaluation, bundle files and the predictor (LLD 5.4 to 5.6, 6.1, 6.6)."""

from pathlib import Path

import numpy as np
import pytest

from app.domain.dataset_schema import TARGETS
from app.ml.bundle import ModelBundle, load_bundle, save_bundle
from app.ml.evaluation import reliability
from app.ml.predictor import Predictor, clip_prediction
from app.ml.training import NOT_ENOUGH_DATA_MESSAGE, NotEnoughDataError, train
from tests.data_factory import make_frame

VERSION_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(scope="module")
def bundle() -> ModelBundle:
    return train(make_frame(), model_version_id=VERSION_ID)


def test_reliability_thresholds() -> None:
    assert [reliability(r) for r in (-0.5, 0.099, 0.10, 0.399, 0.40)] == [
        "low",
        "low",
        "moderate",
        "moderate",
        "good",
    ]


def test_training_finds_a_real_signal_and_reports_every_figure(bundle: ModelBundle) -> None:
    for target in TARGETS:
        entry = bundle.metrics[target]
        assert set(entry) == {"mae", "rmse", "r2", "baseline_mae", "reliability"}
        assert entry["mae"] < entry["baseline_mae"]
    assert bundle.metrics["click_through_rate"]["r2"] > 0.4
    assert bundle.metrics["overall_reliability"] == "good"


def test_global_importance_sums_to_one_and_is_sorted(bundle: ModelBundle) -> None:
    for shares in bundle.global_importance.values():
        values = [s["share"] for s in shares]
        assert sum(values) == pytest.approx(1.0)
        assert values == sorted(values, reverse=True)
    assert bundle.global_importance["click_through_rate"][0]["field"] in {
        "ad_spend",
        "campaign_channel",
    }


def test_predictions_are_clipped_and_contributions_are_per_field(bundle: ModelBundle) -> None:
    predictor = Predictor(bundle)
    frame = make_frame(5, seed=9)
    predictions = predictor.predict(frame)
    assert all(len(v) == 5 for v in predictions.values())
    assert (
        (predictions["click_through_rate"] >= 0) & (predictions["click_through_rate"] <= 1)
    ).all()
    assert (predictions["website_visits"] >= 0).all()
    contributions = predictor.contributions(frame)["click_through_rate"]
    assert set(contributions.columns) == set(bundle.spec.features_used)
    assert list(clip_prediction("conversion_rate", np.array([-1.0, 2.0]))) == [0.0, 1.0]
    assert list(clip_prediction("website_visits", np.array([-3.0, 7.0]))) == [0.0, 7.0]


def test_a_saved_bundle_loads_back_with_the_same_predictions(
    bundle: ModelBundle, tmp_path: Path
) -> None:
    directory = save_bundle(bundle, tmp_path / "versions" / VERSION_ID)
    assert sorted(p.name for p in directory.iterdir()) == [
        "bundle.json",
        "click_through_rate.json",
        "conversion_rate.json",
        "website_visits.json",
    ]
    loaded = load_bundle(directory)
    assert loaded.model_version_id == VERSION_ID
    assert loaded.spec == bundle.spec
    assert loaded.metrics == bundle.metrics
    assert loaded.target_means == bundle.target_means
    assert bundle.target_means is not None and set(bundle.target_means) == set(TARGETS)
    frame = make_frame(20, seed=4)
    before, after = Predictor(bundle).predict(frame), Predictor(loaded).predict(frame)
    for target in TARGETS:
        assert np.allclose(before[target], after[target])
    save_bundle(bundle, directory)  # saving again replaces the folder


def test_too_few_rows_is_a_readable_error() -> None:
    with pytest.raises(NotEnoughDataError, match="Not enough data") as error:
        train(make_frame(100), model_version_id=VERSION_ID)
    assert str(error.value) == NOT_ENOUGH_DATA_MESSAGE
