"""Connector interfaces for data sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class SalesRecord:
    """Single sales transaction record."""

    product_id: str
    date: date
    quantity: float
    revenue: float
    price: float | None
    promo_flag: bool = False
    category_id: str | None = None
    source: str | None = None


@dataclass
class StockRecord:
    """Stock/inventory record."""

    product_id: str
    date: date
    quantity: float
    warehouse_id: str | None = None


@dataclass
class PriceRecord:
    """Price record for a product."""

    product_id: str
    date: date
    price: float
    currency: str = "EUR"


class ERPConnector(ABC):
    """Interface for ERP data connectors."""

    @abstractmethod
    async def fetch_sales(
        self,
        from_date: date,
        to_date: date,
        product_ids: list[str] | None = None,
    ) -> list[SalesRecord]:
        """Fetch sales data from ERP."""
        ...

    @abstractmethod
    async def fetch_stock(
        self,
        from_date: date,
        to_date: date,
        product_ids: list[str] | None = None,
    ) -> list[StockRecord]:
        """Fetch stock data from ERP."""
        ...


class EcommerceConnector(ABC):
    """Interface for e-commerce platform connectors."""

    @abstractmethod
    async def fetch_sales(
        self,
        from_date: date,
        to_date: date,
        product_ids: list[str] | None = None,
    ) -> list[SalesRecord]:
        """Fetch sales from e-shop."""
        ...

    @abstractmethod
    async def fetch_prices(
        self,
        from_date: date,
        to_date: date,
        product_ids: list[str] | None = None,
    ) -> list[PriceRecord]:
        """Fetch price history from e-shop."""
        ...


class CRMConnector(ABC):
    """Interface for CRM connectors."""

    @abstractmethod
    async def fetch_customer_metrics(
        self,
        from_date: date,
        to_date: date,
    ) -> dict[str, Any]:
        """Fetch customer-related metrics."""
        ...


class MarketingConnector(ABC):
    """Interface for marketing platform connectors."""

    @abstractmethod
    async def fetch_promo_calendar(
        self,
        from_date: date,
        to_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch promotion calendar (dates, descriptions, product_ids)."""
        ...


class ScrapingConnector(ABC):
    """Interface for scraping connectors (placeholder for future implementation)."""

    @abstractmethod
    async def scrape_product_data(
        self,
        product_ids: list[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Scrape product data from external sources."""
        ...
