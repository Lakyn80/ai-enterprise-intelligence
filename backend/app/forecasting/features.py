"""Feature engineering for forecasting model."""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.shared.utils import safe_float


def build_time_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Add time-based features."""
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    out["dow"] = out[date_col].dt.dayofweek
    out["day_of_month"] = out[date_col].dt.day
    out["month"] = out[date_col].dt.month
    out["week_of_year"] = out[date_col].dt.isocalendar().week.astype(int)
    out["is_weekend"] = (out["dow"] >= 5).astype(int)
    return out


def build_lag_features(
    df: pd.DataFrame,
    target_col: str,
    entity_col: str,
    date_col: str,
    lags: tuple[int, ...] = (7, 14, 30),
) -> pd.DataFrame:
    """Add lag features per product."""
    out = df.copy()
    out = out.sort_values([entity_col, date_col])
    for lag in lags:
        out[f"lag_{lag}"] = out.groupby(entity_col)[target_col].shift(lag)
    return out


def build_rolling_features(
    df: pd.DataFrame,
    target_col: str,
    entity_col: str,
    date_col: str,
    windows: tuple[int, ...] = (7, 30),
) -> pd.DataFrame:
    """Add rolling mean features per product."""
    out = df.copy()
    out = out.sort_values([entity_col, date_col])
    for w in windows:
        out[f"rolling_mean_{w}"] = (
            out.groupby(entity_col)[target_col]
            .transform(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
        )
    return out


def build_price_features(
    df: pd.DataFrame,
    price_col: str = "price",
    entity_col: str = "product_id",
    date_col: str = "date",
) -> pd.DataFrame:
    """Add price-related features (including price change)."""
    out = df.copy()
    out = out.sort_values([entity_col, date_col])
    out["price_change_pct"] = out.groupby(entity_col)[price_col].pct_change()
    out["price_change_pct"] = out["price_change_pct"].fillna(0)
    out["log_price"] = np.log(out[price_col].clip(lower=1e-8))
    out["rolling_mean_price_30"] = (
        out.groupby(entity_col)[price_col]
        .transform(lambda x: x.shift(1).rolling(window=30, min_periods=7).mean())
    )
    out["price_vs_avg_30"] = out[price_col] / out["rolling_mean_price_30"]
    out["price_vs_avg_30"] = out["price_vs_avg_30"].replace([np.inf, -np.inf], np.nan).fillna(1)
    return out


def engineer_features(
    df: pd.DataFrame,
    target_col: str = "quantity",
    entity_col: str = "product_id",
    date_col: str = "date",
    price_col: str = "price",
    promo_col: str = "promo_flag",
) -> pd.DataFrame:
    """
    Full feature engineering pipeline.
    Returns DataFrame with all features for model training.
    """
    out = df.copy()
    out[price_col] = out[price_col].fillna(out[price_col].median())
    out[promo_col] = out[promo_col].fillna(0).astype(int)

    out = build_time_features(out, date_col)
    out = build_lag_features(out, target_col, entity_col, date_col)
    out = build_rolling_features(out, target_col, entity_col, date_col)
    out = build_price_features(out, price_col, entity_col, date_col)

    # Drop rows with NaN in lag_30 (from lags at start), or fillna if all NaN (inference)
    if out["lag_30"].notna().any():
        out = out.dropna(subset=["lag_30"])
    else:
        out = out.fillna(0)

    return out


def apply_price_delta(
    df: pd.DataFrame,
    price_delta_pct: float,
    price_col: str = "price",
) -> pd.DataFrame:
    """
    Apply hypothetical price change for scenario analysis.
    price_delta_pct: e.g. 5 for +5%, -10 for -10%
    """
    out = df.copy()
    factor = 1.0 + (price_delta_pct / 100.0)
    out[price_col] = out[price_col] * factor
    return out
