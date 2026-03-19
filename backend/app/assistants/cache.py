"""
Redis cache layer for preset assistant answers.

Cache key schema:
    assistants:{assistant_type}:{question_id}
    e.g.  assistants:knowledge:k_001

One source answer (EN) is cached per question.
Translations are applied at response time (cheap LLM call or client-side).
TTL: 24 h by default, configurable via ASSISTANTS_CACHE_TTL env var.
"""

import json
import logging
from typing import Any

from app.settings import settings

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 60 * 60 * 24  # 24 hours


def _get_ttl() -> int:
    return getattr(settings, "assistants_cache_ttl", _DEFAULT_TTL)


def _make_key(assistant_type: str, question_id: str) -> str:
    return f"assistants:{assistant_type}:{question_id}"


class AssistantCache:
    """Thin async wrapper around redis-py for preset Q&A caching."""

    def __init__(self) -> None:
        self._redis: Any = None

    async def _get_client(self) -> Any:
        """Lazy-init Redis client (avoids import errors when Redis is unavailable)."""
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis  # type: ignore
            self._redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Verify connection
            await self._redis.ping()
            logger.info("Redis cache connected: %s", settings.redis_url)
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — cache disabled.", exc)
            self._redis = None
        return self._redis

    # ------------------------------------------------------------------

    async def get(self, assistant_type: str, question_id: str) -> dict | None:
        """Return cached payload or None on miss / Redis unavailable."""
        client = await self._get_client()
        if client is None:
            return None
        try:
            raw = await client.get(_make_key(assistant_type, question_id))
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning("Cache GET error: %s", exc)
        return None

    async def set(
        self,
        assistant_type: str,
        question_id: str,
        payload: dict,
        ttl: int | None = None,
    ) -> None:
        """Store payload in Redis. Silently ignores failures."""
        client = await self._get_client()
        if client is None:
            return
        try:
            await client.set(
                _make_key(assistant_type, question_id),
                json.dumps(payload, ensure_ascii=False),
                ex=ttl or _get_ttl(),
            )
        except Exception as exc:
            logger.warning("Cache SET error: %s", exc)

    async def delete(self, assistant_type: str, question_id: str) -> None:
        client = await self._get_client()
        if client is None:
            return
        try:
            await client.delete(_make_key(assistant_type, question_id))
        except Exception as exc:
            logger.warning("Cache DELETE error: %s", exc)

    async def flush_assistant(self, assistant_type: str) -> int:
        """Delete all cached answers for one assistant type. Returns count deleted."""
        client = await self._get_client()
        if client is None:
            return 0
        try:
            pattern = f"assistants:{assistant_type}:*"
            keys = await client.keys(pattern)
            if keys:
                await client.delete(*keys)
            return len(keys)
        except Exception as exc:
            logger.warning("Cache FLUSH error: %s", exc)
            return 0

    async def close(self) -> None:
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None


# Module-level singleton — one connection pool shared across requests
assistant_cache = AssistantCache()
