"""Tests for idempotency store module."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.assistants.idempotency import IdempotencyStore, _PREFIX, _LOCK_SUFFIX, _LOCK_TTL, _RESULT_TTL


def _make_store():
    store = IdempotencyStore()
    mock = AsyncMock()
    store._redis = mock
    return store, mock


# ---------------------------------------------------------------------------
# get_result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_result_returns_none_on_miss():
    store, mock = _make_store()
    mock.get = AsyncMock(return_value=None)
    result = await store.get_result("key123")
    assert result is None
    mock.get.assert_called_with(_PREFIX + "key123")


@pytest.mark.asyncio
async def test_get_result_returns_parsed_dict():
    store, mock = _make_store()
    payload = {"answer": "42", "locale": "en", "cached": False, "citations": [], "used_tools": []}
    mock.get = AsyncMock(return_value=json.dumps(payload))
    result = await store.get_result("key123")
    assert result["answer"] == "42"


@pytest.mark.asyncio
async def test_get_result_none_when_redis_unavailable():
    store = IdempotencyStore()
    store._redis = None
    assert await store.get_result("key") is None


# ---------------------------------------------------------------------------
# acquire_lock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_lock_returns_true_on_first():
    store, mock = _make_store()
    mock.set = AsyncMock(return_value=True)
    acquired = await store.acquire_lock("key123")
    assert acquired is True
    # Must use NX=True and EX=_LOCK_TTL to prevent deadlock
    mock.set.assert_called_once_with(
        _PREFIX + "key123" + _LOCK_SUFFIX,
        "processing",
        nx=True,
        ex=_LOCK_TTL,
    )


@pytest.mark.asyncio
async def test_acquire_lock_returns_false_when_already_locked():
    store, mock = _make_store()
    mock.set = AsyncMock(return_value=None)  # SET NX returns None when key exists
    acquired = await store.acquire_lock("key123")
    assert acquired is False


@pytest.mark.asyncio
async def test_acquire_lock_ttl_is_set():
    """Lock TTL must be set — prevents deadlock if worker crashes."""
    store, mock = _make_store()
    mock.set = AsyncMock(return_value=True)
    await store.acquire_lock("key123")
    call_kwargs = mock.set.call_args[1]
    assert "ex" in call_kwargs
    assert call_kwargs["ex"] == _LOCK_TTL
    assert _LOCK_TTL > 0


@pytest.mark.asyncio
async def test_acquire_lock_fail_open_when_redis_unavailable():
    """If Redis is down, fail open (allow processing rather than blocking)."""
    store = IdempotencyStore()
    store._redis = None
    acquired = await store.acquire_lock("key")
    assert acquired is True


# ---------------------------------------------------------------------------
# store_result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_store_result_sets_key_and_deletes_lock():
    store, mock = _make_store()
    # redis.asyncio pipeline() is synchronous; only execute() is async
    pipe = MagicMock()
    pipe.set = MagicMock()
    pipe.delete = MagicMock()
    pipe.execute = AsyncMock(return_value=[True, 1])
    mock.pipeline = MagicMock(return_value=pipe)

    payload = {"answer": "hello", "locale": "en", "cached": False, "citations": [], "used_tools": []}
    await store.store_result("key123", payload)

    pipe.set.assert_called_once()
    set_args = pipe.set.call_args
    assert set_args[0][0] == _PREFIX + "key123"
    assert set_args[1]["ex"] == _RESULT_TTL

    pipe.delete.assert_called_once_with(_PREFIX + "key123" + _LOCK_SUFFIX)


# ---------------------------------------------------------------------------
# release_lock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_release_lock_deletes_lock_key():
    store, mock = _make_store()
    mock.delete = AsyncMock(return_value=1)
    await store.release_lock("key123")
    mock.delete.assert_called_once_with(_PREFIX + "key123" + _LOCK_SUFFIX)


# ---------------------------------------------------------------------------
# is_processing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_processing_true():
    store, mock = _make_store()
    mock.get = AsyncMock(return_value="processing")
    assert await store.is_processing("key") is True


@pytest.mark.asyncio
async def test_is_processing_false():
    store, mock = _make_store()
    mock.get = AsyncMock(return_value=None)
    assert await store.is_processing("key") is False


# ---------------------------------------------------------------------------
# wait_for_result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wait_for_result_returns_result_when_available():
    """Poll succeeds: get_result returns None on first poll, result on second."""
    store, _ = _make_store()
    payload = {"answer": "done", "locale": "en", "cached": False, "citations": [], "used_tools": []}

    call_count = 0

    async def mock_get_result(key):
        nonlocal call_count
        call_count += 1
        return payload if call_count >= 2 else None

    # Patch the high-level methods to avoid Redis client interactions
    store.get_result = mock_get_result
    store.is_processing = AsyncMock(return_value=True)  # lock still held

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await store.wait_for_result("key123")

    assert result is not None
    assert result["answer"] == "done"


@pytest.mark.asyncio
async def test_wait_for_result_returns_none_on_timeout():
    store, mock = _make_store()
    mock.get = AsyncMock(return_value=None)  # always None → timeout

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await store.wait_for_result("key123")

    assert result is None
