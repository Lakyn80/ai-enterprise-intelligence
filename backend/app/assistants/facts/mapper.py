"""Rule-based mapper from natural language to canonical deterministic facts specs."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from app.assistants.facts.schemas import FactDirection, FactMetric, FactQuerySpec
from app.assistants.query_normalization import normalise_query

_PRODUCT_TERMS = (
    "produkt",
    "produktu",
    "produkty",
    "product",
    "products",
)
_UNSUPPORTED_ENTITY_TERMS = (
    "kategorie",
    "kategorii",
    "category",
    "categories",
)
_UNSUPPORTED_FILTER_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bv kategorii\b", "Category filters are not supported yet."),
    (r"\bin category\b", "Category filters are not supported yet."),
    (r"\bfrom\b.+\bto\b", "Date-range filters are not supported yet."),
    (r"\bbetween\b", "Date-range filters are not supported yet."),
    (r"\bod\b.+\bdo\b", "Date-range filters are not supported yet."),
    (r"\bza rok\b", "Date-range filters are not supported yet."),
    (r"\bv roce\b", "Date-range filters are not supported yet."),
    (r"\btop\s+\d+\b", "Only top/bottom 1 queries are supported in v1."),
    (r"\bbottom\s+\d+\b", "Only top/bottom 1 queries are supported in v1."),
    (r"\bprvnich\s+\d+\b", "Only top/bottom 1 queries are supported in v1."),
    (r"\bnejlepsich\s+\d+\b", "Only top/bottom 1 queries are supported in v1."),
)
_REVENUE_TERMS = (
    "trzby",
    "revenue",
    "utrzi",
)
_PROMO_LIFT_TERMS = (
    "promo lift",
    "promo efekt",
    "promo effect",
    "promotional lift",
    "promotion lift",
    "tezi z akci",
    "tezi z promo akci",
    "profituje z akci",
    "profituje z promo akci",
    "benefits from promotions",
    "benefits the most from promotions",
    "gains from promotions",
    "gains the most from promotions",
    "profits from promotions",
    "benefit most from promotions",
    "most from promotions",
)
_AVG_PRICE_TERMS = (
    "prumernou prodejni cenu",
    "prumernou cenu",
    "average selling price",
    "average sale price",
    "average price",
)
_QUANTITY_TERMS = (
    "nejprodavanejsi",
    "nejmene prodavany",
    "nejmin prodavany",
    "prodava nejvic",
    "prodava nejmin",
    "sold the most",
    "sold the least",
    "sells the most",
    "sells the least",
    "most sold",
    "best selling",
    "least selling",
    "quantity",
    "units",
    "pieces",
    "pocet prodanych kusu",
    "prodanych kusu",
    "pocet kusu",
)
_DESC_TERMS = (
    "nejprodavanejsi",
    "nejvic",
    "nejvice",
    "nejvyssi",
    "nejvetsi",
    "top",
    "best",
    "most",
    "highest",
)
_ASC_TERMS = (
    "nejmene",
    "nejmin",
    "nejnizsi",
    "nejmensi",
    "bottom",
    "least",
    "lowest",
    "worst",
)


@dataclass(frozen=True, slots=True)
class FactQueryMapping:
    matched: bool
    normalized_query: str
    spec: FactQuerySpec | None = None
    unsupported_reason: str | None = None


def map_fact_query(query: str) -> FactQueryMapping:
    normalized = _normalize_for_matching(query)
    if not normalized:
        return FactQueryMapping(matched=False, normalized_query="")

    metric = _resolve_metric(normalized)
    direction = _resolve_direction(normalized)
    mentions_product = any(term in normalized for term in _PRODUCT_TERMS)
    mentions_unsupported_entity = any(term in normalized for term in _UNSUPPORTED_ENTITY_TERMS)

    if metric is None or direction is None:
        return FactQueryMapping(matched=False, normalized_query=normalized)

    for pattern, reason in _UNSUPPORTED_FILTER_PATTERNS:
        if re.search(pattern, normalized):
            return FactQueryMapping(
                matched=True,
                normalized_query=normalized,
                unsupported_reason=reason,
            )

    if mentions_unsupported_entity:
        return FactQueryMapping(
            matched=True,
            normalized_query=normalized,
            unsupported_reason="Only product ranking questions are supported in deterministic facts v1.",
        )

    if not mentions_product:
        return FactQueryMapping(matched=False, normalized_query=normalized)

    return FactQueryMapping(
        matched=True,
        normalized_query=normalized,
        spec=FactQuerySpec(
            entity="product",
            operation="rank",
            metric=metric,
            direction=direction,
            filters={},
            date_range=None,
            limit=1,
        ),
    )


def _resolve_metric(normalized: str) -> FactMetric | None:
    if any(term in normalized for term in _REVENUE_TERMS):
        return "revenue"
    if any(term in normalized for term in _AVG_PRICE_TERMS):
        return "avg_price"
    if any(term in normalized for term in _PROMO_LIFT_TERMS):
        return "promo_lift"
    if any(term in normalized for term in _QUANTITY_TERMS):
        return "quantity"
    return None


def _resolve_direction(normalized: str) -> FactDirection | None:
    if any(term in normalized for term in _ASC_TERMS):
        return "asc"
    if any(term in normalized for term in _DESC_TERMS):
        return "desc"
    return None


def _normalize_for_matching(query: str) -> str:
    normalized = normalise_query(query)
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.strip()
