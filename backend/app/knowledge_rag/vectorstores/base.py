"""Vector store interface for RAG."""

from abc import ABC, abstractmethod
from typing import Any


class VectorStore(ABC):
    """Interface for vector stores (Chroma, FAISS, etc.)."""

    @abstractmethod
    async def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """Add documents and return their IDs."""
        ...

    @abstractmethod
    async def similarity_search(
        self,
        query: str,
        k: int = 4,
    ) -> list[dict[str, Any]]:
        """Search for similar documents. Returns list of {content, metadata}."""
        ...
