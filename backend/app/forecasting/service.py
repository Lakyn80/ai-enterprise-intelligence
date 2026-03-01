"""Forecasting service - orchestration of forecast and scenario logic."""

from datetime import date, datetime, timedelta
import os

import pandas as pd

from app.forecasting.backtest import backtest_metrics, rolling_backtest
from app.forecasting.features import apply_price_delta, engineer_features
from app.forecasting.repository import ForecastingRepository
from app.forecasting.schemas import ForecastPoint, ScenarioPriceChangeResponse
from app.forecasting.training import (
    DATE_COL,
    ENTITY_COL,
    FEATURE_COLS,
    load_model,
    predict,
    train_model,
)
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

    _PRODUCT_ALIASES = {"P001": "P0001", "P002": "P0002", "P003": "P0003"}

    async def get_forecast(
        self,
        product_id: str,
        from_date: date,
        to_date: date,
    ) -> tuple[list[ForecastPoint], str | None]:
        """Generate forecast for product and date range."""
        product_id = self._PRODUCT_ALIASES.get(product_id, product_id)
        lookback = 60
        hist_start = from_date - timedelta(days=lookback)
        df = await self._repo.get_sales_df(hist_start, to_date, [product_id])
        if df.empty:
            # Requested range beyond data - use latest available and extend to forecast dates
            df = await self._repo.get_latest_sales_df([product_id], min_days=lookback + 30)
        if df.empty:
            return [], None

        file_path = await self._repo.get_active_model_path()
        if not file_path or not os.path.exists(file_path):
            return [], None

        model = load_model(file_path)
        version = await self._repo.get_active_model_version()

        # Build full date range: from earliest in df to to_date (covers history + forecast range)
        df["date"] = pd.to_datetime(df["date"])
        range_start = min(df["date"]).date() if hasattr(min(df["date"]), "date") else min(df["date"])
        all_dates = pd.date_range(range_start, to_date, freq="D")
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
        df_feat[FEATURE_COLS] = df_feat[FEATURE_COLS].fillna(0)

        preds = predict(model, df_feat)
        df_feat["predicted_quantity"] = preds
        df_feat["predicted_revenue"] = df_feat["predicted_quantity"] * df_feat["price"]

        df_feat["date"] = pd.to_datetime(df_feat["date"]).dt.date
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
        product_id = self._PRODUCT_ALIASES.get(product_id, product_id)
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
            df = await self._repo.get_latest_sales_df([product_id], min_days=lookback + 30)
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
        range_start = min(df_scenario["date"]).date() if hasattr(min(df_scenario["date"]), "date") else min(df_scenario["date"])
        all_dates = pd.date_range(range_start, to_date, freq="D")
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
        df_feat[FEATURE_COLS] = df_feat[FEATURE_COLS].fillna(0)

        preds = predict(model, df_feat)
        df_feat["predicted_quantity"] = preds
        df_feat["predicted_revenue"] = df_feat["predicted_quantity"] * df_feat["price"]

        df_feat["date"] = pd.to_datetime(df_feat["date"]).dt.date
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

    async def run_backtest(
        self,
        product_id: str,
        from_date: date,
        to_date: date,
        train_window_days: int = 90,
        step_days: int = 7,
    ) -> dict:
        """Run rolling backtest: compare predictions with actuals, return MAE/MAPE."""
        product_id = self._PRODUCT_ALIASES.get(product_id, product_id)
        # Fetch extended history so we have enough for train window + predictions
        hist_start = from_date - timedelta(days=train_window_days)
        df = await self._repo.get_sales_df(hist_start, to_date, [product_id])
        if df.empty or len(df) < train_window_days + step_days:
            return {"mae": None, "mape": None, "message": "Insufficient data"}
        file_path = await self._repo.get_active_model_path()
        if not file_path or not os.path.exists(file_path):
            return {"mae": None, "mape": None, "message": "No trained model"}
        model = load_model(file_path)

        def predict_fn(d: pd.DataFrame):
            return predict(model, d)

        actuals, preds, _ = rolling_backtest(
            df,
            date_col=DATE_COL,
            entity_col=ENTITY_COL,
            predict_fn=predict_fn,
            train_window_days=train_window_days,
            step_days=step_days,
        )
        metrics = backtest_metrics(actuals, preds)
        return {
            "mae": metrics["mae"],
            "mape": metrics["mape"],
            "product_id": product_id,
            "from_date": str(from_date),
            "to_date": str(to_date),
            "n_predictions": len(preds),
        }
