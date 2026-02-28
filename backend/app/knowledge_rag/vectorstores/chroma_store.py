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
            path="./chroma_db",
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=settings.rag_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        ids = ids or [str(uuid.uuid4()) for _ in documents]
        metadatas = metadatas or [{}] * len(documents)
        embeddings = await self._embedding_provider.embed_documents(documents)
        self._collection.add(
            ids=ids[:len(documents)],
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        return ids[:len(documents)]

    async def similarity_search(
        self,
        query: str,
        k: int = 4,
    ) -> list[dict[str, Any]]:
        query_embedding = await self._embedding_provider.embed_query(query)
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas"],
        )
        if not result or not result["documents"]:
            return []
        docs = result["documents"][0] or []
        metas = result["metadatas"][0] or [{}] * len(docs)
        return [
            {"content": doc, "metadata": meta}
            for doc, meta in zip(docs, metas)
        ]
