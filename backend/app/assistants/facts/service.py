"""Orchestration layer for deterministic facts queries."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from app.assistants.facts.cache import deterministic_facts_cache
from app.assistants.facts.mapper import map_fact_query
from app.assistants.facts.renderer import render_fact_answer
from app.assistants.facts.resolver import deterministic_facts_resolver
from app.assistants.facts.schemas import FactQuerySpec, FactResolveResult
from app.assistants.schemas import AssistantAnswer
from app.settings import settings

if TYPE_CHECKING:
    from app.assistants.trace_recorder import AssistantTraceRecorder


class DeterministicFactsError(ValueError):
    """Base error for deterministic facts path."""


class UnsupportedDeterministicFactsQueryError(DeterministicFactsError):
    """Raised when a deterministic fact-like query is recognized but not supported."""


class DeterministicFactsService:
    """Resolve supported business fact questions without LLM answer generation."""

    async def try_answer(
        self,
        *,
        assistant_type: str,
        query: str,
        locale: str,
        forecasting_repo: Any,
        trace: "AssistantTraceRecorder | None" = None,
    ) -> AssistantAnswer | None:
        if not settings.assistants_deterministic_facts_enabled:
            return None

        mapping = map_fact_query(query)
        if not mapping.matched:
            if trace:
                trace.add_step(
                    "route_selected",
                    {
                        "assistant_type": assistant_type,
                        "selected_route": "default_assistant",
                        "reason": "no_supported_deterministic_fact_match",
                    },
                )
            return None

        if trace:
            trace.add_step(
                "route_selected",
                {
                    "assistant_type": assistant_type,
                    "selected_route": "deterministic_facts",
                    "normalized_query": mapping.normalized_query,
                },
            )

        if mapping.unsupported_reason:
            if trace:
                trace.add_step(
                    "deterministic_facts_unsupported",
                    {
                        "reason": mapping.unsupported_reason,
                        "normalized_query": mapping.normalized_query,
                    },
                    status="error",
                )
            raise UnsupportedDeterministicFactsQueryError(mapping.unsupported_reason)

        spec = FactQuerySpec.model_validate(mapping.spec.model_dump(mode="json"))
        spec_hash = spec.spec_hash()
        if trace:
            trace.add_step(
                "canonical_spec_mapped",
                {
                    "canonical_spec": spec.model_dump(mode="json"),
                    "spec_hash": spec_hash,
                },
            )

        data_signature = await forecasting_repo.get_sales_dataset_signature()
        data_fingerprint = _build_data_fingerprint(data_signature)
        cached = await deterministic_facts_cache.get(spec_hash, data_fingerprint)
        if trace:
            trace.add_step(
                "deterministic_cache_lookup",
                {
                    "spec_hash": spec_hash,
                    "data_fingerprint": data_fingerprint,
                    "data_signature": data_signature,
                    "cache_hit": bool(cached),
                },
            )

        if cached:
            result = FactResolveResult.model_validate(cached["result"])
            cache_source = "deterministic_facts_cache"
            cache_strategy = "facts_spec_hash_hit"
            cached_flag = True
        else:
            if trace:
                trace.add_step(
                    "deterministic_resolver_input",
                    {
                        "resolver_input": spec.model_dump(mode="json"),
                    },
                )
            result = await deterministic_facts_resolver.resolve(forecasting_repo, spec)
            if trace:
                trace.add_step(
                    "deterministic_resolver_output",
                    {
                        "resolver_output": result.model_dump(mode="json"),
                        "ambiguity": result.tie,
                    },
                )
            await deterministic_facts_cache.set(
                spec_hash,
                data_fingerprint,
                {
                    "spec": spec.model_dump(mode="json"),
                    "result": result.model_dump(mode="json"),
                },
            )
            if trace:
                trace.add_step(
                    "deterministic_cache_store",
                    {
                        "spec_hash": spec_hash,
                        "data_fingerprint": data_fingerprint,
                    },
                )
            cache_source = "deterministic_facts_resolver"
            cache_strategy = "facts_resolve"
            cached_flag = False

        answer = render_fact_answer(spec, result, locale)
        if trace:
            trace.add_step(
                "deterministic_render",
                {
                    "rendered_answer": answer,
                    "ambiguity": result.tie,
                },
            )
            trace.cache_source = cache_source
            trace.cache_strategy = cache_strategy
            trace.cached = cached_flag

        return AssistantAnswer(
            question_id=None,
            query=query,
            answer=answer,
            locale=locale,
            cached=cached_flag,
            citations=[],
            used_tools=[],
        )


def _build_data_fingerprint(data_signature: dict[str, Any]) -> str:
    canonical = json.dumps(
        data_signature,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


deterministic_facts_service = DeterministicFactsService()
