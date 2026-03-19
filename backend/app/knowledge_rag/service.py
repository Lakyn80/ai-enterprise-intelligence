"""Knowledge RAG service."""

from typing import Any

from app.knowledge_rag.ingest.chunking import chunk_text
from app.knowledge_rag.ingest.loaders import load_documents_from_path
from app.knowledge_rag.ingest.embeddings import get_embedding_provider
from app.knowledge_rag.vectorstores.base import VectorStore
from app.settings import settings


def get_vector_store() -> VectorStore | None:
    """Create vector store based on settings."""
    if not settings.rag_enabled:
        return None
    emb = get_embedding_provider()
    if settings.vectorstore == "faiss":
        from app.knowledge_rag.vectorstores.faiss_store import FAISSVectorStore
        return FAISSVectorStore(emb)
    from app.knowledge_rag.vectorstores.chroma_store import ChromaVectorStore
    return ChromaVectorStore(emb)


class KnowledgeService:
    """RAG service for document ingestion and querying."""

    def __init__(self, store: VectorStore | None = None):
        self._store = store or get_vector_store()

    async def ingest_from_folder(self, folder_path: str) -> dict[str, Any]:
        """Ingest documents from a folder."""
        if not self._store:
            return {"status": "rag_disabled", "ingested": 0}
        chunks: list[str] = []
        metadatas: list[dict] = []
        for text, meta in load_documents_from_path(folder_path):
            for chunk in chunk_text(text):
                chunks.append(chunk)
                metadatas.append(meta)
        if not chunks:
            return {"status": "ok", "ingested": 0, "message": "No documents found"}
        ids = await self._store.add_documents(chunks, metadatas)
        return {"status": "ok", "ingested": len(ids)}

    async def ingest_text(
        self,
        text: str,
        source: str = "upload",
        metadata: dict[str, Any] | None = None,
        context_prefix: str = "",
    ) -> dict[str, Any]:
        """
        Ingest raw text into the vector store.

        Args:
            text:           Raw text to chunk and embed.
            source:         Source identifier stored in metadata.
            metadata:       Optional structured metadata (product_id, report_type, etc.)
                            merged with {"source": source} for every chunk.
            context_prefix: Prepended to each chunk before embedding to improve
                            semantic relevance (e.g. "Product P0001 sales report: ").
                            The prefix is stored but not duplicated in the chunk text.
        """
        if not self._store:
            return {"status": "rag_disabled", "ingested": 0}

        chunks = list(chunk_text(text))
        if not chunks:
            return {"status": "ok", "ingested": 0}

        base_meta: dict[str, Any] = {"source": source}
        if metadata:
            base_meta.update(metadata)

        chunk_texts: list[str] = []
        chunk_metas: list[dict] = []
        for i, chunk in enumerate(chunks):
            embed_text = f"{context_prefix}{chunk}" if context_prefix else chunk
            chunk_texts.append(embed_text)
            chunk_metas.append({**base_meta, "chunk_index": i, "total_chunks": len(chunks)})

        ids = await self._store.add_documents(chunk_texts, chunk_metas)
        return {"status": "ok", "ingested": len(ids)}

    async def query(self, query: str) -> dict[str, Any]:
        """Query RAG and return LLM-composed answer with citations."""
        if not self._store:
            return {"answer": "RAG is disabled.", "citations": []}
        docs = await self._store.similarity_search(query, k=4)
        if not docs:
            return {"answer": "No relevant documents found.", "citations": []}
        context = "\n\n".join(d["content"] for d in docs)
        citations = [
            {"document_id": d.get("metadata", {}).get("source", "unknown"), "chunk": d["content"][:200]}
            for d in docs
        ]
        try:
            from app.ai_assistant.providers.deepseek_provider import DeepSeekProvider
            llm = DeepSeekProvider()
            result = await llm.generate([
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant for a retail forecasting platform. "
                        "Answer the user's question based ONLY on the provided document excerpts. "
                        "Be concise and cite relevant facts. If the excerpts don't contain enough "
                        "information, say so clearly."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Document excerpts:\n\n{context[:4000]}\n\nQuestion: {query}",
                },
            ])
            answer = result["content"] or "No answer generated."
        except Exception:
            answer = f"Based on the following excerpts:\n\n{context[:2000]}"
        return {"answer": answer, "citations": citations}
