"""OpenAI LLM provider adapter."""

from typing import Any

from openai import AsyncOpenAI

from app.ai_assistant.providers.base import LLMProvider
from app.settings import settings


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": "gpt-4o-mini",
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = await self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0] if resp.choices else None
        if not choice:
            return {"content": "", "tool_calls": []}
        msg = choice.message
        tool_calls = []
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                })
        return {
            "content": msg.content or "",
            "tool_calls": tool_calls,
        }
