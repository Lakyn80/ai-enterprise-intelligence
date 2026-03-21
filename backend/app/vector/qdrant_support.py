"""Shared helpers for Qdrant-backed vector infrastructure."""

from __future__ import annotations

from typing import Any

from app.settings import settings


def create_async_qdrant_client() -> Any:
    """Create an async Qdrant client from settings."""
    from qdrant_client import AsyncQdrantClient

    kwargs: dict[str, Any] = {
        "timeout": settings.qdrant_timeout,
        "prefer_grpc": settings.qdrant_prefer_grpc,
        # The local stack pins an older Qdrant server image, while the Python client
        # may be newer. We handle request-shape compatibility in this module.
        "check_compatibility": False,
    }
    if settings.qdrant_api_key:
        kwargs["api_key"] = settings.qdrant_api_key
    if settings.qdrant_path:
        kwargs["path"] = settings.qdrant_path
    else:
        kwargs["url"] = settings.qdrant_url
    return AsyncQdrantClient(**kwargs)


def get_qdrant_models() -> Any:
    """Return qdrant_client models lazily."""
    from qdrant_client.http import models

    return models


async def qdrant_similarity_query(
    client: Any,
    *,
    collection_name: str,
    query_vector: list[float],
    query_filter: Any | None,
    limit: int,
    with_payload: bool = True,
    with_vectors: bool = False,
) -> list[Any]:
    """Run a similarity query across supported qdrant-client versions."""
    if hasattr(client, "query_points"):
        response = await client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=with_payload,
            with_vectors=with_vectors,
        )
        return list(getattr(response, "points", []) or [])

    if hasattr(client, "search"):
        return list(
            await client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=with_payload,
                with_vectors=with_vectors,
            )
            or []
        )

    raise AttributeError("Qdrant client does not support similarity search methods")


def build_qdrant_filter(where: dict[str, Any] | None) -> Any | None:
    """Translate a simple Chroma-style where clause into a Qdrant filter."""
    if not where:
        return None

    models = get_qdrant_models()

    if "$and" in where:
        clauses = [build_qdrant_filter(clause) for clause in where["$and"]]
        clauses = [clause for clause in clauses if clause is not None]
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return models.Filter(must=clauses)

    if "$or" in where:
        clauses = [build_qdrant_filter(clause) for clause in where["$or"]]
        clauses = [clause for clause in clauses if clause is not None]
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return models.Filter(should=clauses)

    must: list[Any] = []
    must_not: list[Any] = []
    for key, value in where.items():
        if key.startswith("$"):
            continue
        if isinstance(value, dict):
            if "$eq" in value:
                must.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value["$eq"]),
                    )
                )
            elif "$ne" in value:
                must_not.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value["$ne"]),
                    )
                )
        else:
            must.append(
                models.FieldCondition(
                    key=key,
                    match=models.MatchValue(value=value),
                )
            )

    if not must and not must_not:
        return None
    return models.Filter(must=must or None, must_not=must_not or None)


async def ensure_qdrant_collection(
    client: Any,
    collection_name: str,
    vector_size: int,
    *,
    indexed_fields: list[str] | None = None,
) -> None:
    """Create a Qdrant collection if it does not exist yet."""
    exists = await client.collection_exists(collection_name)
    if not exists:
        models = get_qdrant_models()
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    if indexed_fields:
        models = get_qdrant_models()
        for field_name in indexed_fields:
            try:
                await client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            except Exception:
                # Benign if index already exists or backend doesn't support re-creation.
                pass
