"""Tests for RAG retrieval and citations."""

import pytest
from unittest.mock import patch

from app.knowledge_rag.service import KnowledgeService
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
