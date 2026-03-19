"""
Migrate old EN cache + translate all 40 preset answers to CS/SK/RU.

Steps:
  1. Read old-format keys assistants:{type}:{id}  (no locale suffix)
  2. Store as assistants:{type}:{id}:en
  3. Translate EN answer → CS, SK, RU via DeepSeek
  4. Store each translation as assistants:{type}:{id}:{locale}
  5. Delete old-format keys

Usage (inside Docker):
    docker exec ai-enterprise-intelligence-backend-1 \
        python -m scripts.translate_preset_qa
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOCALES = ["cs", "sk", "ru"]
LOCALE_NAMES = {"cs": "Czech", "sk": "Slovak", "ru": "Russian"}


async def translate_answer(answer: str, target_locale: str) -> str:
    """Translate answer text to target locale via DeepSeek."""
    from app.ai_assistant.providers.deepseek_provider import DeepSeekProvider
    provider = DeepSeekProvider()
    lang = LOCALE_NAMES[target_locale]
    result = await provider.generate([
        {
            "role": "system",
            "content": (
                f"You are a professional translator. Translate the following retail analytics "
                f"answer from English to {lang}. "
                "Rules: Keep all numbers, product IDs (e.g. P0001), percentages, and dates unchanged. "
                "Keep technical terms (MAE, RMSE, std dev) in their original form. "
                "Output only the translated text, nothing else."
            ),
        },
        {"role": "user", "content": answer},
    ])
    return result.get("content", answer).strip()


async def main() -> None:
    import redis.asyncio as aioredis
    from app.settings import settings
    from app.assistants.presets import get_presets

    print(f"Redis: {settings.redis_url}")
    client = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    await client.ping()

    all_presets = (
        [("knowledge", p) for p in get_presets("knowledge")] +
        [("analyst", p) for p in get_presets("analyst")]
    )
    total = len(all_presets)

    for idx, (atype, preset) in enumerate(all_presets, 1):
        qid = preset.id
        print(f"\n[{idx}/{total}] {atype}/{qid}: {preset.query_en[:60]}")

        # ----------------------------------------------------------------
        # 1. Get EN answer — try new key first, then old key
        # ----------------------------------------------------------------
        new_en_key = f"assistants:{atype}:{qid}:en"
        old_key = f"assistants:{atype}:{qid}"

        en_raw = await client.get(new_en_key)
        if en_raw:
            en_payload = json.loads(en_raw)
            print(f"  EN: already in new key")
        else:
            en_raw = await client.get(old_key)
            if en_raw:
                en_payload = json.loads(en_raw)
                # Migrate to new key
                await client.set(new_en_key, en_raw, ex=60 * 60 * 24)
                await client.delete(old_key)
                print(f"  EN: migrated from old key → {new_en_key}")
            else:
                print(f"  EN: NOT IN CACHE — skipping (run ingest_preset_qa.py first)")
                continue

        en_answer = en_payload.get("answer", "")
        if not en_answer:
            print(f"  EN: empty answer — skipping")
            continue

        # ----------------------------------------------------------------
        # 2. Translate to each locale
        # ----------------------------------------------------------------
        for locale in LOCALES:
            locale_key = f"assistants:{atype}:{qid}:{locale}"
            existing = await client.get(locale_key)
            if existing:
                print(f"  {locale.upper()}: already cached — skipping")
                continue

            try:
                translated = await translate_answer(en_answer, locale)
                payload = {
                    "answer": translated,
                    "citations": en_payload.get("citations", []),
                    "used_tools": en_payload.get("used_tools", []),
                }
                await client.set(locale_key, json.dumps(payload, ensure_ascii=False), ex=60 * 60 * 24)
                print(f"  {locale.upper()}: cached ({len(translated)} chars)")
            except Exception as exc:
                print(f"  {locale.upper()}: ERROR — {exc}")

    await client.aclose()

    # Summary
    print("\n=== Cache summary ===")
    for atype in ("knowledge", "analyst"):
        for locale in ("en", "cs", "sk", "ru"):
            pattern = f"assistants:{atype}:*:{locale}"
            keys = await client.keys(pattern) if not client.is_closed else []
            # reopen for keys check
            pass

    client2 = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    for atype in ("knowledge", "analyst"):
        counts = {}
        for locale in ("en", "cs", "sk", "ru"):
            keys = await client2.keys(f"assistants:{atype}:*:{locale}")
            counts[locale] = len(keys)
        print(f"  {atype}: EN={counts['en']} CS={counts['cs']} SK={counts['sk']} RU={counts['ru']}")
    await client2.aclose()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
