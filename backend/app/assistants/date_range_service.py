"""Deterministic handler for dataset date range questions."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import TYPE_CHECKING, Any

from app.assistants.cache import assistant_cache
from app.assistants.schemas import AssistantAnswer
from app.assistants.query_normalization import normalise_query
from app.settings import settings

if TYPE_CHECKING:
    from app.assistants.trace_recorder import AssistantTraceRecorder

_INTENT_NAME = "date_range_of_data"
_RANGE_TERMS = (
    "date range",
    "time range",
    "casovy rozsah",
    "casov",
    "rozsah",
    "rozmez",
    "od kdy do kdy",
    "od kdy",
    "do kdy",
    "v jakem obdobi",
    "jake obdobi",
    "pokryvaji",
    "cover",
    "диапазон дат",
    "временной диапазон",
    "период",
    "охватывают",
    "охватывает",
)
_DATA_TERMS = (
    "sales data",
    "prodejni data",
    "predajne data",
    "data prodeje",
    "data predaje",
    "prodejnich dat",
    "predajnych dat",
    "dat prodeje",
    "dat predaje",
    "data o prodej",
    "data o predaj",
    "данные о продажах",
    "данные продаж",
)
_GENERIC_DATA_TERMS = (
    "jsou data",
    "maji data",
    "data jsou",
)
_TRAILING_NOISE_SUFFIXES = (
    " v tomto reportu",
    " v reportu",
    " v datech",
)


class DateRangeDeterministicService:
    async def try_answer(
        self,
        *,
        assistant_type: str,
        query: str,
        locale: str,
        forecasting_repo: Any,
        trace: "AssistantTraceRecorder | None" = None,
    ) -> AssistantAnswer | None:
        if not settings.assistants_deterministic_facts_enabled or forecasting_repo is None:
            return None

        normalized = _normalize_for_matching(query)
        if not _is_date_range_query(normalized):
            return None

        if trace:
            trace.add_step(
                "route_selected",
                {
                    "assistant_type": assistant_type,
                    "selected_route": "deterministic_date_range",
                    "normalized_query": normalized,
                },
            )

        data_signature = await forecasting_repo.get_sales_dataset_signature()
        data_fingerprint = _build_data_fingerprint(data_signature)
        cache_key = _cache_key(locale, data_fingerprint)
        cached = await _get_cache(cache_key)
        if trace:
            trace.add_step(
                "deterministic_cache_lookup",
                {
                    "intent": _INTENT_NAME,
                    "data_fingerprint": data_fingerprint,
                    "data_signature": data_signature,
                    "cache_hit": bool(cached),
                },
            )

        if cached:
            date_from = cached["date_from"]
            date_to = cached["date_to"]
            answer = cached["answer"]
            cache_source = "deterministic_date_range_cache"
            cache_strategy = "intent_cache_hit"
            cached_flag = True
        else:
            date_from, date_to = await forecasting_repo.get_date_range()
            if not date_from or not date_to:
                raise ValueError("No sales data available for date range query.")

            answer = _render_answer(locale, str(date_from), str(date_to))
            payload = {
                "intent": _INTENT_NAME,
                "date_from": str(date_from),
                "date_to": str(date_to),
                "answer": answer,
            }
            await _set_cache(cache_key, payload)
            if trace:
                trace.add_step(
                    "deterministic_resolver_output",
                    {
                        "intent": _INTENT_NAME,
                        "date_from": str(date_from),
                        "date_to": str(date_to),
                    },
                )
                trace.add_step(
                    "deterministic_cache_store",
                    {
                        "intent": _INTENT_NAME,
                        "data_fingerprint": data_fingerprint,
                    },
                )
            cache_source = "deterministic_date_range_resolver"
            cache_strategy = "intent_resolve"
            cached_flag = False

        if trace:
            trace.add_step(
                "deterministic_render",
                {
                    "rendered_answer": answer,
                    "intent": _INTENT_NAME,
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


def _normalize_for_matching(query: str) -> str:
    normalized = normalise_query(query)
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.strip()


def _is_date_range_query(normalized: str) -> bool:
    if not normalized:
        return False
    canonical = _canonicalize_date_range_query(normalized)
    return any(term in canonical for term in _RANGE_TERMS) and (
        any(term in canonical for term in _DATA_TERMS)
        or any(term in canonical for term in _GENERIC_DATA_TERMS)
    )


def _canonicalize_date_range_query(normalized: str) -> str:
    canonical = re.sub(r"\bodkdy\b", "od kdy", normalized)
    canonical = re.sub(r"\bdokdy\b", "do kdy", canonical)
    canonical = re.sub(r"\s+", " ", canonical).strip()

    changed = True
    while changed:
        changed = False
        for suffix in _TRAILING_NOISE_SUFFIXES:
            if canonical.endswith(suffix):
                canonical = canonical[: -len(suffix)].rstrip()
                changed = True

    return canonical


def _render_answer(locale: str, date_from: str, date_to: str) -> str:
    if locale == "cs":
        return f"Prodejní data pokrývají období od {date_from} do {date_to}."
    if locale == "sk":
        return f"Predajné dáta pokrývajú obdobie od {date_from} do {date_to}."
    if locale == "ru":
        return f"Данные о продажах охватывают период с {date_from} по {date_to}."
    return f"Sales data covers the period from {date_from} to {date_to}."


def _build_data_fingerprint(data_signature: dict[str, Any]) -> str:
    canonical = json.dumps(
        data_signature,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _cache_key(locale: str, data_fingerprint: str) -> str:
    return f"assistants:deterministic_intent:{_INTENT_NAME}:{locale}:{data_fingerprint}"


async def _get_cache(key: str) -> dict[str, Any] | None:
    client = await assistant_cache._get_client()
    if client is None:
        return None
    raw = await client.get(key)
    return json.loads(raw) if raw else None


async def _set_cache(key: str, payload: dict[str, Any]) -> None:
    client = await assistant_cache._get_client()
    if client is None:
        return
    await client.set(key, json.dumps(payload, ensure_ascii=False))


deterministic_date_range_service = DateRangeDeterministicService()
