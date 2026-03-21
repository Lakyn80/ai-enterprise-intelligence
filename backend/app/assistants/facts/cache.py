"""Redis cache for deterministic facts results keyed by canonical spec hash."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.assistants.cache import assistant_cache
from app.settings import settings

logger = logging.getLogger(__name__)


def _make_key(spec_hash: str, data_fingerprint: str) -> str:
    return f"assistants:facts:v1:{data_fingerprint}:{spec_hash}"


def _set_kwargs() -> dict[str, int]:
    ttl = getattr(settings, "assistants_cache_ttl", 0)
    return {"ex": ttl} if ttl > 0 else {}


class DeterministicFactsCache:
    """Caches machine-readable deterministic resolver outputs."""

    async def get(self, spec_hash: str, data_fingerprint: str) -> dict[str, Any] | None:
        client = await assistant_cache._get_client()
        if client is None:
            return None
        try:
            raw = await client.get(_make_key(spec_hash, data_fingerprint))
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("Deterministic facts cache GET error: %s", exc)
            return None

    async def set(self, spec_hash: str, data_fingerprint: str, payload: dict[str, Any]) -> None:
        client = await assistant_cache._get_client()
        if client is None:
            return
        try:
            await client.set(
                _make_key(spec_hash, data_fingerprint),
                json.dumps(payload, ensure_ascii=False),
                **_set_kwargs(),
            )
        except Exception as exc:
            logger.warning("Deterministic facts cache SET error: %s", exc)


deterministic_facts_cache = DeterministicFactsCache()
