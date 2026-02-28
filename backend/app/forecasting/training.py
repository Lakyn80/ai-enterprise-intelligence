"""Model training and persistence."""

from datetime import date, datetime
import json
import os
import uuid

import lightgbm as lgb
import numpy as np
import pandas as pd

from app.forecasting.features import engineer_features
from app.settings import settings


# Features used by the model (must match training)
FEATURE_COLS = [
    "dow",
    "day_of_month",
    "month",
    "week_of_year",
    "is_weekend",
    "lag_7",
    "lag_14",
    "lag_30",
    "rolling_mean_7",
    "rolling_mean_30",
    "price",
    "price_change_pct",
    "promo_flag",
]
TARGET_COL = "quantity"
ENTITY_COL = "product_id"
DATE_COL = "date"


def train_model(
    df: pd.DataFrame,
    data_from: date,
    data_to: date,
    artifacts_dir: str | None = None,
) -> tuple[lgb.Booster, dict]:
    """
    Train LightGBM regressor on prepared data.
    Returns (model, metrics_dict).
    """
    artifacts_dir = artifacts_dir or settings.artifacts_path
    os.makedirs(artifacts_dir, exist_ok=True)

    df = engineer_features(df)
    # Ensure all feature cols exist
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0

    X = df[FEATURE_COLS]
    y = df[TARGET_COL]

    # Deterministic training
    params = {
        "objective": "regression",
        "metric": "mae",
        "verbosity": -1,
        "seed": 42,
        "deterministic": True,
        "force_col_wise": True,
        "num_leaves": 31,
        "learning_rate": 0.05,
        "n_estimators": 100,
    }

    model = lgb.LGBMRegressor(**params)
    model.fit(X, y)

    preds = model.predict(X)
    mae = float(np.mean(np.abs(preds - y)))
    mape = float(np.mean(np.abs((preds - y) / (y + 1e-8)))) * 100

    version = datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    filename = f"lgb_{version}.txt"
    filepath = os.path.join(artifacts_dir, filename)
    model.booster_.save_model(filepath)

    meta = {
        "version": version,
        "file_path": filepath,
        "trained_at": datetime.utcnow().isoformat(),
        "data_from": data_from.isoformat(),
        "data_to": data_to.isoformat(),
        "mae": mae,
        "mape": mape,
        "feature_cols": FEATURE_COLS,
    }
    meta_path = filepath.replace(".txt", "_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return model.booster_, {"mae": mae, "mape": mape, "version": version, "file_path": filepath}


def load_model(file_path: str) -> lgb.Booster:
    """Load LightGBM model from file."""
    return lgb.Booster(model_file=file_path)


def predict(
    model: lgb.Booster,
    df: pd.DataFrame,
) -> np.ndarray:
    """Run prediction on feature-prepared DataFrame."""
    for col in FEATURE_COLS:
        if col not in df.columns:
            df = df.copy()
            df[col] = 0
    X = df[FEATURE_COLS]
    return model.predict(X)
