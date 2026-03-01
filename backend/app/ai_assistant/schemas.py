"""AI Assistant Pydantic schemas."""

from typing import Literal

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Chat request body."""

    message: str
    provider: Literal["openai", "deepseek"] = "deepseek"


class ChatResponse(BaseModel):
    """Chat response with answer and metadata."""

    answer: str
    used_tools: list[str] = []
    citations: list[dict] = []


class ExplainForecastRequest(BaseModel):
    """Request for explain-forecast endpoint."""

    product_id: str
    from_date: str
    to_date: str
    provider: Literal["openai", "deepseek"] = "deepseek"
