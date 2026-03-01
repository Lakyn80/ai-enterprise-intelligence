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
    "log_price",
    "price_vs_avg_30",
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
    df["target"] = np.log1p(df[TARGET_COL])
    # Ensure all feature cols exist
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0

    X = df[FEATURE_COLS]
    y = df["target"]

    # Deterministic training
    params = {
        "objective": "regression",
        "metric": "mae",
        "verbosity": -1,
        "seed": 42,
        "deterministic": True,
        "force_col_wise": True,
        "num_leaves": 63,
        "learning_rate": 0.05,
        "n_estimators": 300,
    }

    model = lgb.LGBMRegressor(**params)
    model.fit(X, y)

    preds = model.predict(X)
    quantity_pred = np.expm1(preds)
    mae = float(np.mean(np.abs(quantity_pred - df[TARGET_COL])))
    mape = float(np.mean(np.abs((quantity_pred - df[TARGET_COL]) / (df[TARGET_COL] + 1e-8)))) * 100

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
    """Run prediction on feature-prepared DataFrame. Returns quantity (expm1 of log-space output)."""
    for col in FEATURE_COLS:
        if col not in df.columns:
            df = df.copy()
            df[col] = 0
    X = df[FEATURE_COLS]
    pred = model.predict(X)
    return np.expm1(pred)
