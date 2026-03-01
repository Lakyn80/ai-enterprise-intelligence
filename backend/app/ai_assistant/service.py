"""AI Assistant service - modulární (default DeepSeek)."""

from typing import Any

from app.ai_assistant.graph.agent_graph import run_agent
from app.ai_assistant.providers.base import LLMProvider
from app.ai_assistant.providers.openai_provider import OpenAIProvider
from app.ai_assistant.providers.deepseek_provider import DeepSeekProvider
from app.settings import settings


def get_provider(provider_name: str) -> LLMProvider:
    """Přepínač LLM provideru (default: deepseek)."""
    if provider_name == "openai":
        return OpenAIProvider()
    return DeepSeekProvider()


async def chat(
    message: str,
    provider_name: str,
    forecasting_service: Any,
    forecasting_repo: Any,
    knowledge_service: Any | None = None,
) -> tuple[str, list[str], list[dict]]:
    """Process chat message through agent."""
    provider = get_provider(provider_name)
    return await run_agent(
        user_message=message,
        provider=provider,
        forecasting_service=forecasting_service,
        forecasting_repo=forecasting_repo,
        knowledge_service=knowledge_service,
        rag_enabled=settings.rag_enabled,
    )
