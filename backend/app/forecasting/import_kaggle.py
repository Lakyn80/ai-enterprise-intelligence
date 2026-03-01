"""Import Kaggle retail_store_inventory.csv into sales_facts."""

import csv
from datetime import date
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.db.base import Base
from app.forecasting.db_models import SalesFact
from app.settings import settings


def _parse_row(row: dict) -> tuple[date, str, float, float, float, bool, str]:
    d = date.fromisoformat(row["Date"])
    pid = row["Product ID"]
    qty = float(row["Units Sold"])
    price = float(row["Price"])
    discount = float(row.get("Discount", 0))
    revenue = qty * price * (1 - discount / 100)
    promo = int(row.get("Holiday/Promotion", 0)) == 1
    cat = row.get("Category", "")
    return (d, pid, qty, revenue, price, promo, cat)


def _find_csv(data_dir: Path = Path("/data")) -> Path:
    """Find retail CSV in data dir; prefer retail_store_inventory.csv."""
    preferred = data_dir / "retail_store_inventory.csv"
    if preferred.exists():
        return preferred
    for f in data_dir.glob("*.csv"):
        return f
    raise FileNotFoundError(
        f"No CSV found in {data_dir}. Download from Kaggle and run scripts/download-kaggle-data.ps1"
    )


async def import_csv(csv_path: str | Path | None = None) -> int:
    data_dir = Path("/data")
    if csv_path:
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")
    else:
        csv_path = _find_csv(data_dir)

    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    agg: dict[tuple[date, str], list] = {}
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d, pid, qty, revenue, price, promo, cat = _parse_row(row)
            key = (d, pid)
            if key not in agg:
                agg[key] = [0.0, 0.0, price, promo, cat]
            agg[key][0] += qty
            agg[key][1] += revenue
            if promo:
                agg[key][3] = True

    async with Session() as sess:
        await sess.execute(delete(SalesFact).where(SalesFact.source == "kaggle"))
        for (d, pid), (qty, rev, price, promo, cat) in agg.items():
            eff_price = rev / qty if qty > 0 else price
            sess.add(
                SalesFact(
                    product_id=pid,
                    date=d,
                    quantity=qty,
                    revenue=rev,
                    price=eff_price,
                    promo_flag=promo,
                    category_id=cat or None,
                    source="kaggle",
                )
            )
        await sess.commit()
        return len(agg)
