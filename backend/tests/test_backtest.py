"""Tests for backtest module."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.forecasting.backtest import (
    time_based_split,
    time_based_split_by_date,
    rolling_backtest,
    backtest_metrics,
    evaluate_time_split,
    _compute_test_features_with_context,
)
from app.forecasting.training import DATE_COL, ENTITY_COL, TARGET_COL


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_df():
    """100-day single-product DataFrame with deterministic quantity."""
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(100)]
    rows = [
        {
            "date": d,
            "product_id": "P001",
            "quantity": 10.0 + (d.day % 5),
            "price": 19.99,
            "promo_flag": 0,
            "revenue": 199.9,
        }
        for d in dates
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def multi_product_df():
    """60-day, 2-product DataFrame."""
    rows = []
    for pid in ["P001", "P002"]:
        for i in range(60):
            d = date(2024, 1, 1) + timedelta(days=i)
            rows.append(
                {
                    "date": d,
                    "product_id": pid,
                    "quantity": float(10 + i % 7),
                    "price": 20.0,
                    "promo_flag": 0,
                    "revenue": 200.0,
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# time_based_split (original, percentage-based)
# ---------------------------------------------------------------------------

def test_time_based_split_sizes(sample_df):
    train, test = time_based_split(sample_df, "date", train_pct=0.8)
    assert len(train) > 0
    assert len(test) > 0
    assert len(train) + len(test) == len(sample_df)


def test_time_based_split_no_overlap(sample_df):
    train, test = time_based_split(sample_df, "date", train_pct=0.8)
    assert train["date"].max() < test["date"].min()


# ---------------------------------------------------------------------------
# time_based_split_by_date (explicit split date)
# ---------------------------------------------------------------------------

def test_time_based_split_by_date_boundary(sample_df):
    split = date(2024, 3, 1)
    train, test = time_based_split_by_date(sample_df, "date", split)
    assert (train["date"] < split).all(), "Train must not include split_date or later"
    assert (test["date"] >= split).all(), "Test must not include rows before split_date"


def test_time_based_split_by_date_complete(sample_df):
    split = date(2024, 3, 1)
    train, test = time_based_split_by_date(sample_df, "date", split)
    assert len(train) + len(test) == len(sample_df)


def test_time_based_split_by_date_no_leakage(multi_product_df):
    split = date(2024, 2, 15)
    train, test = time_based_split_by_date(multi_product_df, DATE_COL, split)
    assert train[DATE_COL].max() < split
    assert test[DATE_COL].min() >= split


# ---------------------------------------------------------------------------
# backtest_metrics
# ---------------------------------------------------------------------------

def test_backtest_metrics_values():
    actuals = np.array([10.0, 20.0, 30.0])
    preds = np.array([11.0, 19.0, 31.0])
    m = backtest_metrics(actuals, preds)
    assert m["mae"] == pytest.approx(1.0)
    assert m["rmse"] == pytest.approx(1.0)
    assert m["mape"] >= 0


def test_backtest_metrics_has_rmse():
    m = backtest_metrics(np.array([10.0, 20.0]), np.array([12.0, 18.0]))
    assert "rmse" in m
    # RMSE >= MAE always
    assert m["rmse"] >= m["mae"]


def test_backtest_metrics_zero_actuals():
    """MAPE must be 0 when all actuals are 0 (no division by zero)."""
    actuals = np.array([0.0, 0.0, 0.0])
    preds = np.array([1.0, 2.0, 3.0])
    m = backtest_metrics(actuals, preds)
    assert m["mape"] == 0.0
    assert m["mae"] > 0


def test_backtest_metrics_empty():
    m = backtest_metrics(np.array([]), np.array([]))
    assert m["mae"] == 0.0
    assert m["rmse"] == 0.0
    assert m["mape"] == 0.0


def test_backtest_metrics_mape_excludes_zeros():
    """MAPE should only use non-zero actuals."""
    actuals = np.array([0.0, 10.0, 20.0])
    preds = np.array([5.0, 11.0, 19.0])
    m = backtest_metrics(actuals, preds)
    # Manual: mean(|[1, 1]| / [10, 20]) * 100 = mean([10%, 5%]) = 7.5%
    assert m["mape"] == pytest.approx(7.5, abs=0.01)


# ---------------------------------------------------------------------------
# _compute_test_features_with_context (lag leakage fix)
# ---------------------------------------------------------------------------

def test_context_features_lag30_not_all_zero(multi_product_df):
    """
    lag_30 for test rows should be non-zero when computed with train context.
    Without context, engineer_features(test_df_only) would fill lag_30 with 0.
    """
    split = date(2024, 2, 1)
    train_df, test_df = time_based_split_by_date(multi_product_df, DATE_COL, split)
    test_feat = _compute_test_features_with_context(train_df, test_df)
    assert len(test_feat) > 0
    assert (test_feat["lag_30"] != 0).any(), (
        "lag_30 is all zeros – context from train window not applied"
    )


def test_context_features_no_future_leakage(multi_product_df):
    """Test features must only contain test-window dates."""
    split = date(2024, 2, 1)
    train_df, test_df = time_based_split_by_date(multi_product_df, DATE_COL, split)
    test_feat = _compute_test_features_with_context(train_df, test_df)
    test_dates = set(pd.to_datetime(test_df[DATE_COL]).dt.date)
    result_dates = set(pd.to_datetime(test_feat[DATE_COL]).dt.date)
    assert result_dates.issubset(test_dates), "Feature rows outside test window"


# ---------------------------------------------------------------------------
# evaluate_time_split
# ---------------------------------------------------------------------------

def test_evaluate_time_split_structure(multi_product_df):
    split = date(2024, 2, 1)
    train_df, test_df = time_based_split_by_date(multi_product_df, DATE_COL, split)

    def predict_fn(df):
        return df[TARGET_COL].values * 1.1  # fixed 10% overestimate

    result = evaluate_time_split(train_df, test_df, predict_fn)

    assert "mae" in result
    assert "rmse" in result
    assert "mape" in result
    assert "n_samples" in result
    assert "date_range" in result
    assert result["n_samples"] > 0


def test_evaluate_time_split_date_range(multi_product_df):
    split = date(2024, 2, 1)
    train_df, test_df = time_based_split_by_date(multi_product_df, DATE_COL, split)

    result = evaluate_time_split(train_df, test_df, lambda df: df[TARGET_COL].values)

    dr = result["date_range"]
    assert dr["test_start"] == str(split)
    assert dr["train_end"] < dr["test_start"]


def test_evaluate_time_split_perfect_predict(multi_product_df):
    """Perfect predictions should yield MAE=RMSE=MAPE=0."""
    split = date(2024, 2, 1)
    train_df, test_df = time_based_split_by_date(multi_product_df, DATE_COL, split)

    result = evaluate_time_split(train_df, test_df, lambda df: df[TARGET_COL].values)

    assert result["mae"] == pytest.approx(0.0, abs=1e-6)
    assert result["rmse"] == pytest.approx(0.0, abs=1e-6)
    assert result["mape"] == pytest.approx(0.0, abs=1e-6)


def test_evaluate_time_split_empty(sample_df):
    empty = pd.DataFrame(columns=sample_df.columns)
    result = evaluate_time_split(empty, sample_df, lambda df: df[TARGET_COL].values)
    assert result["n_samples"] == 0
    assert result["mae"] == 0.0


# ---------------------------------------------------------------------------
# rolling_backtest
# ---------------------------------------------------------------------------

def test_rolling_backtest_returns_arrays(sample_df):
    sample_df = sample_df.copy()
    sample_df["promo_flag"] = 0
    sample_df["revenue"] = 200.0

    def predict_fn(df):
        return df[TARGET_COL].values if TARGET_COL in df.columns else np.zeros(len(df))

    actuals, preds, test_dates = rolling_backtest(
        sample_df,
        date_col=DATE_COL,
        entity_col=ENTITY_COL,
        predict_fn=predict_fn,
        train_window_days=60,
        step_days=7,
    )
    assert isinstance(actuals, np.ndarray)
    assert isinstance(preds, np.ndarray)
    assert len(actuals) == len(preds)
    assert len(test_dates) > 0


def test_rolling_backtest_insufficient_data(sample_df):
    tiny = sample_df.head(10)
    actuals, preds, _ = rolling_backtest(
        tiny, DATE_COL, ENTITY_COL, lambda df: np.zeros(len(df)),
        train_window_days=90, step_days=7,
    )
    assert len(actuals) == 0
    assert len(preds) == 0
