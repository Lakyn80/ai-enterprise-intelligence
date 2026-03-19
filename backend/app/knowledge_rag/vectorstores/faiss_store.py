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

    @staticmethod
    def _matches_where(meta: dict[str, Any], where: dict[str, Any]) -> bool:
        """Evaluate a ChromaDB-style where clause against a metadata dict."""
        if "$and" in where:
            return all(FAISSVectorStore._matches_where(meta, clause) for clause in where["$and"])
        if "$or" in where:
            return any(FAISSVectorStore._matches_where(meta, clause) for clause in where["$or"])
        # Simple field equality ({"field": "value"} or {"field": {"$eq": "value"}})
        for key, val in where.items():
            if key.startswith("$"):
                continue
            if isinstance(val, dict):
                op = list(val.keys())[0]
                v = list(val.values())[0]
                if op == "$eq" and meta.get(key) != v:
                    return False
                if op == "$ne" and meta.get(key) == v:
                    return False
            else:
                if meta.get(key) != val:
                    return False
        return True

    async def similarity_search(
        self,
        query: str,
        k: int = 4,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not self._documents or self._index is None:
            return []
        q_emb = await self._embedding_fn.embed_query(query)
        q_arr = np.array([q_emb], dtype=np.float32)
        fetch_k = min(len(self._documents), k * 4 if where else k)
        _, indices = self._index.search(q_arr, fetch_k)
        results = []
        for idx in indices[0]:
            if 0 <= idx < len(self._documents):
                meta = self._metadatas[idx] if idx < len(self._metadatas) else {}
                if where and not self._matches_where(meta, where):
                    continue
                results.append({"content": self._documents[idx], "metadata": meta})
                if len(results) == k:
                    break
        return results
