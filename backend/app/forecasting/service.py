"""Forecasting service - orchestration of forecast and scenario logic."""

from datetime import date, datetime, timedelta
import logging
import os

import pandas as pd

from app.forecasting.backtest import (
    backtest_metrics,
    evaluate_time_split,
    rolling_backtest,
    time_based_split_by_date,
)
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

logger = logging.getLogger(__name__)


class ForecastingService:
    """Service for forecasting and scenario computation."""

    def __init__(self, repository: ForecastingRepository):
        self._repo = repository

    _MAX_TRAIN_YEARS = 3

    async def train(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        split_date: date | None = None,
    ) -> dict:
        """
        Train model on historical data and persist artifact.

        When from_date / to_date are omitted the service auto-detects the maximum
        available window from the database, capped at _MAX_TRAIN_YEARS years back
        from the latest row:
            to_date   = max(sales_facts.date)
            from_date = max(min_db_date, to_date - 3 years)

        When split_date is provided the model is trained only on [from_date, split_date)
        and evaluated out-of-sample on [split_date, to_date].  Metrics in the response
        then reflect real held-out performance, not in-sample error.
        """
        # --- Auto-detect date range if not explicitly supplied ---
        if from_date is None or to_date is None:
            min_db_date, max_db_date = await self._repo.get_date_range()
            if max_db_date is None:
                raise ValueError("No sales data in database — cannot auto-detect training range")
            if to_date is None:
                to_date = max_db_date
            if from_date is None:
                three_years_back = date(to_date.year - self._MAX_TRAIN_YEARS, to_date.month, to_date.day)
                from_date = max(min_db_date, three_years_back)
            logger.info(
                "Auto-detected training range: from=%s  to=%s  (cap=%d years, db_min=%s  db_max=%s)",
                from_date,
                to_date,
                self._MAX_TRAIN_YEARS,
                min_db_date,
                max_db_date,
            )

        df = await self._repo.get_sales_df(from_date, to_date)
        if df.empty or len(df) < 100:
            raise ValueError(
                f"Insufficient data for training (got {len(df)} rows for "
                f"{from_date} → {to_date}, need ≥ 100)"
            )

        if split_date is not None and not (from_date < split_date <= to_date):
            raise ValueError(
                f"split_date {split_date} must be strictly between from_date {from_date} "
                f"and to_date {to_date}"
            )

        logger.info(
            "Training request: from=%s  to=%s  split=%s  total_rows=%d  products=%d",
            from_date,
            to_date,
            split_date,
            len(df),
            df["product_id"].nunique() if "product_id" in df.columns else "?",
        )

        _, meta = train_model(df, from_date, to_date, split_date=split_date)

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

        logger.info(
            "Model artifact saved: version=%s  MAE=%.4f  RMSE=%.4f  MAPE=%.2f%%  "
            "eval_source=%s  n_eval=%d",
            meta["version"],
            meta["mae"],
            meta["rmse"],
            meta["mape"],
            meta["eval_source"],
            meta["n_eval_samples"],
        )

        result: dict = {
            "version": meta["version"],
            "artifact_id": art.id,
            "mae": meta["mae"],
            "rmse": meta["rmse"],
            "mape": meta["mape"],
            "n_eval_samples": meta["n_eval_samples"],
            "eval_source": meta["eval_source"],
        }
        if split_date:
            result["date_range"] = {
                "train_start": str(from_date),
                "train_end": str(split_date),
                "test_start": str(split_date),
                "test_end": str(to_date),
            }
        return result

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
        """
        Run rolling backtest: evaluate predictions against actuals across the date range.

        Returns structured evaluation:
        {
            "mae": float, "rmse": float, "mape": float,
            "n_samples": int,
            "date_range": {"train_start", "train_end", "test_start", "test_end"},
            "product_id": str
        }
        """
        product_id = self._PRODUCT_ALIASES.get(product_id, product_id)

        # Extend history so the first training window has enough rows
        hist_start = from_date - timedelta(days=train_window_days)
        df = await self._repo.get_sales_df(hist_start, to_date, [product_id])

        if df.empty or len(df) < train_window_days + step_days:
            logger.warning(
                "Backtest skipped for %s: insufficient rows (%d)",
                product_id,
                len(df),
            )
            return {
                "mae": None,
                "rmse": None,
                "mape": None,
                "n_samples": 0,
                "message": "Insufficient data",
                "product_id": product_id,
            }

        file_path = await self._repo.get_active_model_path()
        if not file_path or not os.path.exists(file_path):
            return {
                "mae": None,
                "rmse": None,
                "mape": None,
                "n_samples": 0,
                "message": "No trained model",
                "product_id": product_id,
            }

        model = load_model(file_path)

        def predict_fn(d: pd.DataFrame) -> "np.ndarray":  # noqa: F821
            return predict(model, d)

        logger.info(
            "Rolling backtest: product=%s  range=[%s, %s]  train_window=%d  step=%d",
            product_id,
            hist_start,
            to_date,
            train_window_days,
            step_days,
        )

        actuals, preds, test_dates_list = rolling_backtest(
            df,
            date_col=DATE_COL,
            entity_col=ENTITY_COL,
            predict_fn=predict_fn,
            train_window_days=train_window_days,
            step_days=step_days,
        )

        metrics = backtest_metrics(actuals, preds)

        date_range: dict = {}
        if len(test_dates_list) > 0:
            date_range = {
                "train_start": str(hist_start),
                "train_end": str(hist_start + timedelta(days=train_window_days - 1)),
                "test_start": str(min(test_dates_list)),
                "test_end": str(max(test_dates_list)),
            }

        logger.info(
            "Backtest result: product=%s  MAE=%.4f  RMSE=%.4f  MAPE=%.2f%%  n=%d",
            product_id,
            metrics["mae"],
            metrics["rmse"],
            metrics["mape"],
            len(preds),
        )

        return {
            "mae": metrics["mae"],
            "rmse": metrics["rmse"],
            "mape": metrics["mape"],
            "n_samples": int(len(preds)),
            "date_range": date_range,
            "product_id": product_id,
        }
