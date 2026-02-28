"""Forecasting repository - data access layer."""

from datetime import date, datetime
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
