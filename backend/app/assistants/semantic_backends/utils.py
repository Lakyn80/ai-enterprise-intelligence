"""Shared helpers for assistant semantic cache backends."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def semantic_doc_id(assistant_type: str, locale: str, normalised_query: str) -> str:
    digest = hashlib.sha256(normalised_query.encode("utf-8")).hexdigest()
    return f"{assistant_type}:{locale}:{digest}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def payload_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer": metadata.get("answer", ""),
        "citations": json.loads(metadata.get("citations_json", "[]")),
        "used_tools": json.loads(metadata.get("used_tools_json", "[]")),
    }


def semantic_candidate_from_metadata(
    metadata: dict[str, Any],
    *,
    normalised_query: str,
    similarity: float,
    distance: float,
) -> dict[str, Any]:
    cached_normalised = str(metadata.get("normalised_query", "")).strip()
    exact_normalised_match = cached_normalised == normalised_query
    resolved_similarity = 1.0 if exact_normalised_match else max(0.0, similarity)
    resolved_distance = 0.0 if exact_normalised_match else max(0.0, distance)
    payload = payload_from_metadata(metadata)
    payload.update(
        {
            "cached_query": metadata.get("query", ""),
            "similarity": resolved_similarity,
            "distance": resolved_distance,
            "exact_normalised_match": exact_normalised_match,
        }
    )
    return payload
