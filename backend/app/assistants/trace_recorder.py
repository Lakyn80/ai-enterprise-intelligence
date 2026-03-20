"""In-memory trace recorder for assistant request audit trails."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import time
from typing import Any
from uuid import uuid4

from app.assistants.query_normalization import normalise_query


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


@dataclass(slots=True)
class AssistantTraceStepRecord:
    step_index: int
    step_name: str
    status: str
    payload: dict[str, Any] | None
    created_at: datetime
    latency_ms: int | None = None


@dataclass(slots=True)
class AssistantTraceRecorder:
    assistant_type: str
    request_kind: str
    locale: str
    user_query: str
    question_id: str | None = None
    normalized_query: str = field(init=False)
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=_utcnow)
    status: str = "in_progress"
    cached: bool = False
    cache_source: str | None = None
    cache_strategy: str | None = None
    similarity: float | None = None
    answer: str | None = None
    error: str | None = None
    total_latency_ms: int | None = None
    completed_at: datetime | None = None
    steps: list[AssistantTraceStepRecord] = field(default_factory=list)
    _started_monotonic: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.normalized_query = normalise_query(self.user_query)

    def add_step(
        self,
        step_name: str,
        payload: dict[str, Any] | None = None,
        *,
        status: str = "ok",
        latency_ms: int | None = None,
    ) -> None:
        self.steps.append(
            AssistantTraceStepRecord(
                step_index=len(self.steps) + 1,
                step_name=step_name,
                status=status,
                payload=_json_safe(payload) if payload is not None else None,
                created_at=_utcnow(),
                latency_ms=latency_ms,
            )
        )

    def finalize_success(
        self,
        *,
        answer: str,
        cached: bool,
        cache_source: str | None,
        cache_strategy: str | None,
        similarity: float | None = None,
    ) -> None:
        self.status = "ok"
        self.cached = cached
        self.cache_source = cache_source
        self.cache_strategy = cache_strategy
        self.similarity = similarity
        self.answer = answer
        self.completed_at = _utcnow()
        self.total_latency_ms = int((time.monotonic() - self._started_monotonic) * 1000)

    def finalize_error(
        self,
        *,
        error: str,
        cache_source: str | None = None,
        cache_strategy: str | None = None,
        similarity: float | None = None,
        status: str = "error",
    ) -> None:
        self.status = status
        self.cache_source = cache_source
        self.cache_strategy = cache_strategy
        self.similarity = similarity
        self.error = error
        self.completed_at = _utcnow()
        self.total_latency_ms = int((time.monotonic() - self._started_monotonic) * 1000)

    def to_summary(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "status": self.status,
            "request_kind": self.request_kind,
            "cached": self.cached,
            "cache_source": self.cache_source,
            "cache_strategy": self.cache_strategy,
            "similarity": self.similarity,
            "total_latency_ms": self.total_latency_ms,
        }
