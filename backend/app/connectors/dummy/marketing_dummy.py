"""Dummy marketing connector returning static promo calendar."""

from datetime import date, timedelta

from app.connectors.base import MarketingConnector


class DummyMarketingConnector(MarketingConnector):
    """Returns static promotion calendar."""

    async def fetch_promo_calendar(
        self,
        from_date: date,
        to_date: date,
    ) -> list[dict]:
        entries: list[dict] = []
        current = from_date
        week = 0
        while current <= to_date:
            if current.weekday() in (4, 5):  # Fri/Sat
                entries.append(
                    {
                        "date": current.isoformat(),
                        "description": "Weekend Sale",
                        "product_ids": ["P001", "P002", "P003"],
                        "discount_pct": 10.0,
                    }
                )
            if current.day in (1, 15):  # Monthly specials
                entries.append(
                    {
                        "date": current.isoformat(),
                        "description": "Monthly Flash",
                        "product_ids": ["P001"],
                        "discount_pct": 15.0,
                    }
                )
            current += timedelta(days=1)
            week += 1
        return entries
