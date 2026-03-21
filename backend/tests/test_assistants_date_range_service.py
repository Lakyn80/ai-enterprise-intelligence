from unittest.mock import AsyncMock, patch

import pytest

from app.assistants.date_range_service import deterministic_date_range_service
from app.assistants.trace_recorder import AssistantTraceRecorder


class FakeDateRangeRepo:
    async def get_sales_dataset_signature(self):
        return {
            "row_count": 4,
            "quantity_sum": 62.0,
            "revenue_sum": 460.0,
            "price_sum": 189.8,
            "promo_row_count": 2,
            "promo_quantity_sum": 29.0,
            "date_from": "2022-01-01",
            "date_to": "2024-01-01",
        }

    async def get_date_range(self):
        return "2022-01-01", "2024-01-01"


@pytest.mark.asyncio
async def test_date_range_service_returns_none_for_unrelated_query():
    result = await deterministic_date_range_service.try_answer(
        assistant_type="knowledge",
        query="Který produkt má nejvyšší tržby?",
        locale="cs",
        forecasting_repo=FakeDateRangeRepo(),
    )

    assert result is None


@pytest.mark.asyncio
async def test_date_range_service_resolves_czech_paraphrase():
    trace = AssistantTraceRecorder(
        assistant_type="knowledge",
        request_kind="custom",
        locale="cs",
        user_query="v jakém časovém rozmezí jsou prodejní data?",
    )

    with patch("app.assistants.date_range_service._get_cache", AsyncMock(return_value=None)), \
         patch("app.assistants.date_range_service._set_cache", AsyncMock()) as mock_set_cache:
        result = await deterministic_date_range_service.try_answer(
            assistant_type="knowledge",
            query="v jakém časovém rozmezí jsou prodejní data?",
            locale="cs",
            forecasting_repo=FakeDateRangeRepo(),
            trace=trace,
        )

    assert result is not None
    assert result.answer == "Prodejní data pokrývají období od 2022-01-01 do 2024-01-01."
    assert trace.cache_source == "deterministic_date_range_resolver"
    mock_set_cache.assert_awaited_once()


@pytest.mark.asyncio
async def test_date_range_service_resolves_czech_genitive_variant():
    with patch("app.assistants.date_range_service._get_cache", AsyncMock(return_value=None)), \
         patch("app.assistants.date_range_service._set_cache", AsyncMock()):
        result = await deterministic_date_range_service.try_answer(
            assistant_type="knowledge",
            query="Jaké je datumové rozmezí prodejních dat?",
            locale="cs",
            forecasting_repo=FakeDateRangeRepo(),
        )

    assert result is not None
    assert result.answer == "Prodejní data pokrývají období od 2022-01-01 do 2024-01-01."


@pytest.mark.asyncio
async def test_date_range_service_resolves_czech_data_o_prodejich_variant():
    with patch("app.assistants.date_range_service._get_cache", AsyncMock(return_value=None)), \
         patch("app.assistants.date_range_service._set_cache", AsyncMock()):
        result = await deterministic_date_range_service.try_answer(
            assistant_type="knowledge",
            query="Od kdy do kdy máme data o prodejích?",
            locale="cs",
            forecasting_repo=FakeDateRangeRepo(),
        )

    assert result is not None
    assert result.answer == "Prodejní data pokrývají období od 2022-01-01 do 2024-01-01."


@pytest.mark.asyncio
async def test_date_range_service_reuses_intent_cache_for_paraphrase():
    cached = {
        "intent": "date_range_of_data",
        "date_from": "2022-01-01",
        "date_to": "2024-01-01",
        "answer": "Sales data covers the period from 2022-01-01 to 2024-01-01.",
    }

    with patch("app.assistants.date_range_service._get_cache", AsyncMock(return_value=cached)):
        result = await deterministic_date_range_service.try_answer(
            assistant_type="knowledge",
            query="What date range does the sales data cover?",
            locale="en",
            forecasting_repo=FakeDateRangeRepo(),
        )

    assert result is not None
    assert result.cached is True
    assert result.answer == "Sales data covers the period from 2022-01-01 to 2024-01-01."
