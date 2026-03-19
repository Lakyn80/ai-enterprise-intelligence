"""
RAG Quality Test — 50 questions against the Knowledge Assistant.

Scoring per question (0-5):
  5 = Correct and specific  (all required keywords found)
  4 = Mostly correct        (≥75% keywords found)
  3 = Partially correct     (≥50% keywords found)
  2 = Vague / incomplete    (≥25% keywords found)
  1 = Wrong / irrelevant    (<25% keywords found)
  0 = "not enough info" returned when answer exists

Each question has:
  - question:     the query
  - kw_required:  keywords the correct answer MUST contain (case-insensitive)
  - kw_any:       at least one of these should appear  (optional boost)
  - expect_no_info: True if "not enough information" is the correct answer
"""

import asyncio
import json
import sys
from datetime import datetime

# ── ground-truth from DB ──────────────────────────────────────────────────────
# Products: P0001-P0020, data 2022-01-01 → 2024-01-01 (731 days)
# Highest total sales:    P0016 (508 472) / P0014 (507 622) / P0020 (507 708)
# Lowest total sales:     P0002 (487 827) / P0008 (488 563)
# Increasing trend prods: P0002, P0008, P0009
# Decreasing trend prods: P0001, P0012, P0015, P0018
# Best promo lift:        P0002 (+13.9%), P0001 (+12.9%)
# Negative promo:         P0013 (-9.6%), P0012 (-9.2%)
# Most expensive avg px:  P0011 (50.89), P0004 (50.16)
# Cheapest avg px:        P0017 (48.50)
# Single-day peak max:    P0007 (1 766 units 2022-04-30)
# Single-day min lowest:  P0012 (61 units)
# Categories (5): Electronics, Groceries, Furniture, Toys, Clothing
# Increasing cat trend:   Electronics, Groceries
# Decreasing cat trend:   Toys, Clothing
# Stable cat trend:       Furniture
# Highest cat total:      Furniture (2 016 166)
# Lowest cat total:       Clothing (1 979 474)
# Top Groceries products: P0001, P0013, P0009
# Top Electronics products: P0007, P0016, P0020
# Top Furniture products: P0012, P0008, P0018
# Top Toys products:      P0011, P0019, P0020
# Top Clothing products:  P0002, P0014, P0018

QUESTIONS = [
    # ── CATEGORY TREND ────────────────────────────────────────────────────────
    {
        "id": 1,
        "group": "category_trend",
        "question": "Which categories have an increasing sales trend?",
        "kw_required": ["electronics", "groceries"],
        "kw_any": ["increasing"],
    },
    {
        "id": 2,
        "group": "category_trend",
        "question": "Which category has a decreasing trend?",
        "kw_required": ["toys"],
        "kw_any": ["clothing", "decreasing"],
    },
    {
        "id": 3,
        "group": "category_trend",
        "question": "What is the 30-day sales trend for the Furniture category?",
        "kw_required": ["furniture", "stable"],
        "kw_any": [],
    },
    {
        "id": 4,
        "group": "category_trend",
        "question": "Is the Groceries category growing or shrinking?",
        "kw_required": ["groceries", "increasing"],
        "kw_any": ["growing", "positive"],
    },
    {
        "id": 5,
        "group": "category_trend",
        "question": "Compare the trends of Electronics and Clothing categories.",
        "kw_required": ["electronics", "clothing"],
        "kw_any": ["increasing", "decreasing"],
    },

    # ── CATEGORY VOLUME ───────────────────────────────────────────────────────
    {
        "id": 6,
        "group": "category_volume",
        "question": "Which category has the highest total sales volume?",
        "kw_required": ["furniture"],
        "kw_any": ["2,016,166", "2016166", "highest"],
    },
    {
        "id": 7,
        "group": "category_volume",
        "question": "Which category has the lowest total sales?",
        "kw_required": ["clothing"],
        "kw_any": ["1,979,474", "lowest"],
    },
    {
        "id": 8,
        "group": "category_volume",
        "question": "How many units did the Toys category sell in total?",
        "kw_required": ["toys", "2,003,435"],
        "kw_any": [],
    },
    {
        "id": 9,
        "group": "category_volume",
        "question": "What is the average daily sales for Electronics?",
        "kw_required": ["electronics", "2769"],
        "kw_any": ["units/day"],
    },
    {
        "id": 10,
        "group": "category_volume",
        "question": "What are the top products in the Groceries category?",
        "kw_required": ["groceries", "p0001"],
        "kw_any": ["p0013", "p0009"],
    },

    # ── PRODUCT VOLUME ────────────────────────────────────────────────────────
    {
        "id": 11,
        "group": "product_volume",
        "question": "Which product has the highest total sales?",
        "kw_required": ["p0016"],
        "kw_any": ["508", "highest"],
    },
    {
        "id": 12,
        "group": "product_volume",
        "question": "Which product has the lowest total sales?",
        "kw_required": ["p0002"],
        "kw_any": ["487", "lowest"],
    },
    {
        "id": 13,
        "group": "product_volume",
        "question": "What is the total sales of product P0005?",
        "kw_required": ["p0005", "503,648"],
        "kw_any": ["503648"],
    },
    {
        "id": 14,
        "group": "product_volume",
        "question": "How many units per day does P0014 sell on average?",
        "kw_required": ["p0014", "694"],
        "kw_any": ["units/day"],
    },
    {
        "id": 15,
        "group": "product_volume",
        "question": "What was the peak sales day for P0007 and how many units?",
        "kw_required": ["p0007", "1,766"],
        "kw_any": ["1766", "april", "2022-04-30"],
    },

    # ── PRODUCT TREND ─────────────────────────────────────────────────────────
    {
        "id": 16,
        "group": "product_trend",
        "question": "Which products have an increasing 30-day sales trend?",
        "kw_required": ["p0002", "p0008"],
        "kw_any": ["p0009", "increasing"],
    },
    {
        "id": 17,
        "group": "product_trend",
        "question": "Is P0001 trending up or down?",
        "kw_required": ["p0001", "decreasing"],
        "kw_any": ["down", "declining"],
    },
    {
        "id": 18,
        "group": "product_trend",
        "question": "What is the sales trend for P0009?",
        "kw_required": ["p0009", "increasing"],
        "kw_any": [],
    },
    {
        "id": 19,
        "group": "product_trend",
        "question": "Which products are showing a decreasing trend?",
        "kw_required": ["p0012", "p0015"],
        "kw_any": ["p0001", "p0018", "decreasing"],
    },
    {
        "id": 20,
        "group": "product_trend",
        "question": "Is P0016 trending up, down, or stable?",
        "kw_required": ["p0016", "stable"],
        "kw_any": [],
    },

    # ── PROMO ANALYSIS ────────────────────────────────────────────────────────
    {
        "id": 21,
        "group": "promo",
        "question": "Which product benefits the most from promotions?",
        "kw_required": ["p0002"],
        "kw_any": ["13", "13.9", "lift"],
    },
    {
        "id": 22,
        "group": "promo",
        "question": "What is the promo lift for P0001?",
        "kw_required": ["p0001", "12.9"],
        "kw_any": ["12", "lift"],
    },
    {
        "id": 23,
        "group": "promo",
        "question": "Which products have a negative promotional lift?",
        "kw_required": ["p0013"],
        "kw_any": ["p0012", "p0016", "negative"],
    },
    {
        "id": 24,
        "group": "promo",
        "question": "Does P0006 sell more units during promotions?",
        "kw_required": ["p0006"],
        "kw_any": ["6.0", "+6", "yes", "higher", "more"],
    },
    {
        "id": 25,
        "group": "promo",
        "question": "What is the promotion effectiveness of P0013?",
        "kw_required": ["p0013", "-9.6"],
        "kw_any": ["negative", "worse", "lower"],
    },

    # ── VOLATILITY & RISK ─────────────────────────────────────────────────────
    {
        "id": 26,
        "group": "volatility",
        "question": "Which products have moderate sales volatility?",
        "kw_required": ["moderate"],
        "kw_any": [],
    },
    {
        "id": 27,
        "group": "volatility",
        "question": "What is the sales volatility level of P0005?",
        "kw_required": ["p0005", "moderate"],
        "kw_any": ["232", "std"],
    },
    {
        "id": 28,
        "group": "volatility",
        "question": "Which product has the most consistent (lowest std dev) daily sales?",
        "kw_required": ["p0002"],
        "kw_any": ["229", "consistent", "lowest"],
    },
    {
        "id": 29,
        "group": "volatility",
        "question": "What is the minimum sales day for P0012?",
        "kw_required": ["p0012", "61"],
        "kw_any": ["minimum", "units"],
    },
    {
        "id": 30,
        "group": "volatility",
        "question": "What was the minimum sales day recorded for P0002?",
        "kw_required": ["p0002", "206"],
        "kw_any": ["minimum"],
    },

    # ── PRICE ANALYSIS ────────────────────────────────────────────────────────
    {
        "id": 31,
        "group": "price",
        "question": "Which product has the highest average price?",
        "kw_required": ["p0011"],
        "kw_any": ["50.89", "highest", "expensive"],
    },
    {
        "id": 32,
        "group": "price",
        "question": "Which product has the lowest average price?",
        "kw_required": ["p0017"],
        "kw_any": ["48.50", "cheapest", "lowest"],
    },
    {
        "id": 33,
        "group": "price",
        "question": "What is the average price for P0004?",
        "kw_required": ["p0004", "50.16"],
        "kw_any": [],
    },
    {
        "id": 34,
        "group": "price",
        "question": "What is the average selling price of P0020?",
        "kw_required": ["p0020", "50.09"],
        "kw_any": [],
    },
    {
        "id": 35,
        "group": "price",
        "question": "Is P0017 more or less expensive than P0011?",
        "kw_required": ["p0017", "p0011"],
        "kw_any": ["cheaper", "less expensive", "lower", "48", "50"],
    },

    # ── CATEGORY TOP PRODUCTS ─────────────────────────────────────────────────
    {
        "id": 36,
        "group": "category_top",
        "question": "What are the top 3 products by volume in the Toys category?",
        "kw_required": ["p0011", "p0019"],
        "kw_any": ["p0020", "toys"],
    },
    {
        "id": 37,
        "group": "category_top",
        "question": "Which products lead the Electronics category?",
        "kw_required": ["electronics", "p0007"],
        "kw_any": ["p0016", "p0020"],
    },
    {
        "id": 38,
        "group": "category_top",
        "question": "Who are the top sellers in the Clothing category?",
        "kw_required": ["clothing", "p0002"],
        "kw_any": ["p0014", "p0018"],
    },
    {
        "id": 39,
        "group": "category_top",
        "question": "Which products drive the most sales in Furniture?",
        "kw_required": ["furniture", "p0012"],
        "kw_any": ["p0008", "p0018"],
    },
    {
        "id": 40,
        "group": "category_top",
        "question": "What is the number of unique products in the Groceries category?",
        "kw_required": ["groceries", "20"],
        "kw_any": ["products"],
    },

    # ── DATE & TIMEFRAME ──────────────────────────────────────────────────────
    {
        "id": 41,
        "group": "dates",
        "question": "What date range does the sales data cover?",
        "kw_required": ["2022", "2024"],
        "kw_any": ["january", "01-01"],
    },
    {
        "id": 42,
        "group": "dates",
        "question": "How many days of sales data are available for P0001?",
        "kw_required": ["731"],
        "kw_any": ["days"],
    },
    {
        "id": 43,
        "group": "dates",
        "question": "When did P0012 reach its peak sales?",
        "kw_required": ["p0012", "2023"],
        "kw_any": ["september", "09", "1,713", "1713"],
    },
    {
        "id": 44,
        "group": "dates",
        "question": "What was P0018's peak sales date and volume?",
        "kw_required": ["p0018", "1,640"],
        "kw_any": ["2023", "1640", "may"],
    },
    {
        "id": 45,
        "group": "dates",
        "question": "When did P0005 hit its peak sales day?",
        "kw_required": ["p0005", "2022-11-27"],
        "kw_any": ["november", "1,456", "1456"],
    },

    # ── OUT-OF-SCOPE (should say not enough info) ─────────────────────────────
    {
        "id": 46,
        "group": "out_of_scope",
        "question": "What will be the forecasted demand for P0001 next month?",
        "kw_required": [],
        "kw_any": [],
        "expect_no_info": True,
    },
    {
        "id": 47,
        "group": "out_of_scope",
        "question": "What is the weather forecast for next week?",
        "kw_required": [],
        "kw_any": [],
        "expect_no_info": True,
    },
    {
        "id": 48,
        "group": "out_of_scope",
        "question": "Which competitor has the best pricing strategy?",
        "kw_required": [],
        "kw_any": [],
        "expect_no_info": True,
    },
    {
        "id": 49,
        "group": "out_of_scope",
        "question": "What is the profit margin for P0005?",
        "kw_required": [],
        "kw_any": [],
        "expect_no_info": True,
    },
    {
        "id": 50,
        "group": "out_of_scope",
        "question": "Which new products should we launch next quarter?",
        "kw_required": [],
        "kw_any": [],
        "expect_no_info": True,
    },
]


def score_answer(answer: str, q: dict) -> tuple[int, str]:
    """Return (score 0-5, reason)."""
    a_lower = answer.lower()

    no_info_phrases = [
        "not enough information",
        "don't contain enough",
        "do not contain enough",
        "excerpts don't",
        "no information",
        "cannot determine",
        "not available",
        "unable to",
        "not provided",
    ]
    said_no_info = any(p in a_lower for p in no_info_phrases)

    # Out-of-scope questions
    if q.get("expect_no_info"):
        if said_no_info:
            return 5, "correctly declined (no info)"
        # If it still gave a somewhat relevant refusal or general answer
        if len(answer) < 200:
            return 3, "short answer but didn't clearly decline"
        return 1, "answered out-of-scope question instead of declining"

    # In-scope questions — penalise if model declined
    if said_no_info and q.get("kw_required"):
        return 0, "said 'not enough info' but answer exists in data"

    required = q.get("kw_required", [])
    any_kw = q.get("kw_any", [])

    found_required = [kw for kw in required if kw.lower() in a_lower]
    found_any = any(kw.lower() in a_lower for kw in any_kw) if any_kw else True

    if not required:
        return 3, "no required keywords defined"

    ratio = len(found_required) / len(required)
    missing = [kw for kw in required if kw.lower() not in a_lower]

    if ratio == 1.0 and found_any:
        return 5, "all keywords found"
    if ratio == 1.0:
        return 4, f"required keywords found but missing any-keyword bonus"
    if ratio >= 0.75:
        return 4, f"missing: {missing}"
    if ratio >= 0.50:
        return 3, f"missing: {missing}"
    if ratio >= 0.25:
        return 2, f"missing: {missing}"
    return 1, f"missing all required: {missing}"


async def run_tests():
    from app.knowledge_rag.service import KnowledgeService

    svc = KnowledgeService()
    results = []

    print(f"\n{'='*70}")
    print(f"  RAG QUALITY TEST — {len(QUESTIONS)} questions")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")

    for i, q in enumerate(QUESTIONS, 1):
        print(f"[{i:02d}/{len(QUESTIONS)}] {q['question'][:65]}", end="", flush=True)
        try:
            resp = await svc.query(q["question"])
            answer = resp.get("answer", "")
        except Exception as e:
            answer = f"ERROR: {e}"

        score, reason = score_answer(answer, q)
        results.append({**q, "answer": answer, "score": score, "reason": reason})

        bar = "█" * score + "░" * (5 - score)
        print(f"  [{bar}] {score}/5  {reason}")

    # ── Summary ──────────────────────────────────────────────────────────────
    total = sum(r["score"] for r in results)
    max_total = len(results) * 5
    pct = total / max_total * 100

    print(f"\n{'='*70}")
    print(f"  OVERALL SCORE: {total}/{max_total}  ({pct:.1f}%)")
    print(f"{'='*70}")

    # Per-group breakdown
    groups: dict[str, list] = {}
    for r in results:
        groups.setdefault(r["group"], []).append(r["score"])
    print("\n  Per-category breakdown:")
    for grp, scores in sorted(groups.items()):
        g_total = sum(scores)
        g_max = len(scores) * 5
        g_pct = g_total / g_max * 100
        bar = "█" * round(g_pct / 20) + "░" * (5 - round(g_pct / 20))
        print(f"    {grp:<20} [{bar}] {g_total}/{g_max}  ({g_pct:.0f}%)")

    # Score distribution
    dist = {i: sum(1 for r in results if r["score"] == i) for i in range(6)}
    print("\n  Score distribution:")
    for s in range(5, -1, -1):
        bar = "█" * dist[s]
        print(f"    {s}/5  {bar:<20} {dist[s]} questions")

    # Failed questions (score ≤ 2)
    failed = [r for r in results if r["score"] <= 2]
    if failed:
        print(f"\n  LOW-SCORE QUESTIONS (≤2/5) — {len(failed)} total:")
        for r in failed:
            print(f"    [{r['id']:02d}] {r['question'][:55]}")
            print(f"         Score: {r['score']}/5 — {r['reason']}")
            print(f"         Answer: {r['answer'][:120].strip()}")
            print()

    # Save detailed JSON report
    report_path = "/app/scripts/rag_test_results.json"
    with open(report_path, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "total_score": total,
                "max_score": max_total,
                "percent": round(pct, 1),
                "per_group": {
                    grp: {
                        "score": sum(scores),
                        "max": len(scores) * 5,
                        "pct": round(sum(scores) / (len(scores) * 5) * 100, 1),
                    }
                    for grp, scores in groups.items()
                },
                "questions": [
                    {
                        "id": r["id"],
                        "group": r["group"],
                        "question": r["question"],
                        "score": r["score"],
                        "reason": r["reason"],
                        "answer": r["answer"],
                    }
                    for r in results
                ],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"  Full results saved to: {report_path}")
    return pct


if __name__ == "__main__":
    pct = asyncio.run(run_tests())
    sys.exit(0 if pct >= 60 else 1)
