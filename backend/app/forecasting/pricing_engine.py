"""Pure pricing objective functions."""

from app.forecasting.pricing_schemas import PricingStrategyParams


def compute_objective_score(
    *,
    profit: float,
    quantity: float,
    baseline_quantity: float,
    strategy: PricingStrategyParams,
) -> tuple[float, float]:
    """Return (objective_score, risk_penalty) for candidate ranking."""
    risk_penalty = 0.0
    if strategy.objective == "risk_adjusted_profit":
        risk_penalty = strategy.quantity_swing_penalty * abs(quantity - baseline_quantity)

    score = profit - risk_penalty
    return score, risk_penalty
