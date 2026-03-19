"""
Idempotency store — prevent duplicate LLM calls on client retries.

Key schema:
    idempotency:{key}        →  JSON result  (TTL: 24h)
    idempotency:{key}:lock   →  "processing" (TTL: 30s — MUST have TTL to avoid deadlock)

Flow:
    1. GET result key  → HIT: return stored response
    2. SET NX lock key → acquired: process request, store result, delete lock
                       → not acquired: poll up to 5× / 500 ms, then 202
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_PREFIX = "idempotency:"
_LOCK_SUFFIX = ":lock"
_RESULT_TTL = 60 * 60 * 24   # 24 h
_LOCK_TTL = 30               # 30 s — hard cap to prevent deadlock
_POLL_INTERVAL = 0.5         # seconds
_POLL_MAX = 5                # attempts before giving up with 202


class IdempotencyStore:

    def __init__(self) -> None:
        self._redis = None

    async def _client(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis
            from app.settings import settings
            self._redis = aioredis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True
            )
            await self._redis.ping()
        except Exception as exc:
            logger.warning("Idempotency Redis unavailable: %s", exc)
            self._redis = None
        return self._redis

    # ------------------------------------------------------------------

    async def get_result(self, key: str) -> dict | None:
        """Return stored result or None on miss / Redis down."""
        client = await self._client()
        if client is None:
            return None
        try:
            raw = await client.get(_PREFIX + key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("Idempotency GET error: %s", exc)
            return None

    async def acquire_lock(self, key: str) -> bool:
        """
        Try to acquire processing lock via SET NX.
        Returns True if lock was acquired.
        TTL is enforced server-side — no deadlock risk.
        """
        client = await self._client()
        if client is None:
            return True  # Redis down → proceed without idempotency
        try:
            lock_key = _PREFIX + key + _LOCK_SUFFIX
            acquired = await client.set(lock_key, "processing", nx=True, ex=_LOCK_TTL)
            return bool(acquired)
        except Exception as exc:
            logger.warning("Idempotency lock error: %s", exc)
            return True  # fail open

    async def store_result(self, key: str, result: dict) -> None:
        """Store result and release lock atomically via pipeline."""
        client = await self._client()
        if client is None:
            return
        try:
            lock_key = _PREFIX + key + _LOCK_SUFFIX
            pipe = client.pipeline()
            pipe.set(_PREFIX + key, json.dumps(result, ensure_ascii=False), ex=_RESULT_TTL)
            pipe.delete(lock_key)
            await pipe.execute()
        except Exception as exc:
            logger.warning("Idempotency store error: %s", exc)

    async def release_lock(self, key: str) -> None:
        """Release lock without storing result (error path)."""
        client = await self._client()
        if client is None:
            return
        try:
            await client.delete(_PREFIX + key + _LOCK_SUFFIX)
        except Exception:
            pass

    async def is_processing(self, key: str) -> bool:
        """Check whether another worker is currently processing this key."""
        client = await self._client()
        if client is None:
            return False
        try:
            val = await client.get(_PREFIX + key + _LOCK_SUFFIX)
            return val == "processing"
        except Exception:
            return False

    async def wait_for_result(self, key: str) -> dict | None:
        """
        Poll until the processing lock clears or a result appears.
        Returns result dict if available within timeout, else None (→ 202).
        """
        for _ in range(_POLL_MAX):
            await asyncio.sleep(_POLL_INTERVAL)
            result = await self.get_result(key)
            if result is not None:
                return result
            still_processing = await self.is_processing(key)
            if not still_processing:
                # Lock expired or released without result → fail-safe, re-process
                return None
        return None


# Module singleton
idempotency_store = IdempotencyStore()
