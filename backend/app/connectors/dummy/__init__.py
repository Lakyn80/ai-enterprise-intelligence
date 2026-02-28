"""Dummy connector implementations for development and testing."""

from app.connectors.dummy.crm_dummy import DummyCRMConnector
from app.connectors.dummy.ecommerce_dummy import DummyEcommerceConnector
from app.connectors.dummy.erp_dummy import DummyERPConnector
from app.connectors.dummy.marketing_dummy import DummyMarketingConnector
from app.connectors.dummy.scraping_dummy import DummyScrapingConnector

__all__ = [
    "DummyCRMConnector",
    "DummyEcommerceConnector",
    "DummyERPConnector",
    "DummyMarketingConnector",
    "DummyScrapingConnector",
]
