"""Text report generators: DB DataFrame → human-readable string."""

from datetime import date
from typing import Protocol

import pandas as pd


# ---------------------------------------------------------------------------
# Protocol — every generator must implement this
# ---------------------------------------------------------------------------

class ReportGenerator(Protocol):
    """
    Contract for report generators.

    Each generator receives a product/group DataFrame and returns
    (text_report, metadata_dict).  New report types only need to
    implement this interface and register themselves in service.py.
    """

    def generate(
        self,
        group_id: str,
        df: pd.DataFrame,
        date_from: date,
        date_to: date,
    ) -> tuple[str, dict]:
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trend_label(current_avg: float, previous_avg: float) -> str:
    if previous_avg == 0:
        return "unknown"
    change = (current_avg - previous_avg) / previous_avg
    if change > 0.05:
        return "increasing"
    if change < -0.05:
        return "decreasing"
    return "stable"


def _volatility_label(std: float, mean: float) -> str:
    if mean == 0:
        return "unknown"
    cv = std / mean
    if cv > 0.5:
        return "high"
    if cv > 0.2:
        return "moderate"
    return "low"


# ---------------------------------------------------------------------------
# Generator 1 — per-product report
# ---------------------------------------------------------------------------

class ProductReportGenerator:
    """Generates a sales report for a single product."""

    def generate(
        self,
        group_id: str,
        df: pd.DataFrame,
        date_from: date,
        date_to: date,
    ) -> tuple[str, dict]:
        metadata = {
            "report_type": "product",
            "product_id": group_id,
            "date_from": str(date_from),
            "date_to": str(date_to),
            "source": f"report:product:{group_id}",
        }

        if df.empty:
            return (
                f"Product {group_id}\n\nNo sales data available.",
                metadata,
            )

        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        qty = df["quantity"]
        total = float(qty.sum())
        avg_daily = float(qty.mean())
        max_day = float(qty.max())
        min_day = float(qty.min())
        std_dev = float(qty.std()) if len(qty) > 1 else 0.0

        price_avg = float(df["price"].dropna().mean()) if "price" in df else 0.0

        cutoff = df["date"].max() - pd.Timedelta(days=30)
        recent = df[df["date"] > cutoff]["quantity"]
        previous = df[df["date"] <= cutoff]["quantity"]
        trend = _trend_label(
            float(recent.mean()) if not recent.empty else 0.0,
            float(previous.mean()) if not previous.empty else 0.0,
        )
        volatility = _volatility_label(std_dev, avg_daily)

        promo_line = ""
        if "promo_flag" in df.columns:
            promo = df[df["promo_flag"] == True]["quantity"]
            non_promo = df[df["promo_flag"] == False]["quantity"]
            if not promo.empty and not non_promo.empty:
                lift = (promo.mean() - non_promo.mean()) / non_promo.mean() * 100
                promo_line = f"\n- Promo lift: {lift:+.1f}% ({promo.mean():.1f} vs {non_promo.mean():.1f} units/day)"

        cat_line = ""
        if "category_id" in df.columns:
            cats = df["category_id"].dropna().unique()
            if len(cats):
                cat_line = f"\n- Category: {', '.join(str(c) for c in cats)}"

        peak_date = df.loc[df["quantity"].idxmax(), "date"].date()

        text = f"""Product {group_id}
Date range: {date_from} to {date_to} ({len(df)} days of data){cat_line}

Sales summary:
- Total sales: {total:,.0f} units
- Average daily sales: {avg_daily:.1f} units/day
- Peak sales: {max_day:,.0f} units (on {peak_date})
- Minimum sales day: {min_day:.0f} units
- Sales volatility: {volatility} (std dev: {std_dev:.1f})

Trends:
- 30-day trend: {trend}
- Average price: {price_avg:.2f}{promo_line}"""

        return text.strip(), metadata


# ---------------------------------------------------------------------------
# Generator 2 — per-category summary
# ---------------------------------------------------------------------------

class CategoryReportGenerator:
    """Generates an aggregated sales report for a product category."""

    def generate(
        self,
        group_id: str,
        df: pd.DataFrame,
        date_from: date,
        date_to: date,
    ) -> tuple[str, dict]:
        metadata = {
            "report_type": "category",
            "category_id": group_id,
            "date_from": str(date_from),
            "date_to": str(date_to),
            "source": f"report:category:{group_id}",
        }

        if df.empty:
            return (
                f"Category {group_id}\n\nNo sales data available.",
                metadata,
            )

        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])

        n_products = df["product_id"].nunique() if "product_id" in df.columns else 0
        total = float(df["quantity"].sum())
        avg_daily = float(df.groupby("date")["quantity"].sum().mean())

        cutoff = df["date"].max() - pd.Timedelta(days=30)
        recent = df[df["date"] > cutoff].groupby("date")["quantity"].sum()
        previous = df[df["date"] <= cutoff].groupby("date")["quantity"].sum()
        trend = _trend_label(
            float(recent.mean()) if not recent.empty else 0.0,
            float(previous.mean()) if not previous.empty else 0.0,
        )

        top_products = (
            df.groupby("product_id")["quantity"].sum()
            .sort_values(ascending=False)
            .head(3)
            .index.tolist()
            if "product_id" in df.columns
            else []
        )

        text = f"""Category {group_id}
Date range: {date_from} to {date_to}

Category summary:
- Products in category: {n_products}
- Total category sales: {total:,.0f} units
- Average daily sales (all products): {avg_daily:.1f} units/day
- 30-day trend: {trend}
- Top products by volume: {', '.join(top_products) if top_products else 'N/A'}"""

        return text.strip(), metadata
