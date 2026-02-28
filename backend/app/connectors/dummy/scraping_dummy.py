"""Placeholder scraping connector - to be implemented later."""

from app.connectors.base import ScrapingConnector


class DummyScrapingConnector(ScrapingConnector):
    """Placeholder - returns empty data. Implement real scraping logic when needed."""

    async def scrape_product_data(
        self,
        product_ids: list[str],
        **kwargs,
    ) -> dict:
        return {
            "status": "not_implemented",
            "message": "Scraping connector placeholder - implement when external sources are ready",
            "product_ids": product_ids,
            "data": {},
        }
