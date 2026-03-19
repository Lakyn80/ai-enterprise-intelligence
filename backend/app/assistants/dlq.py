"""
Dead Letter Queue — failed assistant requests after all retries exhausted.

Redis key:  assistants:dlq          (List, LPUSH / LRANGE / LTRIM)
Max items:  500 (oldest dropped on overflow)

Payload is intentionally small — no large answer text, no full query body.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_DLQ_KEY = "assistants:dlq"
_MAX_ITEMS = 500
_QUERY_MAX = 200   # truncate query to keep payload small
_ERROR_MAX = 300


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_entry(
    assistant_type: str,
    query: str,
    error: str,
    attempts: int,
    question_id: str | None = None,
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "assistant_type": assistant_type,
        "question_id": question_id,
        "query": query[:_QUERY_MAX],
        "error": str(error)[:_ERROR_MAX],
        "attempts": attempts,
        "timestamp": _now_iso(),
    }


class DLQ:
    """Thin async Redis wrapper for the Dead Letter Queue."""

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
            logger.warning("DLQ Redis unavailable: %s", exc)
            self._redis = None
        return self._redis

    # ------------------------------------------------------------------

    async def push(
        self,
        assistant_type: str,
        query: str,
        error: str,
        attempts: int,
        question_id: str | None = None,
    ) -> None:
        client = await self._client()
        if client is None:
            logger.error(
                "DLQ push failed (Redis down) | type=%s qid=%s error=%s",
                assistant_type, question_id, error,
            )
            return
        entry = _build_entry(assistant_type, query, error, attempts, question_id)
        try:
            pipe = client.pipeline()
            pipe.lpush(_DLQ_KEY, json.dumps(entry))
            pipe.ltrim(_DLQ_KEY, 0, _MAX_ITEMS - 1)  # cap list size
            await pipe.execute()
            logger.warning(
                "DLQ | type=%s qid=%s error=%s",
                assistant_type, question_id, error[:80],
            )
        except Exception as exc:
            logger.error("DLQ push error: %s", exc)

    async def list_items(self, limit: int = 100) -> list[dict]:
        client = await self._client()
        if client is None:
            return []
        try:
            raw_items = await client.lrange(_DLQ_KEY, 0, limit - 1)
            return [json.loads(r) for r in raw_items]
        except Exception as exc:
            logger.warning("DLQ list error: %s", exc)
            return []

    async def flush(self) -> int:
        client = await self._client()
        if client is None:
            return 0
        try:
            count = await client.llen(_DLQ_KEY)
            await client.delete(_DLQ_KEY)
            return count
        except Exception as exc:
            logger.warning("DLQ flush error: %s", exc)
            return 0

    async def length(self) -> int:
        client = await self._client()
        if client is None:
            return 0
        try:
            return await client.llen(_DLQ_KEY)
        except Exception:
            return 0


# Module singleton
dlq = DLQ()
