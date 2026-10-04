"""Metrics on the test rows (LLD 5.5, DATA_MODEL 4.7) and global importance (LLD 6.6)."""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.domain.dataset_schema import TARGETS
from app.domain.scoring import FloatArray
from app.ml.predictor import Predictor

LOW_R2 = 0.10
GOOD_R2 = 0.40


def reliability(r2: float) -> str:
    """r2 < 0.10 low, 0.10 <= r2 < 0.40 moderate, r2 >= 0.40 good."""
    if r2 < LOW_R2:
        return "low"
    return "moderate" if r2 < GOOD_R2 else "good"


def target_metrics(y_true: FloatArray, y_pred: FloatArray, train_mean: float) -> dict[str, Any]:
    """MAE, RMSE, R2 and the MAE of a constant prediction equal to the training mean."""
    r2 = float(r2_score(y_true, y_pred))
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": r2,
        "baseline_mae": float(mean_absolute_error(y_true, np.full(len(y_true), train_mean))),
        "reliability": reliability(r2),
    }


def evaluate(predictor: Predictor, test: pd.DataFrame, train: pd.DataFrame) -> dict[str, Any]:
    predictions = predictor.predict(test)
    metrics: dict[str, Any] = {
        t: target_metrics(test[t].to_numpy(), predictions[t], float(train[t].mean()))
        for t in TARGETS
    }
    mean_r2 = float(np.mean([metrics[t]["r2"] for t in TARGETS]))
    metrics["overall_reliability"] = reliability(mean_r2)
    return metrics


def global_importance(predictor: Predictor, test: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    """Mean absolute contribution per field on the test rows, normalised to 1, largest first."""
    result: dict[str, list[dict[str, Any]]] = {}
    for target, contributions in predictor.contributions(test).items():
        shares = contributions.abs().mean()
        total = float(shares.sum())
        shares = (shares / total if total > 0 else shares).sort_values(ascending=False)
        result[target] = [{"field": str(f), "share": float(s)} for f, s in shares.items()]
    return result
