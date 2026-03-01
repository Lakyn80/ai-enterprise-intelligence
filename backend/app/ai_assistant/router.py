"""AI Assistant API routes."""

from fastapi import APIRouter, Depends

from app.core.deps import AsyncSessionDep
from app.ai_assistant.schemas import ChatRequest, ChatResponse, ExplainForecastRequest
from app.ai_assistant.service import chat
from app.forecasting.repository import ForecastingRepository
from app.forecasting.service import ForecastingService
from app.knowledge_rag.service import KnowledgeService
from app.settings import settings

router = APIRouter(prefix="/api", tags=["ai_assistant"])


async def get_forecasting_service(session: AsyncSessionDep) -> ForecastingService:
    return ForecastingService(ForecastingRepository(session))


@router.post("/assistant/chat", response_model=ChatResponse)
async def assistant_chat(
    body: ChatRequest,
    session: AsyncSessionDep,
):
    """Chat with AI analyst (modulární: openai/deepseek, default deepseek)."""
    forecasting_service = get_forecasting_service(session)
    forecasting_repo = ForecastingRepository(session)
    knowledge_service = KnowledgeService() if settings.rag_enabled else None
    answer, used_tools, citations = await chat(
        message=body.message,
        provider_name=body.provider,
        forecasting_service=forecasting_service,
        forecasting_repo=forecasting_repo,
        knowledge_service=knowledge_service,
    )
    return ChatResponse(
        answer=answer,
        used_tools=used_tools,
        citations=citations,
    )


@router.post("/assistant/explain-forecast", response_model=ChatResponse)
async def explain_forecast(
    body: ExplainForecastRequest,
    session: AsyncSessionDep,
):
    """Get AI explanation of forecast for product and date range."""
    message = (
        f"Explain the demand forecast for product {body.product_id} "
        f"from {body.from_date} to {body.to_date}. "
        "What drives the predictions? What patterns do you see in the data? "
        "Base your explanation only on the data and forecast values you retrieve."
    )
    forecasting_service = get_forecasting_service(session)
    forecasting_repo = ForecastingRepository(session)
    knowledge_service = KnowledgeService() if settings.rag_enabled else None
    answer, used_tools, citations = await chat(
        message=message,
        provider_name=body.provider,
        forecasting_service=forecasting_service,
        forecasting_repo=forecasting_repo,
        knowledge_service=knowledge_service,
    )
    return ChatResponse(
        answer=answer,
        used_tools=used_tools,
        citations=citations,
    )
