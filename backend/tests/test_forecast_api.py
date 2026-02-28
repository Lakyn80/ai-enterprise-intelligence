"""Tests for forecast API endpoint."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_forecast_endpoint_structure(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get(
            "/api/forecast",
            params={
                "product_id": "P001",
                "from_date": "2024-06-01",
                "to_date": "2024-06-30",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "product_id" in data
        assert "from_date" in data
        assert "to_date" in data
        assert "points" in data
        assert isinstance(data["points"], list)
