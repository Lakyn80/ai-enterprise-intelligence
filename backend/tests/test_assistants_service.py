"""Tests for assistants service orchestration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.assistants.service import (
    list_presets,
    _normalise_citations,
    _generate,
    ask_preset,
    ask_custom,
)
from app.assistants.presets import get_presets


# ---------------------------------------------------------------------------
# list_presets
# ---------------------------------------------------------------------------

def test_list_presets_knowledge_en():
    presets = list_presets("knowledge", "en")
    assert len(presets) == 20
    assert all(p.id.startswith("k_") for p in presets)
    assert all(isinstance(p.text, str) and p.text for p in presets)


def test_list_presets_analyst_en():
    presets = list_presets("analyst", "en")
    assert len(presets) == 20
    assert all(p.id.startswith("a_") for p in presets)


def test_list_presets_locale_cs():
    en_presets = list_presets("knowledge", "en")
    cs_presets = list_presets("knowledge", "cs")
    assert len(cs_presets) == len(en_presets)
    # At least some questions should differ between locales
    assert any(e.text != c.text for e, c in zip(en_presets, cs_presets))


def test_list_presets_locale_sk():
    presets = list_presets("knowledge", "sk")
    assert len(presets) == 20


def test_list_presets_locale_ru():
    presets = list_presets("knowledge", "ru")
    assert len(presets) == 20


def test_list_presets_all_locales_same_ids():
    """IDs must be stable across all locales."""
    ids_en = [p.id for p in list_presets("knowledge", "en")]
    ids_cs = [p.id for p in list_presets("knowledge", "cs")]
    ids_sk = [p.id for p in list_presets("knowledge", "sk")]
    ids_ru = [p.id for p in list_presets("knowledge", "ru")]
    assert ids_en == ids_cs == ids_sk == ids_ru


# ---------------------------------------------------------------------------
# _normalise_citations
# ---------------------------------------------------------------------------

def test_normalise_citations_passes_through_source_key():
    raw = [{"source": "report.txt", "excerpt": "some text"}]
    result = _normalise_citations(raw)
    assert result[0]["source"] == "report.txt"


def test_normalise_citations_maps_document_id_to_source():
    raw = [{"document_id": "product_P001.txt", "chunk": "Total sales: 1,234"}]
    result = _normalise_citations(raw)
    assert result[0]["source"] == "product_P001.txt"
    assert result[0]["excerpt"] == "Total sales: 1,234"


def test_normalise_citations_ignores_non_dicts():
    raw = [{"source": "a"}, "not a dict", 42]
    result = _normalise_citations(raw)
    assert len(result) == 1
    assert result[0]["source"] == "a"


def test_normalise_citations_empty():
    assert _normalise_citations([]) == []


# ---------------------------------------------------------------------------
# _generate — knowledge path (mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_knowledge_calls_knowledge_service():
    with patch("app.assistants.service._call_knowledge", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = ("Great answer", [{"source": "doc.txt"}])
        answer, citations, tools = await _generate("knowledge", "test query", None, None)

    assert answer == "Great answer"
    assert citations == [{"source": "doc.txt"}]
    assert tools == []
    mock_call.assert_called_once_with("test query")


@pytest.mark.asyncio
async def test_generate_analyst_calls_analyst_service():
    with patch("app.assistants.service._call_analyst", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = ("Analyst answer", ["get_forecast"], [])
        answer, citations, tools = await _generate("analyst", "test query", MagicMock(), MagicMock())

    assert answer == "Analyst answer"
    assert tools == ["get_forecast"]
    mock_call.assert_called_once()


@pytest.mark.asyncio
async def test_generate_pushes_to_dlq_on_failure():
    with patch("app.assistants.service._call_knowledge", new_callable=AsyncMock) as mock_call, \
         patch("app.assistants.service.dlq") as mock_dlq:
        mock_call.side_effect = ConnectionError("LLM down")
        mock_dlq.push = AsyncMock()

        with pytest.raises(ConnectionError):
            await _generate("knowledge", "q", None, None, question_id="k_001")

        mock_dlq.push.assert_called_once()
        call_kwargs = mock_dlq.push.call_args[1]
        assert call_kwargs["assistant_type"] == "knowledge"
        assert call_kwargs["question_id"] == "k_001"


@pytest.mark.asyncio
async def test_generate_logs_status_on_success():
    with patch("app.assistants.service._call_knowledge", new_callable=AsyncMock) as mock_call, \
         patch("app.assistants.service._set_status", new_callable=AsyncMock) as mock_status:
        mock_call.return_value = ("ok", [])
        await _generate("knowledge", "q", None, None, question_id="k_005")
        mock_status.assert_called_once()
        args = mock_status.call_args[0]
        assert args[0] == "knowledge"
        assert args[1] == "k_005"
        assert args[2] == "ok"


@pytest.mark.asyncio
async def test_generate_logs_error_status_on_failure():
    with patch("app.assistants.service._call_knowledge", new_callable=AsyncMock) as mock_call, \
         patch("app.assistants.service._set_status", new_callable=AsyncMock) as mock_status, \
         patch("app.assistants.service.dlq") as mock_dlq:
        mock_call.side_effect = RuntimeError("exploded")
        mock_dlq.push = AsyncMock()
        mock_status.return_value = None

        with pytest.raises(RuntimeError):
            await _generate("knowledge", "q", None, None, question_id="k_001")

        mock_status.assert_called_once()
        assert mock_status.call_args[0][2] == "error"


# ---------------------------------------------------------------------------
# ask_preset — cache hit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ask_preset_returns_cached_answer():
    cached_payload = {
        "answer": "cached answer",
        "citations": [{"source": "x.txt"}],
        "used_tools": [],
    }
    with patch("app.assistants.service.assistant_cache") as mock_cache:
        mock_cache.get = AsyncMock(return_value=cached_payload)
        result = await ask_preset("knowledge", "k_001", "en")

    assert result.cached is True
    assert result.answer == "cached answer"
    assert result.question_id == "k_001"


@pytest.mark.asyncio
async def test_ask_preset_generates_and_caches_on_miss():
    with patch("app.assistants.service.assistant_cache") as mock_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        mock_gen.return_value = ("fresh answer", [], [])

        result = await ask_preset("knowledge", "k_001", "cs")

    assert result.cached is False
    assert result.answer == "fresh answer"
    assert result.locale == "cs"
    mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_ask_preset_raises_for_unknown_id():
    with pytest.raises(ValueError, match="Unknown question_id"):
        await ask_preset("knowledge", "k_999", "en")


# ---------------------------------------------------------------------------
# ask_custom
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ask_custom_no_cache():
    with patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        mock_query_cache.get_exact = AsyncMock(return_value=None)
        mock_query_cache.get_semantic = AsyncMock(return_value=None)
        mock_query_cache.set_exact = AsyncMock()
        mock_query_cache.set_semantic = AsyncMock()
        mock_gen.return_value = ("custom answer", [{"source": "s"}], ["tool_x"])
        result = await ask_custom("analyst", "what is revenue?", "sk")

    assert result.cached is False
    assert result.question_id is None
    assert result.answer == "custom answer"
    assert result.locale == "sk"
    assert result.used_tools == ["tool_x"]
    mock_query_cache.set_exact.assert_called_once()
    mock_query_cache.set_semantic.assert_called_once()


@pytest.mark.asyncio
async def test_ask_custom_returns_exact_cached_answer():
    cached_payload = {
        "answer": "cached custom",
        "citations": [{"source": "doc.txt"}],
        "used_tools": ["tool_x"],
    }
    with patch("app.assistants.service.assistant_query_cache") as mock_query_cache:
        mock_query_cache.get_exact = AsyncMock(return_value=cached_payload)

        result = await ask_custom("knowledge", "what is revenue?", "en")

    assert result.cached is True
    assert result.answer == "cached custom"
    assert result.used_tools == ["tool_x"]


@pytest.mark.asyncio
async def test_ask_custom_returns_semantic_cached_answer():
    cached_payload = {
        "answer": "semantic custom",
        "citations": [{"source": "doc.txt"}],
        "used_tools": [],
        "similarity": 0.97,
        "cached_query": "what is revenue?",
    }
    with patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        mock_query_cache.get_exact = AsyncMock(return_value=None)
        mock_query_cache.get_semantic = AsyncMock(return_value=cached_payload)
        mock_query_cache.set_exact = AsyncMock()
        mock_gen.return_value = ("fresh answer", [], [])

        result = await ask_custom("knowledge", "what is revenue?", "en")

    assert result.cached is True
    assert result.answer == "semantic custom"
    mock_gen.assert_not_called()
    mock_query_cache.set_exact.assert_called_once_with(
        "knowledge",
        "what is revenue?",
        "en",
        {
            "answer": "semantic custom",
            "citations": [{"source": "doc.txt"}],
            "used_tools": [],
        },
    )


@pytest.mark.asyncio
async def test_ask_custom_rewrites_mid_similarity_cached_answer():
    cached_payload = {
        "answer": "cached base answer",
        "citations": [{"source": "doc.txt"}],
        "used_tools": ["tool_x"],
        "similarity": 0.62,
        "cached_query": "what is revenue?",
    }
    with patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._call_semantic_rewrite", new_callable=AsyncMock) as mock_rewrite, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen, \
         patch("app.assistants.service.settings.assistants_semantic_cache_reuse_similarity", 0.90), \
         patch("app.assistants.service.settings.assistants_semantic_cache_rewrite_similarity", 0.30):
        mock_query_cache.get_exact = AsyncMock(return_value=None)
        mock_query_cache.get_semantic = AsyncMock(return_value=cached_payload)
        mock_query_cache.set_exact = AsyncMock()
        mock_query_cache.set_semantic = AsyncMock()
        mock_rewrite.return_value = "rewritten answer"

        result = await ask_custom("knowledge", "show me revenue", "en")

    assert result.cached is False
    assert result.answer == "rewritten answer"
    mock_rewrite.assert_awaited_once()
    mock_gen.assert_not_called()
    mock_query_cache.set_exact.assert_called_once()
    mock_query_cache.set_semantic.assert_called_once()
