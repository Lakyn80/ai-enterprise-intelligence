"""Forecasting service - orchestration of forecast and scenario logic."""

from datetime import date, datetime, timedelta
import os

import pandas as pd

from app.forecasting.backtest import backtest_metrics, time_based_split
from app.forecasting.features import apply_price_delta, engineer_features
from app.forecasting.repository import ForecastingRepository
from app.forecasting.schemas import ForecastPoint, ScenarioPriceChangeResponse
from app.forecasting.training import load_model, predict, train_model, FEATURE_COLS
from app.settings import settings


class ForecastingService:
    """Service for forecasting and scenario computation."""

    def __init__(self, repository: ForecastingRepository):
        self._repo = repository

    async def train(self, from_date: date, to_date: date) -> dict:
        """Train model on historical data and persist artifact."""
        df = await self._repo.get_sales_df(from_date, to_date)
        if df.empty or len(df) < 100:
            raise ValueError("Insufficient data for training (need at least 100 rows)")

        _, meta = train_model(df, from_date, to_date)
        art = await self._repo.create_model_artifact(
            version=meta["version"],
            file_path=meta["file_path"],
            trained_at=datetime.utcnow(),
            data_from=from_date,
            data_to=to_date,
            mae=meta["mae"],
            mape=meta["mape"],
        )
        await self._repo._session.commit()
        return {
            "version": meta["version"],
            "mae": meta["mae"],
            "mape": meta["mape"],
            "artifact_id": art.id,
        }

    async def get_forecast(
        self,
        product_id: str,
        from_date: date,
        to_date: date,
    ) -> tuple[list[ForecastPoint], str | None]:
        """Generate forecast for product and date range."""
        # Need extended history for feature computation (lags, rolling)
        lookback = 60
        hist_start = from_date - timedelta(days=lookback)
        df = await self._repo.get_sales_df(hist_start, to_date, [product_id])
        if df.empty:
            return [], None

        file_path = await self._repo.get_active_model_path()
        if not file_path or not os.path.exists(file_path):
            return [], None

        model = load_model(file_path)
        version = await self._repo.get_active_model_version()

        # Build full date range for forecast (fill missing days with last known values)
        df["date"] = pd.to_datetime(df["date"])
        all_dates = pd.date_range(hist_start, to_date, freq="D")
        df_full = df.set_index("date").reindex(all_dates)
        df_full = df_full.ffill().bfill()
        df_full = df_full.reset_index()
        df_full = df_full.rename(columns={"index": "date"})
        df_full["product_id"] = product_id
        df_full["date"] = pd.to_datetime(df_full["date"]).dt.date

        df_feat = engineer_features(df_full)
        for col in FEATURE_COLS:
            if col not in df_feat.columns:
                df_feat[col] = 0

        preds = predict(model, df_feat)
        df_feat["predicted_quantity"] = preds
        df_feat["predicted_revenue"] = df_feat["predicted_quantity"] * df_feat["price"]

        mask = (df_feat["date"] >= from_date) & (df_feat["date"] <= to_date)
        subset = df_feat[mask]
        points = [
            ForecastPoint(
                date=row["date"],
                product_id=product_id,
                predicted_quantity=float(row["predicted_quantity"]),
                predicted_revenue=float(row["predicted_revenue"]) if pd.notna(row.get("predicted_revenue")) else None,
            )
            for _, row in subset.iterrows()
        ]
        return points, version

    async def scenario_price_change(
        self,
        product_id: str,
        from_date: date,
        to_date: date,
        price_delta_pct: float,
    ) -> ScenarioPriceChangeResponse:
        """Recompute forecast with hypothetical price change."""
        base_points, _ = await self.get_forecast(product_id, from_date, to_date)
        if not base_points:
            return ScenarioPriceChangeResponse(
                product_id=product_id,
                from_date=from_date,
                to_date=to_date,
                price_delta_pct=price_delta_pct,
            )

        lookback = 60
        hist_start = from_date - timedelta(days=lookback)
        df = await self._repo.get_sales_df(hist_start, to_date, [product_id])
        if df.empty:
            return ScenarioPriceChangeResponse(
                product_id=product_id,
                from_date=from_date,
                to_date=to_date,
                price_delta_pct=price_delta_pct,
                base_forecast_points=base_points,
            )

        df_scenario = apply_price_delta(df, price_delta_pct)
        file_path = await self._repo.get_active_model_path()
        if not file_path or not os.path.exists(file_path):
            return ScenarioPriceChangeResponse(
                product_id=product_id,
                from_date=from_date,
                to_date=to_date,
                price_delta_pct=price_delta_pct,
                base_forecast_points=base_points,
            )

        model = load_model(file_path)
        df_scenario["date"] = pd.to_datetime(df_scenario["date"])
        all_dates = pd.date_range(hist_start, to_date, freq="D")
        df_full = df_scenario.set_index("date").reindex(all_dates)
        df_full = df_full.ffill().bfill()
        df_full = df_full.reset_index()
        df_full = df_full.rename(columns={"index": "date"})
        df_full["product_id"] = product_id
        df_full["date"] = pd.to_datetime(df_full["date"]).dt.date

        df_feat = engineer_features(df_full)
        for col in FEATURE_COLS:
            if col not in df_feat.columns:
                df_feat[col] = 0

        preds = predict(model, df_feat)
        df_feat["predicted_quantity"] = preds
        df_feat["predicted_revenue"] = df_feat["predicted_quantity"] * df_feat["price"]

        mask = (df_feat["date"] >= from_date) & (df_feat["date"] <= to_date)
        subset = df_feat[mask]
        scenario_points = [
            ForecastPoint(
                date=row["date"],
                product_id=product_id,
                predicted_quantity=float(row["predicted_quantity"]),
                predicted_revenue=float(row["predicted_revenue"]) if pd.notna(row.get("predicted_revenue")) else None,
            )
            for _, row in subset.iterrows()
        ]

        base_rev = sum(p.predicted_revenue or 0 for p in base_points)
        scenario_rev = sum(p.predicted_revenue or 0 for p in scenario_points)
        base_qty = sum(p.predicted_quantity for p in base_points)
        scenario_qty = sum(p.predicted_quantity for p in scenario_points)
        delta_revenue_pct = ((scenario_rev - base_rev) / (base_rev + 1e-8)) * 100 if base_rev else None
        delta_quantity_pct = ((scenario_qty - base_qty) / (base_qty + 1e-8)) * 100 if base_qty else None

        return ScenarioPriceChangeResponse(
            product_id=product_id,
            from_date=from_date,
            to_date=to_date,
            price_delta_pct=price_delta_pct,
            base_forecast_points=base_points,
            scenario_forecast_points=scenario_points,
            delta_revenue_pct=delta_revenue_pct,
            delta_quantity_pct=delta_quantity_pct,
        )
