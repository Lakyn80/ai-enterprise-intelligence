"""Abstract interface for assistant semantic cache backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SemanticCacheBackend(ABC):
    """Interface for semantic cache vector backends."""

    @abstractmethod
    async def get(
        self,
        assistant_type: str,
        query: str,
        locale: str,
    ) -> dict[str, Any] | None:
        """Return the best semantic cache candidate."""
        ...

    @abstractmethod
    async def set(
        self,
        assistant_type: str,
        query: str,
        locale: str,
        payload: dict[str, Any],
    ) -> None:
        """Upsert a semantic cache entry."""
        ...

    @abstractmethod
    async def flush_assistant(self, assistant_type: str) -> int:
        """Delete semantic cache entries for one assistant type."""
        ...
