"""Forecasting repository - data access layer."""

from datetime import date, datetime, timedelta
from typing import Sequence

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.forecasting.db_models import ModelArtifact, SalesFact


class ForecastingRepository:
    """Repository for forecasting data access."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_sales_df(
        self,
        from_date: date,
        to_date: date,
        product_ids: list[str] | None = None,
    ) -> pd.DataFrame:
        """Fetch sales as DataFrame for feature engineering."""
        q = (
            select(SalesFact)
            .where(SalesFact.date >= from_date, SalesFact.date <= to_date)
        )
        if product_ids:
            q = q.where(SalesFact.product_id.in_(product_ids))
        q = q.order_by(SalesFact.date)
        result = await self._session.execute(q)
        rows = result.scalars().all()
        if not rows:
            return pd.DataFrame(
                columns=["product_id", "date", "quantity", "revenue", "price", "promo_flag", "category_id"]
            )
        data = [
            {
                "product_id": r.product_id,
                "date": r.date,
                "quantity": r.quantity,
                "revenue": r.revenue,
                "price": r.price,
                "promo_flag": r.promo_flag,
                "category_id": r.category_id,
            }
            for r in rows
        ]
        return pd.DataFrame(data)

    async def get_aggregated_daily(
        self,
        from_date: date,
        to_date: date,
        product_ids: list[str] | None = None,
        group_by: str = "product",
    ) -> list[dict]:
        """Get daily aggregated data for visualization."""
        from sqlalchemy import func
        q = (
            select(
                SalesFact.date,
                SalesFact.product_id,
                func.sum(SalesFact.quantity).label("quantity"),
                func.sum(SalesFact.revenue).label("revenue"),
                func.avg(SalesFact.price).label("price"),
            )
            .where(SalesFact.date >= from_date, SalesFact.date <= to_date)
        )
        if product_ids:
            q = q.where(SalesFact.product_id.in_(product_ids))
        q = q.group_by(SalesFact.date, SalesFact.product_id)
        q = q.order_by(SalesFact.date, SalesFact.product_id)
        result = await self._session.execute(q)
        rows = result.all()
        return [
            {
                "date": str(r.date),
                "product_id": r.product_id,
                "quantity": float(r.quantity),
                "revenue": float(r.revenue),
                "price": float(r.price or 0),
            }
            for r in rows
        ]

    async def get_latest_sales_df(
        self,
        product_ids: list[str],
        min_days: int = 90,
    ) -> pd.DataFrame:
        """Fetch most recent sales for product(s) - for forecast when requested range has no data."""
        from sqlalchemy import func
        subq = (
            select(SalesFact.date)
            .where(SalesFact.product_id.in_(product_ids))
            .order_by(SalesFact.date.desc())
            .limit(1)
        )
        result = await self._session.execute(subq)
        max_date = result.scalar_one_or_none()
        if not max_date:
            return pd.DataFrame(
                columns=["product_id", "date", "quantity", "revenue", "price", "promo_flag", "category_id"]
            )
        from_date = max_date - timedelta(days=min_days)
        return await self.get_sales_df(from_date, max_date, product_ids)

    async def get_date_range(self) -> tuple["date | None", "date | None"]:
        """Return (min_date, max_date) across all sales_facts rows."""
        from sqlalchemy import func
        result = await self._session.execute(
            select(func.min(SalesFact.date), func.max(SalesFact.date))
        )
        row = result.one()
        return row[0], row[1]

    async def get_product_list(self) -> list[str]:
        """Get distinct product IDs."""
        from sqlalchemy import distinct, select
        result = await self._session.execute(
            select(distinct(SalesFact.product_id)).order_by(SalesFact.product_id)
        )
        return [r[0] for r in result.all()]

    async def get_sales_dataset_signature(self) -> dict[str, str | int | float | None]:
        """Return a stable aggregate signature for sales_facts cache invalidation."""
        from sqlalchemy import case, func

        result = await self._session.execute(
            select(
                func.count(SalesFact.id),
                func.coalesce(func.sum(SalesFact.quantity), 0.0),
                func.coalesce(func.sum(SalesFact.revenue), 0.0),
                func.coalesce(
                    func.sum(case((SalesFact.promo_flag.is_(True), 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((SalesFact.promo_flag.is_(True), SalesFact.quantity), else_=0.0)),
                    0.0,
                ),
                func.min(SalesFact.date),
                func.max(SalesFact.date),
            )
        )
        row = result.one()
        return {
            "row_count": int(row[0] or 0),
            "quantity_sum": round(float(row[1] or 0.0), 6),
            "revenue_sum": round(float(row[2] or 0.0), 6),
            "promo_row_count": int(row[3] or 0),
            "promo_quantity_sum": round(float(row[4] or 0.0), 6),
            "date_from": row[5].isoformat() if row[5] else None,
            "date_to": row[6].isoformat() if row[6] else None,
        }

    async def get_product_rank_winners(
        self,
        *,
        metric: str,
        direction: str,
        filters: dict | None = None,
        date_range: None = None,
        limit: int = 1,
    ) -> list[dict[str, float | str]]:
        """Return all tied winners for a supported top/bottom product query."""
        from sqlalchemy import case, func

        if filters:
            raise ValueError("Product rank resolver does not support filters yet.")
        if date_range is not None:
            raise ValueError("Product rank resolver does not support date_range yet.")
        if limit != 1:
            raise ValueError("Product rank resolver supports only limit=1.")

        if metric == "quantity":
            metric_column = SalesFact.quantity
            grouped = (
                select(
                    SalesFact.product_id.label("product_id"),
                    func.sum(metric_column).label("metric_value"),
                )
                .group_by(SalesFact.product_id)
                .subquery()
            )
        elif metric == "revenue":
            metric_column = SalesFact.revenue
            grouped = (
                select(
                    SalesFact.product_id.label("product_id"),
                    func.sum(metric_column).label("metric_value"),
                )
                .group_by(SalesFact.product_id)
                .subquery()
            )
        elif metric == "promo_lift":
            promo_avg = func.avg(case((SalesFact.promo_flag.is_(True), SalesFact.quantity), else_=None))
            non_promo_avg = func.avg(case((SalesFact.promo_flag.is_(False), SalesFact.quantity), else_=None))
            promo_count = func.sum(case((SalesFact.promo_flag.is_(True), 1), else_=0))
            non_promo_count = func.sum(case((SalesFact.promo_flag.is_(False), 1), else_=0))
            grouped = (
                select(
                    SalesFact.product_id.label("product_id"),
                    (((promo_avg - non_promo_avg) / func.nullif(non_promo_avg, 0.0)) * 100.0).label("metric_value"),
                )
                .group_by(SalesFact.product_id)
                .having(promo_count > 0)
                .having(non_promo_count > 0)
                .having(non_promo_avg != 0)
                .subquery()
            )
        else:
            raise ValueError(f"Unsupported metric '{metric}'.")
        aggregate_fn = func.max if direction == "desc" else func.min if direction == "asc" else None
        if aggregate_fn is None:
            raise ValueError(f"Unsupported direction '{direction}'.")

        extreme_result = await self._session.execute(select(aggregate_fn(grouped.c.metric_value)))
        extreme_value = extreme_result.scalar_one_or_none()
        if extreme_value is None:
            return []

        winners_result = await self._session.execute(
            select(grouped.c.product_id, grouped.c.metric_value)
            .where(grouped.c.metric_value == extreme_value)
            .order_by(grouped.c.product_id.asc())
        )
        rows = winners_result.all()
        return [
            {"product_id": row.product_id, "value": float(row.metric_value)}
            for row in rows
        ]

    async def get_active_model_path(self) -> str | None:
        """Get file path of active model artifact."""
        q = select(ModelArtifact).where(ModelArtifact.is_active == True).limit(1)
        result = await self._session.execute(q)
        art = result.scalar_one_or_none()
        return art.file_path if art else None

    async def get_active_model_version(self) -> str | None:
        """Get version string of active model."""
        q = select(ModelArtifact).where(ModelArtifact.is_active == True).limit(1)
        result = await self._session.execute(q)
        art = result.scalar_one_or_none()
        return art.version if art else None

    async def create_model_artifact(
        self,
        version: str,
        file_path: str,
        trained_at: datetime,
        data_from: date,
        data_to: date,
        mae: float | None = None,
        mape: float | None = None,
    ) -> ModelArtifact:
        """Create and persist model artifact; deactivate previous."""
        await self._session.execute(
            ModelArtifact.__table__.update().values(is_active=False)
        )
        art = ModelArtifact(
            version=version,
            file_path=file_path,
            trained_at=trained_at,
            data_from=data_from,
            data_to=data_to,
            mae=mae,
            mape=mape,
            is_active=True,
        )
        self._session.add(art)
        await self._session.flush()
        return art
