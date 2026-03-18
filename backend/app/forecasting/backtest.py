"""Backtesting module - time-based split and rolling backtest."""

from datetime import date, timedelta
from typing import Callable

import numpy as np
import pandas as pd

from app.forecasting.features import engineer_features
from app.forecasting.training import DATE_COL, ENTITY_COL, FEATURE_COLS, TARGET_COL

# Rows of lookback context per product needed for lag_30 to be valid
_LAG_CONTEXT_ROWS = 30


def time_based_split(
    df: pd.DataFrame,
    date_col: str,
    train_pct: float = 0.8,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split data by time - earlier portion for train, later for test.
    train_pct: fraction of unique dates allocated to training.
    """
    df = df.sort_values(date_col)
    dates = df[date_col].unique()
    n_train = int(len(dates) * train_pct)
    train_dates = set(dates[:n_train])
    df = df.copy()
    df["_split"] = df[date_col].apply(lambda d: "train" if d in train_dates else "test")
    train_df = df[df["_split"] == "train"].drop(columns=["_split"])
    test_df = df[df["_split"] == "test"].drop(columns=["_split"])
    return train_df, test_df


def time_based_split_by_date(
    df: pd.DataFrame,
    date_col: str,
    split_date: date,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split data at an explicit split_date boundary.
    Train: rows with date < split_date.
    Test:  rows with date > train_end  (= train_end + 1 day).

    Using train_end + 1 day (not split_date) as the test boundary ensures
    test_start is always exactly one day after the last training row, even
    when the dataset has gaps around split_date.
    """
    df = df.sort_values(date_col)
    train_df = df[df[date_col] < split_date].copy()
    if train_df.empty:
        return train_df, df.copy()

    train_end = pd.to_datetime(train_df[date_col]).max()
    test_start = train_end + timedelta(days=1)
    test_df = df[pd.to_datetime(df[date_col]) >= test_start].copy()

    if not train_df.empty and not test_df.empty:
        assert pd.to_datetime(train_df[date_col]).max() < pd.to_datetime(test_df[date_col]).min(), (
            f"Split leakage: train_end={pd.to_datetime(train_df[date_col]).max().date()} "
            f">= test_start={pd.to_datetime(test_df[date_col]).min().date()}"
        )

    return train_df, test_df


def _compute_test_features_with_context(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Engineer features for test rows with training context to prevent lag/rolling leakage.

    Problem: calling engineer_features(test_df) alone causes the first ~30 rows of each
    product group to have NaN lags (no prior history), which engineer_features fills with 0.
    These zeroed lags are wrong – the model was trained on real lag values.

    Fix: prepend the last _LAG_CONTEXT_ROWS training rows per product before feature
    engineering, then return only the test rows with correctly computed lag/rolling features.
    """
    # Keep only tail of each product's training history for context
    context = (
        train_df.sort_values(DATE_COL)
        .groupby(ENTITY_COL, group_keys=False)
        .tail(_LAG_CONTEXT_ROWS)
    )
    combined = (
        pd.concat([context, test_df], ignore_index=True)
        .sort_values([ENTITY_COL, DATE_COL])
    )
    combined_feat = engineer_features(combined)

    # Return only the rows that belong to the test window.
    # Normalise to date objects to avoid dtype mismatch in isin (pandas FutureWarning).
    test_dates = set(pd.to_datetime(test_df[DATE_COL]).dt.date)
    test_feat = combined_feat[
        pd.to_datetime(combined_feat[DATE_COL]).dt.date.isin(test_dates)
    ].copy()

    for col in FEATURE_COLS:
        if col not in test_feat.columns:
            test_feat[col] = 0
    test_feat[FEATURE_COLS] = test_feat[FEATURE_COLS].fillna(0)
    return test_feat


def rolling_backtest(
    df: pd.DataFrame,
    date_col: str,
    entity_col: str,
    predict_fn: Callable[[pd.DataFrame], np.ndarray],
    train_window_days: int = 90,
    step_days: int = 7,
) -> tuple[np.ndarray, np.ndarray, list[date]]:
    """
    Rolling backtest: evaluate predict_fn on successive sliding test windows.

    Features for each test window are computed with context from the train window
    (see _compute_test_features_with_context) to prevent lag/rolling leakage.

    Returns (actuals, predictions, test_dates).
    """
    df = df.sort_values([entity_col, date_col])
    dates = sorted(df[date_col].unique())
    if len(dates) < train_window_days + step_days:
        return np.array([]), np.array([]), []

    actuals: list[float] = []
    preds: list[float] = []
    test_dates: list[date] = []

    for i in range(train_window_days, len(dates) - step_days + 1, step_days):
        train_end = dates[i - 1]
        # Always anchor test exactly 1 day after train_end so there is no gap
        # even when the dataset has missing dates (dates[i] could be train_end + N days).
        test_start = train_end + timedelta(days=1)
        test_end = dates[min(i + step_days - 1, len(dates) - 1)]

        train_df = df[
            (df[date_col] >= dates[i - train_window_days]) & (df[date_col] <= train_end)
        ]
        test_df = df[(df[date_col] >= test_start) & (df[date_col] <= test_end)]

        if train_df.empty or test_df.empty:
            continue

        assert train_df[date_col].max() < test_df[date_col].min(), (
            f"Rolling split leakage at window i={i}: "
            f"train_end={train_df[date_col].max()}  test_start={test_df[date_col].min()}"
        )

        test_feat = _compute_test_features_with_context(train_df, test_df)
        if test_feat.empty:
            continue

        pred = predict_fn(test_feat)
        actual = test_df[TARGET_COL].values

        actuals.extend(actual.tolist())
        preds.extend(pred.tolist())
        test_dates.extend(test_df[date_col].unique().tolist())

    return np.array(actuals), np.array(preds), test_dates


def backtest_metrics(actuals: np.ndarray, preds: np.ndarray) -> dict[str, float]:
    """
    Compute MAE, RMSE, and MAPE.
    MAPE excludes zero-actual rows to avoid division by zero (IEEE-safe).
    """
    if len(actuals) == 0 or len(preds) == 0:
        return {"mae": 0.0, "rmse": 0.0, "mape": 0.0}

    errors = actuals - preds
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    nonzero = actuals > 0
    mape = (
        float(np.mean(np.abs(errors[nonzero] / actuals[nonzero]))) * 100
        if nonzero.any()
        else 0.0
    )
    return {"mae": mae, "rmse": rmse, "mape": mape}


def evaluate_time_split(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    predict_fn: Callable[[pd.DataFrame], np.ndarray],
) -> dict:
    """
    Evaluate predict_fn on an explicit train/test time split.

    Returns structured evaluation dict:
    {
        "mae": float,
        "rmse": float,
        "mape": float,
        "n_samples": int,
        "date_range": {
            "train_start": str, "train_end": str,
            "test_start": str,  "test_end": str
        }
    }
    """
    empty = {"mae": 0.0, "rmse": 0.0, "mape": 0.0, "n_samples": 0, "date_range": {}}
    if train_df.empty or test_df.empty:
        return empty

    test_feat = _compute_test_features_with_context(train_df, test_df)
    if test_feat.empty:
        return empty

    preds = predict_fn(test_feat)
    actuals = test_feat[TARGET_COL].values

    metrics = backtest_metrics(actuals, preds)
    metrics["n_samples"] = int(len(actuals))
    metrics["date_range"] = {
        "train_start": str(train_df[DATE_COL].min()),
        "train_end": str(train_df[DATE_COL].max()),
        "test_start": str(test_df[DATE_COL].min()),
        "test_end": str(test_df[DATE_COL].max()),
    }
    return metrics
