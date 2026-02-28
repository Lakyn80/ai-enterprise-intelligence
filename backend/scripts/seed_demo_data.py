#!/usr/bin/env python3
"""Seed demo data for local development."""

import asyncio
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Import before base - ensure models are registered
from app.db.base import Base
from app.forecasting.db_models import SalesFact
from app.settings import settings


async def seed():
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with Session() as session:
        # Check if we already have data
        from sqlalchemy import select, func
        result = await session.execute(select(func.count(SalesFact.id)))
        count = result.scalar() or 0
        if count > 0:
            print(f"Sales facts already exist ({count} rows). Skipping seed.")
            return

        # Generate 120 days of demo data for P001, P002, P003
        start = date.today() - timedelta(days=120)
        products = [
            ("P001", 19.99, "C1"),
            ("P002", 24.99, "C2"),
            ("P003", 29.99, "C3"),
        ]
        for i in range(120):
            d = start + timedelta(days=i)
            for j, (pid, price, cat) in enumerate(products):
                qty = 10 + (j * 5) + (d.day % 7)
                promo = d.weekday() in (4, 5)
                if promo:
                    price = price * 0.9
                rev = qty * price
                session.add(
                    SalesFact(
                        product_id=pid,
                        date=d,
                        quantity=float(qty),
                        revenue=rev,
                        price=price,
                        promo_flag=promo,
                        category_id=cat,
                        source="seed",
                    )
                )
        await session.commit()
        print(f"Seeded 360 sales facts (120 days x 3 products).")


if __name__ == "__main__":
    asyncio.run(seed())
