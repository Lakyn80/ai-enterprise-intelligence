"""
Assistants service — orchestrates: idempotency → cache → RAG/LLM → cache write.

Retry + backoff wraps only external I/O (LLM provider, vector store).
Failed requests (all retries exhausted) are pushed to DLQ.
Status of every preset question is tracked in Redis.
"""

from __future__ import annotations

import logging
import json
import time
from typing import Any

from app.assistants.cache import assistant_cache
from app.assistants.dlq import dlq
from app.assistants.query_cache import assistant_query_cache
from app.assistants.presets import AssistantType, Locale, get_preset_by_id, get_presets
from app.assistants.retry import build_retry
from app.assistants.schemas import AssistantAnswer, Citation, PresetQuestionOut
from app.assistants.semantic_policy import decide_semantic_cache_strategy
from app.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status tracking helpers (Redis key: assistants:status:{type}:{id})
# ---------------------------------------------------------------------------

from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _set_status(
    assistant_type: str,
    question_id: str,
    status: str,
    latency_ms: int = 0,
    error: str | None = None,
) -> None:
    try:
        client = await assistant_cache._get_client()
        if client is None:
            return
        key = f"assistants:status:{assistant_type}:{question_id}"
        payload = {
            "status": status,
            "latency_ms": latency_ms,
            "last_updated": _now_iso(),
            "error": error,
        }
        await client.set(key, json.dumps(payload), ex=60 * 60 * 48)  # 48h
    except Exception as exc:
        logger.warning("Status write failed: %s", exc)


async def get_all_statuses(assistant_type: AssistantType) -> list[dict]:
    """Return status for all preset questions of an assistant type."""
    try:
        client = await assistant_cache._get_client()
        if client is None:
            return []
        pattern = f"assistants:status:{assistant_type}:*"
        keys = await client.keys(pattern)
        if not keys:
            return []
        values = await client.mget(*keys)
        result = []
        for key, raw in zip(keys, values):
            question_id = key.split(":")[-1]
            entry = {"question_id": question_id}
            if raw:
                entry.update(json.loads(raw))
            result.append(entry)
        return sorted(result, key=lambda x: x["question_id"])
    except Exception as exc:
        logger.warning("Status read failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Preset listing
# ---------------------------------------------------------------------------


def list_presets(assistant_type: AssistantType, locale: Locale) -> list[PresetQuestionOut]:
    return [
        PresetQuestionOut(id=p.id, text=p.text(locale))
        for p in get_presets(assistant_type)
    ]


# ---------------------------------------------------------------------------
# External call wrappers — retry lives ONLY here
# ---------------------------------------------------------------------------


async def _call_knowledge(query: str) -> tuple[str, list[dict]]:
    """RAG query with retry. Raises on final failure."""
    from app.knowledge_rag.service import KnowledgeService
    svc = KnowledgeService()

    async for attempt in build_retry():
        with attempt:
            result = await svc.query(query)

    return result.get("answer", ""), result.get("citations", [])


async def _call_analyst(
    query: str,
    forecasting_service: Any,
    forecasting_repo: Any,
) -> tuple[str, list[str], list[dict]]:
    """LangGraph agent call with retry. Raises on final failure."""
    from app.ai_assistant.providers.deepseek_provider import DeepSeekProvider
    from app.ai_assistant.graph.agent_graph import run_agent

    provider = DeepSeekProvider()
    knowledge_service = None
    if settings.rag_enabled:
        from app.knowledge_rag.service import KnowledgeService
        knowledge_service = KnowledgeService()

    async for attempt in build_retry():
        with attempt:
            result = await run_agent(
                user_message=query,
                provider=provider,
                forecasting_service=forecasting_service,
                forecasting_repo=forecasting_repo,
                knowledge_service=knowledge_service,
                rag_enabled=settings.rag_enabled,
            )

    return result  # (answer, used_tools, citations)


async def _call_semantic_rewrite(
    assistant_type: AssistantType,
    query: str,
    cached_query: str,
    cached_payload: dict[str, Any],
) -> str | None:
    """Cheap LLM adaptation using the nearest cached answer as context."""
    from app.ai_assistant.providers.deepseek_provider import DeepSeekProvider

    provider = DeepSeekProvider()
    citations_json = json.dumps(cached_payload.get("citations", []), ensure_ascii=False)
    used_tools_json = json.dumps(cached_payload.get("used_tools", []), ensure_ascii=False)

    async for attempt in build_retry():
        with attempt:
            result = await provider.generate([
                {
                    "role": "system",
                    "content": (
                        "You adapt a cached assistant answer to a new, similar user question. "
                        "Use only the information present in the cached answer, citations, and tool list. "
                        "If the cached answer is not sufficient to answer the new question safely, "
                        "reply with exactly __CACHE_MISS__. "
                        "Keep the final answer in the same language as the new user question. "
                        "Do not invent numbers, entities, tools, or facts."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Assistant type: {assistant_type}\n"
                        f"New question: {query}\n"
                        f"Nearest cached question: {cached_query}\n"
                        f"Cached answer:\n{cached_payload.get('answer', '')}\n\n"
                        f"Citations JSON: {citations_json}\n"
                        f"Used tools JSON: {used_tools_json}\n\n"
                        "Return only the final answer text or __CACHE_MISS__."
                    ),
                },
            ])

    answer = (result.get("content") or "").strip()
    if not answer or answer == "__CACHE_MISS__":
        return None
    return answer


# ---------------------------------------------------------------------------
# Internal dispatch — logging, DLQ on failure
# ---------------------------------------------------------------------------


async def _generate(
    assistant_type: AssistantType,
    query: str,
    forecasting_service: Any,
    forecasting_repo: Any,
    question_id: str | None = None,
) -> tuple[str, list[dict], list[str]]:
    """
    Returns (answer, citations, used_tools).
    On final failure: pushes to DLQ, re-raises.
    """
    t0 = time.monotonic()
    try:
        if assistant_type == "knowledge":
            answer, citations = await _call_knowledge(query)
            used_tools: list[str] = []
        else:
            answer, used_tools, citations = await _call_analyst(
                query, forecasting_service, forecasting_repo
            )

        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "assistants | type=%s qid=%s status=ok latency_ms=%d tools=%s",
            assistant_type, question_id or "custom", latency_ms,
            ",".join(used_tools) if used_tools else "-",
        )
        if question_id:
            await _set_status(assistant_type, question_id, "ok", latency_ms)

        return answer, _normalise_citations(citations), used_tools

    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.error(
            "assistants | type=%s qid=%s status=error latency_ms=%d error=%s",
            assistant_type, question_id or "custom", latency_ms, exc,
        )
        if question_id:
            await _set_status(assistant_type, question_id, "error",
                              latency_ms, error=str(exc)[:200])
        await dlq.push(
            assistant_type=assistant_type,
            query=query,
            error=str(exc),
            attempts=3,
            question_id=question_id,
        )
        raise


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

    # 1. Cache check (locale-aware)
    cached = await assistant_cache.get(assistant_type, question_id, locale)
    if cached:
        logger.info(
            "assistants | type=%s qid=%s locale=%s status=cache_hit",
            assistant_type, question_id, locale,
        )
        return AssistantAnswer(
            question_id=question_id,
            query=preset.text(locale),
            answer=cached["answer"],
            locale=locale,
            cached=True,
            citations=[Citation(**c) for c in _normalise_citations(cached.get("citations", []))],
            used_tools=cached.get("used_tools", []),
        )

    # 2. Generate (with retry inside _generate)
    answer, citations_raw, used_tools = await _generate(
        assistant_type, query_en, forecasting_service, forecasting_repo, question_id
    )

    # 3. Store in cache (locale-aware)
    await assistant_cache.set(
        assistant_type,
        question_id,
        {"answer": answer, "citations": citations_raw, "used_tools": used_tools},
        locale=locale,
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
    exact_cached = await assistant_query_cache.get_exact(assistant_type, query, locale)
    if exact_cached:
        logger.info(
            "assistants | type=%s locale=%s status=custom_exact_cache_hit",
            assistant_type, locale,
        )
        return AssistantAnswer(
            question_id=None,
            query=query,
            answer=exact_cached["answer"],
            locale=locale,
            cached=True,
            citations=[Citation(**c) for c in _normalise_citations(exact_cached.get("citations", []))],
            used_tools=exact_cached.get("used_tools", []),
        )

    semantic_cached = await assistant_query_cache.get_semantic(assistant_type, query, locale)
    if semantic_cached:
        cached_payload = _cache_payload_from_entry(semantic_cached)
        decision = decide_semantic_cache_strategy(
            similarity=float(semantic_cached.get("similarity", 0.0)),
            reuse_similarity=settings.assistants_semantic_cache_reuse_similarity,
            rewrite_similarity=settings.assistants_semantic_cache_rewrite_similarity,
        )

        if decision.strategy == "reuse":
            logger.info(
                "assistants | type=%s locale=%s status=custom_semantic_cache_hit similarity=%.3f",
                assistant_type, locale, decision.similarity,
            )
            await assistant_query_cache.set_exact(assistant_type, query, locale, cached_payload)
            return _build_custom_answer(query, locale, cached_payload, cached=True)

        if decision.strategy == "rewrite":
            logger.info(
                "assistants | type=%s locale=%s status=custom_semantic_rewrite similarity=%.3f",
                assistant_type, locale, decision.similarity,
            )
            rewritten_answer = await _call_semantic_rewrite(
                assistant_type=assistant_type,
                query=query,
                cached_query=str(semantic_cached.get("cached_query", "")),
                cached_payload=cached_payload,
            )
            if rewritten_answer:
                payload = _cache_payload(
                    answer=rewritten_answer,
                    citations=cached_payload.get("citations", []),
                    used_tools=cached_payload.get("used_tools", []),
                )
                await assistant_query_cache.set_exact(assistant_type, query, locale, payload)
                await assistant_query_cache.set_semantic(assistant_type, query, locale, payload)
                return _build_custom_answer(query, locale, payload, cached=False)

        logger.info(
            "assistants | type=%s locale=%s status=custom_semantic_miss similarity=%.3f",
            assistant_type,
            locale,
            decision.similarity,
        )

    answer, citations_raw, used_tools = await _generate(
        assistant_type, query, forecasting_service, forecasting_repo
    )
    payload = _cache_payload(answer=answer, citations=citations_raw, used_tools=used_tools)
    await assistant_query_cache.set_exact(assistant_type, query, locale, payload)
    await assistant_query_cache.set_semantic(assistant_type, query, locale, payload)
    return _build_custom_answer(query, locale, payload, cached=False)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalise_citations(raw: list[Any]) -> list[dict]:
    out: list[dict] = []
    for c in raw:
        if isinstance(c, dict):
            if "source" not in c and "document_id" in c:
                c = {"source": c["document_id"], "excerpt": c.get("chunk", "")}
            out.append(c)
    return out


def _cache_payload(answer: str, citations: list[dict], used_tools: list[str]) -> dict[str, Any]:
    return {
        "answer": answer,
        "citations": citations,
        "used_tools": used_tools,
    }


def _cache_payload_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return _cache_payload(
        answer=entry.get("answer", ""),
        citations=_normalise_citations(entry.get("citations", [])),
        used_tools=entry.get("used_tools", []),
    )


def _build_custom_answer(
    query: str,
    locale: Locale,
    payload: dict[str, Any],
    cached: bool,
) -> AssistantAnswer:
    return AssistantAnswer(
        question_id=None,
        query=query,
        answer=payload["answer"],
        locale=locale,
        cached=cached,
        citations=[Citation(**c) for c in _normalise_citations(payload.get("citations", []))],
        used_tools=payload.get("used_tools", []),
    )
