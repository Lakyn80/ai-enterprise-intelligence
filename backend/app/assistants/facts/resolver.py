"""Deterministic resolver for exact fact queries."""

from __future__ import annotations

from typing import Any

from app.assistants.facts.schemas import FactQuerySpec, FactResolveResult, FactWinner


class DeterministicFactsResolver:
    """Resolve canonical fact specs using deterministic DB aggregations."""

    async def resolve(self, forecasting_repo: Any, spec: FactQuerySpec) -> FactResolveResult:
        winners = await forecasting_repo.get_product_rank_winners(
            metric=spec.metric,
            direction=spec.direction,
            filters=spec.filters,
            date_range=spec.date_range,
            limit=spec.limit,
        )
        if not winners:
            raise ValueError("No sales data available for deterministic facts query.")

        return FactResolveResult(
            resolved=True,
            entity=spec.entity,
            metric=spec.metric,
            direction=spec.direction,
            winners=[FactWinner(**winner) for winner in winners],
            tie=len(winners) > 1,
        )


deterministic_facts_resolver = DeterministicFactsResolver()
