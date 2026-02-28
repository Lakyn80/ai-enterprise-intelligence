"""Dummy ERP connector returning static sample data."""

from datetime import date, timedelta

from app.connectors.base import ERPConnector, SalesRecord, StockRecord


class DummyERPConnector(ERPConnector):
    """Returns static sample sales and stock data."""

    async def fetch_sales(
        self,
        from_date: date,
        to_date: date,
        product_ids: list[str] | None = None,
    ) -> list[SalesRecord]:
        products = product_ids or ["P001", "P002", "P003"]
        records: list[SalesRecord] = []
        current = from_date
        while current <= to_date:
            for i, pid in enumerate(products):
                qty = 10 + (i * 5) + (current.day % 7)
                price = 19.99 + (i * 5.0)
                promo = current.weekday() in (4, 5)  # Fri/Sat
                if promo:
                    price *= 0.9
                records.append(
                    SalesRecord(
                        product_id=pid,
                        date=current,
                        quantity=float(qty),
                        revenue=qty * price,
                        price=price,
                        promo_flag=promo,
                        category_id=f"C{i % 3 + 1}",
                        source="erp_dummy",
                    )
                )
            current += timedelta(days=1)
        return records

    async def fetch_stock(
        self,
        from_date: date,
        to_date: date,
        product_ids: list[str] | None = None,
    ) -> list[StockRecord]:
        products = product_ids or ["P001", "P002", "P003"]
        records: list[StockRecord] = []
        current = from_date
        while current <= to_date:
            for i, pid in enumerate(products):
                records.append(
                    StockRecord(
                        product_id=pid,
                        date=current,
                        quantity=float(100 + i * 50 + current.day),
                        warehouse_id="WH1",
                    )
                )
            current += timedelta(days=1)
        return records
