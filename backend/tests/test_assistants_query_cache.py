"""Tests for custom assistant query cache."""

from unittest.mock import AsyncMock, patch

import pytest

from app.assistants.query_cache import AssistantQueryCache, normalise_query


def test_normalise_query_collapses_case_punctuation_and_whitespace():
    assert normalise_query("  Který produkt   nejvíce těží z akcí?!  ") == "který produkt nejvíce těží z akcí"


@pytest.mark.asyncio
async def test_get_semantic_delegates_to_selected_backend():
    cache = AssistantQueryCache()
    backend = AsyncMock()
    backend.get = AsyncMock(
        return_value={
            "answer": "cached answer",
            "citations": [{"source": "doc.txt"}],
            "used_tools": ["tool_x"],
            "cached_query": "",
            "similarity": 1.0,
            "distance": 0.9,
            "exact_normalised_match": True,
        }
    )

    with patch.object(cache, "_get_backend", return_value=backend):
        result = await cache.get_semantic("analyst", "What is total revenue?", "en")

    assert result == {
        "answer": "cached answer",
        "citations": [{"source": "doc.txt"}],
        "used_tools": ["tool_x"],
        "cached_query": "",
        "similarity": 1.0,
        "distance": 0.9,
        "exact_normalised_match": True,
    }


@pytest.mark.asyncio
async def test_set_semantic_delegates_to_selected_backend():
    cache = AssistantQueryCache()
    backend = AsyncMock()
    payload = {"answer": "x", "citations": [], "used_tools": []}

    with patch.object(cache, "_get_backend", return_value=backend):
        await cache.set_semantic("knowledge", "Which product gains the most from promotions?", "en", payload)

    backend.set.assert_awaited_once_with(
        "knowledge",
        "Which product gains the most from promotions?",
        "en",
        payload,
    )

@pytest.mark.asyncio
async def test_flush_assistant_removes_exact_and_semantic_entries():
    cache = AssistantQueryCache()
    redis = AsyncMock()
    redis.keys.return_value = ["assistants:custom:knowledge:en:1", "assistants:custom:knowledge:cs:2"]
    backend = AsyncMock()
    backend.flush_assistant = AsyncMock(return_value=2)

    with patch("app.assistants.query_cache.assistant_cache._get_client", AsyncMock(return_value=redis)), \
         patch.object(cache, "_get_backend", return_value=backend):
        result = await cache.flush_assistant("knowledge")

    redis.delete.assert_awaited_once_with(
        "assistants:custom:knowledge:en:1",
        "assistants:custom:knowledge:cs:2",
    )
    backend.flush_assistant.assert_awaited_once_with("knowledge")
    assert result == {"redis_deleted": 2, "semantic_deleted": 2}


def test_get_backend_selects_qdrant_when_configured():
    cache = AssistantQueryCache()
    with patch("app.assistants.query_cache.settings.assistants_semantic_cache_backend", "qdrant"):
        backend = cache._get_backend()

    assert backend.__class__.__name__ == "QdrantSemanticCacheBackend"


def test_get_backend_selects_chroma_by_default():
    cache = AssistantQueryCache()
    with patch("app.assistants.query_cache.settings.assistants_semantic_cache_backend", "chroma"):
        backend = cache._get_backend()

    assert backend.__class__.__name__ == "ChromaSemanticCacheBackend"
