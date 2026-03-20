"""Decision policy for semantic assistant query cache."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SemanticCacheStrategy = Literal["reuse", "rewrite", "regenerate"]


@dataclass(frozen=True)
class SemanticCacheDecision:
    strategy: SemanticCacheStrategy
    similarity: float


def decide_semantic_cache_strategy(
    similarity: float,
    reuse_similarity: float,
    rewrite_similarity: float,
) -> SemanticCacheDecision:
    """Choose cache behaviour from a normalized similarity score."""
    if not 0.0 <= rewrite_similarity <= reuse_similarity <= 1.0:
        raise ValueError("Semantic cache thresholds must satisfy 0 <= rewrite <= reuse <= 1")

    resolved_similarity = max(0.0, min(1.0, similarity))
    if resolved_similarity >= reuse_similarity:
        return SemanticCacheDecision(strategy="reuse", similarity=resolved_similarity)
    if resolved_similarity >= rewrite_similarity:
        return SemanticCacheDecision(strategy="rewrite", similarity=resolved_similarity)
    return SemanticCacheDecision(strategy="regenerate", similarity=resolved_similarity)
