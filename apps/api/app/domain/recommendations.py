"""Candidate changes and the choice of the best ones (LLD 6.7). Scoring is done by the caller."""

from bisect import bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.domain.dataset_schema import CATEGORICAL, LIMITS

MIN_GAIN = 5.0
MAX_ITEMS = 3
SPEND_FACTORS = (0.5, 0.6, 0.7, 0.8, 0.9, 1.1, 1.2, 1.3, 1.4, 1.5)
AGE_BOUNDS, AGE_MIDDLES = (25, 35, 45, 55), (21, 30, 40, 50, 62)
INCOME_BOUNDS = (45_000, 70_000, 95_000, 120_000)
INCOME_MIDDLES = (32_500, 57_500, 82_500, 107_500, 135_000)
PURCHASES = (0, 3, 6, 9)
POINTS = (0, 1250, 2500, 3750, 4999)
OPTIONAL_LEVERS = ("advertising_platform", "advertising_tool")


@dataclass(frozen=True)
class Candidate:
    lever: str
    from_value: Any
    to_value: Any
    inputs: dict[str, Any]


def _bands(value: float, bounds: tuple[int, ...], middles: tuple[int, ...]) -> list[int]:
    """Band middles, except the band the current value belongs to."""
    current = bisect_right(bounds, value)
    return [m for i, m in enumerate(middles) if i != current]


def build_candidates(
    inputs: Mapping[str, Any], optional_categories: Mapping[str, Sequence[str]]
) -> list[Candidate]:
    """Every variant, one lever changed at a time, in the order of the LLD table."""
    spend_max = float(LIMITS["ad_spend"]["max"])
    options: list[tuple[str, list[Any]]] = [
        (
            "ad_spend",
            [s for f in SPEND_FACTORS if 0 < (s := round(inputs["ad_spend"] * f, 2)) <= spend_max],
        ),
        ("campaign_channel", list(CATEGORICAL["campaign_channel"])),
        ("campaign_type", list(CATEGORICAL["campaign_type"])),
        ("age", _bands(inputs["age"], AGE_BOUNDS, AGE_MIDDLES)),
        ("income", _bands(inputs["income"], INCOME_BOUNDS, INCOME_MIDDLES)),
        ("gender", list(CATEGORICAL["gender"])),
        ("previous_purchases", list(PURCHASES)),
        ("loyalty_points", list(POINTS)),
        *[
            (name, [v for v in optional_categories[name] if not v.startswith("__")])
            for name in OPTIONAL_LEVERS
            if name in optional_categories
        ],
    ]
    return [
        Candidate(lever, inputs[lever], value, {**inputs, lever: value})
        for lever, values in options
        for value in values
        if value != inputs[lever]
    ]


def pick_best(
    candidates: Sequence[Candidate], scores: Sequence[float], base_score: float
) -> list[tuple[int, float]]:
    """(index, gain) of the best variant of each lever, gain >= 5 points, 3 at most, best first."""
    best: dict[str, tuple[int, float]] = {}
    for index, (candidate, score) in enumerate(zip(candidates, scores, strict=True)):
        gain = round(score - base_score, 1)
        if candidate.lever not in best or gain > best[candidate.lever][1]:
            best[candidate.lever] = (index, gain)
    kept = [item for item in best.values() if item[1] >= MIN_GAIN]
    order = {lever: i for i, lever in enumerate(best)}  # table order breaks ties
    kept.sort(key=lambda item: (-item[1], order[candidates[item[0]].lever]))
    return kept[:MAX_ITEMS]
