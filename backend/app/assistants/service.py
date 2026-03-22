"""
Assistants service — orchestrates: idempotency → cache → RAG/LLM → cache write.

Retry + backoff wraps only external I/O (LLM provider, vector store).
Failed requests (all retries exhausted) are pushed to DLQ.
Status of every preset question is tracked in Redis.
"""

from __future__ import annotations

import logging
import json
import hashlib
import time
from typing import TYPE_CHECKING, Any

from app.assistants.ambiguity_detector import detect_analytical_ambiguity
from app.assistants.cache import assistant_cache
from app.assistants.clarification_service import (
    build_analytical_guard_clarification,
    build_clarification,
    localize_clarification_message,
)
from app.assistants.date_range_service import deterministic_date_range_service
from app.assistants.dlq import dlq
from app.assistants.facts.service import deterministic_facts_service
from app.assistants.intent_mapper import detect_analytical_guard, map_analytical_intent
from app.assistants.query_cache import assistant_query_cache
from app.assistants.presets import AssistantType, Locale, find_preset_by_text, get_preset_by_id, get_presets
from app.assistants.retry import build_retry
from app.assistants.schemas import AssistantAnswer, Citation, PresetQuestionOut
from app.assistants.semantic_policy import decide_semantic_cache_strategy
from app.settings import settings

if TYPE_CHECKING:
    from app.assistants.trace_recorder import AssistantTraceRecorder

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


async def _call_knowledge(
    query: str,
    trace: "AssistantTraceRecorder | None" = None,
) -> tuple[str, list[dict]]:
    """RAG query with retry. Raises on final failure."""
    from app.knowledge_rag.service import KnowledgeService
    svc = KnowledgeService()

    async for attempt in build_retry():
        with attempt:
            result = await svc.query(query, trace=trace)

    return result.get("answer", ""), result.get("citations", [])


async def _call_analyst(
    query: str,
    forecasting_service: Any,
    forecasting_repo: Any,
    trace: "AssistantTraceRecorder | None" = None,
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
                trace=trace,
            )

    return result  # (answer, used_tools, citations)


async def _call_semantic_rewrite(
    assistant_type: AssistantType,
    query: str,
    cached_query: str,
    cached_payload: dict[str, Any],
    trace: "AssistantTraceRecorder | None" = None,
) -> str | None:
    """Cheap LLM adaptation using the nearest cached answer as context."""
    from app.ai_assistant.providers.deepseek_provider import DeepSeekProvider

    provider = DeepSeekProvider()
    citations_json = json.dumps(cached_payload.get("citations", []), ensure_ascii=False)
    used_tools_json = json.dumps(cached_payload.get("used_tools", []), ensure_ascii=False)

    async for attempt in build_retry():
        with attempt:
            messages = [
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
            ]
            if trace:
                trace.add_step(
                    "semantic_rewrite_request",
                    {"messages": messages},
                )
            result = await provider.generate(messages)

    answer = (result.get("content") or "").strip()
    if trace:
        trace.add_step(
            "semantic_rewrite_response",
            {"content": answer, "tool_calls": result.get("tool_calls", [])},
        )
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
    trace: "AssistantTraceRecorder | None" = None,
) -> tuple[str, list[dict], list[str]]:
    """
    Returns (answer, citations, used_tools).
    On final failure: pushes to DLQ, re-raises.
    """
    t0 = time.monotonic()
    try:
        if trace:
            trace.add_step(
                "generation_dispatch",
                {
                    "assistant_type": assistant_type,
                    "question_id": question_id,
                    "query": query,
                },
            )
        if assistant_type == "knowledge":
            answer, citations = await _call_knowledge(query, trace=trace)
            used_tools: list[str] = []
        else:
            answer, used_tools, citations = await _call_analyst(
                query, forecasting_service, forecasting_repo, trace=trace
            )

        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "assistants | type=%s qid=%s status=ok latency_ms=%d tools=%s",
            assistant_type, question_id or "custom", latency_ms,
            ",".join(used_tools) if used_tools else "-",
        )
        if question_id:
            await _set_status(assistant_type, question_id, "ok", latency_ms)
        if trace:
            trace.add_step(
                "generation_complete",
                {
                    "answer": answer,
                    "citations": citations,
                    "used_tools": used_tools,
                },
                latency_ms=latency_ms,
            )

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
        if trace:
            trace.add_step(
                "generation_error",
                {"error": str(exc)},
                status="error",
                latency_ms=latency_ms,
            )
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
    trace: "AssistantTraceRecorder | None" = None,
) -> AssistantAnswer:
    preset = get_preset_by_id(assistant_type, question_id)
    if preset is None:
        raise ValueError(f"Unknown question_id '{question_id}' for assistant '{assistant_type}'")

    query_en = preset.query_en
    if trace:
        trace.add_step(
            "preset_selected",
            {
                "question_id": question_id,
                "locale": locale,
                "localized_query": preset.text(locale),
                "query_en": query_en,
            },
        )

    analytical_answer = None
    if forecasting_repo is not None:
        analytical_answer = await _try_analytical_intent_answer(
            assistant_type=assistant_type,
            query=preset.text(locale),
            locale=locale,
            forecasting_repo=forecasting_repo,
            question_id=question_id,
            trace=trace,
        )
    else:
        analytical_answer = await _try_legacy_deterministic_answer(
            assistant_type=assistant_type,
            query=query_en,
            locale=locale,
            forecasting_repo=forecasting_repo,
            question_id=question_id,
            trace=trace,
        )
    if analytical_answer is not None:
        citations_raw = [citation.model_dump(mode="json") for citation in analytical_answer.citations]
        used_tools = analytical_answer.used_tools
        answer = analytical_answer.answer
        await assistant_cache.set(
            assistant_type,
            question_id,
            {"answer": answer, "citations": citations_raw, "used_tools": used_tools},
            locale=locale,
        )
        if trace:
            trace.add_step(
                "preset_cache_store",
                {
                    "assistant_type": assistant_type,
                    "question_id": question_id,
                    "locale": locale,
                    "source": trace.cache_source or "deterministic_analytical_intent",
                },
            )
        response_type = analytical_answer.response_type
        if response_type not in {"answer", "clarification"}:
            response_type = "answer"
        clarification = analytical_answer.clarification if response_type == "clarification" else None
        return AssistantAnswer(
            question_id=question_id,
            query=preset.text(locale),
            answer=answer,
            locale=locale,
            response_type=response_type,
            clarification=clarification,
            cached=bool(analytical_answer.cached),
            citations=[Citation(**c) for c in citations_raw],
            used_tools=used_tools,
        )

    # 1. Cache check (locale-aware)
    cached = await assistant_cache.get(assistant_type, question_id, locale)
    if trace:
        trace.add_step(
            "preset_cache_lookup",
            {
                "assistant_type": assistant_type,
                "question_id": question_id,
                "locale": locale,
                "hit": bool(cached),
            },
        )
    if cached:
        logger.info(
            "assistants | type=%s qid=%s locale=%s status=cache_hit",
            assistant_type, question_id, locale,
        )
        if trace:
            trace.cache_source = "preset_cache"
            trace.cache_strategy = "preset_cache_hit"
            trace.cached = True
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
        assistant_type, query_en, forecasting_service, forecasting_repo, question_id, trace=trace
    )

    # 3. Store in cache (locale-aware)
    await assistant_cache.set(
        assistant_type,
        question_id,
        {"answer": answer, "citations": citations_raw, "used_tools": used_tools},
        locale=locale,
    )
    if trace:
        trace.add_step(
            "preset_cache_store",
            {
                "assistant_type": assistant_type,
                "question_id": question_id,
                "locale": locale,
            },
        )
        trace.cache_source = "llm_generate"
        trace.cache_strategy = "preset_regenerate"
        trace.cached = False

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
    trace: "AssistantTraceRecorder | None" = None,
) -> AssistantAnswer:
    matched_preset = find_preset_by_text(assistant_type, query, locale)
    if matched_preset is not None:
        if trace:
            trace.add_step(
                "preset_text_match",
                {
                    "assistant_type": assistant_type,
                    "locale": locale,
                    "query": query,
                    "question_id": matched_preset.id,
                },
            )
        preset_answer = await ask_preset(
            assistant_type=assistant_type,
            question_id=matched_preset.id,
            locale=locale,
            forecasting_service=forecasting_service,
            forecasting_repo=forecasting_repo,
            trace=trace,
        )
        preset_answer.query = query
        return preset_answer

    analytical_answer = None
    if forecasting_repo is not None:
        analytical_answer = await _try_analytical_intent_answer(
            assistant_type=assistant_type,
            query=query,
            locale=locale,
            forecasting_repo=forecasting_repo,
            trace=trace,
        )
    else:
        analytical_answer = await _try_legacy_deterministic_answer(
            assistant_type=assistant_type,
            query=query,
            locale=locale,
            forecasting_repo=forecasting_repo,
            trace=trace,
        )
    if analytical_answer is not None:
        return analytical_answer
    if trace:
        trace.add_step(
            "fallback_reason",
            {
                "reason": "no_canonical_intent_match_before_cache",
                "query": query,
            },
            status="warning",
        )

    exact_cached = await assistant_query_cache.get_exact(assistant_type, query, locale)
    if trace:
        trace.add_step(
            "custom_exact_cache_lookup",
            {
                "assistant_type": assistant_type,
                "locale": locale,
                "query": query,
                "hit": bool(exact_cached),
            },
        )
    if exact_cached:
        logger.info(
            "assistants | type=%s locale=%s status=custom_exact_cache_hit",
            assistant_type, locale,
        )
        if trace:
            trace.cache_source = "custom_exact_cache"
            trace.cache_strategy = "exact_reuse"
            trace.cached = True
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
    if trace:
        trace.add_step(
            "custom_semantic_lookup",
            {
                "assistant_type": assistant_type,
                "locale": locale,
                "query": query,
                "hit": bool(semantic_cached),
                "candidate": semantic_cached,
            },
        )
    if semantic_cached:
        cached_payload = _cache_payload_from_entry(semantic_cached)
        decision = decide_semantic_cache_strategy(
            similarity=float(semantic_cached.get("similarity", 0.0)),
            reuse_similarity=settings.assistants_semantic_cache_reuse_similarity,
            rewrite_similarity=settings.assistants_semantic_cache_rewrite_similarity,
        )
        if trace:
            trace.add_step(
                "semantic_policy_decision",
                {
                    "decision": decision.strategy,
                    "similarity": decision.similarity,
                    "reuse_similarity": settings.assistants_semantic_cache_reuse_similarity,
                    "rewrite_similarity": settings.assistants_semantic_cache_rewrite_similarity,
                    "rewrite_enabled": settings.assistants_semantic_cache_rewrite_enabled,
                },
            )

        if decision.strategy == "reuse":
            logger.info(
                "assistants | type=%s locale=%s status=custom_semantic_cache_hit similarity=%.3f",
                assistant_type, locale, decision.similarity,
            )
            await assistant_query_cache.set_exact(assistant_type, query, locale, cached_payload)
            if trace:
                trace.add_step(
                    "custom_exact_cache_store",
                    {
                        "assistant_type": assistant_type,
                        "locale": locale,
                        "source": "semantic_reuse",
                    },
                )
                trace.cache_source = "custom_semantic_cache"
                trace.cache_strategy = "semantic_reuse"
                trace.cached = True
                trace.similarity = decision.similarity
            return _build_custom_answer(query, locale, cached_payload, cached=True)

        if decision.strategy == "rewrite" and settings.assistants_semantic_cache_rewrite_enabled:
            logger.info(
                "assistants | type=%s locale=%s status=custom_semantic_rewrite similarity=%.3f",
                assistant_type, locale, decision.similarity,
            )
            rewritten_answer = await _call_semantic_rewrite(
                assistant_type=assistant_type,
                query=query,
                cached_query=str(semantic_cached.get("cached_query", "")),
                cached_payload=cached_payload,
                trace=trace,
            )
            if rewritten_answer:
                payload = _cache_payload(
                    answer=rewritten_answer,
                    citations=cached_payload.get("citations", []),
                    used_tools=cached_payload.get("used_tools", []),
                )
                await assistant_query_cache.set_exact(assistant_type, query, locale, payload)
                await assistant_query_cache.set_semantic(assistant_type, query, locale, payload)
                if trace:
                    trace.add_step(
                        "custom_cache_store",
                        {
                            "assistant_type": assistant_type,
                            "locale": locale,
                            "source": "semantic_rewrite",
                        },
                    )
                    trace.cache_source = "semantic_rewrite"
                    trace.cache_strategy = "semantic_rewrite"
                    trace.cached = False
                    trace.similarity = decision.similarity
                return _build_custom_answer(query, locale, payload, cached=False)

        if decision.strategy == "rewrite" and not settings.assistants_semantic_cache_rewrite_enabled and trace:
            trace.add_step(
                "semantic_rewrite_disabled",
                {
                    "assistant_type": assistant_type,
                    "locale": locale,
                    "similarity": decision.similarity,
                },
                status="warning",
            )

        logger.info(
            "assistants | type=%s locale=%s status=custom_semantic_miss similarity=%.3f",
            assistant_type,
            locale,
            decision.similarity,
        )

    answer, citations_raw, used_tools = await _generate(
        assistant_type, query, forecasting_service, forecasting_repo, trace=trace
    )
    payload = _cache_payload(answer=answer, citations=citations_raw, used_tools=used_tools)
    await assistant_query_cache.set_exact(assistant_type, query, locale, payload)
    await assistant_query_cache.set_semantic(assistant_type, query, locale, payload)
    if trace:
        trace.add_step(
            "custom_cache_store",
            {
                "assistant_type": assistant_type,
                "locale": locale,
                "source": "regenerate",
            },
        )
        trace.cache_source = "llm_generate"
        trace.cache_strategy = "regenerate"
        trace.cached = False
        if semantic_cached:
            trace.similarity = float(semantic_cached.get("similarity", 0.0))
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


async def _try_analytical_intent_answer(
    *,
    assistant_type: AssistantType,
    query: str,
    locale: Locale,
    forecasting_repo: Any,
    question_id: str | None = None,
    trace: "AssistantTraceRecorder | None" = None,
) -> AssistantAnswer | None:
    match = map_analytical_intent(query, locale)
    if match is None:
        guard = detect_analytical_guard(query, locale)
        if guard is not None:
            if trace:
                trace.add_step(
                    "analytical_query_detected",
                    {
                        "classification": (
                            "analytical_but_unsupported"
                            if guard.reason == "unsupported_query"
                            else "analytical_but_ambiguous"
                        ),
                        "normalized_query": guard.normalized_query,
                        "reason": guard.reason,
                        "unsupported_reason": guard.unsupported_reason,
                    },
                    status="warning",
                )

            clarification = build_analytical_guard_clarification(
                reason=guard.reason,
                unsupported_reason=guard.unsupported_reason,
            )
            localized_message = localize_clarification_message(clarification, locale)

            if trace:
                trace.add_step(
                    "analytical_fallback_blocked",
                    {
                        "reason": guard.reason,
                        "unsupported_reason": guard.unsupported_reason,
                    },
                    status="warning",
                )
                trace.add_step(
                    "clarification_returned",
                    {
                        "reason": guard.reason,
                        "missing": clarification.missing,
                        "response_type": "clarification",
                    },
                )
                trace.cache_source = "clarification"
                trace.cache_strategy = "analytical_guard_clarification"
                trace.cached = False

            return AssistantAnswer(
                question_id=question_id,
                query=query,
                answer=localized_message,
                locale=locale,
                response_type="clarification",
                clarification=clarification,
                cached=False,
                citations=[],
                used_tools=[],
            )

        date_range_answer = await deterministic_date_range_service.try_answer(
            assistant_type=assistant_type,
            query=query,
            locale=locale,
            forecasting_repo=forecasting_repo,
            trace=trace,
        )
        if date_range_answer is not None:
            date_range_answer.question_id = question_id
            return date_range_answer

        deterministic_answer = await deterministic_facts_service.try_answer(
            assistant_type=assistant_type,
            query=query,
            locale=locale,
            forecasting_repo=forecasting_repo,
            trace=trace,
        )
        if deterministic_answer is not None:
            deterministic_answer.question_id = question_id
            return deterministic_answer
        return None

    if trace:
        trace.add_step(
            "analytical_query_detected",
            {
                "classification": "deterministic_analytical_supported",
                "normalized_query": match.normalized_query,
                "intent_id": match.intent.intent_id,
                "source": match.source,
            },
        )
        trace.add_step(
            "canonical_intent_matched",
            {
                "intent_id": match.intent.intent_id,
                "domain": match.intent.domain,
                "parameters": match.parameters,
                "executor_target": match.intent.executor_target,
                "source": match.source,
            },
        )

    ambiguity = detect_analytical_ambiguity(match)
    if ambiguity is not None:
        clarification = build_clarification(match.intent.intent_id, ambiguity.missing)
        localized_message = localize_clarification_message(clarification, locale)
        if trace:
            trace.add_step(
                "ambiguity_detected",
                {
                    "intent_id": match.intent.intent_id,
                    "missing": ambiguity.missing,
                    "parameters": match.parameters,
                },
                status="warning",
            )
            trace.add_step(
                "analytical_fallback_blocked",
                {
                    "reason": "ambiguity_requires_clarification",
                    "intent_id": match.intent.intent_id,
                    "missing": ambiguity.missing,
                },
                status="warning",
            )
            trace.add_step(
                "clarification_returned",
                {
                    "intent_id": match.intent.intent_id,
                    "missing": ambiguity.missing,
                    "response_type": "clarification",
                },
            )
            trace.cache_source = "clarification"
            trace.cache_strategy = "intent_clarification"
            trace.cached = False

        return AssistantAnswer(
            question_id=question_id,
            query=query,
            answer=localized_message,
            locale=locale,
            response_type="clarification",
            clarification=clarification,
            cached=False,
            citations=[],
            used_tools=[],
        )

    if match.intent.executor_target == "deterministic_date_range":
        if trace:
            trace.add_step(
                "deterministic_intent_selected",
                {
                    "intent_id": match.intent.intent_id,
                    "executor_target": match.intent.executor_target,
                },
            )
        answer = await deterministic_date_range_service.try_answer(
            assistant_type=assistant_type,
            query=query,
            locale=locale,
            forecasting_repo=forecasting_repo,
            trace=trace,
        )
        if answer is not None:
            answer.question_id = question_id
        return answer

    if match.intent.executor_target == "deterministic_facts":
        if trace:
            trace.add_step(
                "deterministic_intent_selected",
                {
                    "intent_id": match.intent.intent_id,
                    "executor_target": match.intent.executor_target,
                },
            )
        answer = await deterministic_facts_service.try_answer(
            assistant_type=assistant_type,
            query=query,
            locale=locale,
            forecasting_repo=forecasting_repo,
            trace=trace,
        )
        if answer is not None:
            answer.question_id = question_id
        return answer

    if match.intent.executor_target == "top_products_ranking":
        if trace:
            trace.add_step(
                "deterministic_list_intent_selected",
                {
                    "intent_id": match.intent.intent_id,
                    "executor_target": match.intent.executor_target,
                    "parameters": match.parameters,
                },
            )
        return await _answer_top_products_ranking(
            query=query,
            locale=locale,
            forecasting_repo=forecasting_repo,
            intent_id=match.intent.intent_id,
            parameters=match.parameters,
            question_id=question_id,
            trace=trace,
        )

    return None


async def _try_legacy_deterministic_answer(
    *,
    assistant_type: AssistantType,
    query: str,
    locale: Locale,
    forecasting_repo: Any,
    question_id: str | None = None,
    trace: "AssistantTraceRecorder | None" = None,
) -> AssistantAnswer | None:
    date_range_answer = await deterministic_date_range_service.try_answer(
        assistant_type=assistant_type,
        query=query,
        locale=locale,
        forecasting_repo=forecasting_repo,
        trace=trace,
    )
    if date_range_answer is not None:
        date_range_answer.question_id = question_id
        return date_range_answer

    deterministic_answer = await deterministic_facts_service.try_answer(
        assistant_type=assistant_type,
        query=query,
        locale=locale,
        forecasting_repo=forecasting_repo,
        trace=trace,
    )
    if deterministic_answer is not None:
        deterministic_answer.question_id = question_id
        return deterministic_answer
    return None


async def _answer_top_products_ranking(
    *,
    query: str,
    locale: Locale,
    forecasting_repo: Any,
    intent_id: str,
    parameters: dict[str, Any],
    question_id: str | None = None,
    trace: "AssistantTraceRecorder | None" = None,
) -> AssistantAnswer:
    limit = int(parameters.get("limit") or 5)
    metric = str(parameters.get("metric") or "quantity")
    direction = str(parameters.get("direction") or "desc")

    data_signature = await forecasting_repo.get_sales_dataset_signature()
    data_fingerprint = _build_data_fingerprint(data_signature)
    cache_key = _deterministic_intent_cache_key(
        intent_id=intent_id,
        locale=locale,
        parameters=parameters,
        data_fingerprint=data_fingerprint,
    )
    cached = await _get_deterministic_intent_cache(cache_key)
    if trace:
        trace.add_step(
            "deterministic_cache_lookup",
            {
                "intent_id": intent_id,
                "data_fingerprint": data_fingerprint,
                "data_signature": data_signature,
                "parameters": parameters,
                "cache_hit": bool(cached),
            },
        )

    if cached:
        ranking = cached["ranking"]
        cache_source = "deterministic_intent_cache"
        cache_strategy = "intent_parameters_hit"
        cached_flag = True
    else:
        ranking = await forecasting_repo.get_product_ranked_list(
            metric=metric,
            direction=direction,
            limit=limit,
        )
        if trace:
            trace.add_step(
                "deterministic_resolver_output",
                {
                    "intent_id": intent_id,
                    "ranking": ranking,
                },
            )
        await _set_deterministic_intent_cache(
            cache_key,
            {
                "intent_id": intent_id,
                "parameters": parameters,
                "ranking": ranking,
            },
        )
        if trace:
            trace.add_step(
                "deterministic_cache_store",
                {
                    "intent_id": intent_id,
                    "data_fingerprint": data_fingerprint,
                },
            )
        cache_source = "deterministic_intent_resolver"
        cache_strategy = "intent_parameters_resolve"
        cached_flag = False

    answer = _render_top_products_ranking(locale, metric, ranking)
    if trace:
        trace.add_step(
            "deterministic_render",
            {
                "intent_id": intent_id,
                "rendered_answer": answer,
            },
        )
        trace.cache_source = cache_source
        trace.cache_strategy = cache_strategy
        trace.cached = cached_flag

    return AssistantAnswer(
        question_id=question_id,
        query=query,
        answer=answer,
        locale=locale,
        cached=cached_flag,
        citations=[],
        used_tools=[],
    )


def _render_top_products_ranking(locale: Locale, metric: str, ranking: list[dict[str, Any]]) -> str:
    if not ranking:
        if locale == "cs":
            return "Pro tento dotaz nejsou k dispozici žádná prodejní data."
        if locale == "ru":
            return "Для этого запроса нет доступных данных о продажах."
        return "No sales data is available for this query."

    if metric == "revenue":
        if locale == "cs":
            intro = "Produkty s nejvyššími tržbami jsou:"
            lines = [f"{idx}. Produkt {item['product_id']}: {float(item['value']):.2f}" for idx, item in enumerate(ranking, start=1)]
        elif locale == "ru":
            intro = "Продукты с самой высокой выручкой:"
            lines = [f"{idx}. Продукт {item['product_id']}: {float(item['value']):.2f}" for idx, item in enumerate(ranking, start=1)]
        else:
            intro = "Products with the highest revenue are:"
            lines = [f"{idx}. Product {item['product_id']}: {float(item['value']):.2f}" for idx, item in enumerate(ranking, start=1)]
    else:
        if locale == "cs":
            intro = "Produkty s nejvyššími celkovými prodeji jsou:"
            lines = [f"{idx}. Produkt {item['product_id']}: {int(item['value'])} ks" for idx, item in enumerate(ranking, start=1)]
        elif locale == "ru":
            intro = "Продукты с наибольшими общими продажами:"
            lines = [f"{idx}. Продукт {item['product_id']}: {int(item['value'])} шт." for idx, item in enumerate(ranking, start=1)]
        else:
            intro = "Products with the highest total sales are:"
            lines = [f"{idx}. Product {item['product_id']}: {int(item['value'])} units" for idx, item in enumerate(ranking, start=1)]
    return "\n".join([intro, *lines])


def _deterministic_intent_cache_key(
    *,
    intent_id: str,
    locale: str,
    parameters: dict[str, Any],
    data_fingerprint: str,
) -> str:
    canonical = json.dumps(parameters, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"assistants:deterministic_intent:{intent_id}:{locale}:{data_fingerprint}:{digest}"


async def _get_deterministic_intent_cache(key: str) -> dict[str, Any] | None:
    client = await assistant_cache._get_client()
    if client is None:
        return None
    raw = await client.get(key)
    return json.loads(raw) if raw else None


async def _set_deterministic_intent_cache(key: str, payload: dict[str, Any]) -> None:
    client = await assistant_cache._get_client()
    if client is None:
        return
    await client.set(key, json.dumps(payload, ensure_ascii=False))


def _build_data_fingerprint(data_signature: dict[str, Any]) -> str:
    canonical = json.dumps(
        data_signature,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
