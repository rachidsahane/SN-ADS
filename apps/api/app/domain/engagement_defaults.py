"""Pre-filled engagement values (LLD 6.5): channel + type, else channel, else all rows."""

from typing import Any

import pandas as pd

from app.domain.dataset_schema import ENGAGEMENT

MIN_ROWS = 30
_ONE_DECIMAL = ("pages_per_visit", "time_on_site")


def _means(frame: pd.DataFrame) -> dict[str, float]:
    out: dict[str, float] = {}
    for name in ENGAGEMENT:
        mean = float(frame[name].mean())
        out[name] = round(mean, 1) if name in _ONE_DECIMAL else float(round(mean))
    out["n"] = float(len(frame))
    return out


def build_engagement_defaults(frame: pd.DataFrame) -> dict[str, Any]:
    by_channel_type = {
        f"{channel}|{ctype}": _means(group)
        for (channel, ctype), group in frame.groupby(["campaign_channel", "campaign_type"])
    }
    by_channel = {str(c): _means(g) for c, g in frame.groupby("campaign_channel")}
    return {"by_channel_type": by_channel_type, "by_channel": by_channel, "all": _means(frame)}


def defaults_for(defaults: dict[str, Any], channel: str, campaign_type: str) -> dict[str, Any]:
    """Values and basis (`channel_and_type`, `channel` or `all`) for a channel and a type."""
    for basis, key, table in (
        ("channel_and_type", f"{channel}|{campaign_type}", defaults["by_channel_type"]),
        ("channel", channel, defaults["by_channel"]),
    ):
        entry = table.get(key)
        if entry is not None and entry["n"] >= MIN_ROWS:
            return {**entry, "basis": basis}
    return {**defaults["all"], "basis": "all"}
