"""Warnings attached to a prediction (LLD 6.8)."""

from collections.abc import Mapping
from typing import Any

LOW_RELIABILITY_MESSAGE = (
    "The current model has low accuracy. Its predictions stay close to average values."
)
OUT_OF_RANGE_MESSAGE = "Outside the values the model has seen. Treat this prediction with caution."
FALLBACK_MESSAGE = (
    "Too few similar campaigns to compare with: the score uses all campaign types instead."
)


def build_warnings(
    *,
    reliability: str,
    values: Mapping[str, Any],
    ranges: Mapping[str, Mapping[str, float]],
    reference_fallback: bool,
) -> list[dict[str, str | None]]:
    warnings: list[dict[str, str | None]] = []
    if reliability == "low":
        warnings.append(
            {"code": "LOW_MODEL_RELIABILITY", "field": None, "message": LOW_RELIABILITY_MESSAGE}
        )
    for field, bounds in ranges.items():
        value = values.get(field)
        if value is not None and not bounds["min"] <= value <= bounds["max"]:
            warnings.append(
                {"code": "OUT_OF_TRAINING_RANGE", "field": field, "message": OUT_OF_RANGE_MESSAGE}
            )
    if reference_fallback:
        warnings.append({"code": "REFERENCE_FALLBACK", "field": None, "message": FALLBACK_MESSAGE})
    return warnings
