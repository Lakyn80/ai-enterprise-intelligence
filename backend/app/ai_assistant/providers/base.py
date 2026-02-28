"""LLM provider interface - provider-agnostic abstraction."""

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Interface for LLM providers (OpenAI, DeepSeek, etc.)."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Generate response from LLM.
        Returns dict with 'content', 'tool_calls', etc.
        """
        ...
