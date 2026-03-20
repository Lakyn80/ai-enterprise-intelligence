"""Assistants API routes."""

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AsyncSessionDep
from app.assistants.schemas import (
    AssistantAnswer,
    AssistantTraceOut,
    AssistantTraceStepOut,
    AssistantTraceSummary,
    AssistantType,
    AskCustomRequest,
    AskPresetRequest,
    Locale,
    PresetsResponse,
)
from app.assistants import service
from app.assistants.presets import get_preset_by_id
from app.assistants.trace_recorder import AssistantTraceRecorder
from app.assistants.trace_repository import assistant_trace_repository
from app.assistants.dlq import dlq
from app.assistants.idempotency import idempotency_store
from app.forecasting.repository import ForecastingRepository
from app.forecasting.service import ForecastingService

router = APIRouter(prefix="/api/assistants", tags=["assistants"])


async def _get_forecasting(session: AsyncSessionDep):
    repo = ForecastingRepository(session)
    svc = ForecastingService(repo)
    return svc, repo


def _attach_trace(answer: AssistantAnswer, trace: AssistantTraceRecorder, response: Response | None) -> AssistantAnswer:
    if response:
        response.headers["X-Trace-Id"] = trace.trace_id
    return answer.model_copy(
        update={
            "trace_id": trace.trace_id,
            "trace_summary": AssistantTraceSummary(**trace.to_summary()),
        }
    )


async def _persist_trace(session: AsyncSession, trace: AssistantTraceRecorder, *, commit: bool = False) -> None:
    await assistant_trace_repository.save(session, trace)
    if commit:
        await session.commit()


def _trace_model_to_schema(trace_model) -> AssistantTraceOut:
    return AssistantTraceOut(
        trace_id=trace_model.trace_id,
        status=trace_model.status,
        request_kind=trace_model.request_kind,
        cached=trace_model.cached,
        cache_source=trace_model.cache_source,
        cache_strategy=trace_model.cache_strategy,
        similarity=trace_model.similarity,
        total_latency_ms=trace_model.total_latency_ms,
        assistant_type=trace_model.assistant_type,
        locale=trace_model.locale,
        question_id=trace_model.question_id,
        user_query=trace_model.user_query,
        normalized_query=trace_model.normalized_query,
        answer=trace_model.answer,
        error=trace_model.error,
        created_at=trace_model.created_at,
        completed_at=trace_model.completed_at,
        steps=[
            AssistantTraceStepOut(
                step_index=step.step_index,
                step_name=step.step_name,
                status=step.status,
                latency_ms=step.latency_ms,
                payload=step.payload,
                created_at=step.created_at,
            )
            for step in trace_model.steps
        ],
    )


# ---------------------------------------------------------------------------
# Preset listing
# ---------------------------------------------------------------------------


@router.get("/{assistant_type}/presets", response_model=PresetsResponse)
async def list_presets(
    assistant_type: AssistantType,
    locale: Locale = "en",
):
    questions = service.list_presets(assistant_type, locale)
    return PresetsResponse(
        assistant_type=assistant_type,
        locale=locale,
        questions=questions,
    )


# ---------------------------------------------------------------------------
# Ask preset question
# ---------------------------------------------------------------------------


@router.post("/ask-preset", response_model=AssistantAnswer)
async def ask_preset(
    body: AskPresetRequest,
    session: AsyncSessionDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    response: Response = None,
):
    """
    Answer a preset question (Redis cache).

    Optional header: Idempotency-Key — prevents duplicate LLM calls on client retries.
    On duplicate in-flight request: polls up to 2.5 s, then returns 202.
    """
    svc, repo = await _get_forecasting(session)
    preset = get_preset_by_id(body.assistant_type, body.question_id)
    trace = AssistantTraceRecorder(
        assistant_type=body.assistant_type,
        request_kind="preset",
        locale=body.locale,
        user_query=preset.text(body.locale) if preset else body.question_id,
        question_id=body.question_id,
    )
    trace.add_step(
        "request_received",
        {
            "assistant_type": body.assistant_type,
            "question_id": body.question_id,
            "locale": body.locale,
            "idempotency_key_present": bool(idempotency_key),
        },
    )

    # Idempotency check
    if idempotency_key:
        existing = await idempotency_store.get_result(idempotency_key)
        if existing:
            trace.add_step(
                "idempotency_lookup",
                {"hit": True, "mode": "stored_result"},
            )
            cached_answer = AssistantAnswer(**existing)
            trace.finalize_success(
                answer=cached_answer.answer,
                cached=cached_answer.cached,
                cache_source="idempotency_result",
                cache_strategy="idempotency_reuse",
            )
            await _persist_trace(session, trace)
            if response:
                response.headers["X-Idempotency-Cached"] = "true"
            return _attach_trace(cached_answer, trace, response)

        acquired = await idempotency_store.acquire_lock(idempotency_key)
        if not acquired:
            # Another worker is processing — poll
            result = await idempotency_store.wait_for_result(idempotency_key)
            if result:
                trace.add_step(
                    "idempotency_lookup",
                    {"hit": True, "mode": "wait_for_result"},
                )
                cached_answer = AssistantAnswer(**result)
                trace.finalize_success(
                    answer=cached_answer.answer,
                    cached=cached_answer.cached,
                    cache_source="idempotency_wait",
                    cache_strategy="idempotency_reuse",
                )
                await _persist_trace(session, trace)
                if response:
                    response.headers["X-Idempotency-Cached"] = "true"
                return _attach_trace(cached_answer, trace, response)
            trace.add_step(
                "idempotency_lookup",
                {"hit": False, "mode": "wait_timeout"},
                status="warning",
            )
            trace.finalize_error(
                error="Request is being processed. Retry with the same Idempotency-Key.",
                cache_source="idempotency_wait",
                cache_strategy="pending",
                status="pending",
            )
            await _persist_trace(session, trace, commit=True)
            raise HTTPException(
                status_code=202,
                detail="Request is being processed. Retry with the same Idempotency-Key.",
            )
        trace.add_step(
            "idempotency_lookup",
            {"hit": False, "mode": "lock_acquired"},
        )

    try:
        answer = await service.ask_preset(
            assistant_type=body.assistant_type,
            question_id=body.question_id,
            locale=body.locale,
            forecasting_service=svc,
            forecasting_repo=repo,
            trace=trace,
        )
    except ValueError as e:
        if idempotency_key:
            await idempotency_store.release_lock(idempotency_key)
        trace.finalize_error(error=str(e), cache_source=trace.cache_source, cache_strategy=trace.cache_strategy)
        await _persist_trace(session, trace, commit=True)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        if idempotency_key:
            await idempotency_store.release_lock(idempotency_key)
        trace.finalize_error(
            error=str(e),
            cache_source=trace.cache_source,
            cache_strategy=trace.cache_strategy,
            similarity=trace.similarity,
        )
        await _persist_trace(session, trace, commit=True)
        raise HTTPException(status_code=502, detail=str(e))

    trace.finalize_success(
        answer=answer.answer,
        cached=answer.cached,
        cache_source=trace.cache_source or ("preset_cache" if answer.cached else "llm_generate"),
        cache_strategy=trace.cache_strategy or ("preset_cache_hit" if answer.cached else "preset_regenerate"),
        similarity=trace.similarity,
    )
    await _persist_trace(session, trace)

    if idempotency_key:
        await idempotency_store.store_result(
            idempotency_key,
            answer.model_dump(exclude={"trace_id", "trace_summary"}),
        )

    return _attach_trace(answer, trace, response)


# ---------------------------------------------------------------------------
# Ask custom question
# ---------------------------------------------------------------------------


@router.post("/ask-custom", response_model=AssistantAnswer)
async def ask_custom(
    body: AskCustomRequest,
    session: AsyncSessionDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    response: Response = None,
):
    """
    Answer a free-form question with exact + semantic cache.

    Idempotency-Key prevents duplicate LLM calls on client retries.
    """
    svc, repo = await _get_forecasting(session)
    trace = AssistantTraceRecorder(
        assistant_type=body.assistant_type,
        request_kind="custom",
        locale=body.locale,
        user_query=body.query,
    )
    trace.add_step(
        "request_received",
        {
            "assistant_type": body.assistant_type,
            "query": body.query,
            "locale": body.locale,
            "idempotency_key_present": bool(idempotency_key),
        },
    )

    if idempotency_key:
        existing = await idempotency_store.get_result(idempotency_key)
        if existing:
            trace.add_step(
                "idempotency_lookup",
                {"hit": True, "mode": "stored_result"},
            )
            cached_answer = AssistantAnswer(**existing)
            trace.finalize_success(
                answer=cached_answer.answer,
                cached=cached_answer.cached,
                cache_source="idempotency_result",
                cache_strategy="idempotency_reuse",
            )
            await _persist_trace(session, trace)
            if response:
                response.headers["X-Idempotency-Cached"] = "true"
            return _attach_trace(cached_answer, trace, response)

        acquired = await idempotency_store.acquire_lock(idempotency_key)
        if not acquired:
            result = await idempotency_store.wait_for_result(idempotency_key)
            if result:
                trace.add_step(
                    "idempotency_lookup",
                    {"hit": True, "mode": "wait_for_result"},
                )
                cached_answer = AssistantAnswer(**result)
                trace.finalize_success(
                    answer=cached_answer.answer,
                    cached=cached_answer.cached,
                    cache_source="idempotency_wait",
                    cache_strategy="idempotency_reuse",
                )
                await _persist_trace(session, trace)
                if response:
                    response.headers["X-Idempotency-Cached"] = "true"
                return _attach_trace(cached_answer, trace, response)
            trace.add_step(
                "idempotency_lookup",
                {"hit": False, "mode": "wait_timeout"},
                status="warning",
            )
            trace.finalize_error(
                error="Request is being processed. Retry with the same Idempotency-Key.",
                cache_source="idempotency_wait",
                cache_strategy="pending",
                status="pending",
            )
            await _persist_trace(session, trace, commit=True)
            raise HTTPException(
                status_code=202,
                detail="Request is being processed. Retry with the same Idempotency-Key.",
            )
        trace.add_step(
            "idempotency_lookup",
            {"hit": False, "mode": "lock_acquired"},
        )

    try:
        answer = await service.ask_custom(
            assistant_type=body.assistant_type,
            query=body.query,
            locale=body.locale,
            forecasting_service=svc,
            forecasting_repo=repo,
            trace=trace,
        )
    except Exception as e:
        if idempotency_key:
            await idempotency_store.release_lock(idempotency_key)
        trace.finalize_error(
            error=str(e),
            cache_source=trace.cache_source,
            cache_strategy=trace.cache_strategy,
            similarity=trace.similarity,
        )
        await _persist_trace(session, trace, commit=True)
        raise HTTPException(status_code=502, detail=str(e))

    trace.finalize_success(
        answer=answer.answer,
        cached=answer.cached,
        cache_source=trace.cache_source or ("custom_exact_cache" if answer.cached else "llm_generate"),
        cache_strategy=trace.cache_strategy or ("exact_reuse" if answer.cached else "regenerate"),
        similarity=trace.similarity,
    )
    await _persist_trace(session, trace)

    if idempotency_key:
        await idempotency_store.store_result(
            idempotency_key,
            answer.model_dump(exclude={"trace_id", "trace_summary"}),
        )

    return _attach_trace(answer, trace, response)


# ---------------------------------------------------------------------------
# Trace inspection
# ---------------------------------------------------------------------------


@router.get("/traces/{trace_id}", response_model=AssistantTraceOut)
async def get_trace(trace_id: str, session: AsyncSessionDep):
    trace = await assistant_trace_repository.get_by_trace_id(session, trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")
    return _trace_model_to_schema(trace)


@router.get("/traces")
async def list_traces(
    session: AsyncSessionDep,
    assistant_type: AssistantType | None = None,
    limit: int = 20,
):
    items = await assistant_trace_repository.list_recent(
        session,
        assistant_type=assistant_type,
        limit=limit,
    )
    return {
        "count": len(items),
        "items": [
            AssistantTraceSummary(
                trace_id=item.trace_id,
                status=item.status,
                request_kind=item.request_kind,
                cached=item.cached,
                cache_source=item.cache_source,
                cache_strategy=item.cache_strategy,
                similarity=item.similarity,
                total_latency_ms=item.total_latency_ms,
            )
            for item in items
        ],
    }


# ---------------------------------------------------------------------------
# Status overview
# ---------------------------------------------------------------------------


@router.get("/{assistant_type}/status")
async def get_status(assistant_type: AssistantType):
    """Return status of all preset questions for an assistant type."""
    statuses = await service.get_all_statuses(assistant_type)
    return {"assistant_type": assistant_type, "questions": statuses}


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------


@router.delete("/{assistant_type}/cache")
async def flush_cache(assistant_type: AssistantType):
    from app.assistants.cache import assistant_cache
    from app.assistants.query_cache import assistant_query_cache

    preset_deleted = await assistant_cache.flush_assistant(assistant_type)
    custom_deleted = await assistant_query_cache.flush_assistant(assistant_type)
    return {
        "deleted": preset_deleted + custom_deleted["redis_deleted"] + custom_deleted["semantic_deleted"],
        "assistant_type": assistant_type,
        "preset_deleted": preset_deleted,
        "custom_exact_deleted": custom_deleted["redis_deleted"],
        "custom_semantic_deleted": custom_deleted["semantic_deleted"],
    }


# ---------------------------------------------------------------------------
# DLQ management
# ---------------------------------------------------------------------------


@router.get("/dlq")
async def get_dlq(limit: int = 100):
    items = await dlq.list_items(limit=min(limit, 100))
    return {"count": len(items), "items": items}


@router.delete("/dlq")
async def flush_dlq():
    deleted = await dlq.flush()
    return {"deleted": deleted}
