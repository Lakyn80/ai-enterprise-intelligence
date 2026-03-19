"""
Assistants service — orchestrates: cache → RAG/LLM → cache write.

Knowledge assistant:  answers preset + custom queries via KnowledgeService (RAG).
Analyst assistant:    answers preset + custom queries via the LangGraph agent (tools).
"""

from __future__ import annotations

import logging
from typing import Any

from app.assistants.cache import assistant_cache
from app.assistants.presets import AssistantType, Locale, get_preset_by_id, get_presets
from app.assistants.schemas import AssistantAnswer, Citation, PresetQuestionOut
from app.settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Preset listing
# ---------------------------------------------------------------------------


def list_presets(assistant_type: AssistantType, locale: Locale) -> list[PresetQuestionOut]:
    return [
        PresetQuestionOut(id=p.id, text=p.text(locale))
        for p in get_presets(assistant_type)
    ]


# ---------------------------------------------------------------------------
# Knowledge assistant
# ---------------------------------------------------------------------------


async def _answer_knowledge(query: str) -> tuple[str, list[dict]]:
    """Call KnowledgeService.query() and return (answer, citations)."""
    from app.knowledge_rag.service import KnowledgeService

    svc = KnowledgeService()
    result = await svc.query(query)
    return result.get("answer", ""), result.get("citations", [])


# ---------------------------------------------------------------------------
# Analyst assistant
# ---------------------------------------------------------------------------


async def _answer_analyst(
    query: str,
    forecasting_service: Any,
    forecasting_repo: Any,
) -> tuple[str, list[str], list[dict]]:
    """Run the LangGraph agent and return (answer, used_tools, citations)."""
    from app.ai_assistant.providers.deepseek_provider import DeepSeekProvider
    from app.ai_assistant.graph.agent_graph import run_agent

    provider = DeepSeekProvider()
    knowledge_service = None
    if settings.rag_enabled:
        from app.knowledge_rag.service import KnowledgeService
        knowledge_service = KnowledgeService()

    return await run_agent(
        user_message=query,
        provider=provider,
        forecasting_service=forecasting_service,
        forecasting_repo=forecasting_repo,
        knowledge_service=knowledge_service,
        rag_enabled=settings.rag_enabled,
    )


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


async def ask_preset(
    assistant_type: AssistantType,
    question_id: str,
    locale: Locale,
    forecasting_service: Any = None,
    forecasting_repo: Any = None,
) -> AssistantAnswer:
    preset = get_preset_by_id(assistant_type, question_id)
    if preset is None:
        raise ValueError(f"Unknown question_id '{question_id}' for assistant '{assistant_type}'")

    query_en = preset.query_en

    # 1. Cache check (EN answer, locale-agnostic)
    cached = await assistant_cache.get(assistant_type, question_id)
    if cached:
        logger.debug("Cache HIT %s/%s", assistant_type, question_id)
        return AssistantAnswer(
            question_id=question_id,
            query=preset.text(locale),
            answer=cached["answer"],
            locale=locale,
            cached=True,
            citations=[Citation(**c) for c in cached.get("citations", [])],
            used_tools=cached.get("used_tools", []),
        )

    # 2. Generate answer
    logger.debug("Cache MISS %s/%s — generating", assistant_type, question_id)
    answer, citations_raw, used_tools = await _generate(
        assistant_type, query_en, forecasting_service, forecasting_repo
    )

    # 3. Store in cache
    await assistant_cache.set(
        assistant_type,
        question_id,
        {"answer": answer, "citations": citations_raw, "used_tools": used_tools},
    )

    return AssistantAnswer(
        question_id=question_id,
        query=preset.text(locale),
        answer=answer,
        locale=locale,
        cached=False,
        citations=[Citation(**c) for c in citations_raw],
        used_tools=used_tools,
    )


async def ask_custom(
    assistant_type: AssistantType,
    query: str,
    locale: Locale,
    forecasting_service: Any = None,
    forecasting_repo: Any = None,
) -> AssistantAnswer:
    answer, citations_raw, used_tools = await _generate(
        assistant_type, query, forecasting_service, forecasting_repo
    )
    return AssistantAnswer(
        question_id=None,
        query=query,
        answer=answer,
        locale=locale,
        cached=False,
        citations=[Citation(**c) for c in citations_raw],
        used_tools=used_tools,
    )


# ---------------------------------------------------------------------------
# Internal dispatch
# ---------------------------------------------------------------------------


async def _generate(
    assistant_type: AssistantType,
    query: str,
    forecasting_service: Any,
    forecasting_repo: Any,
) -> tuple[str, list[dict], list[str]]:
    """Return (answer, citations_list, used_tools_list)."""
    if assistant_type == "knowledge":
        answer, citations = await _answer_knowledge(query)
        return answer, _normalise_citations(citations), []
    else:
        answer, used_tools, citations = await _answer_analyst(
            query, forecasting_service, forecasting_repo
        )
        return answer, _normalise_citations(citations), used_tools


def _normalise_citations(raw: list[Any]) -> list[dict]:
    """Ensure every citation is a plain dict with 'source' key."""
    out: list[dict] = []
    for c in raw:
        if isinstance(c, dict):
            if "source" not in c and "document_id" in c:
                c = {"source": c["document_id"], "excerpt": c.get("chunk", "")}
            out.append(c)
    return out
