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
    "продукт",
    "продукта",
    "продукты",
)
_UNSUPPORTED_ENTITY_TERMS = (
    "kategorie",
    "kategorii",
    "category",
    "categories",
    "категория",
    "категории",
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
    "выручк",
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
    "выгоду от акции",
    "выгоду от акций",
    "выигрывает от акции",
    "выигрывает от акций",
    "промо эффект",
    "промо-эффект",
)
_AVG_PRICE_TERMS = (
    "prumernou prodejni cenu",
    "prumernou cenu",
    "average selling price",
    "average sale price",
    "average price",
    "среднюю цену продажи",
    "средняя цена продажи",
    "цену продажи",
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
    "продается больше всего",
    "продается меньше всего",
    "самый продаваемый",
    "наиболее продаваемый",
    "количество",
    "количеству",
    "объем продаж",
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
    "больше всего",
    "наибольш",
    "самый высокий",
    "самую высок",
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
    "меньше всего",
    "наимень",
    "самый низкий",
    "самую низ",
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

    if not mentions_product and not _can_imply_default_product_entity(metric, direction):
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


def _can_imply_default_product_entity(
    metric: FactMetric,
    direction: FactDirection | None,
) -> bool:
    # In the current deterministic facts domain, top promo-lift phrasings such as
    # "co nejvíce těží z akcí?" still unambiguously ask for the top product.
    return metric == "promo_lift" and direction == "desc"


def _normalize_for_matching(query: str) -> str:
    normalized = normalise_query(query)
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.strip()
