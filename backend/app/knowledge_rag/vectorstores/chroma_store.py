"""Chroma vector store adapter."""

import asyncio
import uuid
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.knowledge_rag.vectorstores.base import VectorStore
from app.settings import settings


class ChromaVectorStore(VectorStore):
    """ChromaDB vector store."""

    def __init__(self, embedding_provider: Any):
        self._embedding_provider = embedding_provider
        self._client = chromadb.PersistentClient(
            path=settings.rag_chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=settings.rag_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    _EMBED_BATCH_SIZE = 8  # max chunks per embedding API call

    async def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        ids = ids or [str(uuid.uuid4()) for _ in documents]
        metadatas = metadatas or [{}] * len(documents)

        # Embed in small batches to avoid API payload/timeout limits
        all_embeddings: list[list[float]] = []
        for i in range(0, len(documents), self._EMBED_BATCH_SIZE):
            batch = documents[i: i + self._EMBED_BATCH_SIZE]
            batch_emb = await self._embedding_provider.embed_documents(batch)
            all_embeddings.extend(batch_emb)

        self._collection.add(
            ids=ids[:len(documents)],
            embeddings=all_embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        return ids[:len(documents)]

    async def similarity_search(
        self,
        query: str,
        k: int = 4,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        query_embedding = await self._embedding_provider.embed_query(query)
        query_kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": k,
            "include": ["documents", "metadatas"],
        }
        if where:
            query_kwargs["where"] = where
        result = self._collection.query(**query_kwargs)
        if not result or not result["documents"]:
            return []
        docs = result["documents"][0] or []
        metas = result["metadatas"][0] or [{}] * len(docs)
        return [
            {"content": doc, "metadata": meta}
            for doc, meta in zip(docs, metas)
        ]
