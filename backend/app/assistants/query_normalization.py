"""Shared helpers for assistant query normalization."""

from __future__ import annotations

import re


def normalise_query(query: str) -> str:
    query = query.strip().lower()
    query = re.sub(r"[^\w\s]", " ", query, flags=re.UNICODE)
    return re.sub(r"\s+", " ", query).strip()
