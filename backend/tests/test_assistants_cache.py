"""Tests for Redis cache TTL behaviour."""

from unittest.mock import AsyncMock, patch

import pytest

from app.assistants.cache import AssistantCache, _build_set_kwargs


def test_build_set_kwargs_without_ttl_uses_persistent_cache():
    with patch("app.assistants.cache.settings.assistants_cache_ttl", 0):
        assert _build_set_kwargs() == {}


def test_build_set_kwargs_with_positive_ttl_sets_expiry():
    with patch("app.assistants.cache.settings.assistants_cache_ttl", 3600):
        assert _build_set_kwargs() == {"ex": 3600}


@pytest.mark.asyncio
async def test_set_omits_expiry_when_cache_is_persistent():
    cache = AssistantCache()
    client = AsyncMock()

    with patch.object(cache, "_get_client", AsyncMock(return_value=client)), \
         patch("app.assistants.cache.settings.assistants_cache_ttl", 0):
        await cache.set("knowledge", "k_001", {"answer": "cached"})

    client.set.assert_awaited_once_with(
        "assistants:knowledge:k_001:en",
        '{"answer": "cached"}',
    )


@pytest.mark.asyncio
async def test_set_passes_expiry_when_ttl_is_positive():
    cache = AssistantCache()
    client = AsyncMock()

    with patch.object(cache, "_get_client", AsyncMock(return_value=client)), \
         patch("app.assistants.cache.settings.assistants_cache_ttl", 120):
        await cache.set("knowledge", "k_001", {"answer": "cached"})

    client.set.assert_awaited_once_with(
        "assistants:knowledge:k_001:en",
        '{"answer": "cached"}',
        ex=120,
    )
