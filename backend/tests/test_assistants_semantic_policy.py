"""Tests for semantic cache strategy selection."""

import pytest

from app.assistants.semantic_policy import decide_semantic_cache_strategy


def test_decide_semantic_cache_strategy_reuse():
    decision = decide_semantic_cache_strategy(0.95, reuse_similarity=0.90, rewrite_similarity=0.30)
    assert decision.strategy == "reuse"
    assert decision.similarity == 0.95


def test_decide_semantic_cache_strategy_rewrite():
    decision = decide_semantic_cache_strategy(0.62, reuse_similarity=0.90, rewrite_similarity=0.30)
    assert decision.strategy == "rewrite"


def test_decide_semantic_cache_strategy_regenerate():
    decision = decide_semantic_cache_strategy(0.12, reuse_similarity=0.90, rewrite_similarity=0.30)
    assert decision.strategy == "regenerate"


def test_decide_semantic_cache_strategy_validates_thresholds():
    with pytest.raises(ValueError, match="Semantic cache thresholds"):
        decide_semantic_cache_strategy(0.5, reuse_similarity=0.20, rewrite_similarity=0.30)
