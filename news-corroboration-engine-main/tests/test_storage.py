from datetime import timedelta

import pytest
from conftest import article

from news_engine.storage import canonical_url, iso, utcnow


def test_duplicate_and_update(store):
    a = article()
    first, changed = store.upsert_article(a)
    assert changed
    same, changed = store.upsert_article({**a, "url": a["url"] + "?utm_source=rss#top"})
    assert not changed and first["id"] == same["id"]
    updated, changed = store.upsert_article({**a, "title": "Karachi airport remains closed"})
    assert changed and updated["collected_at"] == first["collected_at"]
    assert len(store.articles()) == 1


def test_old_future_and_missing_dates(store):
    store.upsert_article(article(slug="old", published_at=iso(utcnow() - timedelta(days=30))))
    store.upsert_article(article(slug="future", published_at=iso(utcnow() + timedelta(days=1))))
    store.upsert_article(article(slug="unknown", published_at=None))
    assert len(store.articles()) == 1


def test_cache_invalidation_and_expiry(store):
    store.cache_put("a", {"value": 1}, 30)
    assert store.cache_get("a") == {"value": 1}
    store.upsert_article(article())
    assert store.cache_get("a") is None
    store.cache_put("a", {}, -1)
    assert store.cache_get("a") is None


def test_pagination_and_flag_filters(store):
    store.upsert_article(article(slug="one", flag_level="high"))
    store.upsert_article(article(slug="two", source="geo"))
    assert len(store.articles(flagged=True)) == 1
    assert len(store.articles(source="geo")) == 1
    assert len(store.articles(limit=1, offset=1)) == 1


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///etc/passwd", "https://user:pass@dawn.com/a"])
def test_unsafe_urls(url):
    with pytest.raises(ValueError):
        canonical_url(url)
