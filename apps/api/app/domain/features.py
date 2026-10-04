"""Model inputs (LLD 5.2): the frozen list of encoded columns and the 0/1 encoding."""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.domain.dataset_schema import CATEGORICAL, NUMERIC, OPTIONAL

OPTIONAL_MIN_COUNT = 5
OTHER = "__other__"


@dataclass(frozen=True)
class FeatureSpec:
    numeric: tuple[str, ...]
    categorical: dict[str, tuple[str, ...]]
    optional_categories: dict[str, tuple[str, ...]]
    columns: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "numeric": list(self.numeric),
            "categorical": {k: list(v) for k, v in self.categorical.items()},
            "optional_categories": {k: list(v) for k, v in self.optional_categories.items()},
            "columns": list(self.columns),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureSpec":
        return cls(
            tuple(data["numeric"]),
            {k: tuple(v) for k, v in data["categorical"].items()},
            {k: tuple(v) for k, v in data["optional_categories"].items()},
            tuple(data["columns"]),
        )

    @property
    def features_used(self) -> list[str]:
        """Original fields behind the columns, in order, without duplicates."""
        return list(dict.fromkeys(field_of(c) for c in self.columns))


def field_of(column: str) -> str:
    """`campaign_channel=Email` -> `campaign_channel`."""
    return column.split("=", 1)[0]


def build_feature_spec(train: pd.DataFrame) -> FeatureSpec:
    """Optional fields are used only with at least 2 distinct training values."""
    optional: dict[str, tuple[str, ...]] = {}
    for name in OPTIONAL:
        counts = train[name].value_counts()
        if len(counts) >= 2:  # noqa: PLR2004
            kept = tuple(sorted(counts[counts >= OPTIONAL_MIN_COUNT].index))
            optional[name] = (*kept, OTHER)
    columns = list(NUMERIC)
    for name, values in CATEGORICAL.items():
        columns += [f"{name}={value}" for value in values]
    for name, values in optional.items():
        columns += [f"{name}={value}" for value in values]
    return FeatureSpec(NUMERIC, dict(CATEGORICAL), optional, tuple(columns))


def encode(frame: pd.DataFrame, spec: FeatureSpec) -> pd.DataFrame:
    """Numeric matrix with 0/1 indicator columns in the frozen column order."""
    out = frame[list(spec.numeric)].astype(float).copy()
    for name, values in spec.categorical.items():
        for value in values:
            out[f"{name}={value}"] = (frame[name] == value).astype(float)
    for name, values in spec.optional_categories.items():
        known = set(values) - {OTHER}
        mapped = frame[name].where(frame[name].isin(known), OTHER)  # unknown value -> __other__
        for value in values:
            out[f"{name}={value}"] = (mapped == value).astype(float)
    return out[list(spec.columns)]


def training_ranges(frame: pd.DataFrame, spec: FeatureSpec) -> dict[str, dict[str, float]]:
    return {
        name: {"min": float(frame[name].min()), "max": float(frame[name].max())}
        for name in spec.numeric
    }
