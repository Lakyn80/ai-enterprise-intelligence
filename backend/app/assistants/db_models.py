"""Database models for assistant request tracing."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AssistantTrace(Base):
    """Top-level trace for a single assistant request."""

    __tablename__ = "assistant_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    assistant_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    request_kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    question_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    cached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cache_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cache_strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    step_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    steps: Mapped[list["AssistantTraceStep"]] = relationship(
        back_populates="trace",
        cascade="all, delete-orphan",
        order_by="AssistantTraceStep.step_index",
    )


class AssistantTraceStep(Base):
    """Single step recorded during assistant request processing."""

    __tablename__ = "assistant_trace_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_pk: Mapped[int] = mapped_column(
        ForeignKey("assistant_traces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    trace: Mapped[AssistantTrace] = relationship(back_populates="steps")
