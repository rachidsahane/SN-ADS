"""Shared rules for the exploratory notebooks (docs/LLD.md section 5 and 6, D-044).

These functions copy the frozen rules of the LLD so the notebooks show exactly what phase 7
will build. Phase 7 replaces this module by imports of ``app.domain`` and ``app.ml``.
Only xgboost, pandas, numpy and ``sklearn.metrics`` are used (no scikit-learn models).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

SEED_CSV_PATH = Path(
    os.environ.get("SEED_CSV_PATH", "../data/seed/digital_marketing_campaign_dataset.csv")
)
OUT_DIR = Path("_out")

# LLD 5.1: CSV column -> internal name
COLUMN_MAP = {
    "CustomerID": "external_id",
    "Age": "age",
    "Gender": "gender",
    "Income": "income",
    "CampaignChannel": "campaign_channel",
    "CampaignType": "campaign_type",
    "AdSpend": "ad_spend",
    "ClickThroughRate": "click_through_rate",
    "ConversionRate": "conversion_rate",
    "WebsiteVisits": "website_visits",
    "PagesPerVisit": "pages_per_visit",
    "TimeOnSite": "time_on_site",
    "SocialShares": "social_shares",
    "EmailOpens": "email_opens",
    "EmailClicks": "email_clicks",
    "PreviousPurchases": "previous_purchases",
    "LoyaltyPoints": "loyalty_points",
    "AdvertisingPlatform": "advertising_platform",
    "AdvertisingTool": "advertising_tool",
    "Conversion": "conversion",
}

# LLD 5.2: model inputs
NUMERIC = (
    "ad_spend",
    "age",
    "income",
    "previous_purchases",
    "loyalty_points",
    "pages_per_visit",
    "time_on_site",
    "social_shares",
    "email_opens",
    "email_clicks",
)
CATEGORICAL = {  # enumerations of DATA_MODEL.md section 2: every value is always present
    "campaign_channel": ("Social Media", "Email", "PPC", "SEO", "Referral"),
    "campaign_type": ("Awareness", "Consideration", "Conversion", "Retention"),
    "gender": ("Male", "Female"),
}
OPTIONAL = ("advertising_platform", "advertising_tool")
OPTIONAL_MIN_COUNT = 5
OTHER = "__other__"

TARGETS = ("click_through_rate", "conversion_rate", "website_visits")
RATE_TARGETS = ("click_through_rate", "conversion_rate")

# LLD 5.4 (ml/params.py)
XGB_PARAMS = {
    "n_estimators": 300,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 1,
    "reg_lambda": 1.0,
    "objective": "reg:squarederror",
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": 2,
}


# ---------------------------------------------------------------------------------------------
# Data loading and holdout (LLD 5.1, 5.3)
# ---------------------------------------------------------------------------------------------
def is_holdout(source: str, external_id: int) -> bool:
    """LLD 5.3: about 20 % of the rows, deterministic, never changes."""
    digest = hashlib.sha256(f"{source}:{external_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 5 == 0


def load_seed(path: Path | str = SEED_CSV_PATH) -> pd.DataFrame:
    """Read the seed CSV with internal column names, ``source`` and ``is_holdout``."""
    frame = pd.read_csv(path).rename(columns=COLUMN_MAP)
    frame["source"] = "seed"
    frame["is_holdout"] = [is_holdout("seed", int(i)) for i in frame["external_id"]]
    return frame


def split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Training rows and holdout (test) rows."""
    return frame[~frame["is_holdout"]].copy(), frame[frame["is_holdout"]].copy()


# ---------------------------------------------------------------------------------------------
# Features (LLD 5.2)
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class FeatureSpec:
    numeric: tuple[str, ...]
    categorical: dict[str, tuple[str, ...]]
    optional_categories: dict[str, tuple[str, ...]]
    columns: tuple[str, ...]


def build_feature_spec(train: pd.DataFrame) -> FeatureSpec:
    """Optional fields are used only with at least 2 distinct training values."""
    optional: dict[str, tuple[str, ...]] = {}
    for field in OPTIONAL:
        counts = train[field].value_counts()
        if len(counts) >= 2:
            kept = tuple(sorted(counts[counts >= OPTIONAL_MIN_COUNT].index))
            optional[field] = (*kept, OTHER)
    columns = list(NUMERIC)
    for field, values in CATEGORICAL.items():
        columns += [f"{field}={value}" for value in values]
    for field, values in optional.items():
        columns += [f"{field}={value}" for value in values]
    return FeatureSpec(NUMERIC, dict(CATEGORICAL), optional, tuple(columns))


def encode(frame: pd.DataFrame, spec: FeatureSpec) -> pd.DataFrame:
    """Numeric matrix with 0/1 indicator columns in the frozen column order."""
    out = frame[list(spec.numeric)].astype(float).copy()
    for field, values in spec.categorical.items():
        for value in values:
            out[f"{field}={value}"] = (frame[field] == value).astype(float)
    for field, values in spec.optional_categories.items():
        known = set(values) - {OTHER}
        mapped = frame[field].where(frame[field].isin(known), OTHER)
        for value in values:
            out[f"{field}={value}"] = (mapped == value).astype(float)
    return out[list(spec.columns)]


def field_of(column: str) -> str:
    """Original field of an encoded column (``campaign_channel=Email`` -> ``campaign_channel``)."""
    return column.split("=", 1)[0]


# ---------------------------------------------------------------------------------------------
# Training and evaluation (LLD 5.4, 5.5, DATA_MODEL 4.7)
# ---------------------------------------------------------------------------------------------
def make_model(**overrides: object) -> xgb.XGBRegressor:
    return xgb.XGBRegressor(**{**XGB_PARAMS, **overrides})


def train_models(
    x_train: pd.DataFrame, train: pd.DataFrame, **overrides: object
) -> dict[str, xgb.XGBRegressor]:
    """Three independent XGBRegressor, one per target, same parameters."""
    models = {}
    for target in TARGETS:
        model = make_model(**overrides)
        model.fit(x_train, train[target])
        models[target] = model
    return models


def clip_prediction(target: str, values: np.ndarray) -> np.ndarray:
    """LLD 6.1: rates in [0, 1], visits >= 0."""
    if target in RATE_TARGETS:
        return np.clip(values, 0.0, 1.0)
    return np.maximum(values, 0.0)


def predict(models: dict[str, xgb.XGBRegressor], x: pd.DataFrame) -> dict[str, np.ndarray]:
    return {t: clip_prediction(t, m.predict(x)) for t, m in models.items()}


def reliability(r2: float) -> str:
    """DATA_MODEL 4.7: r2 < 0.10 low, 0.10 <= r2 < 0.40 moderate, r2 >= 0.40 good."""
    if r2 < 0.10:
        return "low"
    return "moderate" if r2 < 0.40 else "good"


def target_metrics(y_true: np.ndarray, y_pred: np.ndarray, train_mean: float) -> dict[str, float]:
    """MAE, RMSE, R2 and the MAE of a constant prediction equal to the training mean."""
    r2 = float(r2_score(y_true, y_pred))
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": r2,
        "baseline_mae": float(mean_absolute_error(y_true, np.full(len(y_true), train_mean))),
        "reliability": reliability(r2),
    }


def evaluate(
    predictions: dict[str, np.ndarray], test: pd.DataFrame, train: pd.DataFrame
) -> dict[str, object]:
    metrics: dict[str, object] = {
        t: target_metrics(test[t].to_numpy(), predictions[t], float(train[t].mean()))
        for t in TARGETS
    }
    mean_r2 = float(np.mean([metrics[t]["r2"] for t in TARGETS]))  # type: ignore[index]
    metrics["overall_reliability"] = reliability(mean_r2)
    metrics["mean_r2"] = mean_r2
    return metrics


def contributions(model: xgb.XGBRegressor, x: pd.DataFrame, spec: FeatureSpec) -> pd.DataFrame:
    """Per-field SHAP-style contributions (LLD 6.6): encoded columns of a field are summed."""
    raw = (
        model.get_booster().predict(xgb.DMatrix(x), pred_contribs=True)[:, :-1].astype(float)
    )  # drop bias
    frame = pd.DataFrame(raw, columns=list(spec.columns), index=x.index)
    return frame.T.groupby(field_of).sum().T


def global_importance(
    models: dict[str, xgb.XGBRegressor], x_test: pd.DataFrame, spec: FeatureSpec
) -> dict[str, pd.Series]:
    """Mean absolute contribution on the test rows, grouped by field, normalised to 1."""
    result = {}
    for target, model in models.items():
        shares = contributions(model, x_test, spec).abs().mean()
        total = shares.sum()
        result[target] = (shares / total if total > 0 else shares).sort_values(ascending=False)
    return result


# ---------------------------------------------------------------------------------------------
# Derived metrics and scoring (LLD 6.2 to 6.4)
# ---------------------------------------------------------------------------------------------
def estimated_leads(website_visits: float, conversion_rate: float) -> float:
    return website_visits * conversion_rate


def estimated_cost_per_result(ad_spend: float, leads: float) -> float | None:
    return ad_spend / leads if leads > 0 else None


def percentile_rank(value: float, sorted_values: np.ndarray) -> float:
    """100 x (nb(ref < x) + 0.5 x nb(ref == x)) / n, by binary search."""
    below = int(np.searchsorted(sorted_values, value, side="left"))
    upto = int(np.searchsorted(sorted_values, value, side="right"))
    return 100.0 * (below + 0.5 * (upto - below)) / len(sorted_values)


@dataclass(frozen=True)
class ReferenceArrays:
    click_through_rate: np.ndarray
    estimated_leads: np.ndarray
    estimated_cost_per_result: (
        np.ndarray
    )  # infinity (no leads) sorted last, stored as null in bundles
    n: int


@dataclass(frozen=True)
class ScoringReference:
    by_type: dict[str, ReferenceArrays]
    all_types: ReferenceArrays
    low_below: float
    high_from: float


MIN_TYPE_ROWS = 30


def _arrays(frame: pd.DataFrame) -> ReferenceArrays:
    leads = (frame["website_visits"] * frame["conversion_rate"]).to_numpy(float)
    with np.errstate(divide="ignore"):
        cpr = np.where(
            leads > 0, frame["ad_spend"].to_numpy(float) / np.where(leads > 0, leads, 1), np.inf
        )
    return ReferenceArrays(
        np.sort(frame["click_through_rate"].to_numpy(float)),
        np.sort(leads),
        np.sort(cpr),
        len(frame),
    )


def score_campaign(
    ctr: float,
    leads: float,
    cpr: float | None,
    campaign_type: str,
    by_type: dict[str, ReferenceArrays],
    all_types: ReferenceArrays,
) -> dict[str, float | bool]:
    """Three notes (0 to 100) and their mean, rounded to one decimal (LLD 6.3, 6.4)."""
    ref = by_type.get(campaign_type)
    fallback = ref is None or ref.n < MIN_TYPE_ROWS
    if fallback:
        ref = all_types
    assert ref is not None
    ctr_note = percentile_rank(ctr, ref.click_through_rate)
    leads_note = percentile_rank(leads, ref.estimated_leads)
    cost_note = 0.0 if cpr is None else 100.0 - percentile_rank(cpr, ref.estimated_cost_per_result)
    return {
        "ctr_note": ctr_note,
        "leads_note": leads_note,
        "cost_note": cost_note,
        "score": round((ctr_note + leads_note + cost_note) / 3, 1),
        "reference_fallback": fallback,
    }


def build_scoring_reference(frame: pd.DataFrame) -> ScoringReference:
    """Reference distributions from the real rows of the scope, and the tercile thresholds."""
    by_type = {t: _arrays(g) for t, g in frame.groupby("campaign_type")}
    all_types = _arrays(frame)
    scores = []
    for row in frame.itertuples():
        leads = estimated_leads(row.website_visits, row.conversion_rate)
        cpr = estimated_cost_per_result(row.ad_spend, leads)
        scores.append(
            score_campaign(
                row.click_through_rate, leads, cpr, row.campaign_type, by_type, all_types
            )["score"]
        )
    low_below, high_from = np.quantile(np.array(scores), [1 / 3, 2 / 3], method="linear")
    return ScoringReference(by_type, all_types, float(low_below), float(high_from))


def level_for(score: float, reference: ScoringReference) -> str:
    if score < reference.low_below:
        return "low"
    return "high" if score >= reference.high_from else "medium"


# ---------------------------------------------------------------------------------------------
# Helper for honesty controls (notebook 3)
# ---------------------------------------------------------------------------------------------
def strong_signal_copy(frame: pd.DataFrame, seed: int = 7) -> pd.DataFrame:
    """Same rows, targets rebuilt from the features with a real, deterministic signal.

    Positive control: if the training chain works, models must find this signal (R2 >= 0.4).
    """
    rng = np.random.default_rng(seed)
    out = frame.copy()
    channel = out["campaign_channel"]
    ctype = out["campaign_type"]
    out["click_through_rate"] = np.clip(
        0.03
        + 0.05 * (channel == "Email")
        + 0.04 * (ctype == "Conversion")
        + 0.000015 * out["ad_spend"]
        + 0.004 * out["email_clicks"]
        + rng.normal(0, 0.008, len(out)),
        0.01,
        0.30,
    )
    out["conversion_rate"] = np.clip(
        0.02
        + 0.0000008 * out["income"]
        + 0.008 * out["previous_purchases"]
        + 0.03 * (channel == "SEO")
        + rng.normal(0, 0.008, len(out)),
        0.01,
        0.20,
    )
    out["website_visits"] = np.round(
        np.clip(
            2
            + 0.003 * out["ad_spend"]
            + 0.12 * out["social_shares"]
            + 6 * (channel == "PPC")
            + rng.normal(0, 3, len(out)),
            0,
            49,
        )
    )
    return out
