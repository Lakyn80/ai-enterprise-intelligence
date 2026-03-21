"""Qdrant vector store adapter."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.knowledge_rag.vectorstores.base import VectorStore
from app.settings import settings
from app.vector.qdrant_support import (
    build_qdrant_filter,
    create_async_qdrant_client,
    ensure_qdrant_collection,
    get_qdrant_models,
)

logger = logging.getLogger(__name__)


class QdrantVectorStore(VectorStore):
    """Qdrant-backed vector store for production RAG workloads."""

    _EMBED_BATCH_SIZE = 8

    def __init__(self, embedding_provider: Any):
        self._embedding_provider = embedding_provider
        self._client: Any = None

    async def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        if not documents:
            return []

        client = await self._get_client()
        if client is None:
            return []

        ids = ids or [str(uuid.uuid4()) for _ in documents]
        metadatas = metadatas or [{}] * len(documents)
        all_embeddings: list[list[float]] = []
        for i in range(0, len(documents), self._EMBED_BATCH_SIZE):
            batch = documents[i: i + self._EMBED_BATCH_SIZE]
            batch_emb = await self._embedding_provider.embed_documents(batch)
            all_embeddings.extend(batch_emb)

        await ensure_qdrant_collection(
            client,
            settings.rag_collection_name,
            len(all_embeddings[0]),
            indexed_fields=["source", "report_type", "product_id", "category_id"],
        )
        models = get_qdrant_models()
        points = [
            models.PointStruct(
                id=doc_id,
                vector=embedding,
                payload={**metadata, "content": document},
            )
            for doc_id, document, metadata, embedding in zip(
                ids[:len(documents)],
                documents,
                metadatas,
                all_embeddings,
            )
        ]
        await client.upsert(
            collection_name=settings.rag_collection_name,
            points=points,
            wait=True,
        )
        return ids[:len(documents)]

    async def similarity_search(
        self,
        query: str,
        k: int = 4,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        client = await self._get_client()
        if client is None:
            return []
        try:
            exists = await client.collection_exists(settings.rag_collection_name)
            if not exists:
                return []

            query_embedding = await self._embedding_provider.embed_query(query)
            results = await client.search(
                collection_name=settings.rag_collection_name,
                query_vector=query_embedding,
                query_filter=build_qdrant_filter(where),
                limit=k,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            logger.warning("Qdrant similarity search failed: %s", exc)
            return []
        output: list[dict[str, Any]] = []
        for point in results or []:
            payload = dict(point.payload or {})
            output.append(
                {
                    "content": payload.pop("content", ""),
                    "metadata": payload,
                }
            )
        return output

    async def reset(self) -> list[str]:
        client = await self._get_client()
        if client is None:
            return []
        removed: list[str] = []
        try:
            exists = await client.collection_exists(settings.rag_collection_name)
            if exists:
                await client.delete_collection(settings.rag_collection_name)
                removed.append("qdrant_collection")
        except Exception as exc:
            logger.warning("Qdrant reset failed: %s", exc)
        return removed

    async def _get_client(self) -> Any:
        if self._client is None:
            try:
                self._client = create_async_qdrant_client()
            except Exception as exc:
                logger.warning("Qdrant vector store unavailable: %s", exc)
                self._client = None
        return self._client
