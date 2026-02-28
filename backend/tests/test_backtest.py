"""Tests for backtest module."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.forecasting.backtest import time_based_split, rolling_backtest, backtest_metrics


@pytest.fixture
def sample_df():
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(100)]
    data = []
    for d in dates:
        data.append({
            "date": d,
            "product_id": "P001",
            "quantity": 10.0 + (d.day % 5),
            "price": 19.99,
        })
    return pd.DataFrame(data)


def test_time_based_split(sample_df):
    train, test = time_based_split(sample_df, "date", train_pct=0.8)
    assert len(train) > 0
    assert len(test) > 0
    assert len(train) + len(test) == len(sample_df)
    max_train_date = train["date"].max()
    min_test_date = test["date"].min()
    assert max_train_date < min_test_date


def test_backtest_metrics():
    actuals = np.array([10, 20, 30])
    preds = np.array([11, 19, 31])
    m = backtest_metrics(actuals, preds)
    assert "mae" in m
    assert "mape" in m
    assert m["mae"] == 1.0
    assert m["mape"] >= 0
