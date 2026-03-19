"""Orchestrate DB → report generation → ChromaDB ingestion."""

from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.forecasting.repository import ForecastingRepository
from app.knowledge_rag.ingest.chunking import chunk_text
from app.knowledge_rag.service import KnowledgeService, get_vector_store
from app.knowledge_reports.generator import (
    CategoryReportGenerator,
    ProductReportGenerator,
    ReportGenerator,
)


def _build_chunks(
    groups: dict[str, pd.DataFrame],
    date_from: date,
    date_to: date,
    generator: ReportGenerator,
) -> tuple[list[str], list[dict]]:
    """
    Generate text reports for all groups and split into chunks.
    Returns (all_chunk_texts, all_metadatas) — ready for a single add_documents call.
    """
    all_texts: list[str] = []
    all_metas: list[dict] = []

    for group_id, df in groups.items():
        text, meta = generator.generate(group_id, df, date_from, date_to)
        if not text.strip():
            continue

        report_type = meta.get("report_type", "report")
        prefix = (
            f"{report_type.capitalize()} {group_id} "
            f"sales report ({date_from} to {date_to}): "
        )

        chunks = list(chunk_text(text))
        for i, chunk in enumerate(chunks):
            embed_text = f"{prefix}{chunk}"
            chunk_meta = {
                **meta,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            all_texts.append(embed_text)
            all_metas.append(chunk_meta)

    return all_texts, all_metas


class KnowledgeReportService:
    """
    Pluggable report ingestion service.

    All chunks across all products/categories are embedded in a SINGLE
    batch API call — avoids N×(API latency) per product.
    """

    def __init__(self, session: AsyncSession):
        self._repo = ForecastingRepository(session)
        self._store = get_vector_store()

    async def ingest_reports(self) -> dict[str, Any]:
        """Full pipeline: DB → text reports → ChromaDB (single batch embed)."""
        if not self._store:
            return {"status": "error", "message": "RAG disabled", "ingested": 0}

        date_from, date_to = await self._repo.get_date_range()
        if date_from is None or date_to is None:
            return {"status": "error", "message": "No sales data in database", "ingested": 0}

        df_all = await self._repo.get_sales_df(date_from, date_to)
        if df_all.empty:
            return {"status": "error", "message": "No sales rows found", "ingested": 0}

        all_texts: list[str] = []
        all_metas: list[dict] = []
        results: dict[str, Any] = {
            "status": "ok",
            "date_from": str(date_from),
            "date_to": str(date_to),
        }

        # --- Product reports ---
        product_groups = {
            pid: grp.reset_index(drop=True)
            for pid, grp in df_all.groupby("product_id")
        }
        p_texts, p_metas = _build_chunks(
            product_groups, date_from, date_to, ProductReportGenerator()
        )
        all_texts.extend(p_texts)
        all_metas.extend(p_metas)
        results["products"] = {"count": len(product_groups), "chunks": len(p_texts)}

        # --- Category reports ---
        if "category_id" in df_all.columns:
            cat_groups = {
                str(cat): grp.reset_index(drop=True)
                for cat, grp in df_all.groupby("category_id")
                if pd.notna(cat)
            }
            c_texts, c_metas = _build_chunks(
                cat_groups, date_from, date_to, CategoryReportGenerator()
            )
            all_texts.extend(c_texts)
            all_metas.extend(c_metas)
            results["categories"] = {"count": len(cat_groups), "chunks": len(c_texts)}

        if not all_texts:
            return {"status": "ok", "ingested": 0, "message": "No reports generated"}

        # Single batch embed call for ALL chunks at once
        ids = await self._store.add_documents(all_texts, all_metas)
        results["ingested"] = len(ids)
        return results
