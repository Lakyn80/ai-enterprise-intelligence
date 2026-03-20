"""Tests for custom assistant query cache."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.assistants.query_cache import AssistantQueryCache, normalise_query


def test_normalise_query_collapses_case_punctuation_and_whitespace():
    assert normalise_query("  Který produkt   nejvíce těží z akcí?!  ") == "který produkt nejvíce těží z akcí"


@pytest.mark.asyncio
async def test_get_semantic_prefers_same_normalised_query_even_with_higher_distance():
    cache = AssistantQueryCache()
    provider = MagicMock()
    provider.embed_query = AsyncMock(return_value=[0.1, 0.2])
    collection = MagicMock()
    collection.count.return_value = 2
    collection.query.return_value = {
        "metadatas": [[{
            "normalised_query": "what is total revenue",
            "answer": "cached answer",
            "citations_json": '[{"source":"doc.txt"}]',
            "used_tools_json": '["tool_x"]',
        }]],
        "distances": [[0.9]],
    }

    with patch.object(cache, "_get_collection", AsyncMock(return_value=collection)), \
         patch.object(cache, "_get_embedding_provider", return_value=provider):
        result = await cache.get_semantic("analyst", "What is total revenue?", "en")

    assert result == {
        "answer": "cached answer",
        "citations": [{"source": "doc.txt"}],
        "used_tools": ["tool_x"],
    }


@pytest.mark.asyncio
async def test_get_semantic_returns_match_within_distance_threshold():
    cache = AssistantQueryCache()
    provider = MagicMock()
    provider.embed_query = AsyncMock(return_value=[0.1, 0.2])
    collection = MagicMock()
    collection.count.return_value = 1
    collection.query.return_value = {
        "metadatas": [[{
            "normalised_query": "which product benefits the most from promotions",
            "answer": "cached answer",
            "citations_json": "[]",
            "used_tools_json": "[]",
        }]],
        "distances": [[0.05]],
    }

    with patch.object(cache, "_get_collection", AsyncMock(return_value=collection)), \
         patch.object(cache, "_get_embedding_provider", return_value=provider), \
         patch("app.assistants.query_cache.settings.assistants_semantic_cache_max_distance", 0.12):
        result = await cache.get_semantic("knowledge", "Which product gains the most from promotions?", "en")

    assert result is not None
    assert result["answer"] == "cached answer"


@pytest.mark.asyncio
async def test_get_semantic_retries_with_single_result_when_filtered_query_overflows():
    cache = AssistantQueryCache()
    provider = MagicMock()
    provider.embed_query = AsyncMock(return_value=[0.1, 0.2])
    collection = MagicMock()
    collection.count.return_value = 5
    collection.query.side_effect = [
        RuntimeError("n_results too large for filter"),
        {
            "metadatas": [[{
                "normalised_query": "which products have the highest total sales",
                "answer": "cached answer",
                "citations_json": "[]",
                "used_tools_json": "[]",
            }]],
            "distances": [[0.01]],
        },
    ]

    with patch.object(cache, "_get_collection", AsyncMock(return_value=collection)), \
         patch.object(cache, "_get_embedding_provider", return_value=provider):
        result = await cache.get_semantic("knowledge", "Which products have the highest total sales?", "en")

    assert result is not None
    assert collection.query.call_count == 2


@pytest.mark.asyncio
async def test_flush_assistant_removes_exact_and_semantic_entries():
    cache = AssistantQueryCache()
    redis = AsyncMock()
    redis.keys.return_value = ["assistants:custom:knowledge:en:1", "assistants:custom:knowledge:cs:2"]
    collection = MagicMock()
    collection.get.return_value = {"ids": ["knowledge:en:1", "knowledge:cs:2"]}

    with patch("app.assistants.query_cache.assistant_cache._get_client", AsyncMock(return_value=redis)), \
         patch.object(cache, "_get_collection", AsyncMock(return_value=collection)):
        result = await cache.flush_assistant("knowledge")

    redis.delete.assert_awaited_once_with(
        "assistants:custom:knowledge:en:1",
        "assistants:custom:knowledge:cs:2",
    )
    collection.delete.assert_called_once_with(ids=["knowledge:en:1", "knowledge:cs:2"])
    assert result == {"redis_deleted": 2, "semantic_deleted": 2}
