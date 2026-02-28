"""Dummy CRM connector returning static sample data."""

from datetime import date

from app.connectors.base import CRMConnector


class DummyCRMConnector(CRMConnector):
    """Returns static customer metrics."""

    async def fetch_customer_metrics(
        self,
        from_date: date,
        to_date: date,
    ) -> dict:
        days = (to_date - from_date).days + 1
        return {
            "new_customers": 50 + days,
            "returning_customers": 120 + days * 2,
            "churn_rate": 0.05,
            "nps_score": 72,
            "source": "crm_dummy",
        }
