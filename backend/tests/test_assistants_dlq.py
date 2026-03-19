"""Tests for Dead Letter Queue module."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.assistants.dlq import DLQ, _build_entry, _DLQ_KEY, _QUERY_MAX, _ERROR_MAX


# ---------------------------------------------------------------------------
# _build_entry
# ---------------------------------------------------------------------------

def test_build_entry_fields():
    entry = _build_entry("knowledge", "what are the top products?", "timeout", 3, "k_001")
    assert entry["assistant_type"] == "knowledge"
    assert entry["question_id"] == "k_001"
    assert entry["attempts"] == 3
    assert "id" in entry
    assert "timestamp" in entry

def test_build_entry_truncates_query():
    long_query = "x" * 500
    entry = _build_entry("knowledge", long_query, "err", 1)
    assert len(entry["query"]) <= _QUERY_MAX

def test_build_entry_truncates_error():
    long_error = "e" * 500
    entry = _build_entry("knowledge", "q", long_error, 1)
    assert len(entry["error"]) <= _ERROR_MAX

def test_build_entry_no_question_id():
    entry = _build_entry("analyst", "custom query", "err", 2)
    assert entry["question_id"] is None


# ---------------------------------------------------------------------------
# DLQ Redis operations (mocked)
# ---------------------------------------------------------------------------

def _make_dlq_with_mock():
    """Return a DLQ instance with a mocked async Redis client.

    redis.asyncio pipeline() is synchronous; only execute() is async.
    Use MagicMock for pipeline and its queue methods; AsyncMock for execute().
    """
    d = DLQ()
    mock_client = AsyncMock()
    mock_pipe = MagicMock()                          # pipeline() returns sync obj
    mock_pipe.lpush = MagicMock()
    mock_pipe.ltrim = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[1, 1])
    mock_client.pipeline = MagicMock(return_value=mock_pipe)  # pipeline() is sync
    d._redis = mock_client
    return d, mock_client, mock_pipe


@pytest.mark.asyncio
async def test_push_uses_lpush_and_ltrim():
    d, client, pipe = _make_dlq_with_mock()
    await d.push("knowledge", "query text", "timeout error", 3, "k_001")
    pipe.lpush.assert_called_once()
    pipe.ltrim.assert_called_once()
    # Verify the key used
    call_args = pipe.lpush.call_args
    assert call_args[0][0] == _DLQ_KEY
    # Verify payload is valid JSON with expected fields
    payload = json.loads(call_args[0][1])
    assert payload["assistant_type"] == "knowledge"
    assert payload["question_id"] == "k_001"
    assert payload["attempts"] == 3


@pytest.mark.asyncio
async def test_push_when_redis_unavailable_does_not_raise():
    d = DLQ()
    d._redis = None
    # Should not raise even when Redis is down
    await d.push("knowledge", "q", "err", 1)


@pytest.mark.asyncio
async def test_list_items_returns_parsed_entries():
    d, client, _ = _make_dlq_with_mock()
    entry = _build_entry("knowledge", "q", "err", 1, "k_001")
    client.lrange = AsyncMock(return_value=[json.dumps(entry)])

    items = await d.list_items(limit=10)
    assert len(items) == 1
    assert items[0]["assistant_type"] == "knowledge"
    client.lrange.assert_called_with(_DLQ_KEY, 0, 9)


@pytest.mark.asyncio
async def test_list_items_empty_when_redis_unavailable():
    d = DLQ()
    d._client = AsyncMock(return_value=None)
    items = await d.list_items()
    assert items == []


@pytest.mark.asyncio
async def test_flush_deletes_queue():
    d, client, _ = _make_dlq_with_mock()
    client.llen = AsyncMock(return_value=5)
    client.delete = AsyncMock(return_value=1)

    count = await d.flush()
    assert count == 5
    client.delete.assert_called_once_with(_DLQ_KEY)


@pytest.mark.asyncio
async def test_flush_returns_zero_when_redis_unavailable():
    d = DLQ()
    d._client = AsyncMock(return_value=None)
    count = await d.flush()
    assert count == 0


@pytest.mark.asyncio
async def test_length_returns_queue_size():
    d, client, _ = _make_dlq_with_mock()
    client.llen = AsyncMock(return_value=7)
    assert await d.length() == 7


@pytest.mark.asyncio
async def test_push_caps_at_max_items():
    """ltrim is called with MAX_ITEMS - 1 as upper bound."""
    from app.assistants.dlq import _MAX_ITEMS
    d, client, pipe = _make_dlq_with_mock()
    await d.push("analyst", "q", "err", 2)
    pipe.ltrim.assert_called_with(_DLQ_KEY, 0, _MAX_ITEMS - 1)
