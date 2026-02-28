"""Knowledge RAG Pydantic schemas."""

from pydantic import BaseModel


class IngestRequest(BaseModel):
    """Ingest request - folder path or raw text."""

    folder_path: str | None = None
    text: str | None = None
    source: str = "upload"


class QueryRequest(BaseModel):
    """Query request."""

    query: str


class QueryResponse(BaseModel):
    """Query response with answer and citations."""

    answer: str
    citations: list[dict]
