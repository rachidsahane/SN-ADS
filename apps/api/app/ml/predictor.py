"""Predictions of a loaded version: clipped figures and per-field contributions (LLD 6.1, 6.6)."""

import numpy as np
import pandas as pd
import xgboost as xgb

from app.domain.dataset_schema import RATE_TARGETS, TARGETS
from app.domain.features import encode, field_of
from app.domain.scoring import FloatArray
from app.ml.bundle import ModelBundle


def clip_prediction(target: str, values: FloatArray) -> FloatArray:
    """Rates stay in [0, 1], visits are never negative."""
    if target in RATE_TARGETS:
        clipped: FloatArray = np.clip(values, 0.0, 1.0)
    else:
        clipped = np.maximum(values, 0.0)
    return clipped


class Predictor:
    def __init__(self, bundle: ModelBundle) -> None:
        self.bundle = bundle

    @property
    def version_id(self) -> str:
        return self.bundle.model_version_id

    def predict(self, frame: pd.DataFrame) -> dict[str, FloatArray]:
        """Three clipped arrays, one per target, for rows with the raw input fields."""
        x = encode(frame, self.bundle.spec)
        return {t: clip_prediction(t, self.bundle.models[t].predict(x)) for t in TARGETS}

    def contributions(self, frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
        """Per target, one column per input FIELD (encoded columns summed, bias dropped)."""
        x = encode(frame, self.bundle.spec)
        result = {}
        for target in TARGETS:
            raw = (
                self.bundle.models[target].get_booster().predict(xgb.DMatrix(x), pred_contribs=True)
            )
            per_column = pd.DataFrame(
                raw[:, :-1].astype(float), columns=list(self.bundle.spec.columns), index=x.index
            )
            result[target] = per_column.T.groupby(field_of).sum().T
        return result
