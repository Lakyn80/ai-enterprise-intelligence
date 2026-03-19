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
            "en": "Compare sales performance across all product categories.",
            "cs": "Porovnej výkonnost prodejů napříč všemi kategoriemi produktů.",
            "sk": "Porovnaj výkonnosť predajov naprieč všetkými kategóriami produktov.",
            "ru": "Сравни эффективность продаж по всем категориям продуктов.",
        },
        query_en="Compare the trends and total volumes of Electronics, Groceries, Furniture, Toys and Clothing categories.",
    ),
    PresetQuestion(
        id="a_002",
        translations={
            "en": "Which products should be prioritised for promotional campaigns?",
            "cs": "Které produkty by měly být prioritizovány pro promo kampaně?",
            "sk": "Ktoré produkty by mali byť prioritizované pre promo kampane?",
            "ru": "Какие продукты следует приоритизировать для промо-кампаний?",
        },
        query_en="Which products benefit most from promotions and which have negative promotional lift?",
    ),
    PresetQuestion(
        id="a_003",
        translations={
            "en": "What are the key risk products based on sales volatility?",
            "cs": "Jaké jsou klíčové rizikové produkty na základě volatility prodejů?",
            "sk": "Aké sú kľúčové rizikové produkty na základe volatility predajov?",
            "ru": "Каковы ключевые рискованные продукты на основе волатильности продаж?",
        },
        query_en="Which products have high sales volatility and what is their standard deviation?",
    ),
    PresetQuestion(
        id="a_004",
        translations={
            "en": "Which product categories are growing and which are declining?",
            "cs": "Které kategorie produktů rostou a které klesají?",
            "sk": "Ktoré kategórie produktov rastú a ktoré klesajú?",
            "ru": "Какие категории продуктов растут, а какие снижаются?",
        },
        query_en="Which categories have an increasing trend and which have a decreasing trend?",
    ),
    PresetQuestion(
        id="a_005",
        translations={
            "en": "What is the pricing strategy insight across products?",
            "cs": "Jaké jsou poznatky o cenové strategii napříč produkty?",
            "sk": "Aké sú poznatky o cenovej stratégii naprieč produktmi?",
            "ru": "Каковы выводы о ценовой стратегии по продуктам?",
        },
        query_en="Which product has the highest average price and which has the lowest? Compare P0011, P0017 and P0004.",
    ),
    PresetQuestion(
        id="a_006",
        translations={
            "en": "Which products are underperforming compared to the category average?",
            "cs": "Které produkty zaostávají za průměrem kategorie?",
            "sk": "Ktoré produkty zaostávajú za priemerom kategórie?",
            "ru": "Какие продукты отстают от среднего значения по категории?",
        },
        query_en="Which products have the lowest total sales and lowest average daily sales compared to their category peers?",
    ),
    PresetQuestion(
        id="a_007",
        translations={
            "en": "What seasonal patterns can be identified in the sales data?",
            "cs": "Jaké sezónní vzory lze identifikovat v prodejních datech?",
            "sk": "Aké sezónne vzory možno identifikovať v predajných dátach?",
            "ru": "Какие сезонные закономерности можно выявить в данных о продажах?",
        },
        query_en="When did products reach their peak sales days and what months had highest activity?",
    ),
    PresetQuestion(
        id="a_008",
        translations={
            "en": "Which products have the best sales consistency and are safest for forecasting?",
            "cs": "Které produkty mají nejlepší konzistenci prodejů a jsou nejbezpečnější pro prognózu?",
            "sk": "Ktoré produkty majú najlepšiu konzistenciu predajov a sú najbezpečnejšie na prognózu?",
            "ru": "Какие продукты имеют наилучшую стабильность продаж и наиболее безопасны для прогнозирования?",
        },
        query_en="Which products have the most consistent (lowest std dev) daily sales and lowest volatility?",
    ),
    PresetQuestion(
        id="a_009",
        translations={
            "en": "How effective are promotional activities overall across the portfolio?",
            "cs": "Jak efektivní jsou promo aktivity celkově napříč portfoliem?",
            "sk": "Aké efektívne sú promo aktivity celkovo naprieč portfóliom?",
            "ru": "Насколько эффективны промо-активности в целом по всему портфолио?",
        },
        query_en="Compare promo lift across all products — which have positive, negative, or neutral promotional effect?",
    ),
    PresetQuestion(
        id="a_010",
        translations={
            "en": "Which products have the strongest growth momentum?",
            "cs": "Které produkty mají nejsilnější růstový momentum?",
            "sk": "Ktoré produkty majú najsilnejší rastový momentum?",
            "ru": "Какие продукты имеют наибольший импульс роста?",
        },
        query_en="Which products are showing an increasing 30-day sales trend?",
    ),
    PresetQuestion(
        id="a_011",
        translations={
            "en": "What is the revenue concentration risk across the product portfolio?",
            "cs": "Jaké je riziko koncentrace příjmů napříč portfoliem produktů?",
            "sk": "Aké je riziko koncentrácie príjmov naprieč portfóliom produktov?",
            "ru": "Каков риск концентрации доходов по портфелю продуктов?",
        },
        query_en="Which products account for the highest total sales and what is the gap between the top and bottom performers?",
    ),
    PresetQuestion(
        id="a_012",
        translations={
            "en": "Which category offers the best opportunity for sales growth?",
            "cs": "Která kategorie nabízí nejlepší příležitost pro růst prodejů?",
            "sk": "Ktorá kategória ponúka najlepšiu príležitosť pre rast predajov?",
            "ru": "Какая категория предлагает наилучшие возможности для роста продаж?",
        },
        query_en="Which categories have increasing trends and what are their total volumes compared to stable or declining categories?",
    ),
    PresetQuestion(
        id="a_013",
        translations={
            "en": "What insights can be drawn from minimum sales days?",
            "cs": "Jaké poznatky lze vyvodit z minimálních prodejních dnů?",
            "sk": "Aké poznatky možno vyvodiť z minimálnych predajných dní?",
            "ru": "Какие выводы можно сделать из минимальных дней продаж?",
        },
        query_en="What is the minimum sales day for P0012 and P0002? What does this tell us about demand floor?",
    ),
    PresetQuestion(
        id="a_014",
        translations={
            "en": "How does the Clothing category compare to Electronics in terms of trend and volume?",
            "cs": "Jak se kategorie Clothing porovnává s Electronics z hlediska trendu a objemu?",
            "sk": "Ako sa kategória Clothing porovnáva s Electronics z hľadiska trendu a objemu?",
            "ru": "Как категория Clothing сравнивается с Electronics по тренду и объёму?",
        },
        query_en="Compare the trends of Electronics and Clothing categories including their total volumes.",
    ),
    PresetQuestion(
        id="a_015",
        translations={
            "en": "Which products are most sensitive to price changes?",
            "cs": "Které produkty jsou nejcitlivější na cenové změny?",
            "sk": "Ktoré produkty sú najcitlivejšie na cenové zmeny?",
            "ru": "Какие продукты наиболее чувствительны к изменениям цен?",
        },
        query_en="Which products show the highest and lowest average prices? What is the price range across the portfolio?",
    ),
    PresetQuestion(
        id="a_016",
        translations={
            "en": "What is the overall portfolio health based on trend analysis?",
            "cs": "Jaké je celkové zdraví portfolia na základě analýzy trendů?",
            "sk": "Aké je celkové zdravie portfólia na základe analýzy trendov?",
            "ru": "Каково общее состояние портфеля на основе анализа тенденций?",
        },
        query_en="How many products are in increasing, stable, and decreasing trend? Which products are showing a decreasing trend?",
    ),
    PresetQuestion(
        id="a_017",
        translations={
            "en": "Which Furniture products drive the most category revenue?",
            "cs": "Které produkty Furniture generují největší příjmy kategorie?",
            "sk": "Ktoré produkty Furniture generujú najväčšie príjmy kategórie?",
            "ru": "Какие продукты Furniture обеспечивают наибольший доход категории?",
        },
        query_en="Which products drive the most sales in the Furniture category?",
    ),
    PresetQuestion(
        id="a_018",
        translations={
            "en": "How should inventory be prioritised based on sales performance?",
            "cs": "Jak by měly být zásoby prioritizovány na základě výkonnosti prodejů?",
            "sk": "Ako by mali byť zásoby prioritizované na základe výkonnosti predajov?",
            "ru": "Как следует расставлять приоритеты запасов на основе показателей продаж?",
        },
        query_en="Which products have the highest average daily sales and which have the most consistent demand? Rank by reliability.",
    ),
    PresetQuestion(
        id="a_019",
        translations={
            "en": "What does the data say about the Toys category performance?",
            "cs": "Co říkají data o výkonnosti kategorie Toys?",
            "sk": "Čo hovoria dáta o výkonnosti kategórie Toys?",
            "ru": "Что данные говорят о производительности категории Toys?",
        },
        query_en="What are the top products in the Toys category and what is its overall trend?",
    ),
    PresetQuestion(
        id="a_020",
        translations={
            "en": "Summarise the key performance highlights across the entire product portfolio.",
            "cs": "Shrň klíčové výkonnostní ukazatele napříč celým portfoliem produktů.",
            "sk": "Zhrň kľúčové výkonnostné ukazovatele naprieč celým portfóliom produktov.",
            "ru": "Подведи итоги ключевых показателей эффективности по всему портфелю продуктов.",
        },
        query_en="Which product has the highest total sales, which has the lowest, which has the best promo lift, and which categories are growing vs declining?",
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
