"""
Warm the full preset cache workflow for demo usage.

Steps:
  1. Generate/cache all 40 EN preset answers through the backend API
  2. Translate EN answers into the requested locales

Usage (inside Docker):
    docker compose run --rm cache-warmup
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main(flush: bool, locales: list[str]) -> None:
    from scripts.ingest_preset_qa import main as ingest_main
    from scripts.translate_preset_qa import main as translate_main

    await ingest_main(["knowledge", "analyst"], flush=flush, dry_run=False)
    if locales:
        await translate_main(locales)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Warm all preset assistant cache entries")
    parser.add_argument("--flush", action="store_true", help="Flush preset cache before warming")
    parser.add_argument(
        "--locales",
        default="cs,sk,ru",
        help="Comma-separated non-EN locales to translate (default: cs,sk,ru)",
    )
    args = parser.parse_args()
    locales = [locale.strip() for locale in args.locales.split(",") if locale.strip()]
    asyncio.run(main(flush=args.flush, locales=locales))
