"""Text chunking for RAG — sentence-aware, word-based with overlap."""

import re
from typing import Generator


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on '.', '!', '?' followed by whitespace or end."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def chunk_text(
    text: str,
    chunk_size: int = 200,   # words per chunk
    overlap: int = 30,       # words of overlap between consecutive chunks
) -> Generator[str, None, None]:
    """
    Split text into overlapping chunks respecting sentence boundaries.

    Strategy:
      1. Split into sentences so chunks never cut mid-sentence.
      2. Accumulate sentences until the word budget (chunk_size) is reached.
      3. Slide the window back by `overlap` words for the next chunk.

    chunk_size and overlap are measured in words (not characters or tokens).
    """
    if not text or not text.strip():
        return

    sentences = _split_sentences(text)
    if not sentences:
        return

    word_counts = [len(s.split()) for s in sentences]
    n = len(sentences)
    i = 0

    while i < n:
        chunk_sentences: list[str] = []
        word_total = 0
        j = i

        # Accumulate sentences until budget is full
        while j < n and word_total + word_counts[j] <= chunk_size:
            chunk_sentences.append(sentences[j])
            word_total += word_counts[j]
            j += 1

        # Edge case: single sentence exceeds chunk_size — emit it as-is
        if not chunk_sentences:
            chunk_sentences = [sentences[i]]
            word_total = word_counts[i]
            j = i + 1

        yield " ".join(chunk_sentences)

        # If we consumed all remaining sentences, stop
        if j >= n:
            break

        # Slide window back by `overlap` words so next chunk shares context
        # Start from j and walk backwards until we've accumulated `overlap` words
        overlap_start = j
        overlap_words = 0
        for k in range(j - 1, i - 1, -1):
            if overlap_words + word_counts[k] > overlap:
                break
            overlap_words += word_counts[k]
            overlap_start = k

        # Always advance at least one sentence to guarantee progress
        i = max(overlap_start, i + 1)
