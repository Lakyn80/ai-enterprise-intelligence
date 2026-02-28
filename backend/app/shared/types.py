"""Shared type definitions."""

from typing import Protocol, TypeVar

T = TypeVar("T")


class SupportsAsyncContext(Protocol):
    """Protocol for async context managers."""

    async def __aenter__(self) -> "SupportsAsyncContext":
        ...

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        ...
