"""Pricing optimization orchestration service."""

import os

import numpy as np
import pandas as pd

from app.forecasting.features import engineer_features
from app.forecasting.pricing_constraints import (
    PricingConstraintParams,
    apply_business_constraints,
    apply_smoothing,
    should_hold_price_by_hysteresis,
)
from app.forecasting.pricing_engine import compute_objective_score
from app.forecasting.pricing_schemas import PricingOptimizeRequest
from app.forecasting.repository import ForecastingRepository
from app.forecasting.training import FEATURE_COLS, load_model, predict


class PricingOptimizationService:
    """Service for deterministic high-volatility pricing optimization."""

    _PRODUCT_ALIASES = {"P001": "P0001", "P002": "P0002", "P003": "P0003"}

    def __init__(self, repository: ForecastingRepository):
        self._repo = repository

    async def optimize(self, body: PricingOptimizeRequest) -> dict:
        """Run end-to-end pricing optimization and return API payload."""
        self._validate_request(body)

        product_id = self._PRODUCT_ALIASES.get(body.product_id, body.product_id)
        model = await self._load_active_model()
        df = await self._load_product_history(product_id)
        df_feat = self._prepare_features(df)

        base_row = df_feat.iloc[-1].copy()
        base_price = float(base_row["price"])
        base_rolling_mean_price = float(base_row.get("rolling_mean_price_30", base_price))
        if base_rolling_mean_price <= 0:
            base_rolling_mean_price = base_price if base_price > 0 else 1.0

        base_quantity = max(0.0, float(predict(model, df_feat.tail(1))[0]))
        current_revenue = base_price * base_quantity
        current_profit = (base_price - body.cost) * base_quantity

        candidate_prices = np.linspace(body.price_min, body.price_max, body.n_steps)
        scenarios: list[dict] = []
        best_candidate: dict | None = None
        best_score = float("-inf")

        for candidate in candidate_prices:
            price = float(candidate)
            quantity, revenue, profit = self._predict_metrics_for_price(
                model=model,
                base_row=base_row,
                price=price,
                base_price=base_price,
                base_rolling_mean_price=base_rolling_mean_price,
                cost=body.cost,
            )
            score, risk_penalty = compute_objective_score(
                profit=profit,
                quantity=quantity,
                baseline_quantity=base_quantity,
                strategy=body.strategy,
            )

            scenario = {
                "price": round(price, 2),
                "quantity": round(quantity, 2),
                "revenue": round(revenue, 2),
                "profit": round(profit, 2),
                "objective_score": round(score, 2),
            }
            if body.strategy.objective == "risk_adjusted_profit":
                scenario["risk_penalty"] = round(risk_penalty, 2)

            scenarios.append(scenario)

            if score > best_score:
                best_score = score
                best_candidate = {
                    "price": price,
                    "quantity": quantity,
                    "revenue": revenue,
                    "profit": profit,
                    "score": score,
                }

        raw_optimal_price = best_candidate["price"] if best_candidate is not None else base_price
        constraints = PricingConstraintParams(
            max_price_change_pct=body.max_price_change_pct,
            min_margin_pct=body.min_margin_pct,
            smoothing_alpha=body.smoothing_alpha,
        )
        constrained_price, allowed_min, allowed_max = apply_business_constraints(
            raw_optimal_price=raw_optimal_price,
            base_price=base_price,
            cost=body.cost,
            price_min=body.price_min,
            price_max=body.price_max,
            params=constraints,
        )
        smoothed_price = apply_smoothing(
            base_price=base_price,
            constrained_price=constrained_price,
            alpha=constraints.smoothing_alpha,
        )
        smoothed_quantity, smoothed_revenue, smoothed_profit = self._predict_metrics_for_price(
            model=model,
            base_row=base_row,
            price=smoothed_price,
            base_price=base_price,
            base_rolling_mean_price=base_rolling_mean_price,
            cost=body.cost,
        )
        hysteresis_applied, profit_delta_vs_current_pct = should_hold_price_by_hysteresis(
            current_profit=current_profit,
            candidate_profit=smoothed_profit,
            hysteresis_threshold_pct=body.strategy.hysteresis_profit_delta_threshold_pct,
        )

        if hysteresis_applied:
            final_price = base_price
            final_quantity = base_quantity
            final_revenue = current_revenue
            final_profit = current_profit
        else:
            final_price = smoothed_price
            final_quantity = smoothed_quantity
            final_revenue = smoothed_revenue
            final_profit = smoothed_profit

        if base_price > 0:
            price_change_pct = ((final_price - base_price) / base_price) * 100.0
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
                "profit_delta_vs_current_pct": round(profit_delta_vs_current_pct, 2),
            },
            "constraints": {
                "max_price_change_pct": body.max_price_change_pct,
                "min_margin_pct": body.min_margin_pct,
                "smoothing_alpha": body.smoothing_alpha,
                "allowed_price_min": round(allowed_min, 2),
                "allowed_price_max": round(allowed_max, 2),
            },
            "strategy": {
                "objective": body.strategy.objective,
                "quantity_swing_penalty": body.strategy.quantity_swing_penalty,
                "hysteresis_profit_delta_threshold_pct": body.strategy.hysteresis_profit_delta_threshold_pct,
                "hysteresis_applied": hysteresis_applied,
            },
            "elasticity_implicit": "model-based",
            "scenarios": scenarios,
        }

    def _validate_request(self, body: PricingOptimizeRequest) -> None:
        """Validate request and strategy parameters."""
        if not body.product_id or body.cost is None or body.price_min is None or body.price_max is None:
            raise ValueError("Missing required fields: product_id, cost, price_min, price_max")
        if body.price_min >= body.price_max:
            raise ValueError("price_min must be less than price_max")
        if body.n_steps < 2:
            raise ValueError("n_steps must be >= 2")
        if body.max_price_change_pct < 0:
            raise ValueError("max_price_change_pct must be >= 0")
        if body.min_margin_pct < 0:
            raise ValueError("min_margin_pct must be >= 0")
        if not (0.0 <= body.smoothing_alpha <= 1.0):
            raise ValueError("smoothing_alpha must be between 0 and 1")
        if body.strategy.quantity_swing_penalty < 0:
            raise ValueError("strategy.quantity_swing_penalty must be >= 0")
        if body.strategy.hysteresis_profit_delta_threshold_pct < 0:
            raise ValueError("strategy.hysteresis_profit_delta_threshold_pct must be >= 0")

    async def _load_active_model(self):
        file_path = await self._repo.get_active_model_path()
        if not file_path or not os.path.exists(file_path):
            raise ValueError("No trained model available")
        return load_model(file_path)

    async def _load_product_history(self, product_id: str) -> pd.DataFrame:
        """Load recent product history needed for lag features."""
        df = await self._repo.get_latest_sales_df([product_id], min_days=90)
        if df.empty or len(df) < 30:
            raise ValueError("Insufficient data - need at least 30 days of history")
        if "date" in df.columns and "product_id" in df.columns:
            agg = df.groupby(["date", "product_id"]).agg(
                quantity=("quantity", "sum"),
                revenue=("revenue", "sum"),
                price=("price", "mean"),
                promo_flag=("promo_flag", "max"),
                category_id=("category_id", "first"),
            )
            df = agg.reset_index()
        return df

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build feature matrix and enforce required training columns."""
        df_feat = engineer_features(df)
        for col in FEATURE_COLS:
            if col not in df_feat.columns:
                df_feat[col] = 0
        df_feat[FEATURE_COLS] = df_feat[FEATURE_COLS].fillna(0)

        if "lag_30" in df_feat.columns and df_feat["lag_30"].notna().any():
            df_feat = df_feat.dropna(subset=["lag_30"])
        if df_feat.empty:
            raise ValueError("Insufficient data for feature engineering (need 30+ days)")
        return df_feat

    def _predict_metrics_for_price(
        self,
        *,
        model,
        base_row: pd.Series,
        price: float,
        base_price: float,
        base_rolling_mean_price: float,
        cost: float,
    ) -> tuple[float, float, float]:
        """Predict quantity/revenue/profit for a candidate price."""
        row = base_row.copy()
        row["price"] = price
        row["log_price"] = np.log(max(price, 1e-8))
        row["price_vs_avg_30"] = price / base_rolling_mean_price
        row["price_change_pct"] = (price - base_price) / base_price if base_price > 0 else 0.0

        for col in FEATURE_COLS:
            if col not in row.index:
                row[col] = 0

        X = pd.DataFrame([row[FEATURE_COLS]])
        quantity_pred = max(0.0, float(predict(model, X)[0]))
        revenue = price * quantity_pred
        profit = (price - cost) * quantity_pred
        return quantity_pred, revenue, profit
