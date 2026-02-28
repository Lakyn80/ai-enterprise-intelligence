"""Dummy e-commerce connector returning static sample data."""

from datetime import date, timedelta

from app.connectors.base import EcommerceConnector, PriceRecord, SalesRecord


class DummyEcommerceConnector(EcommerceConnector):
    """Returns static sample sales and price data."""

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
                qty = 8 + (i * 3) + (current.day % 5)
                price = 19.99 + (i * 5.0)
                records.append(
                    SalesRecord(
                        product_id=pid,
                        date=current,
                        quantity=float(qty),
                        revenue=qty * price,
                        price=price,
                        promo_flag=False,
                        category_id=f"C{i % 3 + 1}",
                        source="ecommerce_dummy",
                    )
                )
            current += timedelta(days=1)
        return records

    async def fetch_prices(
        self,
        from_date: date,
        to_date: date,
        product_ids: list[str] | None = None,
    ) -> list[PriceRecord]:
        products = product_ids or ["P001", "P002", "P003"]
        records: list[PriceRecord] = []
        current = from_date
        base_prices = [19.99, 24.99, 29.99]
        while current <= to_date:
            for i, pid in enumerate(products):
                records.append(
                    PriceRecord(
                        product_id=pid,
                        date=current,
                        price=base_prices[i % 3] + (current.day % 3) * 0.5,
                        currency="EUR",
                    )
                )
            current += timedelta(days=1)
        return records
