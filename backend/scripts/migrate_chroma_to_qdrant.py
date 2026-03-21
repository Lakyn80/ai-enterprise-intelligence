#!/usr/bin/env python3
"""Migrate existing Chroma collections to Qdrant without re-embedding."""

from __future__ import annotations

import asyncio
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.settings import settings
from app.vector.qdrant_support import (
    create_async_qdrant_client,
    ensure_qdrant_collection,
    get_qdrant_models,
)


async def migrate_collection(
    *,
    source_collection_name: str,
    target_collection_name: str,
    indexed_fields: list[str],
) -> dict[str, Any]:
    chroma_client = chromadb.PersistentClient(
        path=settings.rag_chroma_path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    qdrant_client = create_async_qdrant_client()

    try:
        source = chroma_client.get_collection(source_collection_name)
    except Exception:
        return {"collection": source_collection_name, "migrated": 0, "status": "missing"}

    data = source.get(include=["documents", "metadatas", "embeddings"])
    ids = data.get("ids", []) or []
    documents = data.get("documents", []) or []
    metadatas = data.get("metadatas", []) or []
    embeddings = data.get("embeddings", []) or []
    if not ids or not embeddings:
        return {"collection": source_collection_name, "migrated": 0, "status": "empty"}

    await ensure_qdrant_collection(
        qdrant_client,
        target_collection_name,
        len(embeddings[0]),
        indexed_fields=indexed_fields,
    )
    models = get_qdrant_models()
    points = [
        models.PointStruct(
            id=point_id,
            vector=embedding,
            payload={**(metadata or {}), "content": document or ""},
        )
        for point_id, document, metadata, embedding in zip(ids, documents, metadatas, embeddings)
    ]
    await qdrant_client.upsert(
        collection_name=target_collection_name,
        points=points,
        wait=True,
    )
    return {"collection": source_collection_name, "migrated": len(points), "status": "ok"}


async def main_async() -> None:
    collections = [
        {
            "source": settings.rag_collection_name,
            "target": settings.rag_collection_name,
            "indexed_fields": ["source", "report_type", "product_id", "category_id"],
        },
        {
            "source": settings.assistants_semantic_cache_collection_name,
            "target": settings.assistants_semantic_cache_collection_name,
            "indexed_fields": ["assistant_type", "locale", "normalised_query"],
        },
    ]

    for config in collections:
        result = await migrate_collection(
            source_collection_name=config["source"],
            target_collection_name=config["target"],
            indexed_fields=config["indexed_fields"],
        )
        print(result)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
