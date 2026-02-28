"""Text chunking for RAG."""

from typing import Generator


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> Generator[str, None, None]:
    """Split text into overlapping chunks."""
    if not text or not text.strip():
        return
    text = text.strip()
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        if chunk.strip():
            yield chunk.strip()
        start = end - overlap
        if start >= len(text):
            break
