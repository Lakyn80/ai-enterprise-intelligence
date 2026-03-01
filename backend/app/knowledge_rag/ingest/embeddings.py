"""Embedding provider - modulární (default: DeepSeek)."""

from abc import ABC, abstractmethod

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


class DeepSeekEmbeddingProvider(EmbeddingProvider):
    """DeepSeek embeddings (default). Fallback na stub pokud API není dostupné."""

    def __init__(self):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url.rstrip("/") + "/v1",
        )
        self._fallback = StubEmbeddingProvider()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            resp = await self._client.embeddings.create(
                model="deepseek-embedding",
                input=texts,
            )
            return [d.embedding for d in resp.data]
        except Exception:
            return await self._fallback.embed_documents(texts)

    async def embed_query(self, query: str) -> list[float]:
        try:
            resp = await self._client.embeddings.create(
                model="deepseek-embedding",
                input=[query],
            )
            return resp.data[0].embedding
        except Exception:
            return await self._fallback.embed_query(query)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embeddings (volitelné)."""

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
    """Lokální stub (default)."""

    def _stub_embed(self, text: str) -> list[float]:
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        return [(b / 255 - 0.5) * 0.01 for b in h[:32]] * 32  # 1024 dims (DeepSeek compat)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._stub_embed(t) for t in texts]

    async def embed_query(self, query: str) -> list[float]:
        return self._stub_embed(query)


def get_embedding_provider() -> EmbeddingProvider:
    """Embeddings pro RAG (modulární: deepseek default, openai, stub)."""
    if settings.embeddings_provider == "openai" and settings.openai_api_key:
        return OpenAIEmbeddingProvider()
    if settings.deepseek_api_key:
        return DeepSeekEmbeddingProvider()
    return StubEmbeddingProvider()
