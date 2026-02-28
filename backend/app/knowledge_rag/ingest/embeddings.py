"""Embedding provider interface and implementations."""

from abc import ABC, abstractmethod
from typing import Any

from app.settings import settings


class EmbeddingProvider(ABC):
    """Interface for embedding models."""

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        ...

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query."""
        ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embeddings API."""

    def __init__(self):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = await self._client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [d.embedding for d in resp.data]

    async def embed_query(self, query: str) -> list[float]:
        resp = await self._client.embeddings.create(
            model="text-embedding-3-small",
            input=[query],
        )
        return resp.data[0].embedding


class StubEmbeddingProvider(EmbeddingProvider):
    """Stub for dev when no API key - returns deterministic pseudo-embeddings."""

    def _stub_embed(self, text: str) -> list[float]:
        """Simple hash-based pseudo-embedding (1536 dim for OpenAI compat)."""
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        return [(b / 255 - 0.5) * 0.01 for b in h[:24]] * 64  # 1536 dims

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._stub_embed(t) for t in texts]

    async def embed_query(self, query: str) -> list[float]:
        return self._stub_embed(query)


def get_embedding_provider() -> EmbeddingProvider:
    """Get embedding provider based on settings."""
    if settings.embeddings_provider == "openai" and settings.openai_api_key:
        return OpenAIEmbeddingProvider()
    return StubEmbeddingProvider()
