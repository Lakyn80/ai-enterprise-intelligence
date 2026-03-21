#!/usr/bin/env python3
"""Reset active RAG backend and ingest directly without HTTP."""
import asyncio
import sys

# Přidat /app do path
sys.path.insert(0, "/app")

from app.knowledge_rag.service import get_vector_store
from app.knowledge_rag.ingest.loaders import load_documents_from_path
from app.knowledge_rag.ingest.chunking import chunk_text


async def reset_store():
    store = get_vector_store()
    if not store:
        return []
    return await store.reset()


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
    removed = asyncio.run(reset_store())
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
