"""Tests for RAG retrieval and citations."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.knowledge_rag.service import KnowledgeService
from app.settings import settings


@pytest.mark.asyncio
async def test_rag_query_returns_citations():
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
