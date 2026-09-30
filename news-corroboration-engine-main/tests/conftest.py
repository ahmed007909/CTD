import pytest

from news_engine.settings import Settings
from news_engine.storage import Store, iso
from news_engine.text import KeywordScanner


@pytest.fixture
def settings():
    return Settings(
        database_path=":memory:",
        ingestion_enabled=False,
        scraping_enabled=False,
        live_search_enabled=False,
        save_history=True,
        cache_queries=True,
        allowed_hosts=("testserver", "localhost", "127.0.0.1"),
    )


@pytest.fixture
def store():
    db = Store(":memory:")
    yield db
    db.close()


@pytest.fixture
def scanner(settings):
    return KeywordScanner(settings.keywords_path)


def article(title="Karachi airport reopened after repairs", source="dawn", slug="one", snippet="", **kwargs):
    return {
        "title": title,
        "source_id": source,
        "source_name": source.upper(),
        "url": f"https://{source}.com/news/{slug}",
        "snippet": snippet,
        "published_at": iso(),
        "flag_level": None,
        "matched_keywords": {},
        **kwargs,
    }
