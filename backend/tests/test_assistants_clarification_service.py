"""Tests for analytical clarification templates."""

from app.assistants.clarification_service import (
    build_analytical_guard_clarification,
    build_clarification,
    localize_clarification_message,
)


def test_build_sales_ranking_metric_clarification():
    clarification = build_clarification("sales_ranking_query", ["metric"])

    assert clarification.type == "clarification"
    assert clarification.missing == ["metric"]
    assert "počtu kusů" in clarification.message.cs
    assert "выручке" in clarification.message.ru
    assert "revenue" in clarification.message.en


def test_localize_clarification_message_uses_requested_locale():
    clarification = build_clarification("sales_ranking_query", ["metric", "scope"])

    assert localize_clarification_message(clarification, "cs").startswith("Upřesni")
    assert localize_clarification_message(clarification, "ru").startswith("Пожалуйста")
    assert localize_clarification_message(clarification, "en").startswith("Please")


def test_build_analytical_guard_clarification_for_missing_entity():
    clarification = build_analytical_guard_clarification(reason="missing_entity")

    assert clarification.missing == ["entity"]
    assert "produkt" in clarification.message.cs
    assert "category" in clarification.message.en


def test_build_analytical_guard_clarification_for_unsupported_query():
    clarification = build_analytical_guard_clarification(
        reason="unsupported_query",
        unsupported_reason="Date-range filters are not supported yet.",
    )

    assert clarification.missing == ["supported_query"]
    assert "deterministicky" in clarification.message.cs
    assert "deterministically" in clarification.message.en
