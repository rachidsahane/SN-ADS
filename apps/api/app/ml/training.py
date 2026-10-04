"""Training of one version: three XGBoost models, metrics on the test rows (LLD 5.4, 5.5)."""

from dataclasses import replace
from datetime import UTC, datetime

import pandas as pd
import xgboost as xgb

from app.domain.dataset_schema import TARGETS
from app.domain.engagement_defaults import build_engagement_defaults
from app.domain.features import build_feature_spec, encode, training_ranges
from app.domain.scoring import build_scoring_reference
from app.ml.bundle import ModelBundle
from app.ml.evaluation import evaluate, global_importance
from app.ml.params import XGB_PARAMS
from app.ml.predictor import Predictor

MIN_TRAIN_ROWS = 200
MIN_TEST_ROWS = 50
NOT_ENOUGH_DATA_MESSAGE = (
    "Not enough data: at least 200 training rows and 50 test rows are required."
)


class NotEnoughDataError(Exception):
    """Fewer rows than the minimum; the message is shown to the administrator as is."""

    def __init__(self) -> None:
        super().__init__(NOT_ENOUGH_DATA_MESSAGE)


def train(frame: pd.DataFrame, *, model_version_id: str) -> ModelBundle:
    """Train on the non-test rows, evaluate on the test rows, build the scoring references."""
    train_rows = frame[~frame["is_holdout"]]
    test_rows = frame[frame["is_holdout"]]
    if len(train_rows) < MIN_TRAIN_ROWS or len(test_rows) < MIN_TEST_ROWS:
        raise NotEnoughDataError
    spec = build_feature_spec(train_rows)
    x_train = encode(train_rows, spec)
    models = {}
    for target in TARGETS:
        model = xgb.XGBRegressor(**XGB_PARAMS)
        model.fit(x_train, train_rows[target])
        models[target] = model
    bundle = ModelBundle(
        model_version_id=model_version_id,
        trained_at=datetime.now(UTC).isoformat(timespec="seconds"),
        spec=spec,
        models=models,
        training_ranges=training_ranges(train_rows, spec),
        engagement_defaults=build_engagement_defaults(frame),
        scoring_reference=build_scoring_reference(frame),
        metrics={},
        global_importance={},
        target_means={target: float(frame[target].mean()) for target in TARGETS},
    )
    predictor = Predictor(bundle)
    return replace(
        bundle,
        metrics=evaluate(predictor, test_rows, train_rows),
        global_importance=global_importance(predictor, test_rows),
    )
