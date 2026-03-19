"""Tests for assistants retry/backoff module."""

import pytest
from unittest.mock import AsyncMock, patch

from app.assistants.retry import build_retry, _is_retryable, _SingleAttempt


# ---------------------------------------------------------------------------
# _is_retryable
# ---------------------------------------------------------------------------

def test_not_retryable_value_error():
    assert _is_retryable(ValueError("bad input")) is False

def test_not_retryable_type_error():
    assert _is_retryable(TypeError("wrong type")) is False

def test_not_retryable_key_error():
    assert _is_retryable(KeyError("missing")) is False

def test_retryable_generic_exception():
    assert _is_retryable(Exception("network error")) is True

def test_retryable_os_error():
    assert _is_retryable(OSError("connection reset")) is True

def test_retryable_httpx_429():
    try:
        import httpx
        response = AsyncMock()
        response.status_code = 429
        exc = httpx.HTTPStatusError("rate limit", request=None, response=response)
        assert _is_retryable(exc) is True
    except ImportError:
        pytest.skip("httpx not installed")

def test_not_retryable_httpx_400():
    try:
        import httpx
        response = AsyncMock()
        response.status_code = 400
        exc = httpx.HTTPStatusError("bad request", request=None, response=response)
        assert _is_retryable(exc) is False
    except ImportError:
        pytest.skip("httpx not installed")

def test_retryable_httpx_500():
    try:
        import httpx
        response = AsyncMock()
        response.status_code = 503
        exc = httpx.HTTPStatusError("service unavailable", request=None, response=response)
        assert _is_retryable(exc) is True
    except ImportError:
        pytest.skip("httpx not installed")


# ---------------------------------------------------------------------------
# build_retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_retry_succeeds_first_attempt():
    """Successful call goes through without retries."""
    call_count = 0

    async def external_call():
        nonlocal call_count
        call_count += 1
        return "ok"

    async for attempt in build_retry(max_attempts=3):
        with attempt:
            result = await external_call()

    assert result == "ok"
    assert call_count == 1


@pytest.mark.asyncio
async def test_build_retry_retries_on_transient_error():
    """Transient error triggers retries, succeeds on 3rd attempt."""
    call_count = 0

    async def flaky_call():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("temporary failure")
        return "recovered"

    try:
        from tenacity import AsyncRetrying
    except ImportError:
        pytest.skip("tenacity not installed")

    result = None
    async for attempt in build_retry(max_attempts=3, max_wait=0.1):
        with attempt:
            result = await flaky_call()

    assert result == "recovered"
    assert call_count == 3


@pytest.mark.asyncio
async def test_build_retry_does_not_retry_value_error():
    """ValueError is raised immediately without retrying."""
    call_count = 0

    async def bad_call():
        nonlocal call_count
        call_count += 1
        raise ValueError("invalid input")

    try:
        from tenacity import AsyncRetrying
    except ImportError:
        pytest.skip("tenacity not installed")

    with pytest.raises(ValueError):
        async for attempt in build_retry(max_attempts=3, max_wait=0.1):
            with attempt:
                await bad_call()

    assert call_count == 1


@pytest.mark.asyncio
async def test_build_retry_exhausted_raises():
    """After max_attempts, the last exception is re-raised."""
    call_count = 0

    async def always_fails():
        nonlocal call_count
        call_count += 1
        raise ConnectionError("permanent failure")

    try:
        from tenacity import AsyncRetrying
    except ImportError:
        pytest.skip("tenacity not installed")

    with pytest.raises(ConnectionError):
        async for attempt in build_retry(max_attempts=3, max_wait=0.1):
            with attempt:
                await always_fails()

    assert call_count == 3


# ---------------------------------------------------------------------------
# _SingleAttempt fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_attempt_fallback_runs_once():
    """_SingleAttempt (no-tenacity fallback) runs the body exactly once."""
    call_count = 0

    async for attempt in _SingleAttempt():
        with attempt:
            call_count += 1

    assert call_count == 1


@pytest.mark.asyncio
async def test_single_attempt_fallback_propagates_exception():
    """_SingleAttempt propagates exceptions without retry."""
    with pytest.raises(RuntimeError, match="test error"):
        async for attempt in _SingleAttempt():
            with attempt:
                raise RuntimeError("test error")
