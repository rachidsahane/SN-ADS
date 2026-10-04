"""XGBoost parameters (LLD 5.4): same for the three models, no search, reproducible."""

from typing import Any, Final

XGB_PARAMS: Final[dict[str, Any]] = {
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
