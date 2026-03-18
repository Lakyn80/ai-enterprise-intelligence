"""Pricing request schemas and strategy parameters."""

from typing import Literal

from pydantic import BaseModel, Field


class PricingStrategyParams(BaseModel):
    """Strategy-level configuration for price optimization objective."""

    objective: Literal["profit", "risk_adjusted_profit"] = "profit"
    hysteresis_profit_delta_threshold_pct: float = Field(
        1.0,
        description="Minimum profit delta (in %) required to allow a price change.",
    )
    quantity_swing_penalty: float = Field(
        0.0,
        description="Penalty weight for quantity swings when objective=risk_adjusted_profit.",
    )


class PricingOptimizeRequest(BaseModel):
    """Request body for pricing optimize endpoint."""

    product_id: str
    cost: float
    price_min: float
    price_max: float
    n_steps: int = 50
    max_price_change_pct: float = 0.08
    min_margin_pct: float = 0.15
    smoothing_alpha: float = 0.3
    strategy: PricingStrategyParams = Field(default_factory=PricingStrategyParams)
