"""Constraint and hysteresis rules for price recommendations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PricingConstraintParams:
    """Business constraints controlling final recommendation shape."""

    max_price_change_pct: float
    min_margin_pct: float
    smoothing_alpha: float


def apply_business_constraints(
    *,
    raw_optimal_price: float,
    base_price: float,
    cost: float,
    price_min: float,
    price_max: float,
    params: PricingConstraintParams,
) -> tuple[float, float, float]:
    """Apply max-change and minimum-margin constraints."""
    if base_price > 0:
        allowed_min = base_price * (1.0 - params.max_price_change_pct)
        allowed_max = base_price * (1.0 + params.max_price_change_pct)
    else:
        allowed_min = price_min
        allowed_max = price_max

    constrained_price = max(min(raw_optimal_price, allowed_max), allowed_min)
    min_allowed_price = cost * (1.0 + params.min_margin_pct)
    if constrained_price < min_allowed_price:
        constrained_price = min_allowed_price

    return constrained_price, allowed_min, allowed_max


def apply_smoothing(*, base_price: float, constrained_price: float, alpha: float) -> float:
    """Smooth transition between current and constrained price."""
    return (1.0 - alpha) * base_price + alpha * constrained_price


def compute_profit_delta_vs_current_pct(*, current_profit: float, candidate_profit: float) -> float:
    """Compute profit delta against current state in percent."""
    denominator = abs(current_profit)
    if denominator < 1e-8:
        if candidate_profit > current_profit:
            return 100.0
        if candidate_profit < current_profit:
            return -100.0
        return 0.0
    return ((candidate_profit - current_profit) / denominator) * 100.0


def should_hold_price_by_hysteresis(
    *,
    current_profit: float,
    candidate_profit: float,
    hysteresis_threshold_pct: float,
) -> tuple[bool, float]:
    """Return (hold_price, delta_pct) based on configured hysteresis threshold."""
    delta_pct = compute_profit_delta_vs_current_pct(
        current_profit=current_profit,
        candidate_profit=candidate_profit,
    )
    return delta_pct < hysteresis_threshold_pct, delta_pct
