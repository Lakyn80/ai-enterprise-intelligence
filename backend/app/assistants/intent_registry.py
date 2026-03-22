"""Canonical analytical intent registry for the assistants pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

IntentExecutorTarget = Literal[
    "deterministic_facts",
    "deterministic_date_range",
    "top_products_ranking",
    "clarification",
]


@dataclass(frozen=True, slots=True)
class IntentDefinition:
    intent_id: str
    domain: str
    executor_target: IntentExecutorTarget
    required_parameters: tuple[str, ...]
    optional_parameters: tuple[str, ...] = ()
    response_rendering_mode: str = "deterministic"
    cache_key_strategy: str = "intent_parameters"


INTENT_REGISTRY: dict[str, IntentDefinition] = {
    "top_product_by_quantity": IntentDefinition(
        intent_id="top_product_by_quantity",
        domain="sales",
        executor_target="deterministic_facts",
        required_parameters=("metric", "entity", "aggregation", "direction", "limit"),
    ),
    "bottom_product_by_quantity": IntentDefinition(
        intent_id="bottom_product_by_quantity",
        domain="sales",
        executor_target="deterministic_facts",
        required_parameters=("metric", "entity", "aggregation", "direction", "limit"),
    ),
    "top_product_by_revenue": IntentDefinition(
        intent_id="top_product_by_revenue",
        domain="sales",
        executor_target="deterministic_facts",
        required_parameters=("metric", "entity", "aggregation", "direction", "limit"),
    ),
    "bottom_product_by_revenue": IntentDefinition(
        intent_id="bottom_product_by_revenue",
        domain="sales",
        executor_target="deterministic_facts",
        required_parameters=("metric", "entity", "aggregation", "direction", "limit"),
    ),
    "top_product_by_avg_price": IntentDefinition(
        intent_id="top_product_by_avg_price",
        domain="sales",
        executor_target="deterministic_facts",
        required_parameters=("metric", "entity", "aggregation", "direction", "limit"),
    ),
    "top_product_by_promo_lift": IntentDefinition(
        intent_id="top_product_by_promo_lift",
        domain="sales",
        executor_target="deterministic_facts",
        required_parameters=("metric", "entity", "aggregation", "direction", "limit"),
    ),
    "sales_data_date_range": IntentDefinition(
        intent_id="sales_data_date_range",
        domain="sales",
        executor_target="deterministic_date_range",
        required_parameters=("entity",),
    ),
    "top_products_by_total_sales": IntentDefinition(
        intent_id="top_products_by_total_sales",
        domain="sales",
        executor_target="top_products_ranking",
        required_parameters=("metric", "entity", "aggregation", "direction", "scope"),
        optional_parameters=("limit",),
    ),
    "top_products_by_revenue": IntentDefinition(
        intent_id="top_products_by_revenue",
        domain="sales",
        executor_target="top_products_ranking",
        required_parameters=("metric", "entity", "aggregation", "direction", "scope"),
        optional_parameters=("limit",),
    ),
    "sales_ranking_query": IntentDefinition(
        intent_id="sales_ranking_query",
        domain="sales",
        executor_target="clarification",
        required_parameters=("metric", "scope"),
        optional_parameters=("entity", "aggregation", "direction", "limit"),
        response_rendering_mode="clarification",
        cache_key_strategy="none",
    ),
}


def get_intent_definition(intent_id: str) -> IntentDefinition:
    return INTENT_REGISTRY[intent_id]
