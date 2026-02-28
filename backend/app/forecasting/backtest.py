"""Backtesting module - time-based split and rolling backtest."""

from datetime import date, timedelta
from typing import Callable

import numpy as np
import pandas as pd

from app.forecasting.features import engineer_features
from app.forecasting.training import FEATURE_COLS, TARGET_COL


def time_based_split(
    df: pd.DataFrame,
    date_col: str,
    train_pct: float = 0.8,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split data by time - earlier portion for train, later for test.
    train_pct: fraction of date range for training.
    """
    df = df.sort_values(date_col)
    dates = df[date_col].unique()
    n_train = int(len(dates) * train_pct)
    train_dates = set(dates[:n_train])
    df["_split"] = df[date_col].apply(lambda d: "train" if d in train_dates else "test")
    train_df = df[df["_split"] == "train"].drop(columns=["_split"])
    test_df = df[df["_split"] == "test"].drop(columns=["_split"])
    return train_df, test_df


def rolling_backtest(
    df: pd.DataFrame,
    date_col: str,
    entity_col: str,
    predict_fn: Callable[[pd.DataFrame], np.ndarray],
    train_window_days: int = 90,
    step_days: int = 7,
) -> tuple[np.ndarray, np.ndarray, list[date]]:
    """
    Rolling backtest: train on sliding window, predict next step_days.
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
        test_start = dates[i]
        test_end = dates[min(i + step_days - 1, len(dates) - 1)]

        train_df = df[(df[date_col] >= dates[i - train_window_days]) & (df[date_col] <= train_end)]
        test_df = df[(df[date_col] >= test_start) & (df[date_col] <= test_end)]

        if train_df.empty or test_df.empty:
            continue

        train_feat = engineer_features(train_df)
        test_feat = engineer_features(test_df)

        for col in FEATURE_COLS:
            if col not in test_feat.columns:
                test_feat[col] = 0

        pred = predict_fn(test_feat)
        actual = test_df[TARGET_COL].values

        actuals.extend(actual.tolist())
        preds.extend(pred.tolist())
        test_dates.extend(test_df[date_col].unique().tolist())

    return np.array(actuals), np.array(preds), test_dates


def backtest_metrics(actuals: np.ndarray, preds: np.ndarray) -> dict[str, float]:
    """Compute MAE and MAPE from backtest results."""
    if len(actuals) == 0 or len(preds) == 0:
        return {"mae": 0.0, "mape": 0.0}
    mae = float(np.mean(np.abs(actuals - preds)))
    mape = float(np.mean(np.abs((preds - actuals) / (actuals + 1e-8)))) * 100
    return {"mae": mae, "mape": mape}
