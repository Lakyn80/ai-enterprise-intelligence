"""Tools for AI assistant to fetch forecast and scenario data."""

from datetime import date
from typing import Any

# Avoid circular import - service is injected at runtime


async def get_forecast(
    forecasting_service: Any,
    product_id: str,
    from_date: date,
    to_date: date,
) -> dict[str, Any]:
    """Fetch forecast for product/date range."""
    points, version = await forecasting_service.get_forecast(
        product_id, from_date, to_date
    )
    return {
        "product_id": product_id,
        "from_date": str(from_date),
        "to_date": str(to_date),
        "model_version": version,
        "points": [
            {
                "date": str(p.date),
                "predicted_quantity": p.predicted_quantity,
                "predicted_revenue": p.predicted_revenue,
            }
            for p in points
        ],
    }


async def get_scenario_price_change(
    forecasting_service: Any,
    product_id: str,
    from_date: date,
    to_date: date,
    price_delta_pct: float,
) -> dict[str, Any]:
    """Fetch scenario with price change."""
    result = await forecasting_service.scenario_price_change(
        product_id, from_date, to_date, price_delta_pct
    )
    return {
        "product_id": result.product_id,
        "price_delta_pct": result.price_delta_pct,
        "delta_revenue_pct": result.delta_revenue_pct,
        "delta_quantity_pct": result.delta_quantity_pct,
        "base_points": [
            {"date": str(p.date), "predicted_quantity": p.predicted_quantity}
            for p in result.base_forecast_points[:10]
        ],
        "scenario_points": [
            {"date": str(p.date), "predicted_quantity": p.predicted_quantity}
            for p in result.scenario_forecast_points[:10]
        ],
    }


def get_forecast_tools_spec() -> list[dict[str, Any]]:
    """OpenAI-compatible tools schema for forecast/scenario."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_forecast",
                "description": "Get demand forecast for a product in a date range. Use this when user asks about predictions, expected sales, or future demand.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string", "description": "Product ID"},
                        "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                        "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
                    },
                    "required": ["product_id", "from_date", "to_date"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_scenario_price_change",
                "description": "Get forecast scenario with hypothetical price change (e.g. +5%). Use when user asks 'what if we increase price by X%'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "from_date": {"type": "string"},
                        "to_date": {"type": "string"},
                        "price_delta_pct": {"type": "number", "description": "Price change in % e.g. 5 for +5%"},
                    },
                    "required": ["product_id", "from_date", "to_date", "price_delta_pct"],
                },
            },
        },
    ]
