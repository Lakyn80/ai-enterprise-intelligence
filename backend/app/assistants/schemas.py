"""Pydantic schemas for the Assistants API."""

from typing import Literal
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


class AssistantAnswer(BaseModel):
    question_id: str | None = None
    query: str
    answer: str
    locale: Locale
    cached: bool = False
    citations: list[Citation] = []
    used_tools: list[str] = []
