"""Files of one trained version (LLD 5.6, simplified): 3 XGBoost JSON models and `bundle.json`."""

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import xgboost as xgb

from app.domain.dataset_schema import TARGETS
from app.domain.features import FeatureSpec
from app.domain.scoring import ScoringReference

BUNDLE_SCHEMA_VERSION = 1
BUNDLE_FILE = "bundle.json"


@dataclass(frozen=True)
class ModelBundle:
    model_version_id: str
    trained_at: str
    spec: FeatureSpec
    models: dict[str, xgb.XGBRegressor]
    training_ranges: dict[str, dict[str, float]]
    engagement_defaults: dict[str, Any]
    scoring_reference: ScoringReference
    metrics: dict[str, Any]
    global_importance: dict[str, list[dict[str, Any]]]
    # Mean of each figure over all the rows (display only); absent from bundles saved earlier.
    target_means: dict[str, float] | None = None


def save_bundle(bundle: ModelBundle, directory: Path) -> Path:
    """Write the four files into a temporary folder, then move it in place (all or nothing)."""
    staging = directory.with_name(directory.name + ".tmp")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    for target in TARGETS:
        bundle.models[target].save_model(staging / f"{target}.json")
    payload = {
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "model_version_id": bundle.model_version_id,
        "trained_at": bundle.trained_at,
        "data_scope": "all",
        "feature_spec": bundle.spec.to_dict(),
        "features_used": bundle.spec.features_used,
        "training_ranges": bundle.training_ranges,
        "engagement_defaults": bundle.engagement_defaults,
        "scoring_reference": bundle.scoring_reference.to_dict(),
        "metrics": bundle.metrics,
        "global_importance": bundle.global_importance,
        "target_means": bundle.target_means,
    }
    (staging / BUNDLE_FILE).write_text(json.dumps(payload))
    shutil.rmtree(directory, ignore_errors=True)
    os.replace(staging, directory)
    return directory


def load_bundle(directory: Path) -> ModelBundle:
    data = json.loads((directory / BUNDLE_FILE).read_text())
    if data["bundle_schema_version"] != BUNDLE_SCHEMA_VERSION:
        raise ValueError("Unsupported model bundle version.")
    models = {}
    for target in TARGETS:
        model = xgb.XGBRegressor()
        model.load_model(directory / f"{target}.json")
        models[target] = model
    return ModelBundle(
        model_version_id=data["model_version_id"],
        trained_at=data["trained_at"],
        spec=FeatureSpec.from_dict(data["feature_spec"]),
        models=models,
        training_ranges=data["training_ranges"],
        engagement_defaults=data["engagement_defaults"],
        scoring_reference=ScoringReference.from_dict(data["scoring_reference"]),
        metrics=data["metrics"],
        global_importance=data["global_importance"],
        target_means=data.get("target_means"),
    )
