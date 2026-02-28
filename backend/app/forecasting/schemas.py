"""Forecasting Pydantic schemas."""

from datetime import date

from pydantic import BaseModel, Field


class ForecastPoint(BaseModel):
    """Single forecast data point."""

    date: date
    product_id: str
    predicted_quantity: float
    predicted_revenue: float | None = None
    confidence_lower: float | None = None
    confidence_upper: float | None = None


class ForecastResponse(BaseModel):
    """Response for forecast endpoint."""

    product_id: str
    from_date: date
    to_date: date
    points: list[ForecastPoint] = Field(default_factory=list)
    model_version: str | None = None


class ScenarioPriceChangeRequest(BaseModel):
    """Request for price change scenario."""

    product_id: str
    from_date: date
    to_date: date
    price_delta_pct: float = Field(..., description="Price change in percent, e.g. 5 for +5%")


class ScenarioPriceChangeResponse(BaseModel):
    """Response for price change scenario."""

    product_id: str
    from_date: date
    to_date: date
    price_delta_pct: float
    base_forecast_points: list[ForecastPoint] = Field(default_factory=list)
    scenario_forecast_points: list[ForecastPoint] = Field(default_factory=list)
    delta_revenue_pct: float | None = None
    delta_quantity_pct: float | None = None
