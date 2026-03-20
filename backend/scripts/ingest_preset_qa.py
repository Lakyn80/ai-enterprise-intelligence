"""
Pre-warm the Redis cache for all 40 preset questions.

Usage (inside Docker):
    docker exec ai-enterprise-intelligence-backend-1 \
        python -m scripts.ingest_preset_qa

Options:
    --type knowledge|analyst   Only ingest one assistant type (default: both)
    --flush                    Flush existing cache before ingesting
    --dry-run                  Print questions without calling the backend
"""

import argparse
import asyncio
import sys

# ---------------------------------------------------------------------------
# Make sure app package is importable when running as a module
# ---------------------------------------------------------------------------
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main(assistant_types: list[str], flush: bool, dry_run: bool) -> None:
    from app.assistants.presets import get_presets
    from app.assistants.cache import assistant_cache
    from app.settings import settings
    import httpx

    print(f"RAG enabled: {settings.rag_enabled}")
    print(f"Redis URL:   {settings.redis_url}")
    api_base = os.environ.get("INTERNAL_API_URL", "http://localhost:8000")
    print(f"API base:    {api_base}")

    for atype in assistant_types:
        presets = get_presets(atype)  # type: ignore[arg-type]
        print(f"\n=== {atype.upper()} — {len(presets)} questions ===")

        if flush and not dry_run:
            deleted = await assistant_cache.flush_assistant(atype)
            print(f"  Flushed {deleted} cached entries")

        for preset in presets:
            q = preset.query_en
            print(f"  [{preset.id}] {q[:80]}")

            if dry_run:
                continue

            # Check cache first — skip if already warm
            cached = await assistant_cache.get(atype, preset.id, locale="en")
            if cached:
                print(f"    → already cached, skipping")
                continue

            # Generate answer
            try:
                url = f"{api_base}/api/assistants/ask-preset"
                async with httpx.AsyncClient(timeout=120) as http:
                    resp = await http.post(url, json={
                        "assistant_type": atype,
                        "question_id": preset.id,
                        "locale": "en",
                    })
                    resp.raise_for_status()
                    data = resp.json()

                answer = data.get("answer", "")
                used_tools = data.get("used_tools", [])
                print(f"    → cached via API ({len(answer)} chars, tools: {used_tools})")

            except Exception as exc:
                print(f"    !! ERROR: {exc}")

    await assistant_cache.close()
    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-warm assistant preset cache")
    parser.add_argument(
        "--type",
        choices=["knowledge", "analyst", "both"],
        default="both",
        dest="atype",
    )
    parser.add_argument("--flush", action="store_true", help="Flush cache before ingesting")
    parser.add_argument("--dry-run", action="store_true", help="List questions without calling LLM")
    args = parser.parse_args()

    types = ["knowledge", "analyst"] if args.atype == "both" else [args.atype]
    asyncio.run(main(types, flush=args.flush, dry_run=args.dry_run))
