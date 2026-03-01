#!/usr/bin/env python3
"""Reset RAG a ingest - volá funkce přímo (bez HTTP)."""
import asyncio
import sys
from pathlib import Path

# Přidat /app do path
sys.path.insert(0, "/app")

from app.settings import settings
from app.knowledge_rag.service import get_vector_store
from app.knowledge_rag.ingest.loaders import load_documents_from_path
from app.knowledge_rag.ingest.chunking import chunk_text
import chromadb
from chromadb.config import Settings as ChromaSettings


def reset_store():
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
    return removed


async def ingest_folder(folder_path: str):
    store = get_vector_store()
    if not store:
        return {"status": "rag_disabled"}
    chunks, metadatas = [], []
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
    print(f"   Odstraněno: {removed or 'nic'}")

    print("2. Ingest z /data/knowledge...")
    result = asyncio.run(ingest_folder("/data/knowledge"))
    if result.get("status") == "rag_disabled":
        print("   RAG vypnut")
    else:
        print(f"   Ingestováno: {result.get('ingested', 0)} chunků")
    print("Hotovo.")


if __name__ == "__main__":
    main()
