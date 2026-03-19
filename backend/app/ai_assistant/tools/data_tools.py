"""Tools for AI assistant to fetch historical data from DB."""

from datetime import date
from typing import Any


async def get_sales_summary(
    forecasting_repo: Any,
    product_id: str,
    from_date: date,
    to_date: date,
) -> dict[str, Any]:
    """Fetch aggregated sales summary from DB for a single product."""
    df = await forecasting_repo.get_sales_df(from_date, to_date, [product_id])
    if df.empty:
        return {
            "product_id": product_id,
            "from_date": str(from_date),
            "to_date": str(to_date),
            "total_quantity": 0,
            "total_revenue": 0,
            "avg_price": 0,
            "promo_days": 0,
            "message": "No data found",
        }
    total_qty = float(df["quantity"].sum())
    total_rev = float(df["revenue"].sum())
    avg_price = float(df["price"].mean()) if "price" in df.columns else 0
    promo_days = int((df["promo_flag"] == 1).sum()) if "promo_flag" in df.columns else 0
    return {
        "product_id": product_id,
        "from_date": str(from_date),
        "to_date": str(to_date),
        "total_quantity": total_qty,
        "total_revenue": total_rev,
        "avg_price": avg_price,
        "promo_days": promo_days,
        "row_count": len(df),
    }


async def get_category_sales(
    forecasting_repo: Any,
    category: str,
    from_date: date,
    to_date: date,
) -> dict[str, Any]:
    """Fetch sales aggregated by product for a given category. Returns per-product breakdown sorted by revenue."""
    df = await forecasting_repo.get_sales_df(from_date, to_date)
    if df.empty:
        return {"category": category, "products": [], "message": "No data found"}

    cat_df = df[df["category_id"].str.lower() == category.lower()] if "category_id" in df.columns else df
    if cat_df.empty:
        available = sorted(df["category_id"].dropna().unique().tolist()) if "category_id" in df.columns else []
        return {"category": category, "products": [], "message": f"No data for category '{category}'. Available: {available}"}

    grouped = (
        cat_df.groupby("product_id")
        .agg(
            total_quantity=("quantity", "sum"),
            total_revenue=("revenue", "sum"),
            avg_price=("price", "mean"),
            promo_days=("promo_flag", lambda x: int((x == 1).sum())),
        )
        .reset_index()
        .sort_values("total_revenue", ascending=False)
    )

    products = [
        {
            "product_id": row["product_id"],
            "total_revenue": round(float(row["total_revenue"]), 2),
            "total_quantity": int(row["total_quantity"]),
            "avg_price": round(float(row["avg_price"]), 2),
            "promo_days": int(row["promo_days"]),
        }
        for _, row in grouped.iterrows()
    ]

    return {
        "category": category,
        "from_date": str(from_date),
        "to_date": str(to_date),
        "total_revenue": round(float(cat_df["revenue"].sum()), 2),
        "total_quantity": int(cat_df["quantity"].sum()),
        "product_count": len(products),
        "products_by_revenue": products,
    }


async def get_all_products_summary(
    forecasting_repo: Any,
    from_date: date,
    to_date: date,
) -> dict[str, Any]:
    """Fetch sales summary for ALL products grouped by product and category. Use for comparisons, rankings, trends across all products."""
    df = await forecasting_repo.get_sales_df(from_date, to_date)
    if df.empty:
        return {"products": [], "message": "No data found"}

    grouped = (
        df.groupby(["product_id", "category_id"] if "category_id" in df.columns else ["product_id"])
        .agg(
            total_quantity=("quantity", "sum"),
            total_revenue=("revenue", "sum"),
            avg_price=("price", "mean"),
            promo_days=("promo_flag", lambda x: int((x == 1).sum())),
            days_with_data=("quantity", "count"),
        )
        .reset_index()
        .sort_values("total_revenue", ascending=False)
    )

    products = []
    for _, row in grouped.iterrows():
        entry: dict[str, Any] = {
            "product_id": row["product_id"],
            "total_revenue": round(float(row["total_revenue"]), 2),
            "total_quantity": int(row["total_quantity"]),
            "avg_price": round(float(row["avg_price"]), 2),
            "promo_days": int(row["promo_days"]),
            "days_with_data": int(row["days_with_data"]),
        }
        if "category_id" in row:
            entry["category"] = row["category_id"]
        products.append(entry)

    return {
        "from_date": str(from_date),
        "to_date": str(to_date),
        "total_products": len(products),
        "products_by_revenue": products,
    }


def get_data_tools_spec() -> list[dict[str, Any]]:
    """OpenAI-compatible tools schema for data."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_sales_summary",
                "description": "Get historical sales summary for a single specific product. Use when user asks about one particular product's past performance.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string", "description": "Product ID e.g. P0001"},
                        "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                        "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
                    },
                    "required": ["product_id", "from_date", "to_date"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_category_sales",
                "description": "Get sales aggregated by product for a specific category (e.g. Electronics, Furniture, Groceries, Clothing, Toys). Returns per-product breakdown sorted by revenue. Use when user asks about a category's performance, top products in a category, or category-level analysis.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "description": "Category name: Electronics, Furniture, Groceries, Clothing, or Toys"},
                        "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                        "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
                    },
                    "required": ["category", "from_date", "to_date"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_all_products_summary",
                "description": "Get sales summary for ALL products with category info, sorted by revenue. Use for cross-product comparisons, rankings, identifying top/bottom performers, volatility analysis, or trend comparisons across the entire catalog.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                        "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
                    },
                    "required": ["from_date", "to_date"],
                },
            },
        },
    ]
