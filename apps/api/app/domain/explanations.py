"""Main factors of one prediction (LLD 6.6)."""

from collections.abc import Mapping
from typing import Any

import pandas as pd

TOP_DRIVERS = 5


def top_drivers(
    contributions: "pd.Series[float]", values: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """The 5 fields with the largest absolute contribution, largest first."""
    ranked = contributions.reindex(contributions.abs().sort_values(ascending=False).index)
    return [
        {
            "field": str(field),
            "value": values.get(str(field)),
            "contribution": round(float(amount), 6),
            "direction": "up" if amount > 0 else "down",
        }
        for field, amount in ranked.head(TOP_DRIVERS).items()
    ]
