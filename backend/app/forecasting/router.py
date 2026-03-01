"""Forecasting API routes."""

import asyncio
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import verify_api_key
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


@router.post("/admin/seed", dependencies=[Depends(verify_api_key)])
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


@router.post("/admin/import-kaggle", dependencies=[Depends(verify_api_key)])
async def import_kaggle_data():
    """Import Kaggle retail CSV from /data into sales_facts (API key required)."""
    from app.forecasting.import_kaggle import import_csv
    try:
        n = await import_csv()
        return {"status": "ok", "message": f"Imported {n} rows", "rows": n}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/data/products")
async def list_products(session: AsyncSessionDep) -> list[str]:
    """List available product IDs for visualization."""
    repo = ForecastingRepository(session)
    return await repo.get_product_list()


@router.get("/data/historical")
async def get_historical_data(
    session: AsyncSessionDep,
    from_date: date,
    to_date: date,
    product_id: str | None = None,
):
    """Get aggregated historical data for visualization."""
    repo = ForecastingRepository(session)
    product_ids = [product_id] if product_id else None
    return await repo.get_aggregated_daily(from_date, to_date, product_ids)


@router.post("/admin/train", dependencies=[Depends(verify_api_key)])
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
    try:
        service = get_forecasting_service(session)
        points, version = await service.get_forecast(product_id, from_date, to_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return ForecastResponse(
        product_id=product_id,
        from_date=from_date,
        to_date=to_date,
        points=points,
        model_version=version,
    )


@router.get("/backtest")
async def run_backtest_public(
    session: AsyncSessionDep,
    product_id: str,
    from_date: date,
    to_date: date,
    train_window_days: int = 90,
    step_days: int = 7,
):
    """Run backtest: compare predictions with actuals, return MAE/MAPE."""
    service = get_forecasting_service(session)
    return await service.run_backtest(
        product_id=product_id,
        from_date=from_date,
        to_date=to_date,
        train_window_days=train_window_days,
        step_days=step_days,
    )


@router.post("/admin/backtest", dependencies=[Depends(verify_api_key)])
async def run_backtest_endpoint(
    session: AsyncSessionDep,
    product_id: str,
    from_date: date,
    to_date: date,
    train_window_days: int = 90,
    step_days: int = 7,
):
    """Run backtest (API key required)."""
    service = get_forecasting_service(session)
    return await service.run_backtest(
        product_id=product_id,
        from_date=from_date,
        to_date=to_date,
        train_window_days=train_window_days,
        step_days=step_days,
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
