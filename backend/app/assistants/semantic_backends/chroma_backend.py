"""Chroma-backed semantic cache backend."""

from __future__ import annotations

import json
import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.assistants.query_normalization import normalise_query
from app.assistants.semantic_backends.base import SemanticCacheBackend
from app.assistants.semantic_backends.utils import (
    now_iso,
    semantic_candidate_from_metadata,
    semantic_doc_id,
)
from app.knowledge_rag.ingest.embeddings import get_embedding_provider
from app.settings import settings

logger = logging.getLogger(__name__)


class ChromaSemanticCacheBackend(SemanticCacheBackend):
    """Stores semantic cache entries in Chroma."""

    def __init__(self) -> None:
        self._client: chromadb.PersistentClient | None = None
        self._collection: Any = None
        self._embedding_provider: Any = None

    async def get(
        self,
        assistant_type: str,
        query: str,
        locale: str,
    ) -> dict[str, Any] | None:
        collection = await self._get_collection()
        if collection is None:
            return None

        normalised = normalise_query(query)
        if not normalised:
            return None

        try:
            embedding = await self._get_embedding_provider().embed_query(normalised)
            count = collection.count()
            if count == 0:
                return None

            query_kwargs = {
                "query_embeddings": [embedding],
                "n_results": min(settings.assistants_semantic_cache_top_k, max(count, 1)),
                "where": {"$and": [{"assistant_type": assistant_type}, {"locale": locale}]},
                "include": ["metadatas", "distances"],
            }
            try:
                result = collection.query(**query_kwargs)
            except Exception:
                query_kwargs["n_results"] = 1
                result = collection.query(**query_kwargs)
        except Exception as exc:
            logger.warning("Chroma semantic cache query error: %s", exc)
            return None

        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        if not metadatas:
            return None

        for metadata, distance in zip(metadatas, distances):
            if not metadata:
                continue
            resolved_distance = float(distance or 1.0)
            return semantic_candidate_from_metadata(
                metadata,
                normalised_query=normalised,
                similarity=max(0.0, 1.0 - resolved_distance),
                distance=resolved_distance,
            )

        return None

    async def set(
        self,
        assistant_type: str,
        query: str,
        locale: str,
        payload: dict[str, Any],
    ) -> None:
        collection = await self._get_collection()
        if collection is None:
            return

        normalised = normalise_query(query)
        if not normalised:
            return

        try:
            embedding = await self._get_embedding_provider().embed_query(normalised)
            metadata = {
                "assistant_type": assistant_type,
                "locale": locale,
                "query": query,
                "normalised_query": normalised,
                "answer": payload["answer"],
                "citations_json": json.dumps(payload.get("citations", []), ensure_ascii=False),
                "used_tools_json": json.dumps(payload.get("used_tools", []), ensure_ascii=False),
                "created_at": now_iso(),
            }
            collection.upsert(
                ids=[semantic_doc_id(assistant_type, locale, normalised)],
                documents=[normalised],
                embeddings=[embedding],
                metadatas=[metadata],
            )
        except Exception as exc:
            logger.warning("Chroma semantic cache store error: %s", exc)

    async def flush_assistant(self, assistant_type: str) -> int:
        collection = await self._get_collection()
        if collection is None:
            return 0
        try:
            existing = collection.get(
                where={"assistant_type": assistant_type},
                include=[],
            )
            ids = existing.get("ids", []) if existing else []
            if ids:
                collection.delete(ids=ids)
            return len(ids)
        except Exception as exc:
            logger.warning("Chroma semantic cache FLUSH error: %s", exc)
            return 0

    async def _get_collection(self) -> Any:
        if self._collection is not None:
            return self._collection
        try:
            self._client = chromadb.PersistentClient(
                path=settings.rag_chroma_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=settings.assistants_semantic_cache_collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.warning("Chroma semantic cache unavailable: %s", exc)
            self._collection = None
        return self._collection

    def _get_embedding_provider(self) -> Any:
        if self._embedding_provider is None:
            self._embedding_provider = get_embedding_provider()
        return self._embedding_provider
