"""Knowledge RAG service."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.assistants.trace_recorder import AssistantTraceRecorder

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

    # Known category names in the dataset
    _CATEGORY_NAMES = {"electronics", "groceries", "furniture", "toys", "clothing"}

    @staticmethod
    def _infer_search_params(query: str) -> tuple[int, dict[str, Any] | None]:
        """
        Return (k, where_filter) tuned to the query intent.

        Rules (highest priority first):
          1. Specific product IDs (P0001 etc.) with no category context
             → filter to that product_id, k=2
          2. Comparison across products ("highest", "lowest", "best"…)
             → all product docs, k=20
          3. Named category question ("top products IN Groceries")
             → filter to that specific category doc, k=2
          4. General category comparison ("which category has best trend")
             → all category docs, k=5
          5. General category question → all category docs, k=5
          6. Default → k=8, no filter
        """
        import re
        q = query.lower()

        # Detect specific product IDs like P0001, P0014
        product_ids = re.findall(r"\bp0\d{2,4}\b", q)

        # Detect specific category names
        mentioned_cats = [c for c in KnowledgeService._CATEGORY_NAMES if c in q]

        is_category_ctx = (
            any(kw in q for kw in {"categor", "segment", "department"})
            or bool(mentioned_cats)
        )
        is_comparison = any(
            w in q
            for w in {
                "highest", "lowest", "best", "worst", "most", "least",
                "compare", "which product", "which category",
                "top product", "top seller",
            }
        )

        # 1. Specific product ID, no category context
        if product_ids and not is_category_ctx:
            if len(product_ids) == 1:
                pid = product_ids[0].upper()
                return 2, {"product_id": pid}
            # Multiple product IDs → get all product docs for comparison
            return 20, {"report_type": "product"}

        # 2. Cross-product comparison (no specific category)
        if is_comparison and not is_category_ctx:
            return 20, {"report_type": "product"}

        # 3. Named category + specific question ("top products in Groceries")
        if is_category_ctx and mentioned_cats:
            if len(mentioned_cats) > 1:
                # Multiple categories (e.g. "compare Electronics and Clothing")
                # → fetch all category docs so LLM can compare them
                return 5, {"report_type": "category"}
            cat_name = mentioned_cats[0].capitalize()
            return 2, {"category_id": cat_name}

        # 4 & 5. General category question
        if is_category_ctx:
            return 5, {"report_type": "category"}

        # 6. Default
        return 8, None

    @staticmethod
    def _presort_docs(docs: list[dict], query: str) -> list[dict]:
        """
        For cross-product ranking queries, sort docs so the correct
        answer appears first — preventing the LLM from anchoring on
        whichever product happens to rank highest by embedding similarity.
        """
        import re

        q = query.lower()
        want_min = any(w in q for w in {
            "lowest", "least", "minimum", "cheapest", "consistent",
            "most consistent", "lowest std", "lowest price",
        })
        want_max = any(w in q for w in {
            "highest", "most", "maximum", "expensive", "best promo",
            "most from promo", "most benefit",
        })
        if not (want_min or want_max):
            return docs

        def _num(pattern: str, text: str) -> float | None:
            m = re.search(pattern, text)
            if not m:
                return None
            return float(m.group(1).replace(",", ""))

        # Pick metric
        if any(w in q for w in {"total sales", "sales volume", "units sold"}):
            key_fn = lambda d: _num(r"Total sales:\s*([\d,]+)", d["content"]) or 0.0  # noqa
        elif any(w in q for w in {"std dev", "consistent", "volatil"}):
            key_fn = lambda d: _num(r"std dev:\s*([\d.]+)", d["content"]) or 0.0  # noqa
        elif any(w in q for w in {"price", "expensive", "cheap"}):
            key_fn = lambda d: _num(r"Average price:\s*([\d.]+)", d["content"]) or 0.0  # noqa
        elif any(w in q for w in {"promo", "promotion", "lift"}):
            key_fn = lambda d: _num(r"Promo lift:\s*([+-]?[\d.]+)%", d["content"]) or 0.0  # noqa
        else:
            return docs

        reverse = bool(want_max)
        return sorted(docs, key=key_fn, reverse=reverse)

    async def query(
        self,
        query: str,
        trace: "AssistantTraceRecorder | None" = None,
    ) -> dict[str, Any]:
        """Query RAG and return LLM-composed answer with citations."""
        if not self._store:
            if trace:
                trace.add_step("knowledge_rag_disabled", {"query": query}, status="warning")
            return {"answer": "RAG is disabled.", "citations": []}
        k, where = self._infer_search_params(query)
        if trace:
            trace.add_step(
                "knowledge_search_params",
                {"query": query, "k": k, "where": where},
            )
        docs = await self._store.similarity_search(query, k=k, where=where)
        if trace:
            trace.add_step(
                "knowledge_retrieval_result",
                {
                    "doc_count": len(docs),
                    "documents": [
                        {
                            "content": d.get("content", ""),
                            "metadata": d.get("metadata", {}),
                        }
                        for d in docs
                    ],
                },
            )
        if not docs:
            return {"answer": "No relevant documents found.", "citations": []}
        # For large product-comparison result sets, pre-sort by the relevant
        # metric so the LLM can simply pick the first/last entry.
        if k >= 20 and where and isinstance(where, dict) and where.get("report_type") == "product":
            docs = self._presort_docs(docs, query)
            if trace:
                trace.add_step(
                    "knowledge_presort_docs",
                    {
                        "sorted_documents": [
                            {
                                "content": d.get("content", ""),
                                "metadata": d.get("metadata", {}),
                            }
                            for d in docs
                        ],
                    },
                )
        context = "\n\n".join(d["content"] for d in docs)
        citations = [
            {"document_id": d.get("metadata", {}).get("source", "unknown"), "chunk": d["content"][:200]}
            for d in docs
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant for a retail forecasting platform. "
                    "Answer the user's question based ONLY on the provided document excerpts. "
                    "Rules:\n"
                    "1. Always quote exact numerical values as written in the excerpts — "
                    "never round, approximate, or reformat them.\n"
                    "2. When finding the highest or lowest value, scan EVERY excerpt and "
                    "compare ALL values before giving your answer.\n"
                    "3. If the excerpts do not contain enough information to answer the "
                    "question, respond with exactly: "
                    "'There is not enough information in the provided documents to answer "
                    "this question.'"
                ),
            },
            {
                "role": "user",
                "content": f"Document excerpts:\n\n{context[:12000]}\n\nQuestion: {query}",
            },
        ]
        try:
            from app.ai_assistant.providers.deepseek_provider import DeepSeekProvider
            llm = DeepSeekProvider()
            if trace:
                trace.add_step(
                    "knowledge_llm_request",
                    {"provider": "deepseek", "messages": messages},
                )
            result = await llm.generate(messages)
            answer = result["content"] or "No answer generated."
            if trace:
                trace.add_step(
                    "knowledge_llm_response",
                    {"content": answer, "tool_calls": result.get("tool_calls", [])},
                )
        except Exception:
            answer = f"Based on the following excerpts:\n\n{context[:2000]}"
            if trace:
                trace.add_step(
                    "knowledge_llm_fallback",
                    {"answer": answer},
                    status="warning",
                )
        return {"answer": answer, "citations": citations}
