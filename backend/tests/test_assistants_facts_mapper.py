"""Tests for deterministic facts query mapping."""

import pytest

from app.assistants.facts.mapper import map_fact_query


TOP_QUANTITY_PARAPHRASES = [
    "Který produkt se prodává nejvíc?",
    "Jaký je nejprodávanější produkt?",
    "Který produkt má nejvyšší počet prodaných kusů?",
    "Ktery produkt se prodava nejvic",
    "Ktery produkt ma nejvyssi pocet prodanych kusu",
    "Which product sells the most?",
    "Which product has the highest number of units sold?",
    "What is the best selling product?",
    "Top product by quantity?",
    "Which product is the most sold?",
]

TOP_REVENUE_PARAPHRASES = [
    "Který produkt má nejvyšší tržby?",
    "Jaký produkt generuje nejvyšší tržby?",
    "Který produkt utrží nejvíc?",
    "Ktery produkt ma nejvyssi trzby",
    "Produkt s nejvetsimi trzby",
    "Which product has the highest revenue?",
    "Which product generates the most revenue?",
    "Top product by revenue?",
    "What product makes the most revenue?",
    "Which product earns the most revenue?",
]

BOTTOM_QUANTITY_PARAPHRASES = [
    "Který produkt se prodává nejmíň?",
    "Jaký je nejméně prodávaný produkt?",
    "Který produkt má nejnižší počet prodaných kusů?",
    "Ktery produkt se prodava nejmin",
    "Ktery produkt ma nejnizsi pocet prodanych kusu",
    "Which product sells the least?",
    "Which product has the lowest quantity sold?",
    "Least selling product?",
    "Bottom product by quantity?",
    "Which product is sold the least?",
]

BOTTOM_REVENUE_PARAPHRASES = [
    "Který produkt má nejnižší tržby?",
    "Jaký produkt generuje nejnižší tržby?",
    "Který produkt utrží nejmíň?",
    "Ktery produkt ma nejnizsi trzby",
    "Produkt s nejmensimi trzby",
    "Which product has the lowest revenue?",
    "Which product generates the least revenue?",
    "Bottom product by revenue?",
    "What product makes the least revenue?",
    "Which product earns the least revenue?",
]

TOP_PROMO_LIFT_PARAPHRASES = [
    "Který produkt nejvíce těží z akcí?",
    "Který produkt nejvíce těží z promo akcí?",
    "Který produkt má nejvyšší promo efekt?",
    "Který produkt má nejvyšší promo lift?",
    "Ktery produkt nejvice tezi z akci",
    "Which product benefits the most from promotions?",
    "Which product gains the most from promotions?",
    "Which product has the highest promo lift?",
]


@pytest.mark.parametrize("query", TOP_QUANTITY_PARAPHRASES)
def test_map_top_quantity_paraphrases(query: str):
    mapping = map_fact_query(query)
    assert mapping.matched is True
    assert mapping.unsupported_reason is None
    assert mapping.spec is not None
    assert mapping.spec.metric == "quantity"
    assert mapping.spec.direction == "desc"


@pytest.mark.parametrize("query", TOP_REVENUE_PARAPHRASES)
def test_map_top_revenue_paraphrases(query: str):
    mapping = map_fact_query(query)
    assert mapping.matched is True
    assert mapping.unsupported_reason is None
    assert mapping.spec is not None
    assert mapping.spec.metric == "revenue"
    assert mapping.spec.direction == "desc"


@pytest.mark.parametrize("query", BOTTOM_QUANTITY_PARAPHRASES)
def test_map_bottom_quantity_paraphrases(query: str):
    mapping = map_fact_query(query)
    assert mapping.matched is True
    assert mapping.unsupported_reason is None
    assert mapping.spec is not None
    assert mapping.spec.metric == "quantity"
    assert mapping.spec.direction == "asc"


@pytest.mark.parametrize("query", BOTTOM_REVENUE_PARAPHRASES)
def test_map_bottom_revenue_paraphrases(query: str):
    mapping = map_fact_query(query)
    assert mapping.matched is True
    assert mapping.unsupported_reason is None
    assert mapping.spec is not None
    assert mapping.spec.metric == "revenue"
    assert mapping.spec.direction == "asc"


def test_same_family_maps_to_same_canonical_spec():
    spec_hashes = {
        map_fact_query(query).spec.spec_hash()  # type: ignore[union-attr]
        for query in TOP_QUANTITY_PARAPHRASES
    }
    assert len(spec_hashes) == 1


@pytest.mark.parametrize("query", TOP_PROMO_LIFT_PARAPHRASES)
def test_map_top_promo_lift_paraphrases(query: str):
    mapping = map_fact_query(query)
    assert mapping.matched is True
    assert mapping.unsupported_reason is None
    assert mapping.spec is not None
    assert mapping.spec.metric == "promo_lift"
    assert mapping.spec.direction == "desc"


def test_mapper_marks_unsupported_category_filter():
    mapping = map_fact_query("Který produkt má nejvyšší tržby v kategorii Furniture?")
    assert mapping.matched is True
    assert mapping.unsupported_reason == "Category filters are not supported yet."
