"""Model training and persistence."""

from datetime import date, datetime
import json
import logging
import os
import uuid

import lightgbm as lgb
import numpy as np
import pandas as pd

from app.forecasting.features import engineer_features
from app.settings import settings

logger = logging.getLogger(__name__)

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
    split_date: date | None = None,
    artifacts_dir: str | None = None,
) -> tuple[lgb.Booster, dict]:
    """
    Train LightGBM regressor on prepared data.

    When split_date is provided:
      - Trains on rows with date < split_date  (zero data leakage)
      - Evaluates MAE/RMSE/MAPE on rows with date >= split_date (out-of-sample)

    Without split_date:
      - Trains on all data
      - Evaluates on training data (in-sample; reported as eval_source='train')

    Returns (booster, metrics_dict).
    """
    artifacts_dir = artifacts_dir or settings.artifacts_path
    os.makedirs(artifacts_dir, exist_ok=True)

    # Feature engineering on full DataFrame so lag/rolling features for the test
    # portion reference real history from the training window.
    df = engineer_features(df)
    df["target"] = np.log1p(df[TARGET_COL])
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0

    if split_date is not None:
        split_ts = pd.Timestamp(split_date)
        train_mask = pd.to_datetime(df[DATE_COL]) < split_ts
        test_mask = pd.to_datetime(df[DATE_COL]) >= split_ts
        train_df = df[train_mask]
        test_df = df[test_mask]
        if len(train_df) < 50:
            raise ValueError(
                f"Insufficient training rows before split_date {split_date} "
                f"(got {len(train_df)}, need ≥ 50)"
            )
        logger.info(
            "Time-based split: training on %d rows [%s → %s), evaluating on %d rows [%s → %s]",
            len(train_df),
            data_from,
            split_date,
            len(test_df),
            split_date,
            data_to,
        )
    else:
        train_df = df
        test_df = None
        logger.info("Training on full dataset: %d rows [%s → %s]", len(df), data_from, data_to)

    X_train = train_df[FEATURE_COLS]
    y_train = train_df["target"]

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
    model.fit(X_train, y_train)

    # --- Evaluation ---
    if test_df is not None and not test_df.empty:
        X_test = test_df[FEATURE_COLS].fillna(0)
        quantity_pred = np.expm1(model.predict(X_test))
        actuals = test_df[TARGET_COL].values
        eval_source = "test"
        n_eval = int(len(actuals))
    else:
        quantity_pred = np.expm1(model.predict(X_train))
        actuals = train_df[TARGET_COL].values
        eval_source = "train"
        n_eval = int(len(actuals))

    errors = quantity_pred - actuals
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    nonzero = actuals > 0
    mape = (
        float(np.mean(np.abs(errors[nonzero] / actuals[nonzero]))) * 100
        if nonzero.any()
        else 0.0
    )

    logger.info(
        "Evaluation (%s) – MAE: %.4f  RMSE: %.4f  MAPE: %.2f%%  n=%d",
        eval_source,
        mae,
        rmse,
        mape,
        n_eval,
    )

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
        "split_date": split_date.isoformat() if split_date else None,
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "n_eval_samples": n_eval,
        "eval_source": eval_source,
        "feature_cols": FEATURE_COLS,
    }
    meta_path = filepath.replace(".txt", "_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return model.booster_, {
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "n_eval_samples": n_eval,
        "eval_source": eval_source,
        "version": version,
        "file_path": filepath,
    }


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
