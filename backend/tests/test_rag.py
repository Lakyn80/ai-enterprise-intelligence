"""Tests for RAG retrieval and citations."""

import pytest
from unittest.mock import patch

from app.knowledge_rag.service import KnowledgeService, create_vector_store
from app.knowledge_rag.ingest.embeddings import StubEmbeddingProvider


@pytest.mark.asyncio
@patch("app.knowledge_rag.service.get_embedding_provider", return_value=StubEmbeddingProvider())
async def test_rag_query_returns_citations(_mock):
    """When RAG is disabled or empty, still returns expected structure."""
    service = KnowledgeService()
    if not service._store:
        result = await service.query("test query")
        assert "answer" in result
        assert "citations" in result
        assert isinstance(result["citations"], list)
        return
    result = await service.query("test query")
    assert "answer" in result
    assert "citations" in result
    assert isinstance(result["citations"], list)


@patch("app.knowledge_rag.service.get_embedding_provider", return_value=StubEmbeddingProvider())
def test_create_vector_store_selects_qdrant(_mock):
    with patch("app.knowledge_rag.service.settings.rag_enabled", True), \
         patch("app.knowledge_rag.service.settings.vectorstore", "qdrant"):
        store = create_vector_store()
    assert store.__class__.__name__ == "QdrantVectorStore"


@patch("app.knowledge_rag.service.get_embedding_provider", return_value=StubEmbeddingProvider())
def test_create_vector_store_selects_chroma(_mock):
    with patch("app.knowledge_rag.service.settings.rag_enabled", True), \
         patch("app.knowledge_rag.service.settings.vectorstore", "chroma"):
        store = create_vector_store()
    assert store.__class__.__name__ == "ChromaVectorStore"
