"""Stable locale-aware rendering for deterministic facts answers."""

from __future__ import annotations

from app.assistants.facts.schemas import FactQuerySpec, FactResolveResult


def render_fact_answer(spec: FactQuerySpec, result: FactResolveResult, locale: str) -> str:
    winner_ids = ", ".join(winner.product_id for winner in result.winners)
    value = _format_metric_value(result.metric, result.winners[0].value)
    first_place = result.direction == "desc"

    if result.tie:
        if locale == "cs":
            place = "prvním" if first_place else "posledním"
            return f"Na {place} místě je shoda mezi {winner_ids} ({value})."
        if locale == "sk":
            place = "prvom" if first_place else "poslednom"
            return f"Na {place} mieste je zhoda medzi {winner_ids} ({value})."
        if locale == "ru":
            place = "первом" if first_place else "последнем"
            return f"На {place} месте ничья между {winner_ids} ({value})."
        place = "first" if first_place else "last"
        return f"There is a tie for {place} place between {winner_ids} ({value})."

    product_id = result.winners[0].product_id
    if locale == "cs":
        return _render_czech(spec, product_id, value)
    if locale == "sk":
        return _render_slovak(spec, product_id, value)
    if locale == "ru":
        return _render_russian(spec, product_id, value)
    return _render_english(spec, product_id, value)


def _render_czech(spec: FactQuerySpec, product_id: str, value: str) -> str:
    if spec.metric == "quantity" and spec.direction == "desc":
        return f"Nejprodávanější produkt podle počtu kusů je {product_id} ({value})."
    if spec.metric == "quantity" and spec.direction == "asc":
        return f"Nejméně prodávaný produkt podle počtu kusů je {product_id} ({value})."
    if spec.metric == "revenue" and spec.direction == "desc":
        return f"Produkt s nejvyššími tržbami je {product_id} ({value})."
    if spec.metric == "revenue" and spec.direction == "asc":
        return f"Produkt s nejnižšími tržbami je {product_id} ({value})."
    if spec.metric == "promo_lift" and spec.direction == "desc":
        return f"Produkt, který nejvíce těží z akcí, je {product_id} ({value})."
    if spec.metric == "promo_lift" and spec.direction == "asc":
        return f"Produkt s nejnižším promo efektem je {product_id} ({value})."
    return f"Produkt s nejnižšími tržbami je {product_id} ({value})."


def _render_slovak(spec: FactQuerySpec, product_id: str, value: str) -> str:
    if spec.metric == "quantity" and spec.direction == "desc":
        return f"Najpredávanejší produkt podľa počtu kusov je {product_id} ({value})."
    if spec.metric == "quantity" and spec.direction == "asc":
        return f"Najmenej predávaný produkt podľa počtu kusov je {product_id} ({value})."
    if spec.metric == "revenue" and spec.direction == "desc":
        return f"Produkt s najvyššími tržbami je {product_id} ({value})."
    if spec.metric == "revenue" and spec.direction == "asc":
        return f"Produkt s najnižšími tržbami je {product_id} ({value})."
    if spec.metric == "promo_lift" and spec.direction == "desc":
        return f"Produkt, ktorý najviac profituje z akcií, je {product_id} ({value})."
    if spec.metric == "promo_lift" and spec.direction == "asc":
        return f"Produkt s najnižším promo efektom je {product_id} ({value})."
    return f"Produkt s najnižšími tržbami je {product_id} ({value})."


def _render_russian(spec: FactQuerySpec, product_id: str, value: str) -> str:
    if spec.metric == "quantity" and spec.direction == "desc":
        return f"Самый продаваемый продукт по количеству штук: {product_id} ({value})."
    if spec.metric == "quantity" and spec.direction == "asc":
        return f"Наименее продаваемый продукт по количеству штук: {product_id} ({value})."
    if spec.metric == "revenue" and spec.direction == "desc":
        return f"Продукт с самой высокой выручкой: {product_id} ({value})."
    if spec.metric == "revenue" and spec.direction == "asc":
        return f"Продукт с самой низкой выручкой: {product_id} ({value})."
    if spec.metric == "promo_lift" and spec.direction == "desc":
        return f"Продукт, который больше всего выигрывает от акций: {product_id} ({value})."
    if spec.metric == "promo_lift" and spec.direction == "asc":
        return f"Продукт с самым низким промо-эффектом: {product_id} ({value})."
    return f"Продукт с самой низкой выручкой: {product_id} ({value})."


def _render_english(spec: FactQuerySpec, product_id: str, value: str) -> str:
    if spec.metric == "quantity" and spec.direction == "desc":
        return f"Top product by quantity sold is {product_id} ({value})."
    if spec.metric == "quantity" and spec.direction == "asc":
        return f"Lowest-selling product by quantity is {product_id} ({value})."
    if spec.metric == "revenue" and spec.direction == "desc":
        return f"Product with the highest revenue is {product_id} ({value})."
    if spec.metric == "revenue" and spec.direction == "asc":
        return f"Product with the lowest revenue is {product_id} ({value})."
    if spec.metric == "promo_lift" and spec.direction == "desc":
        return f"Product benefiting the most from promotions is {product_id} ({value})."
    if spec.metric == "promo_lift" and spec.direction == "asc":
        return f"Product with the lowest promotional lift is {product_id} ({value})."
    return f"Product with the lowest revenue is {product_id} ({value})."


def _format_metric_value(metric: str, value: float) -> str:
    if metric == "quantity":
        if float(value).is_integer():
            return f"{int(value)} ks"
        return f"{value:.2f} ks"
    if metric == "promo_lift":
        return f"{value:+.1f}%"
    return f"{value:.2f}"
