"""A small synthetic training frame with a real signal (so a working pipeline reaches a good R2)."""

import numpy as np
import pandas as pd

from app.domain.dataset_schema import CATEGORICAL
from app.domain.holdout import is_holdout


def make_frame(n: int = 800, *, seed: int = 3, optional: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ids = np.arange(8000, 8000 + n)
    frame = pd.DataFrame(
        {
            "external_id": ids,
            "is_holdout": [is_holdout("seed", int(i)) for i in ids],
            "age": rng.integers(18, 70, n),
            "income": rng.integers(10_000, 150_000, n),
            "ad_spend": rng.uniform(100, 10_000, n),
            "previous_purchases": rng.integers(0, 10, n),
            "loyalty_points": rng.integers(0, 5000, n),
            "pages_per_visit": rng.uniform(1, 10, n),
            "time_on_site": rng.uniform(0.5, 15, n),
            "social_shares": rng.integers(0, 100, n),
            "email_opens": rng.integers(0, 20, n),
            "email_clicks": rng.integers(0, 10, n),
            "advertising_platform": "IsConfid",
            "advertising_tool": "ToolConfid",
        }
    )
    for name, values in CATEGORICAL.items():
        frame[name] = rng.choice(values, n)
    if optional:
        frame["advertising_platform"] = rng.choice(["Alpha", "Beta"], n)
    frame["click_through_rate"] = np.clip(
        0.02 + 0.00002 * frame["ad_spend"] + 0.05 * (frame["campaign_channel"] == "Email"), 0, 1
    )
    frame["conversion_rate"] = np.clip(0.02 + 0.01 * frame["previous_purchases"], 0, 1)
    frame["website_visits"] = (frame["ad_spend"] / 200 + 3 * frame["email_clicks"]).round()
    return frame
