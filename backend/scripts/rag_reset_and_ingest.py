#!/usr/bin/env python3
"""Reset RAG store a pře-ingest dokumentů s novými embeddings."""
import asyncio
import shutil
from pathlib import Path

from app.knowledge_rag.ingest.embeddings import get_embedding_provider
from app.knowledge_rag.ingest.loaders import load_documents_from_path
from app.knowledge_rag.ingest.chunking import chunk_text
from app.knowledge_rag.service import get_vector_store


def reset_store():
    """Smazat Chroma collection a faiss_index."""
    from app.settings import settings
    import chromadb
    from chromadb.config import Settings as ChromaSettings

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
    return removed


async def ingest_folder(folder_path: str):
    """Ingestovat dokumenty ze složky."""
    store = get_vector_store()
    if not store:
        return {"status": "rag_disabled"}
    chunks = []
    metadatas = []
    for text, meta in load_documents_from_path(folder_path):
        for chunk in chunk_text(text):
            chunks.append(chunk)
            metadatas.append(meta)
    if not chunks:
        return {"status": "ok", "ingested": 0}
    ids = await store.add_documents(chunks, metadatas)
    return {"status": "ok", "ingested": len(ids)}


def main():
    print("1. Reset RAG store...")
    removed = reset_store()
    print(f"   Odstraněno: {removed or 'nic (už byl prázdný)'}")

    print("2. Ingest dokumentů z /data/knowledge...")
    result = asyncio.run(ingest_folder("/data/knowledge"))
    if result.get("status") == "rag_disabled":
        print("   RAG je vypnutý (RAG_ENABLED=false)")
    else:
        print(f"   Ingestováno: {result.get('ingested', 0)} chunků")

    print("Hotovo.")


if __name__ == "__main__":
    main()
