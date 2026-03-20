"""Persistence and read APIs for assistant request traces."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.assistants.db_models import AssistantTrace, AssistantTraceStep
from app.assistants.trace_recorder import AssistantTraceRecorder


class AssistantTraceRepository:
    """Repository for storing and fetching assistant traces."""

    async def save(self, session: AsyncSession, recorder: AssistantTraceRecorder) -> None:
        trace = AssistantTrace(
            trace_id=recorder.trace_id,
            assistant_type=recorder.assistant_type,
            request_kind=recorder.request_kind,
            locale=recorder.locale,
            question_id=recorder.question_id,
            user_query=recorder.user_query,
            normalized_query=recorder.normalized_query,
            status=recorder.status,
            cached=recorder.cached,
            cache_source=recorder.cache_source,
            cache_strategy=recorder.cache_strategy,
            similarity=recorder.similarity,
            answer=recorder.answer,
            error=recorder.error,
            total_latency_ms=recorder.total_latency_ms,
            step_count=len(recorder.steps),
            created_at=recorder.created_at,
            completed_at=recorder.completed_at,
            steps=[
                AssistantTraceStep(
                    step_index=step.step_index,
                    step_name=step.step_name,
                    status=step.status,
                    latency_ms=step.latency_ms,
                    payload=step.payload,
                    created_at=step.created_at,
                )
                for step in recorder.steps
            ],
        )
        session.add(trace)
        await session.flush()

    async def get_by_trace_id(self, session: AsyncSession, trace_id: str) -> AssistantTrace | None:
        stmt = (
            select(AssistantTrace)
            .options(selectinload(AssistantTrace.steps))
            .where(AssistantTrace.trace_id == trace_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_recent(
        self,
        session: AsyncSession,
        *,
        assistant_type: str | None = None,
        limit: int = 20,
    ) -> Sequence[AssistantTrace]:
        stmt = select(AssistantTrace).order_by(desc(AssistantTrace.created_at)).limit(min(limit, 100))
        if assistant_type:
            stmt = stmt.where(AssistantTrace.assistant_type == assistant_type)
        result = await session.execute(stmt)
        return result.scalars().all()


assistant_trace_repository = AssistantTraceRepository()
