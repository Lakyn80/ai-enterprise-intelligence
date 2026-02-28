"""Forecasting API routes."""

import asyncio
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import ApiKeyDep
from app.core.deps import AsyncSessionDep
from app.forecasting.repository import ForecastingRepository
from app.forecasting.schemas import (
    ForecastResponse,
    ScenarioPriceChangeRequest,
    ScenarioPriceChangeResponse,
)
from app.forecasting.service import ForecastingService

router = APIRouter(prefix="/api", tags=["forecasting"])


def get_forecasting_service(session: AsyncSessionDep) -> ForecastingService:
    return ForecastingService(ForecastingRepository(session))


@router.post("/admin/seed", dependencies=[Depends(ApiKeyDep)])
async def seed_demo_data():
    """Load demo data (API key required)."""
    from datetime import timedelta

    from sqlalchemy import func, select

    from app.db.base import Base
    from app.db.session import async_engine
    from app.forecasting.db_models import SalesFact
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with SessionLocal() as sess:
        result = await sess.execute(select(func.count(SalesFact.id)))
        cnt = result.scalar() or 0
        if cnt > 0:
            return {"status": "ok", "message": "Data already exists", "rows": cnt}
        start = date.today() - timedelta(days=120)
        products = [("P001", 19.99, "C1"), ("P002", 24.99, "C2"), ("P003", 29.99, "C3")]
        for i in range(120):
            d = start + timedelta(days=i)
            for j, (pid, price, cat) in enumerate(products):
                qty = 10 + (j * 5) + (d.day % 7)
                promo = d.weekday() in (4, 5)
                p = price * 0.9 if promo else price
                sess.add(
                    SalesFact(
                        product_id=pid,
                        date=d,
                        quantity=float(qty),
                        revenue=qty * p,
                        price=p,
                        promo_flag=promo,
                        category_id=cat,
                        source="seed",
                    )
                )
        await sess.commit()
    return {"status": "ok", "message": "Seeded 360 sales facts", "rows": 360}


@router.post("/admin/train", dependencies=[Depends(ApiKeyDep)])
async def train_model_endpoint(
    from_date: date,
    to_date: date,
    session: AsyncSessionDep,
):
    """Train forecasting model (API key required)."""
    service = get_forecasting_service(session)
    try:
        result = await service.train(from_date, to_date)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/forecast")
async def get_forecast(
    product_id: str,
    from_date: date,
    to_date: date,
    session: AsyncSessionDep,
) -> ForecastResponse:
    """Get forecast for product and date range."""
    service = get_forecasting_service(session)
    points, version = await service.get_forecast(product_id, from_date, to_date)
    return ForecastResponse(
        product_id=product_id,
        from_date=from_date,
        to_date=to_date,
        points=points,
        model_version=version,
    )


@router.post("/scenario/price-change", response_model=ScenarioPriceChangeResponse)
async def scenario_price_change(
    body: ScenarioPriceChangeRequest,
    session: AsyncSessionDep,
) -> ScenarioPriceChangeResponse:
    """Compute forecast with hypothetical price change."""
    service = get_forecasting_service(session)
    return await service.scenario_price_change(
        product_id=body.product_id,
        from_date=body.from_date,
        to_date=body.to_date,
        price_delta_pct=body.price_delta_pct,
    )
