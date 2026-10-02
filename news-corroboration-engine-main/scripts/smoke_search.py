"""Opt-in live integration check; sends these public example terms to Google News."""

import asyncio
import json

import httpx

from news_engine.ingestion import USER_AGENT, SafeFetcher
from news_engine.search import NewsSearch
from news_engine.settings import Settings
from news_engine.storage import Store
from news_engine.text import KeywordScanner


async def main():
    settings = Settings(database_path=":memory:", ingestion_enabled=False, save_history=False)
    store = Store(":memory:")
    try:
        async with httpx.AsyncClient(
            timeout=15, headers={"User-Agent": USER_AGENT}, trust_env=False
        ) as client:
            search = NewsSearch(store, settings, KeywordScanner(settings.keywords_path), SafeFetcher(client))
            for query in ("CTD", "Dos", "DDos", "cyber", "cyber crime", "Babar"):
                result = await search.search(query, live=True)
                print(
                    json.dumps(
                        {
                            "query": query,
                            "live_search": result["live_search"],
                            "matches": result["total_matches"],
                            "verdict": result["verdict"],
                        }
                    ),
                    flush=True,
                )
    finally:
        store.close()


if __name__ == "__main__":
    asyncio.run(main())
