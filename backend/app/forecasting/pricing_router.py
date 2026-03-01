"""Pricing optimization API - simulation layer over existing LightGBM model."""

import os

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.deps import AsyncSessionDep
from app.forecasting.features import engineer_features
from app.forecasting.repository import ForecastingRepository
from app.forecasting.training import FEATURE_COLS, load_model, predict

router = APIRouter(prefix="/api", tags=["pricing"])

_PRODUCT_ALIASES = {"P001": "P0001", "P002": "P0002", "P003": "P0003"}


def _get_repo(session: AsyncSessionDep) -> ForecastingRepository:
    return ForecastingRepository(session)


class PricingOptimizeRequest(BaseModel):
    """Request body for pricing optimize endpoint."""

    product_id: str
    cost: float
    price_min: float
    price_max: float
    n_steps: int = 50
    max_price_change_pct: float = 0.08
    min_margin_pct: float = 0.15
    smoothing_alpha: float = 0.3


@router.post("/pricing/optimize")
async def pricing_optimize(
    body: PricingOptimizeRequest,
    session: AsyncSessionDep,
):
    """Run price simulation for product and return optimal price (max profit).

    Reuses existing trained model - does not modify training or DB.
    """
    product_id = body.product_id
    cost = body.cost
    price_min = body.price_min
    price_max = body.price_max
    n_steps = body.n_steps
    max_price_change_pct = body.max_price_change_pct
    min_margin_pct = body.min_margin_pct
    smoothing_alpha = body.smoothing_alpha

    if not product_id or cost is None or price_min is None or price_max is None:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: product_id, cost, price_min, price_max",
        )
    if price_min >= price_max:
        raise HTTPException(status_code=400, detail="price_min must be less than price_max")
    if n_steps < 2:
        raise HTTPException(status_code=400, detail="n_steps must be >= 2")
    if max_price_change_pct < 0:
        raise HTTPException(status_code=400, detail="max_price_change_pct must be >= 0")
    if min_margin_pct < 0:
        raise HTTPException(status_code=400, detail="min_margin_pct must be >= 0")
    if not (0.0 <= smoothing_alpha <= 1.0):
        raise HTTPException(status_code=400, detail="smoothing_alpha must be between 0 and 1")

    product_id = _PRODUCT_ALIASES.get(product_id, product_id)
    repo = _get_repo(session)

    # 1) Load model
    file_path = await repo.get_active_model_path()
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="No trained model available")
    model = load_model(file_path)

    # 2) Load recent data (min 30 days, use 90 for lag_30)
    df = await repo.get_latest_sales_df([product_id], min_days=90)
    if df.empty or len(df) < 30:
        raise HTTPException(
            status_code=400,
            detail="Insufficient data - need at least 30 days of history",
        )

    # Aggregate by date if duplicates
    if "date" in df.columns and "product_id" in df.columns:
        agg = df.groupby(["date", "product_id"]).agg(
            quantity=("quantity", "sum"),
            revenue=("revenue", "sum"),
            price=("price", "mean"),
            promo_flag=("promo_flag", "max"),
            category_id=("category_id", "first"),
        )
        df = agg.reset_index()

    # 3) Compute baseline features
    df_feat = engineer_features(df)
    for col in FEATURE_COLS:
        if col not in df_feat.columns:
            df_feat[col] = 0
    df_feat[FEATURE_COLS] = df_feat[FEATURE_COLS].fillna(0)

    # Drop rows with NaN lag_30 to get valid feature rows
    if "lag_30" in df_feat.columns and df_feat["lag_30"].notna().any():
        df_feat = df_feat.dropna(subset=["lag_30"])

    if df_feat.empty:
        raise HTTPException(
            status_code=400,
            detail="Insufficient data for feature engineering (need 30+ days)",
        )

    # 4) Extract base row (last row)
    base_row = df_feat.iloc[-1].copy()
    base_price = float(base_row["price"])
    base_rolling_mean_price = float(base_row.get("rolling_mean_price_30", base_price))
    if base_rolling_mean_price <= 0:
        base_rolling_mean_price = base_price if base_price > 0 else 1.0

    # Current quantity pred (baseline)
    base_quantity = max(0.0, float(predict(model, df_feat.tail(1))[0]))
    current_revenue = base_price * base_quantity
    current_profit = (base_price - cost) * base_quantity

    # 5) Generate candidate prices
    candidate_prices = np.linspace(price_min, price_max, n_steps)
    scenarios = []
    best = None
    best_profit = float("-inf")

    for p in candidate_prices:
        p = float(p)
        row = base_row.copy()

        # Replace price-related features
        row["price"] = p
        row["log_price"] = np.log(max(p, 1e-8))
        row["price_vs_avg_30"] = p / base_rolling_mean_price
        row["price_change_pct"] = (p - base_price) / base_price if base_price > 0 else 0.0

        for col in FEATURE_COLS:
            if col not in row.index:
                row[col] = 0

        X = pd.DataFrame([row[FEATURE_COLS]])
        quantity_pred = float(predict(model, X)[0])
        quantity_pred = max(0.0, quantity_pred)

        revenue = p * quantity_pred
        profit = (p - cost) * quantity_pred

        scenarios.append({
            "price": round(p, 2),
            "quantity": round(quantity_pred, 2),
            "revenue": round(revenue, 2),
            "profit": round(profit, 2),
        })

        if profit > best_profit:
            best_profit = profit
            best = {
                "optimal_price": round(p, 2),
                "expected_quantity": round(quantity_pred, 2),
                "expected_revenue": round(revenue, 2),
                "expected_profit": round(profit, 2),
            }

    if best is None and scenarios:
        raw_optimal_price = base_price
    elif best is not None:
        raw_optimal_price = float(best["optimal_price"])
    else:
        raw_optimal_price = base_price

    # STEP 2 – business constraints
    if base_price > 0:
        allowed_min = base_price * (1.0 - max_price_change_pct)
        allowed_max = base_price * (1.0 + max_price_change_pct)
    else:
        allowed_min = price_min
        allowed_max = price_max

    constrained_price = max(min(raw_optimal_price, allowed_max), allowed_min)
    min_allowed_price = cost * (1.0 + min_margin_pct)
    if constrained_price < min_allowed_price:
        constrained_price = min_allowed_price

    # STEP 3 – smoothing
    final_price = (1.0 - smoothing_alpha) * base_price + smoothing_alpha * constrained_price

    # Recompute quantity at final_price
    final_row = base_row.copy()
    final_row["price"] = final_price
    final_row["log_price"] = np.log(max(final_price, 1e-8))
    final_row["price_vs_avg_30"] = final_price / base_rolling_mean_price
    final_row["price_change_pct"] = (final_price - base_price) / base_price if base_price > 0 else 0.0

    for col in FEATURE_COLS:
        if col not in final_row.index:
            final_row[col] = 0

    X_final = pd.DataFrame([final_row[FEATURE_COLS]])
    final_quantity = float(predict(model, X_final)[0])
    final_quantity = max(0.0, final_quantity)
    final_revenue = final_price * final_quantity
    final_profit = (final_price - cost) * final_quantity

    # STEP 4 – risk metrics
    if base_price > 0:
        price_change_pct = (final_price - base_price) / base_price * 100.0
    else:
        price_change_pct = 0.0

    profit_delta = final_profit - current_profit
    revenue_delta = final_revenue - current_revenue

    return {
        "current_state": {
            "price": round(base_price, 2),
            "quantity_pred": round(base_quantity, 2),
            "revenue": round(current_revenue, 2),
            "profit": round(current_profit, 2),
        },
        "recommendation": {
            "raw_optimal_price": round(raw_optimal_price, 2),
            "constrained_price": round(constrained_price, 2),
            "final_smoothed_price": round(final_price, 2),
            "expected_quantity": round(final_quantity, 2),
            "expected_revenue": round(final_revenue, 2),
            "expected_profit": round(final_profit, 2),
        },
        "risk_metrics": {
            "price_change_pct": round(price_change_pct, 2),
            "profit_delta": round(profit_delta, 2),
            "revenue_delta": round(revenue_delta, 2),
        },
        "constraints": {
            "max_price_change_pct": max_price_change_pct,
            "min_margin_pct": min_margin_pct,
            "smoothing_alpha": smoothing_alpha,
        },
        "elasticity_implicit": "model-based",
        "scenarios": scenarios,
    }
