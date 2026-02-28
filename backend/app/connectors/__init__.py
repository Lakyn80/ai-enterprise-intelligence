"""Data source connectors - interfaces and implementations."""

from app.connectors.base import (
    CRMConnector,
    EcommerceConnector,
    ERPConnector,
    MarketingConnector,
    PriceRecord,
    SalesRecord,
    ScrapingConnector,
    StockRecord,
)

__all__ = [
    "CRMConnector",
    "EcommerceConnector",
    "ERPConnector",
    "MarketingConnector",
    "PriceRecord",
    "SalesRecord",
    "ScrapingConnector",
    "StockRecord",
]
