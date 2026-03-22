"""Analytical intent mapping for deterministic assistant routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
import unicodedata

from app.assistants.date_range_service import _is_date_range_query
from app.assistants.facts.mapper import map_fact_query
from app.assistants.intent_registry import IntentDefinition, get_intent_definition
from app.assistants.query_normalization import normalise_query

IntentSource = Literal["rules", "facts_mapper"]
AnalyticalGuardReason = Literal["missing_entity", "unsupported_query"]

_PLURAL_PRODUCT_TERMS = (
    "produkty",
    "products",
    "продукты",
)
_SINGULAR_PRODUCT_TERMS = (
    "produkt",
    "produktu",
    "product",
    "продукт",
    "продукта",
)
_PRODUCT_TERMS = _PLURAL_PRODUCT_TERMS + _SINGULAR_PRODUCT_TERMS
_SALES_TERMS = (
    "prodej",
    "prodeje",
    "prodeju",
    "sales",
    "sale",
    "продаж",
    "продаж",
)
_REVENUE_TERMS = (
    "trzby",
    "revenue",
    "выручк",
)
_PROMO_TERMS = (
    "promo",
    "promotion",
    "promotions",
    "akci",
    "промо",
    "акци",
)
_AVG_PRICE_TERMS = (
    "prumernou cenu",
    "prumernou prodejni cenu",
    "average price",
    "average selling price",
    "среднюю цену",
    "цену продажи",
)
_RANKING_TERMS = (
    "nejvyssi",
    "nejvic",
    "top",
    "highest",
    "most",
    "best",
    "naibolsh",
    "наибольш",
    "больше всего",
    "самый высок",
    "самые высок",
)
_CLEAR_TOP_TOTAL_SALES_PHRASES = (
    "nejvyssi celkove prodeje",
    "nejvyssi celkove prodeju",
    "nejvyssi celkove prodej",
    "celkove prodeje",
    "celkove prodeju",
    "highest total sales",
    "top products by total sales",
    "best selling products overall",
    "naibolshie obshchie prodazhi",
    "наибольшие общие продажи",
    "общие продажи",
    "top produktov po obshchim prodazham",
    "топ продуктов по общим продажам",
)
_CLEAR_TOP_REVENUE_PHRASES = (
    "nejvyssi trzby",
    "nejvetsi trzby",
    "highest revenue",
    "most revenue",
    "top products by revenue",
    "vyssi vyruchk",
    "samuyu vysokuyu vyruchk",
    "самой высокой выруч",
    "самую высокую выруч",
    "наибольшую выруч",
)
_ANALYTICAL_METRIC_TERMS = _SALES_TERMS + _REVENUE_TERMS + _PROMO_TERMS + _AVG_PRICE_TERMS


@dataclass(frozen=True, slots=True)
class IntentMatch:
    intent: IntentDefinition
    parameters: dict[str, Any]
    normalized_query: str
    source: IntentSource
    unsupported_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AnalyticalGuardMatch:
    normalized_query: str
    reason: AnalyticalGuardReason
    unsupported_reason: str | None = None


def map_analytical_intent(query: str, locale: str) -> IntentMatch | None:
    normalized = _normalize_for_matching(query)
    if not normalized:
        return None

    if _matches_clear_top_total_sales_query(normalized):
        return IntentMatch(
            intent=get_intent_definition("top_products_by_total_sales"),
            parameters={
                "metric": "quantity",
                "entity": "product",
                "aggregation": "sum",
                "direction": "desc",
                "scope": "list",
                "limit": 5,
            },
            normalized_query=normalized,
            source="rules",
        )

    if _matches_clear_top_revenue_list_query(normalized):
        return IntentMatch(
            intent=get_intent_definition("top_products_by_revenue"),
            parameters={
                "metric": "revenue",
                "entity": "product",
                "aggregation": "sum",
                "direction": "desc",
                "scope": "list",
                "limit": 5,
            },
            normalized_query=normalized,
            source="rules",
        )

    fact_mapping = map_fact_query(query)
    if fact_mapping.matched and fact_mapping.spec is not None:
        spec = fact_mapping.spec
        intent_id = _fact_intent_id(spec.metric, spec.direction)
        return IntentMatch(
            intent=get_intent_definition(intent_id),
            parameters={
                "metric": spec.metric,
                "entity": spec.entity,
                "aggregation": spec.operation,
                "direction": spec.direction,
                "limit": spec.limit,
            },
            normalized_query=fact_mapping.normalized_query,
            source="facts_mapper",
            unsupported_reason=fact_mapping.unsupported_reason,
        )

    if _is_date_range_query(normalized):
        return IntentMatch(
            intent=get_intent_definition("sales_data_date_range"),
            parameters={"entity": "sales_data"},
            normalized_query=normalized,
            source="rules",
        )

    if _matches_ambiguous_sales_ranking_query(normalized):
        return IntentMatch(
            intent=get_intent_definition("sales_ranking_query"),
            parameters={
                "metric": None,
                "entity": "product",
                "aggregation": "sum",
                "direction": "desc",
                "scope": _infer_scope(normalized),
                "limit": _infer_limit(normalized),
            },
            normalized_query=normalized,
            source="rules",
        )

    return None


def detect_analytical_guard(query: str, locale: str) -> AnalyticalGuardMatch | None:
    del locale

    normalized = _normalize_for_matching(query)
    if not normalized:
        return None

    fact_mapping = map_fact_query(query)
    if fact_mapping.matched and fact_mapping.unsupported_reason:
        return AnalyticalGuardMatch(
            normalized_query=fact_mapping.normalized_query,
            reason="unsupported_query",
            unsupported_reason=fact_mapping.unsupported_reason,
        )

    if _looks_like_analytical_ranking_without_entity(normalized):
        return AnalyticalGuardMatch(
            normalized_query=normalized,
            reason="missing_entity",
        )

    return None


def _matches_clear_top_total_sales_query(normalized: str) -> bool:
    return any(term in normalized for term in _PLURAL_PRODUCT_TERMS) and any(
        phrase in normalized for phrase in _CLEAR_TOP_TOTAL_SALES_PHRASES
    )


def _matches_clear_top_revenue_list_query(normalized: str) -> bool:
    return any(term in normalized for term in _PLURAL_PRODUCT_TERMS) and any(
        phrase in normalized for phrase in _CLEAR_TOP_REVENUE_PHRASES
    ) and any(term in normalized for term in _REVENUE_TERMS)


def _matches_ambiguous_sales_ranking_query(normalized: str) -> bool:
    if _matches_clear_top_total_sales_query(normalized):
        return False
    if _matches_clear_top_revenue_list_query(normalized):
        return False
    if not any(term in normalized for term in _PRODUCT_TERMS):
        return False
    if not any(term in normalized for term in _RANKING_TERMS):
        return False
    if not any(term in normalized for term in _SALES_TERMS):
        return False
    if any(term in normalized for term in _REVENUE_TERMS):
        return False
    return True


def _looks_like_analytical_ranking_without_entity(normalized: str) -> bool:
    if any(term in normalized for term in _PRODUCT_TERMS):
        return False
    if not any(term in normalized for term in _RANKING_TERMS):
        return False
    if not any(term in normalized for term in _ANALYTICAL_METRIC_TERMS):
        return False
    return True


def _infer_scope(normalized: str) -> str | None:
    if any(term in normalized for term in _PLURAL_PRODUCT_TERMS):
        return "list"
    if any(term in normalized for term in _SINGULAR_PRODUCT_TERMS):
        return "top_1"
    return None


def _infer_limit(normalized: str) -> int | None:
    scope = _infer_scope(normalized)
    if scope == "list":
        return 5
    if scope == "top_1":
        return 1
    return None


def _fact_intent_id(metric: str, direction: str) -> str:
    mapping = {
        ("quantity", "desc"): "top_product_by_quantity",
        ("quantity", "asc"): "bottom_product_by_quantity",
        ("revenue", "desc"): "top_product_by_revenue",
        ("revenue", "asc"): "bottom_product_by_revenue",
        ("avg_price", "desc"): "top_product_by_avg_price",
        ("promo_lift", "desc"): "top_product_by_promo_lift",
    }
    return mapping[(metric, direction)]


def _normalize_for_matching(query: str) -> str:
    normalized = normalise_query(query)
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.strip()
