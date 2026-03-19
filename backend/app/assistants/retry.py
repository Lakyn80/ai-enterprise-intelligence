"""
Retry + exponential backoff for external calls (LLM, RAG).

Use ONLY around external I/O — LLM providers, vector store queries.
Do NOT wrap service orchestration logic.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Errors that should NOT be retried (bad input, logic errors)
_NO_RETRY_TYPES = (ValueError, TypeError, KeyError, AttributeError)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, _NO_RETRY_TYPES):
        return False
    # httpx HTTP errors: retry 429 + 5xx only
    try:
        import httpx
        if isinstance(exc, httpx.HTTPStatusError):
            code = exc.response.status_code
            return code == 429 or code >= 500
        if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout)):
            return True
    except ImportError:
        pass
    # Generic network / connection errors → retry
    return True


def build_retry(max_attempts: int = 3, max_wait: float = 10.0):
    """
    Return a tenacity AsyncRetrying instance.

    Usage:
        async for attempt in build_retry():
            with attempt:
                result = await external_call(...)
    """
    try:
        from tenacity import (
            AsyncRetrying,
            stop_after_attempt,
            wait_exponential,
            retry_if_exception,
            before_sleep_log,
        )

        return AsyncRetrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=max_wait),
            retry=retry_if_exception(_is_retryable),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
    except ImportError:
        # tenacity not installed — return a single-attempt fallback
        return _SingleAttempt()


class _SingleAttempt:
    """Fallback when tenacity is not installed: runs exactly once."""

    def __aiter__(self):
        self._done = False
        return self

    async def __anext__(self):
        if self._done:
            raise StopAsyncIteration
        self._done = True
        return _NullContext()


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, *_: Any):
        return False
