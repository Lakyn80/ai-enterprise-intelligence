"""Tests for analytical intent mapping."""

import pytest

from app.assistants.intent_mapper import detect_analytical_guard, map_analytical_intent


@pytest.mark.parametrize(
    ("query", "locale"),
    [
        ("Jaké produkty mají nejvyšší celkové prodeje?", "cs"),
        ("Which products have the highest total sales?", "en"),
        ("Какие продукты имеют наибольшие общие продажи?", "ru"),
    ],
)
def test_map_top_products_by_total_sales_paraphrases(query: str, locale: str):
    match = map_analytical_intent(query, locale)

    assert match is not None
    assert match.intent.intent_id == "top_products_by_total_sales"
    assert match.parameters["metric"] == "quantity"
    assert match.parameters["scope"] == "list"
    assert match.parameters["limit"] == 5


@pytest.mark.parametrize(
    ("query", "locale"),
    [
        ("Jaké produkty mají nejvyšší tržby?", "cs"),
        ("Which products have the highest revenue?", "en"),
        ("Какие продукты имеют самую высокую выручку?", "ru"),
    ],
)
def test_map_top_products_by_revenue_paraphrases(query: str, locale: str):
    match = map_analytical_intent(query, locale)

    assert match is not None
    assert match.intent.intent_id == "top_products_by_revenue"
    assert match.parameters["metric"] == "revenue"
    assert match.parameters["scope"] == "list"
    assert match.parameters["limit"] == 5


@pytest.mark.parametrize(
    ("query", "locale", "scope"),
    [
        ("jaké produkty maji nejvyšší prodej?", "cs", "list"),
        ("Which product has the highest sales?", "en", "top_1"),
        ("Какие продукты имеют самые высокие продажи?", "ru", "list"),
    ],
)
def test_map_ambiguous_sales_ranking_queries(query: str, locale: str, scope: str):
    match = map_analytical_intent(query, locale)

    assert match is not None
    assert match.intent.intent_id == "sales_ranking_query"
    assert match.parameters["metric"] is None
    assert match.parameters["scope"] == scope


def test_map_existing_fact_query_to_canonical_intent():
    match = map_analytical_intent("Which product sells the most?", "en")

    assert match is not None
    assert match.intent.intent_id == "top_product_by_quantity"
    assert match.parameters["metric"] == "quantity"
    assert match.parameters["direction"] == "desc"


@pytest.mark.parametrize(
    ("query", "locale"),
    [
        ("Který produkt nejvíce těží z akcí?", "cs"),
        ("co nejvíce těží z akcí?", "cs"),
        ("Which product benefits the most from promotions?", "en"),
        ("What benefits the most from promotions?", "en"),
        ("Что больше всего выигрывает от акций?", "ru"),
    ],
)
def test_map_promo_lift_paraphrases_to_same_canonical_intent(query: str, locale: str):
    match = map_analytical_intent(query, locale)

    assert match is not None
    assert match.intent.intent_id == "top_product_by_promo_lift"
    assert match.parameters["metric"] == "promo_lift"
    assert match.parameters["direction"] == "desc"


def test_map_existing_date_range_query_to_canonical_intent():
    match = map_analytical_intent("Какой диапазон дат покрывают данные о продажах?", "ru")

    assert match is not None
    assert match.intent.intent_id == "sales_data_date_range"


@pytest.mark.parametrize(
    "query",
    [
        "Jaký časový rozsah pokrývají prodejní data?",
        "odkdy dokdy jsou prodejní data?",
        "odkdy dokdy jsou prodejní data v tomto reportu?",
        "odkdy do kdy jsou data?",
        "v jakém období jsou prodejní data?",
        "jaký časový rozsah mají data?",
    ],
)
def test_map_czech_date_range_paraphrases_to_canonical_intent(query: str):
    match = map_analytical_intent(query, "cs")

    assert match is not None
    assert match.intent.intent_id == "sales_data_date_range"


def test_detect_analytical_guard_for_missing_entity():
    guard = detect_analytical_guard("What has the highest revenue?", "en")

    assert guard is not None
    assert guard.reason == "missing_entity"


def test_detect_analytical_guard_for_unsupported_category_query():
    guard = detect_analytical_guard("Which category has the highest revenue?", "en")

    assert guard is not None
    assert guard.reason == "unsupported_query"
    assert guard.unsupported_reason is not None
