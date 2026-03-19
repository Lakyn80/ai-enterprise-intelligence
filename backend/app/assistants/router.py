"""Assistants API routes."""

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from app.core.deps import AsyncSessionDep
from app.assistants.schemas import (
    AssistantAnswer,
    AssistantType,
    AskCustomRequest,
    AskPresetRequest,
    Locale,
    PresetsResponse,
)
from app.assistants import service
from app.assistants.dlq import dlq
from app.assistants.idempotency import idempotency_store
from app.forecasting.repository import ForecastingRepository
from app.forecasting.service import ForecastingService

router = APIRouter(prefix="/api/assistants", tags=["assistants"])


async def _get_forecasting(session: AsyncSessionDep):
    repo = ForecastingRepository(session)
    svc = ForecastingService(repo)
    return svc, repo


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

    # Idempotency check
    if idempotency_key:
        existing = await idempotency_store.get_result(idempotency_key)
        if existing:
            if response:
                response.headers["X-Idempotency-Cached"] = "true"
            return AssistantAnswer(**existing)

        acquired = await idempotency_store.acquire_lock(idempotency_key)
        if not acquired:
            # Another worker is processing — poll
            result = await idempotency_store.wait_for_result(idempotency_key)
            if result:
                if response:
                    response.headers["X-Idempotency-Cached"] = "true"
                return AssistantAnswer(**result)
            raise HTTPException(
                status_code=202,
                detail="Request is being processed. Retry with the same Idempotency-Key.",
            )

    try:
        answer = await service.ask_preset(
            assistant_type=body.assistant_type,
            question_id=body.question_id,
            locale=body.locale,
            forecasting_service=svc,
            forecasting_repo=repo,
        )
    except ValueError as e:
        if idempotency_key:
            await idempotency_store.release_lock(idempotency_key)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        if idempotency_key:
            await idempotency_store.release_lock(idempotency_key)
        raise HTTPException(status_code=502, detail=str(e))

    if idempotency_key:
        await idempotency_store.store_result(idempotency_key, answer.model_dump())

    return answer


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
    Answer a free-form question (no preset cache).

    Idempotency-Key prevents duplicate LLM calls on client retries.
    """
    svc, repo = await _get_forecasting(session)

    if idempotency_key:
        existing = await idempotency_store.get_result(idempotency_key)
        if existing:
            if response:
                response.headers["X-Idempotency-Cached"] = "true"
            return AssistantAnswer(**existing)

        acquired = await idempotency_store.acquire_lock(idempotency_key)
        if not acquired:
            result = await idempotency_store.wait_for_result(idempotency_key)
            if result:
                if response:
                    response.headers["X-Idempotency-Cached"] = "true"
                return AssistantAnswer(**result)
            raise HTTPException(
                status_code=202,
                detail="Request is being processed. Retry with the same Idempotency-Key.",
            )

    try:
        answer = await service.ask_custom(
            assistant_type=body.assistant_type,
            query=body.query,
            locale=body.locale,
            forecasting_service=svc,
            forecasting_repo=repo,
        )
    except Exception as e:
        if idempotency_key:
            await idempotency_store.release_lock(idempotency_key)
        raise HTTPException(status_code=502, detail=str(e))

    if idempotency_key:
        await idempotency_store.store_result(idempotency_key, answer.model_dump())

    return answer


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
    deleted = await assistant_cache.flush_assistant(assistant_type)
    return {"deleted": deleted, "assistant_type": assistant_type}


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
