"""AI Assistant Pydantic schemas."""

from typing import Literal

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Chat request body."""

    message: str
    provider: Literal["openai", "deepseek"] = "openai"


class ChatResponse(BaseModel):
    """Chat response with answer and metadata."""

    answer: str
    used_tools: list[str] = []
    citations: list[dict] = []
