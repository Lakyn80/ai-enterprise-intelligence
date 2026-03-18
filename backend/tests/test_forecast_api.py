"""Tests for forecast API endpoints."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.forecasting.schemas import ForecastResponse


@pytest.fixture
def app():
    return create_app()


# ---------------------------------------------------------------------------
# Health check (no DB needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Forecast endpoint – mocked service (no DB required)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_forecast_endpoint_structure(app):
    """Verify /api/forecast returns the expected JSON shape using a mocked service."""
    mock_points = []  # empty – model not trained
    mock_version = "test-version"

    with patch(
        "app.forecasting.router.get_forecasting_service"
    ) as mock_factory:
        mock_service = MagicMock()
        mock_service.get_forecast = AsyncMock(return_value=(mock_points, mock_version))
        mock_factory.return_value = mock_service

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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
    assert data["model_version"] == mock_version


@pytest.mark.asyncio
async def test_forecast_endpoint_returns_points(app):
    """When service returns forecast points they appear in the response."""
    from app.forecasting.schemas import ForecastPoint

    mock_points = [
        ForecastPoint(date=date(2024, 6, 1), product_id="P001", predicted_quantity=12.5),
        ForecastPoint(date=date(2024, 6, 2), product_id="P001", predicted_quantity=14.0),
    ]

    with patch("app.forecasting.router.get_forecasting_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.get_forecast = AsyncMock(return_value=(mock_points, "v1"))
        mock_factory.return_value = mock_service

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/forecast",
                params={"product_id": "P001", "from_date": "2024-06-01", "to_date": "2024-06-02"},
            )

    assert r.status_code == 200
    data = r.json()
    assert len(data["points"]) == 2
    assert data["points"][0]["predicted_quantity"] == pytest.approx(12.5)


@pytest.mark.asyncio
async def test_backtest_endpoint_structure(app):
    """Verify /api/backtest returns the expected JSON shape using a mocked service."""
    mock_result = {
        "mae": 1.23,
        "rmse": 1.67,
        "mape": 8.5,
        "n_samples": 42,
        "date_range": {
            "train_start": "2024-01-01",
            "train_end": "2024-02-01",
            "test_start": "2024-02-01",
            "test_end": "2024-03-01",
        },
        "product_id": "P001",
    }

    with patch("app.forecasting.router.get_forecasting_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.run_backtest = AsyncMock(return_value=mock_result)
        mock_factory.return_value = mock_service

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/backtest",
                params={
                    "product_id": "P001",
                    "from_date": "2024-01-01",
                    "to_date": "2024-03-01",
                },
            )

    assert r.status_code == 200
    data = r.json()
    assert "mae" in data
    assert "rmse" in data
    assert "mape" in data
    assert "n_samples" in data
    assert "date_range" in data
