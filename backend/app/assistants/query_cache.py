"""Exact + pluggable semantic cache for custom assistant questions."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.assistants.cache import assistant_cache
from app.assistants.query_normalization import normalise_query
from app.assistants.semantic_backends.base import SemanticCacheBackend
from app.settings import settings

logger = logging.getLogger(__name__)


def _exact_key(assistant_type: str, locale: str, query: str) -> str:
    normalised = normalise_query(query)
    digest = hashlib.sha256(normalised.encode("utf-8")).hexdigest()
    return f"assistants:custom:{assistant_type}:{locale}:{digest}"


def _set_kwargs() -> dict[str, int]:
    ttl = getattr(settings, "assistants_cache_ttl", 0)
    return {"ex": ttl} if ttl > 0 else {}


class AssistantQueryCache:
    """Stores custom Q&A in Redis (exact) and pluggable vector backend (semantic)."""

    def __init__(self) -> None:
        self._semantic_backend: SemanticCacheBackend | None = None

    async def get_exact(self, assistant_type: str, query: str, locale: str) -> dict[str, Any] | None:
        client = await assistant_cache._get_client()
        if client is None:
            return None
        try:
            raw = await client.get(_exact_key(assistant_type, locale, query))
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("Custom exact cache GET error: %s", exc)
            return None

    async def set_exact(
        self,
        assistant_type: str,
        query: str,
        locale: str,
        payload: dict[str, Any],
    ) -> None:
        client = await assistant_cache._get_client()
        if client is None:
            return
        try:
            await client.set(
                _exact_key(assistant_type, locale, query),
                json.dumps(payload, ensure_ascii=False),
                **_set_kwargs(),
            )
        except Exception as exc:
            logger.warning("Custom exact cache SET error: %s", exc)

    async def get_semantic(
        self,
        assistant_type: str,
        query: str,
        locale: str,
    ) -> dict[str, Any] | None:
        if not settings.assistants_semantic_cache_enabled:
            return None
        backend = self._get_backend()
        return await backend.get(assistant_type, query, locale)

    async def set_semantic(
        self,
        assistant_type: str,
        query: str,
        locale: str,
        payload: dict[str, Any],
    ) -> None:
        if not settings.assistants_semantic_cache_enabled:
            return
        backend = self._get_backend()
        await backend.set(assistant_type, query, locale, payload)

    async def flush_assistant(self, assistant_type: str) -> dict[str, int]:
        redis_deleted = 0
        client = await assistant_cache._get_client()
        if client is not None:
            try:
                keys = await client.keys(f"assistants:custom:{assistant_type}:*")
                if keys:
                    await client.delete(*keys)
                redis_deleted = len(keys)
            except Exception as exc:
                logger.warning("Custom exact cache FLUSH error: %s", exc)

        semantic_deleted = 0
        if settings.assistants_semantic_cache_enabled:
            semantic_deleted = await self._get_backend().flush_assistant(assistant_type)

        return {"redis_deleted": redis_deleted, "semantic_deleted": semantic_deleted}

    def _get_backend(self) -> SemanticCacheBackend:
        if self._semantic_backend is not None:
            return self._semantic_backend

        backend_name = settings.assistants_semantic_cache_backend.lower().strip()
        if backend_name == "qdrant":
            from app.assistants.semantic_backends.qdrant_backend import QdrantSemanticCacheBackend

            self._semantic_backend = QdrantSemanticCacheBackend()
        else:
            from app.assistants.semantic_backends.chroma_backend import ChromaSemanticCacheBackend

            self._semantic_backend = ChromaSemanticCacheBackend()
        return self._semantic_backend


assistant_query_cache = AssistantQueryCache()
