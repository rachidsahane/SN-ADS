"""Notes (0 to 100), score and level (LLD 6.3, 6.4)."""

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from app.domain.derived_metrics import estimated_cost_per_result, estimated_leads

MIN_TYPE_ROWS = 30
FloatArray = NDArray[np.float64]
Level = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ReferenceArrays:
    """Sorted real values of a scope. No lead = infinite cost (sorted last, null in JSON)."""

    click_through_rate: FloatArray
    estimated_leads: FloatArray
    estimated_cost_per_result: FloatArray
    n: int

    def to_dict(self) -> dict[str, Any]:
        cost = [None if np.isinf(v) else float(v) for v in self.estimated_cost_per_result]
        return {
            "click_through_rate": self.click_through_rate.tolist(),
            "estimated_leads": self.estimated_leads.tolist(),
            "estimated_cost_per_result": cost,
            "n": self.n,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReferenceArrays":
        cost = np.array([np.inf if v is None else v for v in data["estimated_cost_per_result"]])
        return cls(
            np.array(data["click_through_rate"], dtype=float),
            np.array(data["estimated_leads"], dtype=float),
            cost.astype(float),
            int(data["n"]),
        )


@dataclass(frozen=True)
class ScoringReference:
    by_type: dict[str, ReferenceArrays]
    all_types: ReferenceArrays
    low_below: float
    high_from: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "by_type": {k: v.to_dict() for k, v in self.by_type.items()},
            "all_types": self.all_types.to_dict(),
            "thresholds": {"low_below": self.low_below, "high_from": self.high_from},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoringReference":
        return cls(
            {k: ReferenceArrays.from_dict(v) for k, v in data["by_type"].items()},
            ReferenceArrays.from_dict(data["all_types"]),
            float(data["thresholds"]["low_below"]),
            float(data["thresholds"]["high_from"]),
        )


@dataclass(frozen=True)
class PerformanceScore:
    ctr_note: float
    leads_note: float
    cost_note: float
    score: float
    reference_fallback: bool


def percentile_rank(value: float, sorted_values: FloatArray) -> float:
    """100 x (nb(ref < x) + 0.5 x nb(ref == x)) / n, by binary search."""
    below = int(np.searchsorted(sorted_values, value, side="left"))
    upto = int(np.searchsorted(sorted_values, value, side="right"))
    return 100.0 * (below + 0.5 * (upto - below)) / len(sorted_values)


def _arrays(frame: pd.DataFrame) -> ReferenceArrays:
    leads = (frame["website_visits"] * frame["conversion_rate"]).to_numpy(float)
    spend = frame["ad_spend"].to_numpy(float)
    cost = np.where(leads > 0, spend / np.where(leads > 0, leads, 1), np.inf)
    return ReferenceArrays(
        np.sort(frame["click_through_rate"].to_numpy(float)),
        np.sort(leads),
        np.sort(cost),
        len(frame),
    )


def score_campaign(
    ctr: float,
    leads: float,
    cost_per_result: float | None,
    campaign_type: str,
    reference: ScoringReference,
) -> PerformanceScore:
    """Three notes and their mean, rounded to one decimal."""
    ref = reference.by_type.get(campaign_type)
    fallback = ref is None or ref.n < MIN_TYPE_ROWS
    if ref is None or fallback:
        ref = reference.all_types
    ctr_note = percentile_rank(ctr, ref.click_through_rate)
    leads_note = percentile_rank(leads, ref.estimated_leads)
    cost_note = (
        0.0
        if cost_per_result is None
        else 100.0 - percentile_rank(cost_per_result, ref.estimated_cost_per_result)
    )
    score = round((ctr_note + leads_note + cost_note) / 3, 1)
    return PerformanceScore(ctr_note, leads_note, cost_note, score, fallback)


def build_scoring_reference(frame: pd.DataFrame) -> ScoringReference:
    """Reference distributions of the real rows, and the terciles of their own scores."""
    by_type = {str(t): _arrays(g) for t, g in frame.groupby("campaign_type")}
    all_types = _arrays(frame)
    provisional = ScoringReference(by_type, all_types, 0.0, 0.0)
    scores = []
    rows = zip(
        frame["click_through_rate"].to_numpy(float),
        frame["website_visits"].to_numpy(float),
        frame["conversion_rate"].to_numpy(float),
        frame["ad_spend"].to_numpy(float),
        frame["campaign_type"],
        strict=True,
    )
    for ctr, visits, conversion, spend, campaign_type in rows:
        leads = estimated_leads(visits, conversion)
        cost = estimated_cost_per_result(spend, leads)
        scores.append(score_campaign(ctr, leads, cost, str(campaign_type), provisional).score)
    low_below, high_from = np.quantile(np.array(scores), [1 / 3, 2 / 3], method="linear")
    return ScoringReference(by_type, all_types, float(low_below), float(high_from))


def level_for(score: float, reference: ScoringReference) -> Level:
    if score < reference.low_below:
        return "low"
    return "high" if score >= reference.high_from else "medium"
