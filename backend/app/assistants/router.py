"""Assistants API routes."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import AsyncSessionDep
from app.assistants.schemas import (
    AssistantAnswer,
    AssistantType,
    AskCustomRequest,
    AskPresetRequest,
    Locale,
    PresetsResponse,
    PresetQuestionOut,
)
from app.assistants import service
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
    """Return all preset questions for an assistant in the requested locale."""
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
):
    """Answer a preset question (uses Redis cache; analyst uses DB tools)."""
    svc, repo = await _get_forecasting(session)
    try:
        return await service.ask_preset(
            assistant_type=body.assistant_type,
            question_id=body.question_id,
            locale=body.locale,
            forecasting_service=svc,
            forecasting_repo=repo,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# Ask custom question
# ---------------------------------------------------------------------------


@router.post("/ask-custom", response_model=AssistantAnswer)
async def ask_custom(
    body: AskCustomRequest,
    session: AsyncSessionDep,
):
    """Answer a free-form question (no caching)."""
    svc, repo = await _get_forecasting(session)
    try:
        return await service.ask_custom(
            assistant_type=body.assistant_type,
            query=body.query,
            locale=body.locale,
            forecasting_service=svc,
            forecasting_repo=repo,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# Cache management (admin)
# ---------------------------------------------------------------------------


@router.delete("/{assistant_type}/cache", response_model=dict)
async def flush_cache(assistant_type: AssistantType):
    """Flush all cached answers for an assistant type."""
    from app.assistants.cache import assistant_cache
    deleted = await assistant_cache.flush_assistant(assistant_type)
    return {"deleted": deleted, "assistant_type": assistant_type}
