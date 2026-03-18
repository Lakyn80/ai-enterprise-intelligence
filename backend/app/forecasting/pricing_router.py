"""Pricing optimization API routes."""

from fastapi import APIRouter, HTTPException

from app.core.deps import AsyncSessionDep
from app.forecasting.pricing_schemas import PricingOptimizeRequest
from app.forecasting.pricing_service import PricingOptimizationService
from app.forecasting.repository import ForecastingRepository

router = APIRouter(prefix="/api", tags=["pricing"])


def _get_service(session: AsyncSessionDep) -> PricingOptimizationService:
    return PricingOptimizationService(ForecastingRepository(session))


@router.post("/pricing/optimize")
async def pricing_optimize(
    body: PricingOptimizeRequest,
    session: AsyncSessionDep,
):
    """Run price simulation for product and return optimal price."""
    service = _get_service(session)
    try:
        return await service.optimize(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
