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
from app.assistants.trace_recorder import AssistantTraceRecorder


class FakeAnalyticalRepo:
    async def get_sales_dataset_signature(self):
        return {
            "row_count": 4,
            "quantity_sum": 62.0,
            "revenue_sum": 460.0,
            "price_sum": 189.8,
            "promo_row_count": 2,
            "promo_quantity_sum": 29.0,
            "date_from": "2022-01-01",
            "date_to": "2024-01-01",
        }

    async def get_date_range(self):
        return "2022-01-01", "2024-01-01"

    async def get_product_ranked_list(self, *, metric, direction, limit=5):
        assert metric in {"quantity", "revenue"}
        assert direction == "desc"
        assert limit == 5
        if metric == "revenue":
            return [
                {"product_id": "P0100", "value": 2550.25},
                {"product_id": "P0101", "value": 2440.10},
                {"product_id": "P0102", "value": 2330.75},
                {"product_id": "P0103", "value": 2220.50},
                {"product_id": "P0104", "value": 2110.00},
            ]
        return [
            {"product_id": "P0001", "value": 25.0},
            {"product_id": "P0002", "value": 24.0},
            {"product_id": "P0003", "value": 23.0},
            {"product_id": "P0004", "value": 22.0},
            {"product_id": "P0005", "value": 21.0},
        ]

    async def get_product_rank_winners(self, *, metric, direction, filters, date_range, limit):
        assert direction in {"desc", "asc"}
        assert filters == {}
        assert date_range is None
        assert limit == 1
        winners = {
            ("quantity", "desc"): [{"product_id": "P0001", "value": 25.0}],
            ("quantity", "asc"): [{"product_id": "P0005", "value": 1.0}],
            ("revenue", "desc"): [{"product_id": "P0100", "value": 2550.25}],
            ("revenue", "asc"): [{"product_id": "P0104", "value": 110.0}],
            ("promo_lift", "desc"): [{"product_id": "P0002", "value": 13.9}],
            ("avg_price", "desc"): [{"product_id": "P0003", "value": 99.9}],
        }
        return winners[(metric, direction)]


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


def test_find_preset_by_exact_localized_text():
    from app.assistants.presets import find_preset_by_text

    preset = find_preset_by_text("knowledge", "Který produkt nejvíce těží z akcí?", "cs")

    assert preset is not None
    assert preset.id == "k_005"


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
    mock_call.assert_called_once_with("test query", trace=None)


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
    with patch("app.assistants.service.assistant_cache") as mock_cache, \
         patch("app.assistants.service.deterministic_facts_service") as mock_facts_service:
        mock_facts_service.try_answer = AsyncMock(return_value=None)
        mock_cache.get = AsyncMock(return_value=cached_payload)
        result = await ask_preset("knowledge", "k_001", "en")

    assert result.cached is True
    assert result.answer == "cached answer"
    assert result.question_id == "k_001"


@pytest.mark.asyncio
async def test_ask_preset_generates_and_caches_on_miss():
    with patch("app.assistants.service.assistant_cache") as mock_cache, \
         patch("app.assistants.service.deterministic_date_range_service") as mock_date_range_service, \
         patch("app.assistants.service.deterministic_facts_service") as mock_facts_service, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        mock_date_range_service.try_answer = AsyncMock(return_value=None)
        mock_facts_service.try_answer = AsyncMock(return_value=None)
        mock_gen.return_value = ("fresh answer", [], [])

        result = await ask_preset("knowledge", "k_001", "cs")

    assert result.cached is False
    assert result.answer == "fresh answer"
    assert result.locale == "cs"
    mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_ask_preset_uses_deterministic_facts_before_llm():
    deterministic_answer = MagicMock(
        cached=False,
        answer="Produkt, který nejvíce těží z akcí, je P0001 (+12.9%).",
        citations=[],
        used_tools=[],
    )
    with patch("app.assistants.service.assistant_cache") as mock_cache, \
         patch("app.assistants.service.deterministic_date_range_service") as mock_date_range_service, \
         patch("app.assistants.service.deterministic_facts_service") as mock_facts_service, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        mock_date_range_service.try_answer = AsyncMock(return_value=None)
        mock_facts_service.try_answer = AsyncMock(return_value=deterministic_answer)

        result = await ask_preset("knowledge", "k_005", "cs")

    assert result.answer == "Produkt, který nejvíce těží z akcí, je P0001 (+12.9%)."
    assert result.question_id == "k_005"
    mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_ask_preset_raises_for_unknown_id():
    with pytest.raises(ValueError, match="Unknown question_id"):
        await ask_preset("knowledge", "k_999", "en")


# ---------------------------------------------------------------------------
# ask_custom
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ask_custom_no_cache():
    with patch("app.assistants.service.deterministic_date_range_service") as mock_date_range_service, \
         patch("app.assistants.service.deterministic_facts_service") as mock_facts_service, \
         patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        mock_date_range_service.try_answer = AsyncMock(return_value=None)
        mock_facts_service.try_answer = AsyncMock(return_value=None)
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
    with patch("app.assistants.service.deterministic_date_range_service") as mock_date_range_service, \
         patch("app.assistants.service.deterministic_facts_service") as mock_facts_service, \
         patch("app.assistants.service.assistant_query_cache") as mock_query_cache:
        mock_date_range_service.try_answer = AsyncMock(return_value=None)
        mock_facts_service.try_answer = AsyncMock(return_value=None)
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
    with patch("app.assistants.service.deterministic_date_range_service") as mock_date_range_service, \
         patch("app.assistants.service.deterministic_facts_service") as mock_facts_service, \
         patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        mock_date_range_service.try_answer = AsyncMock(return_value=None)
        mock_facts_service.try_answer = AsyncMock(return_value=None)
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
    with patch("app.assistants.service.deterministic_date_range_service") as mock_date_range_service, \
         patch("app.assistants.service.deterministic_facts_service") as mock_facts_service, \
         patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._call_semantic_rewrite", new_callable=AsyncMock) as mock_rewrite, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen, \
         patch("app.assistants.service.settings.assistants_semantic_cache_reuse_similarity", 0.90), \
         patch("app.assistants.service.settings.assistants_semantic_cache_rewrite_similarity", 0.30), \
         patch("app.assistants.service.settings.assistants_semantic_cache_rewrite_enabled", True):
        mock_date_range_service.try_answer = AsyncMock(return_value=None)
        mock_facts_service.try_answer = AsyncMock(return_value=None)
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


@pytest.mark.asyncio
async def test_ask_custom_regenerates_when_rewrite_is_disabled():
    cached_payload = {
        "answer": "cached base answer",
        "citations": [{"source": "doc.txt"}],
        "used_tools": ["tool_x"],
        "similarity": 0.62,
        "cached_query": "what is revenue?",
    }
    with patch("app.assistants.service.deterministic_date_range_service") as mock_date_range_service, \
         patch("app.assistants.service.deterministic_facts_service") as mock_facts_service, \
         patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._call_semantic_rewrite", new_callable=AsyncMock) as mock_rewrite, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen, \
         patch("app.assistants.service.settings.assistants_semantic_cache_reuse_similarity", 0.90), \
         patch("app.assistants.service.settings.assistants_semantic_cache_rewrite_similarity", 0.30), \
         patch("app.assistants.service.settings.assistants_semantic_cache_rewrite_enabled", False):
        mock_date_range_service.try_answer = AsyncMock(return_value=None)
        mock_facts_service.try_answer = AsyncMock(return_value=None)
        mock_query_cache.get_exact = AsyncMock(return_value=None)
        mock_query_cache.get_semantic = AsyncMock(return_value=cached_payload)
        mock_query_cache.set_exact = AsyncMock()
        mock_query_cache.set_semantic = AsyncMock()
        mock_gen.return_value = ("fresh answer", [{"source": "new.txt"}], ["tool_y"])

        result = await ask_custom("knowledge", "show me revenue", "en")

    assert result.cached is False
    assert result.answer == "fresh answer"
    mock_rewrite.assert_not_called()
    mock_gen.assert_awaited_once()


@pytest.mark.asyncio
async def test_ask_custom_returns_deterministic_facts_answer_before_free_text_cache():
    deterministic_answer = MagicMock(
        cached=True,
        answer="Nejprodávanější produkt podle počtu kusů je P0001 (25 ks).",
    )
    with patch("app.assistants.service.deterministic_date_range_service") as mock_date_range_service, \
         patch("app.assistants.service.deterministic_facts_service") as mock_facts_service, \
         patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        mock_date_range_service.try_answer = AsyncMock(return_value=None)
        mock_facts_service.try_answer = AsyncMock(return_value=deterministic_answer)

        result = await ask_custom("knowledge", "Který produkt se prodává nejvíc?", "cs")

    assert result is deterministic_answer
    mock_query_cache.get_exact.assert_not_called()
    mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_ask_custom_routes_promo_lift_paraphrase_to_same_deterministic_answer():
    exact_trace = AssistantTraceRecorder(
        assistant_type="knowledge",
        request_kind="custom",
        locale="cs",
        user_query="Který produkt nejvíce těží z akcí?",
    )
    paraphrase_trace = AssistantTraceRecorder(
        assistant_type="knowledge",
        request_kind="custom",
        locale="cs",
        user_query="co nejvíce těží z akcí?",
    )

    with patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        exact = await ask_custom(
            "knowledge",
            "Který produkt nejvíce těží z akcí?",
            "cs",
            forecasting_repo=FakeAnalyticalRepo(),
            trace=exact_trace,
        )
        paraphrase = await ask_custom(
            "knowledge",
            "co nejvíce těží z akcí?",
            "cs",
            forecasting_repo=FakeAnalyticalRepo(),
            trace=paraphrase_trace,
        )

    assert exact.answer == "Produkt, který nejvíce těží z akcí, je P0002 (+13.9%)."
    assert paraphrase.answer == exact.answer
    assert any(step.step_name == "analytical_query_detected" for step in paraphrase_trace.steps)
    assert any(step.step_name == "canonical_intent_matched" for step in paraphrase_trace.steps)
    assert any(step.step_name == "deterministic_intent_selected" for step in paraphrase_trace.steps)
    mock_query_cache.get_exact.assert_not_called()
    mock_query_cache.get_semantic.assert_not_called()
    mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_ask_custom_routes_exact_preset_text_to_preset_cache():
    cached_payload = {
        "answer": "cached preset",
        "citations": [{"source": "preset.txt"}],
        "used_tools": [],
    }
    with patch("app.assistants.service.assistant_cache") as mock_cache, \
         patch("app.assistants.service.deterministic_date_range_service") as mock_date_range_service, \
         patch("app.assistants.service.deterministic_facts_service") as mock_facts_service, \
         patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        mock_cache.get = AsyncMock(return_value=cached_payload)
        mock_date_range_service.try_answer = AsyncMock(return_value=None)
        mock_facts_service.try_answer = AsyncMock(return_value=None)

        result = await ask_custom("knowledge", "Který produkt nejvíce těží z akcí?", "cs")

    assert result.cached is True
    assert result.answer == "cached preset"
    assert result.question_id == "k_005"
    mock_query_cache.get_exact.assert_not_called()
    mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_ask_custom_returns_date_range_answer_before_free_text_cache():
    date_range_answer = MagicMock(
        cached=False,
        answer="Prodejní data pokrývají období od 2022-01-01 do 2024-01-01.",
    )
    with patch("app.assistants.service.deterministic_date_range_service") as mock_date_range_service, \
         patch("app.assistants.service.deterministic_facts_service") as mock_facts_service, \
         patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        mock_date_range_service.try_answer = AsyncMock(return_value=date_range_answer)
        mock_facts_service.try_answer = AsyncMock(return_value=None)

        result = await ask_custom("knowledge", "v jakém časovém rozmezí jsou prodejní data?", "cs")

    assert result is date_range_answer
    mock_facts_service.try_answer.assert_not_called()
    mock_query_cache.get_exact.assert_not_called()
    mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_ask_custom_routes_odkdy_dokdy_paraphrase_to_deterministic_date_range():
    trace = AssistantTraceRecorder(
        assistant_type="knowledge",
        request_kind="custom",
        locale="cs",
        user_query="odkdy dokdy jsou prodejní data v tomto reportu?",
    )

    with patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.date_range_service._get_cache", new_callable=AsyncMock) as mock_get_cache, \
         patch("app.assistants.date_range_service._set_cache", new_callable=AsyncMock), \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        mock_get_cache.return_value = None
        result = await ask_custom(
            "knowledge",
            "odkdy dokdy jsou prodejní data v tomto reportu?",
            "cs",
            forecasting_repo=FakeAnalyticalRepo(),
            trace=trace,
        )

    assert result.response_type == "answer"
    assert result.answer == "Prodejní data pokrývají období od 2022-01-01 do 2024-01-01."
    assert any(step.step_name == "analytical_query_detected" for step in trace.steps)
    assert any(step.step_name == "canonical_intent_matched" for step in trace.steps)
    assert any(step.step_name == "deterministic_intent_selected" for step in trace.steps)
    assert trace.cache_source == "deterministic_date_range_resolver"
    mock_query_cache.get_exact.assert_not_called()
    mock_query_cache.get_semantic.assert_not_called()
    mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_ask_custom_returns_entity_clarification_for_analytical_query_without_entity():
    trace = AssistantTraceRecorder(
        assistant_type="knowledge",
        request_kind="custom",
        locale="cs",
        user_query="Co má nejvyšší tržby?",
    )

    with patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        result = await ask_custom(
            "knowledge",
            "Co má nejvyšší tržby?",
            "cs",
            forecasting_repo=FakeAnalyticalRepo(),
            trace=trace,
        )

    assert result.response_type == "clarification"
    assert result.clarification is not None
    assert result.clarification.missing == ["entity"]
    assert "produkt, kategorii" in result.answer
    assert any(step.step_name == "analytical_query_detected" for step in trace.steps)
    assert any(step.step_name == "analytical_fallback_blocked" for step in trace.steps)
    assert any(step.step_name == "clarification_returned" for step in trace.steps)
    mock_query_cache.get_exact.assert_not_called()
    mock_query_cache.get_semantic.assert_not_called()
    mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_ask_custom_returns_clarification_before_cache_and_llm():
    trace = AssistantTraceRecorder(
        assistant_type="knowledge",
        request_kind="custom",
        locale="cs",
        user_query="jaké produkty maji nejvyšší prodej?",
    )

    with patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen:
        result = await ask_custom(
            "knowledge",
            "jaké produkty maji nejvyšší prodej?",
            "cs",
            forecasting_repo=FakeAnalyticalRepo(),
            trace=trace,
        )

    assert result.response_type == "clarification"
    assert result.clarification is not None
    assert result.clarification.missing == ["metric"]
    assert "počtu kusů" in result.answer
    assert any(step.step_name == "canonical_intent_matched" for step in trace.steps)
    assert any(step.step_name == "ambiguity_detected" for step in trace.steps)
    assert any(step.step_name == "clarification_returned" for step in trace.steps)
    mock_query_cache.get_exact.assert_not_called()
    mock_query_cache.get_semantic.assert_not_called()
    mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_ask_custom_routes_total_sales_paraphrase_to_deterministic_list():
    trace = AssistantTraceRecorder(
        assistant_type="knowledge",
        request_kind="custom",
        locale="cs",
        user_query="Jaké produkty mají nejvyšší celkové prodeje?",
    )

    with patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen, \
         patch("app.assistants.service._get_deterministic_intent_cache", new_callable=AsyncMock) as mock_get_cache, \
         patch("app.assistants.service._set_deterministic_intent_cache", new_callable=AsyncMock) as mock_set_cache:
        mock_get_cache.return_value = None
        result = await ask_custom(
            "knowledge",
            "Jaké produkty mají nejvyšší celkové prodeje?",
            "cs",
            forecasting_repo=FakeAnalyticalRepo(),
            trace=trace,
        )

    assert result.response_type == "answer"
    assert result.answer.startswith("Produkty s nejvyššími celkovými prodeji jsou:")
    assert "1. Produkt P0001: 25 ks" in result.answer
    assert any(step.step_name == "canonical_intent_matched" for step in trace.steps)
    assert any(step.step_name == "deterministic_list_intent_selected" for step in trace.steps)
    mock_query_cache.get_exact.assert_not_called()
    mock_query_cache.get_semantic.assert_not_called()
    mock_gen.assert_not_called()
    mock_set_cache.assert_awaited_once()


@pytest.mark.asyncio
async def test_ask_custom_routes_revenue_list_query_to_deterministic_list():
    with patch("app.assistants.service.assistant_query_cache") as mock_query_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen, \
         patch("app.assistants.service._get_deterministic_intent_cache", new_callable=AsyncMock) as mock_get_cache, \
         patch("app.assistants.service._set_deterministic_intent_cache", new_callable=AsyncMock):
        mock_get_cache.return_value = None
        result = await ask_custom(
            "knowledge",
            "Jaké produkty mají nejvyšší tržby?",
            "cs",
            forecasting_repo=FakeAnalyticalRepo(),
        )

    assert result.response_type == "answer"
    assert result.answer.startswith("Produkty s nejvyššími tržbami jsou:")
    assert "1. Produkt P0100: 2550.25" in result.answer
    mock_query_cache.get_exact.assert_not_called()
    mock_query_cache.get_semantic.assert_not_called()
    mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_ask_preset_routes_k001_to_deterministic_list_before_llm():
    with patch("app.assistants.service.assistant_cache") as mock_cache, \
         patch("app.assistants.service._generate", new_callable=AsyncMock) as mock_gen, \
         patch("app.assistants.service._get_deterministic_intent_cache", new_callable=AsyncMock) as mock_get_cache, \
         patch("app.assistants.service._set_deterministic_intent_cache", new_callable=AsyncMock):
        mock_cache.set = AsyncMock()
        mock_get_cache.return_value = None

        result = await ask_preset(
            "knowledge",
            "k_001",
            "cs",
            forecasting_repo=FakeAnalyticalRepo(),
        )

    assert result.answer.startswith("Produkty s nejvyššími celkovými prodeji jsou:")
    assert result.question_id == "k_001"
    mock_cache.set.assert_called_once()
    mock_gen.assert_not_called()
