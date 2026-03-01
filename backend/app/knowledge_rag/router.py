"""Knowledge RAG API routes."""

from fastapi import APIRouter, Depends

from app.core.security import verify_api_key
from app.knowledge_rag.schemas import IngestRequest, QueryRequest, QueryResponse
from app.knowledge_rag.service import KnowledgeService

router = APIRouter(prefix="/api", tags=["knowledge"])


def get_knowledge_service() -> KnowledgeService:
    return KnowledgeService()


@router.post("/knowledge/reset", dependencies=[Depends(verify_api_key)])
async def reset_rag_store():
    """Smazat RAG vektorový index (pro pře-ingest s novými embeddings)."""
    import shutil
    from pathlib import Path

    import chromadb
    from chromadb.config import Settings as ChromaSettings

    from app.settings import settings

    removed = []
    try:
        client = chromadb.PersistentClient(
            path=settings.rag_chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        client.delete_collection(settings.rag_collection_name)
        removed.append("chroma_collection")
    except Exception:
        pass
    faiss_path = Path("./faiss_index")
    if faiss_path.exists():
        shutil.rmtree(faiss_path)
        removed.append("faiss_index")
    return {"status": "ok", "message": "RAG store resetován", "removed": removed}


@router.post("/knowledge/ingest", dependencies=[Depends(verify_api_key)])
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
