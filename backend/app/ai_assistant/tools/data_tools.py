"""Tools for AI assistant to fetch historical data from DB."""

from datetime import date
from typing import Any


async def get_sales_summary(
    forecasting_repo: Any,
    product_id: str,
    from_date: date,
    to_date: date,
) -> dict[str, Any]:
    """Fetch aggregated sales summary from DB."""
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


def get_data_tools_spec() -> list[dict[str, Any]]:
    """OpenAI-compatible tools schema for data."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_sales_summary",
                "description": "Get historical sales summary for a product in a date range. Use when user asks about past performance, historical data, or sales trends.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "from_date": {"type": "string"},
                        "to_date": {"type": "string"},
                    },
                    "required": ["product_id", "from_date", "to_date"],
                },
            },
        },
    ]
