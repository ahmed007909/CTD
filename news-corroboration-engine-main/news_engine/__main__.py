import argparse
import asyncio
import json

import httpx

from .ingestion import USER_AGENT, Ingestor, SafeFetcher
from .live import LiveHub
from .matching import Matcher
from .settings import Settings
from .storage import Store
from .text import KeywordScanner, TextProcessor


def main():
    parser = argparse.ArgumentParser(description="News Corroboration Engine")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Check against the current local article index")
    check.add_argument("claim")
    commands.add_parser("ingest", help="Fetch all configured sources once")
    args = parser.parse_args()
    settings = Settings.from_env()
    store = Store(settings.database_path)
    scanner = KeywordScanner(settings.keywords_path)
    try:
        if args.command == "check":
            print(
                json.dumps(Matcher(store, settings, scanner).check(args.claim), ensure_ascii=False, indent=2)
            )
        else:

            async def run():
                async with httpx.AsyncClient(
                    timeout=15, headers={"User-Agent": USER_AGENT}, trust_env=False
                ) as client:
                    ingestor = Ingestor(
                        store,
                        settings,
                        scanner,
                        TextProcessor(settings.spacy_model),
                        LiveHub().publish,
                        SafeFetcher(client),
                    )
                    return await ingestor.run_once()

            print(json.dumps(asyncio.run(run()), indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
