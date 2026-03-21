"""Tests for deterministic facts engine orchestration."""

from unittest.mock import AsyncMock, patch

import pytest

from app.assistants.facts.service import (
    UnsupportedDeterministicFactsQueryError,
    deterministic_facts_service,
)
from app.assistants.trace_recorder import AssistantTraceRecorder


class FakeForecastingRepo:
    async def get_sales_dataset_signature(self):
        return {
            "row_count": 4,
            "quantity_sum": 62.0,
            "revenue_sum": 460.0,
            "promo_row_count": 2,
            "promo_quantity_sum": 29.0,
            "date_from": "2022-01-01",
            "date_to": "2024-01-01",
        }

    async def get_product_rank_winners(self, *, metric, direction, filters=None, date_range=None, limit=1):
        data = {
            ("quantity", "desc"): [{"product_id": "P0001", "value": 25.0}],
            ("revenue", "desc"): [{"product_id": "P0002", "value": 180.0}],
            ("quantity", "asc"): [{"product_id": "P0003", "value": 7.0}],
            ("revenue", "asc"): [
                {"product_id": "P0003", "value": 40.0},
                {"product_id": "P0004", "value": 40.0},
            ],
            ("promo_lift", "desc"): [{"product_id": "P0001", "value": 12.9}],
        }
        return data[(metric, direction)]


@pytest.mark.asyncio
async def test_deterministic_facts_service_returns_none_for_non_matching_query():
    trace = AssistantTraceRecorder(
        assistant_type="knowledge",
        request_kind="custom",
        locale="cs",
        user_query="Vysvětli trend pro Electronics",
    )

    result = await deterministic_facts_service.try_answer(
        assistant_type="knowledge",
        query="Vysvětli trend pro Electronics",
        locale="cs",
        forecasting_repo=FakeForecastingRepo(),
        trace=trace,
    )

    assert result is None
    assert any(step.payload and step.payload.get("selected_route") == "default_assistant" for step in trace.steps)


@pytest.mark.asyncio
async def test_deterministic_facts_service_resolves_and_renders_from_data():
    trace = AssistantTraceRecorder(
        assistant_type="analyst",
        request_kind="custom",
        locale="cs",
        user_query="Který produkt se prodává nejvíc?",
    )

    with patch("app.assistants.facts.service.deterministic_facts_cache") as mock_cache:
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()

        result = await deterministic_facts_service.try_answer(
            assistant_type="analyst",
            query="Který produkt se prodává nejvíc?",
            locale="cs",
            forecasting_repo=FakeForecastingRepo(),
            trace=trace,
        )

    assert result is not None
    assert result.cached is False
    assert result.answer == "Nejprodávanější produkt podle počtu kusů je P0001 (25 ks)."
    assert trace.cache_source == "deterministic_facts_resolver"
    assert trace.cache_strategy == "facts_resolve"
    assert any(step.step_name == "canonical_spec_mapped" for step in trace.steps)
    assert any(step.step_name == "deterministic_resolver_output" for step in trace.steps)
    mock_cache.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_deterministic_facts_service_reuses_cache_for_semantically_same_query():
    cached_payload = {
        "spec": {
            "spec_version": 1,
            "query_type": "fact",
            "entity": "product",
            "operation": "rank",
            "metric": "quantity",
            "direction": "desc",
            "filters": {},
            "date_range": None,
            "limit": 1,
        },
        "result": {
            "resolved": True,
            "entity": "product",
            "metric": "quantity",
            "direction": "desc",
            "winners": [{"product_id": "P0001", "value": 25.0}],
            "tie": False,
        },
    }
    trace = AssistantTraceRecorder(
        assistant_type="knowledge",
        request_kind="custom",
        locale="cs",
        user_query="Jaký je nejprodávanější produkt?",
    )

    with patch("app.assistants.facts.service.deterministic_facts_cache") as mock_cache, \
         patch("app.assistants.facts.service.deterministic_facts_resolver") as mock_resolver:
        mock_cache.get = AsyncMock(return_value=cached_payload)
        mock_cache.set = AsyncMock()
        mock_resolver.resolve = AsyncMock()

        result = await deterministic_facts_service.try_answer(
            assistant_type="knowledge",
            query="Jaký je nejprodávanější produkt?",
            locale="cs",
            forecasting_repo=FakeForecastingRepo(),
            trace=trace,
        )

    assert result is not None
    assert result.cached is True
    assert result.answer == "Nejprodávanější produkt podle počtu kusů je P0001 (25 ks)."
    assert trace.cache_source == "deterministic_facts_cache"
    assert trace.cache_strategy == "facts_spec_hash_hit"
    mock_resolver.resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_deterministic_facts_service_surfaces_supported_but_unsupported_query_shape():
    trace = AssistantTraceRecorder(
        assistant_type="analyst",
        request_kind="custom",
        locale="cs",
        user_query="Který produkt má nejvyšší tržby v kategorii Furniture?",
    )

    with pytest.raises(UnsupportedDeterministicFactsQueryError):
        await deterministic_facts_service.try_answer(
            assistant_type="analyst",
            query="Který produkt má nejvyšší tržby v kategorii Furniture?",
            locale="cs",
            forecasting_repo=FakeForecastingRepo(),
            trace=trace,
        )

    assert any(step.step_name == "deterministic_facts_unsupported" for step in trace.steps)


@pytest.mark.asyncio
async def test_deterministic_facts_service_renders_tie_stably():
    with patch("app.assistants.facts.service.deterministic_facts_cache") as mock_cache:
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()

        result = await deterministic_facts_service.try_answer(
            assistant_type="knowledge",
            query="Který produkt má nejnižší tržby?",
            locale="cs",
            forecasting_repo=FakeForecastingRepo(),
        )

    assert result is not None
    assert result.answer == "Na posledním místě je shoda mezi P0003, P0004 (40.00)."


@pytest.mark.asyncio
async def test_deterministic_facts_service_resolves_promo_lift_stably():
    with patch("app.assistants.facts.service.deterministic_facts_cache") as mock_cache:
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()

        result = await deterministic_facts_service.try_answer(
            assistant_type="knowledge",
            query="Který produkt nejvíce těží z akcí?",
            locale="cs",
            forecasting_repo=FakeForecastingRepo(),
        )

    assert result is not None
    assert result.answer == "Produkt, který nejvíce těží z akcí, je P0001 (+12.9%)."
