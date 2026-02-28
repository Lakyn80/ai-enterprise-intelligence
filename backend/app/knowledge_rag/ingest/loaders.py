"""Document loaders for RAG ingestion."""

from pathlib import Path
from typing import Generator


def load_text_file(path: Path) -> str:
    """Load plain text file."""
    return path.read_text(encoding="utf-8", errors="ignore")


def load_pdf(path: Path) -> str:
    """Load PDF and extract text."""
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return "\n".join(p.extract_text() or "" for p in reader.pages)


def load_documents_from_path(folder_path: str) -> Generator[tuple[str, dict], None, None]:
    """Load documents from folder. Yields (text, metadata)."""
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return
    for ext in ["*.txt", "*.md", "*.html"]:
        for p in folder.glob(ext):
            try:
                text = load_text_file(p)
                if text.strip():
                    yield text, {"source": str(p), "filename": p.name}
            except Exception:
                pass
    for p in folder.glob("*.pdf"):
        try:
            text = load_pdf(p)
            if text.strip():
                yield text, {"source": str(p), "filename": p.name}
        except Exception:
            pass
