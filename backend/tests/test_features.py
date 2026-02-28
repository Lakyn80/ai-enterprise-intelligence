"""Tests for feature engineering."""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.forecasting.features import (
    build_lag_features,
    build_rolling_features,
    build_time_features,
    engineer_features,
    apply_price_delta,
)


@pytest.fixture
def sample_df():
    """Sample sales DataFrame."""
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(60)]
    data = []
    for d in dates:
        for pid in ["P001", "P002"]:
            data.append({
                "product_id": pid,
                "date": d,
                "quantity": 10.0,
                "revenue": 199.9,
                "price": 19.99,
                "promo_flag": 1 if d.weekday() >= 5 else 0,
                "category_id": "C1",
            })
    return pd.DataFrame(data)


def test_build_time_features(sample_df):
    df = build_time_features(sample_df)
    assert "dow" in df.columns
    assert "month" in df.columns
    assert "is_weekend" in df.columns
    assert df["dow"].min() >= 0
    assert df["dow"].max() <= 6


def test_build_lag_features(sample_df):
    df = build_lag_features(
        sample_df, target_col="quantity", entity_col="product_id", date_col="date",
        lags=(7, 14),
    )
    assert "lag_7" in df.columns
    assert "lag_14" in df.columns
    # First rows should have NaN for lags
    assert df["lag_7"].isna().any() or df["lag_14"].isna().any()


def test_build_rolling_features(sample_df):
    df = build_rolling_features(
        sample_df, target_col="quantity", entity_col="product_id", date_col="date",
        windows=(7,),
    )
    assert "rolling_mean_7" in df.columns


def test_engineer_features(sample_df):
    df = engineer_features(sample_df)
    assert "lag_30" in df.columns or "lag_7" in df.columns
    assert "rolling_mean_7" in df.columns or "rolling_mean_30" in df.columns
    assert "price_change_pct" in df.columns


def test_apply_price_delta(sample_df):
    df = apply_price_delta(sample_df, 5.0)
    expected_first = sample_df["price"].iloc[0] * 1.05
    assert abs(df["price"].iloc[0] - expected_first) < 0.01
