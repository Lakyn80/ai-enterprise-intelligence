"""Qdrant-backed semantic cache backend."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.assistants.query_normalization import normalise_query
from app.assistants.semantic_backends.base import SemanticCacheBackend
from app.assistants.semantic_backends.utils import (
    now_iso,
    semantic_candidate_from_metadata,
    semantic_doc_id,
)
from app.knowledge_rag.ingest.embeddings import get_embedding_provider
from app.settings import settings
from app.vector.qdrant_support import (
    build_qdrant_filter,
    create_async_qdrant_client,
    ensure_qdrant_collection,
    get_qdrant_models,
    qdrant_similarity_query,
)

logger = logging.getLogger(__name__)


class QdrantSemanticCacheBackend(SemanticCacheBackend):
    """Stores semantic cache entries in Qdrant."""

    def __init__(self) -> None:
        self._client: Any = None
        self._embedding_provider: Any = None

    async def get(
        self,
        assistant_type: str,
        query: str,
        locale: str,
    ) -> dict[str, Any] | None:
        client = await self._get_client()
        if client is None:
            return None

        normalised = normalise_query(query)
        if not normalised:
            return None

        try:
            exists = await client.collection_exists(settings.assistants_semantic_cache_collection_name)
            if not exists:
                return None

            embedding = await self._get_embedding_provider().embed_query(normalised)
            q_filter = build_qdrant_filter(
                {"$and": [{"assistant_type": assistant_type}, {"locale": locale}]}
            )
            results = await qdrant_similarity_query(
                client,
                collection_name=settings.assistants_semantic_cache_collection_name,
                query_vector=embedding,
                query_filter=q_filter,
                limit=settings.assistants_semantic_cache_top_k,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            logger.warning("Qdrant semantic cache query error: %s", exc)
            return None

        for point in results or []:
            payload = dict(point.payload or {})
            score = float(getattr(point, "score", 0.0) or 0.0)
            return semantic_candidate_from_metadata(
                payload,
                normalised_query=normalised,
                similarity=score,
                distance=max(0.0, 1.0 - score),
            )

        return None

    async def set(
        self,
        assistant_type: str,
        query: str,
        locale: str,
        payload: dict[str, Any],
    ) -> None:
        client = await self._get_client()
        if client is None:
            return

        normalised = normalise_query(query)
        if not normalised:
            return

        try:
            embedding = await self._get_embedding_provider().embed_query(normalised)
            await ensure_qdrant_collection(
                client,
                settings.assistants_semantic_cache_collection_name,
                len(embedding),
                indexed_fields=["assistant_type", "locale", "normalised_query"],
            )
            models = get_qdrant_models()
            metadata = {
                "assistant_type": assistant_type,
                "locale": locale,
                "query": query,
                "normalised_query": normalised,
                "answer": payload["answer"],
                "citations_json": json.dumps(payload.get("citations", []), ensure_ascii=False),
                "used_tools_json": json.dumps(payload.get("used_tools", []), ensure_ascii=False),
                "created_at": now_iso(),
                "content": normalised,
            }
            await client.upsert(
                collection_name=settings.assistants_semantic_cache_collection_name,
                points=[
                    models.PointStruct(
                        id=semantic_doc_id(assistant_type, locale, normalised),
                        vector=embedding,
                        payload=metadata,
                    )
                ],
                wait=True,
            )
        except Exception as exc:
            logger.warning("Qdrant semantic cache store error: %s", exc)

    async def flush_assistant(self, assistant_type: str) -> int:
        client = await self._get_client()
        if client is None:
            return 0

        try:
            collection_name = settings.assistants_semantic_cache_collection_name
            exists = await client.collection_exists(collection_name)
            if not exists:
                return 0
            q_filter = build_qdrant_filter({"assistant_type": assistant_type})
            count_result = await client.count(
                collection_name=collection_name,
                count_filter=q_filter,
                exact=True,
            )
            deleted = int(getattr(count_result, "count", 0) or 0)
            if deleted:
                models = get_qdrant_models()
                await client.delete(
                    collection_name=collection_name,
                    points_selector=models.FilterSelector(filter=q_filter),
                    wait=True,
                )
            return deleted
        except Exception as exc:
            logger.warning("Qdrant semantic cache FLUSH error: %s", exc)
            return 0

    async def _get_client(self) -> Any:
        if self._client is None:
            try:
                self._client = create_async_qdrant_client()
            except Exception as exc:
                logger.warning("Qdrant semantic cache unavailable: %s", exc)
                self._client = None
        return self._client

    def _get_embedding_provider(self) -> Any:
        if self._embedding_provider is None:
            self._embedding_provider = get_embedding_provider()
        return self._embedding_provider
