"""Template-based clarification responses for underspecified analytical queries."""

from __future__ import annotations

from app.assistants.schemas import ClarificationMessage, ClarificationOut


def build_clarification(intent_id: str, missing: list[str]) -> ClarificationOut:
    if intent_id == "sales_ranking_query":
        message = _sales_ranking_message(missing)
    else:
        message = _generic_message(missing)
    return ClarificationOut(
        missing=sorted(missing),
        message=ClarificationMessage(**message),
    )


def build_analytical_guard_clarification(
    *,
    reason: str,
    unsupported_reason: str | None = None,
) -> ClarificationOut:
    if reason == "missing_entity":
        missing = ["entity"]
        message = {
            "cs": "Upřesni prosím, myslíš produkt, kategorii nebo něco jiného?",
            "ru": "Пожалуйста, уточни: имеется в виду продукт, категория или что-то другое?",
            "en": "Please clarify whether you mean a product, a category, or something else.",
        }
    else:
        missing = ["supported_query"]
        message = {
            "cs": (
                "Tento analytický dotaz zatím neumím vyřešit deterministicky. "
                "Upřesni prosím jednodušší dotaz na úrovni produktu bez dalších filtrů."
            ),
            "ru": (
                "Этот аналитический запрос пока нельзя обработать детерминированно. "
                "Пожалуйста, уточни более простой запрос на уровне продукта без дополнительных фильтров."
            ),
            "en": (
                "This analytical query cannot be handled deterministically yet. "
                "Please rephrase it as a simpler product-level question without extra filters."
            ),
        }
        if unsupported_reason and "product ranking" in unsupported_reason.lower():
            message = {
                "cs": "Upřesni prosím, myslíš produkt, kategorii nebo něco jiného?",
                "ru": "Пожалуйста, уточни: имеется в виду продукт, категория или что-то другое?",
                "en": "Please clarify whether you mean a product, a category, or something else.",
            }
            missing = ["entity"]

    return ClarificationOut(
        missing=missing,
        message=ClarificationMessage(**message),
    )


def localize_clarification_message(clarification: ClarificationOut, locale: str) -> str:
    messages = clarification.message.model_dump(mode="json")
    return messages.get(locale, messages["en"])


def _sales_ranking_message(missing: list[str]) -> dict[str, str]:
    missing_set = set(missing)
    if missing_set == {"metric"}:
        return {
            "cs": "Mám odpovědět podle počtu kusů, nebo podle tržeb?",
            "ru": "Нужно ответить по количеству проданных единиц или по выручке?",
            "en": "Should I answer by quantity sold or by revenue?",
        }
    if missing_set == {"scope"}:
        return {
            "cs": "Máš na mysli jeden nejlepší produkt, nebo seznam produktů?",
            "ru": "Имеется в виду один лучший продукт или список продуктов?",
            "en": "Do you mean a single top product or a list of products?",
        }
    if missing_set == {"metric", "scope"}:
        return {
            "cs": "Upřesni prosím metriku i rozsah: chceš počet kusů nebo tržby, a jeden produkt nebo seznam produktů?",
            "ru": "Пожалуйста, уточни метрику и масштаб: нужны продажи по количеству или по выручке, и один продукт или список продуктов?",
            "en": "Please clarify both the metric and the scope: do you want quantity sold or revenue, and a single product or a list of products?",
        }
    return _generic_message(missing)


def _generic_message(missing: list[str]) -> dict[str, str]:
    joined = ", ".join(sorted(missing))
    return {
        "cs": f"Dotaz je potřeba upřesnit. Chybí: {joined}.",
        "ru": f"Нужно уточнить запрос. Не хватает параметров: {joined}.",
        "en": f"The query needs clarification. Missing parameters: {joined}.",
    }
