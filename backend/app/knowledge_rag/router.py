"""Knowledge RAG API routes."""

from fastapi import APIRouter, Depends

from app.core.deps import ApiKeyDep
from app.knowledge_rag.schemas import IngestRequest, QueryRequest, QueryResponse
from app.knowledge_rag.service import KnowledgeService

router = APIRouter(prefix="/api", tags=["knowledge"])


def get_knowledge_service() -> KnowledgeService:
    return KnowledgeService()


@router.post("/knowledge/ingest", dependencies=[Depends(ApiKeyDep)])
async def ingest_documents(body: IngestRequest):
    """Ingest documents from folder or raw text (API key required)."""
    service = get_knowledge_service()
    if body.text:
        return await service.ingest_text(body.text, body.source)
    if body.folder_path:
        return await service.ingest_from_folder(body.folder_path)
    return {"status": "error", "message": "Provide folder_path or text"}


@router.post("/knowledge/query", response_model=QueryResponse)
async def query_knowledge(body: QueryRequest) -> QueryResponse:
    """Query RAG knowledge base."""
    service = get_knowledge_service()
    result = await service.query(body.query)
    return QueryResponse(
        answer=result["answer"],
        citations=result.get("citations", []),
    )
