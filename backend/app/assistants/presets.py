"""
Preset questions registry for both assistants.

Each question has:
  - id:           stable language-independent identifier
  - translations: dict with EN / CS / SK / RU text
  - query_en:     canonical English query sent to the RAG/LLM backend
                  (may differ from displayed text to improve retrieval)
"""

from typing import Literal

Locale = Literal["en", "cs", "sk", "ru"]
AssistantType = Literal["knowledge", "analyst"]


class PresetQuestion:
    __slots__ = ("id", "translations", "query_en")

    def __init__(self, id: str, translations: dict[str, str], query_en: str | None = None):
        self.id = id
        self.translations = translations
        # If query_en not supplied, fall back to EN translation
        self.query_en = query_en or translations["en"]

    def text(self, locale: Locale = "en") -> str:
        return self.translations.get(locale, self.translations["en"])

    def to_dict(self, locale: Locale = "en") -> dict:
        return {"id": self.id, "text": self.text(locale)}


# ---------------------------------------------------------------------------
# Knowledge Assistant — 20 questions
# Focused on factual retrieval: what IS the data, not analytical reasoning
# ---------------------------------------------------------------------------

KNOWLEDGE_PRESETS: list[PresetQuestion] = [
    PresetQuestion(
        id="k_001",
        translations={
            "en": "Which products have the highest total sales?",
            "cs": "Které produkty mají nejvyšší celkové prodeje?",
            "sk": "Ktoré produkty majú najvyššie celkové predaje?",
            "ru": "Какие продукты имеют наибольшие общие продажи?",
        },
    ),
    PresetQuestion(
        id="k_002",
        translations={
            "en": "Which products have the lowest total sales?",
            "cs": "Které produkty mají nejnižší celkové prodeje?",
            "sk": "Ktoré produkty majú najnižšie celkové predaje?",
            "ru": "Какие продукты имеют наименьшие общие продажи?",
        },
    ),
    PresetQuestion(
        id="k_003",
        translations={
            "en": "Which categories have an increasing sales trend?",
            "cs": "Které kategorie mají rostoucí trend prodejů?",
            "sk": "Ktoré kategórie majú rastúci trend predajov?",
            "ru": "Какие категории имеют растущую тенденцию продаж?",
        },
    ),
    PresetQuestion(
        id="k_004",
        translations={
            "en": "Which categories have a decreasing sales trend?",
            "cs": "Které kategorie mají klesající trend prodejů?",
            "sk": "Ktoré kategórie majú klesajúci trend predajov?",
            "ru": "Какие категории имеют снижающуюся тенденцию продаж?",
        },
    ),
    PresetQuestion(
        id="k_005",
        translations={
            "en": "Which product benefits the most from promotions?",
            "cs": "Který produkt nejvíce těží z akcí?",
            "sk": "Ktorý produkt najviac profituje z akcií?",
            "ru": "Какой продукт получает наибольшую выгоду от акций?",
        },
    ),
    PresetQuestion(
        id="k_006",
        translations={
            "en": "Which products have a negative promotional lift?",
            "cs": "Které produkty mají negativní promo efekt?",
            "sk": "Ktoré produkty majú negatívny promo efekt?",
            "ru": "Какие продукты имеют отрицательный эффект от акций?",
        },
    ),
    PresetQuestion(
        id="k_007",
        translations={
            "en": "Which product has the highest average selling price?",
            "cs": "Který produkt má nejvyšší průměrnou prodejní cenu?",
            "sk": "Ktorý produkt má najvyššiu priemernú predajnú cenu?",
            "ru": "Какой продукт имеет самую высокую среднюю цену продажи?",
        },
    ),
    PresetQuestion(
        id="k_008",
        translations={
            "en": "Which product has the lowest average selling price?",
            "cs": "Který produkt má nejnižší průměrnou prodejní cenu?",
            "sk": "Ktorý produkt má najnižšiu priemernú predajnú cenu?",
            "ru": "Какой продукт имеет самую низкую среднюю цену продажи?",
        },
    ),
    PresetQuestion(
        id="k_009",
        translations={
            "en": "Which product has the most consistent daily sales?",
            "cs": "Který produkt má nejkonzistentnější denní prodeje?",
            "sk": "Ktorý produkt má najkonzistentnejšie denné predaje?",
            "ru": "Какой продукт имеет наиболее стабильные ежедневные продажи?",
        },
        query_en="Which product has the most consistent (lowest std dev) daily sales?",
    ),
    PresetQuestion(
        id="k_010",
        translations={
            "en": "Which product has the highest sales volatility?",
            "cs": "Který produkt má nejvyšší volatilitu prodejů?",
            "sk": "Ktorý produkt má najvyššiu volatilitu predajov?",
            "ru": "Какой продукт имеет наибольшую волатильность продаж?",
        },
    ),
    PresetQuestion(
        id="k_011",
        translations={
            "en": "What are the top products in the Electronics category?",
            "cs": "Jaké jsou nejprodávanější produkty v kategorii Electronics?",
            "sk": "Aké sú najpredávanejšie produkty v kategórii Electronics?",
            "ru": "Каковы лучшие продукты в категории Electronics?",
        },
    ),
    PresetQuestion(
        id="k_012",
        translations={
            "en": "What are the top products in the Groceries category?",
            "cs": "Jaké jsou nejprodávanější produkty v kategorii Groceries?",
            "sk": "Aké sú najpredávanejšie produkty v kategórii Groceries?",
            "ru": "Каковы лучшие продукты в категории Groceries?",
        },
    ),
    PresetQuestion(
        id="k_013",
        translations={
            "en": "What are the top products in the Furniture category?",
            "cs": "Jaké jsou nejprodávanější produkty v kategorii Furniture?",
            "sk": "Aké sú najpredávanejšie produkty v kategórii Furniture?",
            "ru": "Каковы лучшие продукты в категории Furniture?",
        },
    ),
    PresetQuestion(
        id="k_014",
        translations={
            "en": "Which category has the highest total sales volume?",
            "cs": "Která kategorie má nejvyšší celkový objem prodejů?",
            "sk": "Ktorá kategória má najvyšší celkový objem predajov?",
            "ru": "Какая категория имеет наибольший общий объём продаж?",
        },
    ),
    PresetQuestion(
        id="k_015",
        translations={
            "en": "What date range does the sales data cover?",
            "cs": "Jaký časový rozsah pokrývají prodejní data?",
            "sk": "Aký časový rozsah pokrývajú predajné dáta?",
            "ru": "Какой временной диапазон охватывают данные о продажах?",
        },
    ),
    PresetQuestion(
        id="k_016",
        translations={
            "en": "Which products are showing a decreasing 30-day trend?",
            "cs": "Které produkty vykazují klesající 30denní trend?",
            "sk": "Ktoré produkty vykazujú klesajúci 30-dňový trend?",
            "ru": "Какие продукты показывают снижающуюся 30-дневную тенденцию?",
        },
    ),
    PresetQuestion(
        id="k_017",
        translations={
            "en": "Which products are showing an increasing 30-day trend?",
            "cs": "Které produkty vykazují rostoucí 30denní trend?",
            "sk": "Ktoré produkty vykazujú rastúci 30-dňový trend?",
            "ru": "Какие продукты показывают растущую 30-дневную тенденцию?",
        },
    ),
    PresetQuestion(
        id="k_018",
        translations={
            "en": "What was the peak sales day for the best-performing product?",
            "cs": "Kdy byl rekordní den prodejů pro nejlepší produkt?",
            "sk": "Kedy bol rekordný deň predajov pre najlepší produkt?",
            "ru": "Когда был рекордный день продаж для лучшего продукта?",
        },
        query_en="What was the peak sales day for P0007 and how many units were sold?",
    ),
    PresetQuestion(
        id="k_019",
        translations={
            "en": "Compare the sales trends of Electronics and Clothing categories.",
            "cs": "Porovnej trendy prodejů kategorií Electronics a Clothing.",
            "sk": "Porovnaj trendy predajov kategórií Electronics a Clothing.",
            "ru": "Сравни тенденции продаж категорий Electronics и Clothing.",
        },
    ),
    PresetQuestion(
        id="k_020",
        translations={
            "en": "How many unique products are tracked in the dataset?",
            "cs": "Kolik unikátních produktů je sledováno v datasetu?",
            "sk": "Koľko unikátnych produktov je sledovaných v datasete?",
            "ru": "Сколько уникальных продуктов отслеживается в наборе данных?",
        },
        query_en="What is the number of unique products in the Groceries category and how many total products exist?",
    ),
]

# ---------------------------------------------------------------------------
# AI Analyst Assistant — 20 questions
# Focused on interpretation, comparison, reasoning and business insight
# ---------------------------------------------------------------------------

ANALYST_PRESETS: list[PresetQuestion] = [
    PresetQuestion(
        id="a_001",
        translations={
            "en": "Which category has the highest total revenue?",
            "cs": "Která kategorie má nejvyšší celkové příjmy?",
            "sk": "Ktorá kategória má najvyššie celkové príjmy?",
            "ru": "Какая категория имеет наибольшую общую выручку?",
        },
        query_en="Get sales for all products and rank the 5 categories (Electronics, Furniture, Groceries, Clothing, Toys) by total revenue. Use get_all_products_summary from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_002",
        translations={
            "en": "Which products have the highest revenue overall?",
            "cs": "Které produkty mají celkově nejvyšší příjmy?",
            "sk": "Ktoré produkty majú celkovo najvyššie príjmy?",
            "ru": "Какие продукты имеют наибольшую общую выручку?",
        },
        query_en="Get the top 5 products by total revenue across all categories. Use get_all_products_summary from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_003",
        translations={
            "en": "Which products have the lowest revenue and may need attention?",
            "cs": "Které produkty mají nejnižší příjmy a mohou potřebovat pozornost?",
            "sk": "Ktoré produkty majú najnižšie príjmy a môžu potrebovať pozornosť?",
            "ru": "Какие продукты имеют наименьшую выручку и требуют внимания?",
        },
        query_en="Get the bottom 5 products by total revenue. Use get_all_products_summary from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_004",
        translations={
            "en": "Which Furniture products drive the most category revenue?",
            "cs": "Které produkty Furniture generují největší příjmy kategorie?",
            "sk": "Ktoré produkty Furniture generujú najväčšie príjmy kategórie?",
            "ru": "Какие продукты Furniture обеспечивают наибольший доход категории?",
        },
        query_en="Get the top products in the Furniture category ranked by revenue. Use get_category_sales for Furniture from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_005",
        translations={
            "en": "Which Electronics products are top performers?",
            "cs": "Které produkty Electronics jsou nejlepší?",
            "sk": "Ktoré produkty Electronics sú najlepšie?",
            "ru": "Какие продукты Electronics лучшие?",
        },
        query_en="Get the top products in the Electronics category ranked by revenue. Use get_category_sales for Electronics from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_006",
        translations={
            "en": "Which Toys products drive the most category revenue?",
            "cs": "Které produkty Toys generují největší příjmy kategorie?",
            "sk": "Ktoré produkty Toys generujú najväčšie príjmy kategórie?",
            "ru": "Какие продукты Toys обеспечивают наибольший доход категории?",
        },
        query_en="Get the top products in the Toys category ranked by revenue. Use get_category_sales for Toys from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_007",
        translations={
            "en": "Which Groceries products generate the most revenue?",
            "cs": "Které produkty Groceries generují nejvíce příjmů?",
            "sk": "Ktoré produkty Groceries generujú najviac príjmov?",
            "ru": "Какие продукты Groceries генерируют наибольшую выручку?",
        },
        query_en="Get the top products in the Groceries category ranked by revenue. Use get_category_sales for Groceries from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_008",
        translations={
            "en": "Which Clothing products are the best sellers?",
            "cs": "Které produkty Clothing jsou nejprodávanější?",
            "sk": "Ktoré produkty Clothing sú najpredávanejšie?",
            "ru": "Какие продукты Clothing продаются лучше всего?",
        },
        query_en="Get the top products in the Clothing category ranked by revenue. Use get_category_sales for Clothing from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_009",
        translations={
            "en": "Which products have the highest average selling price?",
            "cs": "Které produkty mají nejvyšší průměrnou prodejní cenu?",
            "sk": "Ktoré produkty majú najvyššiu priemernú predajnú cenu?",
            "ru": "Какие продукты имеют самую высокую среднюю цену продажи?",
        },
        query_en="Get all products and rank by average price (highest to lowest). Use get_all_products_summary from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_010",
        translations={
            "en": "What is the total quantity sold per category?",
            "cs": "Jaké je celkové prodané množství na kategorii?",
            "sk": "Aké je celkové predané množstvo na kategóriu?",
            "ru": "Каков общий объём продаж по категориям?",
        },
        query_en="Get all products and aggregate total quantity by category. Use get_all_products_summary from 2022-01-01 to 2024-12-31 and sum quantities per category.",
    ),
    PresetQuestion(
        id="a_011",
        translations={
            "en": "Which products benefit most from promotions?",
            "cs": "Které produkty nejvíce těží z promo akcí?",
            "sk": "Ktoré produkty najviac profitujú z promo akcií?",
            "ru": "Какие продукты больше всего выигрывают от акций?",
        },
        query_en="Get all products summary and compare products with high promo_days vs their revenue. Which products had more than 60 promo days? Use get_all_products_summary from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_012",
        translations={
            "en": "Compare revenue between Furniture and Electronics categories.",
            "cs": "Porovnej příjmy kategorií Furniture a Electronics.",
            "sk": "Porovnaj príjmy kategórií Furniture a Electronics.",
            "ru": "Сравни выручку категорий Furniture и Electronics.",
        },
        query_en="Get sales data for Furniture and Electronics categories separately and compare their total revenues, quantities and top products. Use get_category_sales for both from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_013",
        translations={
            "en": "What is the revenue gap between the best and worst performing products?",
            "cs": "Jaký je rozdíl příjmů mezi nejlepším a nejhorším produktem?",
            "sk": "Aký je rozdiel príjmov medzi najlepším a najhorším produktom?",
            "ru": "Какова разница в выручке между лучшим и худшим продуктом?",
        },
        query_en="Get all products ranked by total revenue. Show the #1 and last-place product and calculate the revenue gap. Use get_all_products_summary from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_014",
        translations={
            "en": "Which products have the highest sales volume (quantity)?",
            "cs": "Které produkty mají nejvyšší objem prodejů (množství)?",
            "sk": "Ktoré produkty majú najvyšší objem predajov (množstvo)?",
            "ru": "Какие продукты имеют наибольший объём продаж (количество)?",
        },
        query_en="Get all products and rank by total_quantity sold (not revenue). Use get_all_products_summary from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_015",
        translations={
            "en": "How is the revenue distributed across categories (portfolio mix)?",
            "cs": "Jak jsou příjmy distribuovány napříč kategoriemi (portfolio mix)?",
            "sk": "Ako sú príjmy distribuované naprieč kategóriami (portfolio mix)?",
            "ru": "Как распределена выручка по категориям (структура портфеля)?",
        },
        query_en="Get all products, sum revenue per category and calculate each category's % share of total portfolio revenue. Use get_all_products_summary from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_016",
        translations={
            "en": "Which products have average price above $50?",
            "cs": "Které produkty mají průměrnou cenu nad $50?",
            "sk": "Ktoré produkty majú priemernú cenu nad $50?",
            "ru": "Какие продукты имеют среднюю цену выше $50?",
        },
        query_en="Get all products and filter those with avg_price above 50. List them with their category and total revenue. Use get_all_products_summary from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_017",
        translations={
            "en": "Which category has the best revenue per product (efficiency)?",
            "cs": "Která kategorie má nejlepší příjmy na produkt (efektivita)?",
            "sk": "Ktorá kategória má najlepšie príjmy na produkt (efektivita)?",
            "ru": "Какая категория имеет лучшую выручку на продукт (эффективность)?",
        },
        query_en="Get all products, group by category, and calculate average revenue per product in each category. Use get_all_products_summary from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_018",
        translations={
            "en": "What is the total promo impact across the entire product catalog?",
            "cs": "Jaký je celkový dopad promo akcí napříč celým katalogem?",
            "sk": "Aký je celkový dopad promo akcií naprieč celým katalógom?",
            "ru": "Каков общий эффект акций по всему каталогу?",
        },
        query_en="Get all products and sum total promo_days across the catalog. Which category has the most promotional activity? Use get_all_products_summary from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_019",
        translations={
            "en": "Which products should be considered for price optimisation?",
            "cs": "Které produkty by měly být zvažovány pro cenovou optimalizaci?",
            "sk": "Ktoré produkty by mali byť zvažované pre cenovú optimalizáciu?",
            "ru": "Какие продукты следует рассматривать для ценовой оптимизации?",
        },
        query_en="Get all products and identify those with high revenue but low avg_price (potential to increase price) or high avg_price but low quantity (potential overpricing). Use get_all_products_summary from 2022-01-01 to 2024-12-31.",
    ),
    PresetQuestion(
        id="a_020",
        translations={
            "en": "Give a full executive summary of the product portfolio performance.",
            "cs": "Poskytni úplný manažerský přehled výkonnosti portfolia produktů.",
            "sk": "Poskytni úplný manažérsky prehľad výkonnosti portfólia produktov.",
            "ru": "Дай полное управленческое резюме по эффективности портфеля продуктов.",
        },
        query_en="Get a complete portfolio summary: total revenue, top 3 products, weakest 3 products, best category, most promotional activity. Use get_all_products_summary from 2022-01-01 to 2024-12-31.",
    ),
]

# ---------------------------------------------------------------------------
# Unified registry
# ---------------------------------------------------------------------------

PRESETS: dict[str, list[PresetQuestion]] = {
    "knowledge": KNOWLEDGE_PRESETS,
    "analyst": ANALYST_PRESETS,
}


def get_presets(assistant_type: AssistantType) -> list[PresetQuestion]:
    return PRESETS[assistant_type]


def get_preset_by_id(assistant_type: AssistantType, question_id: str) -> PresetQuestion | None:
    for q in PRESETS[assistant_type]:
        if q.id == question_id:
            return q
    return None
