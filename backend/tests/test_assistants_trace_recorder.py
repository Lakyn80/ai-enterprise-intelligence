"""Tests for assistant trace recorder."""

from app.assistants.trace_recorder import AssistantTraceRecorder


def test_trace_recorder_tracks_steps_and_summary():
    trace = AssistantTraceRecorder(
        assistant_type="knowledge",
        request_kind="custom",
        locale="cs",
        user_query="Který produkt má nejvyšší tržby?",
    )
    trace.add_step("request_received", {"foo": "bar"})
    trace.finalize_success(
        answer="P0007 has the highest revenue.",
        cached=True,
        cache_source="custom_semantic_cache",
        cache_strategy="semantic_reuse",
        similarity=0.93,
    )

    summary = trace.to_summary()
    assert trace.normalized_query == "který produkt má nejvyšší tržby"
    assert len(trace.steps) == 1
    assert summary["trace_id"] == trace.trace_id
    assert summary["cached"] is True
    assert summary["cache_source"] == "custom_semantic_cache"
    assert summary["cache_strategy"] == "semantic_reuse"
    assert summary["similarity"] == 0.93
    assert summary["total_latency_ms"] is not None
