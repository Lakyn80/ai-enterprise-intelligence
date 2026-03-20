"""Exact + semantic cache for custom assistant questions."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.assistants.cache import assistant_cache
from app.knowledge_rag.ingest.embeddings import get_embedding_provider
from app.settings import settings

logger = logging.getLogger(__name__)


def normalise_query(query: str) -> str:
    query = query.strip().lower()
    query = re.sub(r"[^\w\s]", " ", query, flags=re.UNICODE)
    return re.sub(r"\s+", " ", query).strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _exact_key(assistant_type: str, locale: str, query: str) -> str:
    normalised = normalise_query(query)
    digest = hashlib.sha256(normalised.encode("utf-8")).hexdigest()
    return f"assistants:custom:{assistant_type}:{locale}:{digest}"


def _set_kwargs() -> dict[str, int]:
    ttl = getattr(settings, "assistants_cache_ttl", 0)
    return {"ex": ttl} if ttl > 0 else {}


class AssistantQueryCache:
    """Stores custom Q&A in Redis (exact) and Chroma (semantic)."""

    def __init__(self) -> None:
        self._client: chromadb.PersistentClient | None = None
        self._collection: Any = None
        self._embedding_provider: Any = None

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
                # Some Chroma versions fail when n_results is greater than the
                # number of documents matching the where filter.
                query_kwargs["n_results"] = 1
                result = collection.query(**query_kwargs)
        except Exception as exc:
            logger.warning("Custom semantic cache query error: %s", exc)
            return None

        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        if not metadatas:
            return None

        for metadata, distance in zip(metadatas, distances):
            if not metadata:
                continue
            return self._semantic_candidate_from_metadata(metadata, distance, normalised)

        return None

    async def set_semantic(
        self,
        assistant_type: str,
        query: str,
        locale: str,
        payload: dict[str, Any],
    ) -> None:
        if not settings.assistants_semantic_cache_enabled:
            return
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
                "created_at": _now_iso(),
            }
            doc_id = f"{assistant_type}:{locale}:{hashlib.sha256(normalised.encode('utf-8')).hexdigest()}"
            collection.upsert(
                ids=[doc_id],
                documents=[normalised],
                embeddings=[embedding],
                metadatas=[metadata],
            )
        except Exception as exc:
            logger.warning("Custom semantic cache store error: %s", exc)

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
        collection = await self._get_collection()
        if collection is not None:
            try:
                existing = collection.get(
                    where={"assistant_type": assistant_type},
                    include=[],
                )
                ids = existing.get("ids", []) if existing else []
                if ids:
                    collection.delete(ids=ids)
                semantic_deleted = len(ids)
            except Exception as exc:
                logger.warning("Custom semantic cache FLUSH error: %s", exc)

        return {"redis_deleted": redis_deleted, "semantic_deleted": semantic_deleted}

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
            logger.warning("Custom semantic cache unavailable: %s", exc)
            self._collection = None
        return self._collection

    def _get_embedding_provider(self) -> Any:
        if self._embedding_provider is None:
            self._embedding_provider = get_embedding_provider()
        return self._embedding_provider

    @staticmethod
    def _payload_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        return {
            "answer": metadata.get("answer", ""),
            "citations": json.loads(metadata.get("citations_json", "[]")),
            "used_tools": json.loads(metadata.get("used_tools_json", "[]")),
        }

    @classmethod
    def _semantic_candidate_from_metadata(
        cls,
        metadata: dict[str, Any],
        distance: Any,
        normalised_query: str,
    ) -> dict[str, Any]:
        cached_normalised = str(metadata.get("normalised_query", "")).strip()
        exact_normalised_match = cached_normalised == normalised_query
        resolved_distance = float(distance or 1.0)
        similarity = 1.0 if exact_normalised_match else max(0.0, 1.0 - resolved_distance)
        payload = cls._payload_from_metadata(metadata)
        payload.update({
            "cached_query": metadata.get("query", ""),
            "similarity": similarity,
            "distance": resolved_distance,
            "exact_normalised_match": exact_normalised_match,
        })
        return payload


assistant_query_cache = AssistantQueryCache()
