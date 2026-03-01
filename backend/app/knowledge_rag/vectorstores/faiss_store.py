"""FAISS vector store adapter."""

import pickle
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from app.knowledge_rag.vectorstores.base import VectorStore
from app.settings import settings


class FAISSVectorStore(VectorStore):
    """FAISS vector store - in-memory with optional persistence."""

    def __init__(self, embedding_fn: Any):
        self._embedding_fn = embedding_fn
        self._index: Any = None
        self._documents: list[str] = []
        self._metadatas: list[dict] = []
        self._ids: list[str] = []
        self._path = Path("./faiss_index")

    def _ensure_index(self, dim: int = 1024) -> None:
        if self._index is None:
            try:
                import faiss
                self._index = faiss.IndexFlatL2(dim)
            except ImportError:
                self._index = None

    async def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        ids = ids or [str(uuid.uuid4()) for _ in documents]
        metadatas = metadatas or [{}] * len(documents)
        embeddings = await self._embedding_fn.embed_documents(documents)
        embeddings_arr = np.array(embeddings, dtype=np.float32)
        dim = embeddings_arr.shape[1] if len(embeddings_arr) > 0 else 1024
        self._ensure_index(dim)
        if self._index is not None:
            self._index.add(embeddings_arr)
        self._documents.extend(documents)
        self._metadatas.extend(metadatas)
        self._ids.extend(ids[:len(documents)])
        return ids[:len(documents)]

    async def similarity_search(
        self,
        query: str,
        k: int = 4,
    ) -> list[dict[str, Any]]:
        if not self._documents or self._index is None:
            return []
        q_emb = await self._embedding_fn.embed_query(query)
        q_arr = np.array([q_emb], dtype=np.float32)
        _, indices = self._index.search(q_arr, min(k, len(self._documents)))
        results = []
        for idx in indices[0]:
            if 0 <= idx < len(self._documents):
                results.append({
                    "content": self._documents[idx],
                    "metadata": self._metadatas[idx] if idx < len(self._metadatas) else {},
                })
        return results
