"""Read-only integration probe; prints feed status without retaining publisher bodies."""

import asyncio
import json

import feedparser
import httpx

from news_engine.ingestion import USER_AGENT, SafeFetcher
from news_engine.settings import Settings


async def main():
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": USER_AGENT}, trust_env=False) as client:
        fetcher = SafeFetcher(client)

        async def probe(source):
            try:
                raw, url = await fetcher.get(source["feed_url"], source["allowed_hosts"])
                parsed = feedparser.parse(raw)
                return {
                    "source": source["id"],
                    "url": url,
                    "format": parsed.get("version", ""),
                    "entries": len(parsed.entries),
                    "valid": bool(parsed.get("version") or parsed.entries),
                }
            except (httpx.HTTPError, ValueError, OSError) as exc:
                result = {"source": source["id"], "error": type(exc).__name__}
                if isinstance(exc, httpx.HTTPStatusError):
                    result["http_status"] = exc.response.status_code
                return result

        print(json.dumps(await asyncio.gather(*(probe(s) for s in Settings().sources)), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
