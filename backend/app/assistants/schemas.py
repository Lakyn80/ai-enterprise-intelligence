"""Pydantic schemas for the Assistants API."""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel

Locale = Literal["en", "cs", "sk", "ru"]
AssistantType = Literal["knowledge", "analyst"]


class PresetQuestionOut(BaseModel):
    id: str
    text: str


class PresetsResponse(BaseModel):
    assistant_type: AssistantType
    locale: Locale
    questions: list[PresetQuestionOut]


class AskPresetRequest(BaseModel):
    assistant_type: AssistantType
    question_id: str
    locale: Locale = "en"


class AskCustomRequest(BaseModel):
    assistant_type: AssistantType
    query: str
    locale: Locale = "en"


class Citation(BaseModel):
    source: str
    excerpt: str | None = None


class ClarificationMessage(BaseModel):
    cs: str
    ru: str
    en: str


class ClarificationOut(BaseModel):
    type: Literal["clarification"] = "clarification"
    missing: list[str]
    message: ClarificationMessage


class AssistantTraceSummary(BaseModel):
    trace_id: str
    status: str
    request_kind: Literal["preset", "custom"]
    cached: bool
    cache_source: str | None = None
    cache_strategy: str | None = None
    similarity: float | None = None
    total_latency_ms: int | None = None


class AssistantTraceStepOut(BaseModel):
    step_index: int
    step_name: str
    status: str
    latency_ms: int | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime


class AssistantTraceOut(AssistantTraceSummary):
    assistant_type: AssistantType
    locale: Locale
    question_id: str | None = None
    user_query: str
    normalized_query: str
    answer: str | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    steps: list[AssistantTraceStepOut] = []


class AssistantAnswer(BaseModel):
    question_id: str | None = None
    query: str
    answer: str
    locale: Locale
    response_type: Literal["answer", "clarification"] = "answer"
    clarification: ClarificationOut | None = None
    cached: bool = False
    citations: list[Citation] = []
    used_tools: list[str] = []
    trace_id: str | None = None
    trace_summary: AssistantTraceSummary | None = None
