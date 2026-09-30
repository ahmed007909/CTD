from unittest.mock import AsyncMock

import httpx
import pytest

from news_engine.ingestion import Ingestor, SafeFetcher, publication_date
from news_engine.live import LiveHub
from news_engine.text import TextProcessor

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Test</title>
<item><title>Bomb explosion reported in Karachi</title><link>https://www.dawn.com/news/123</link>
<description>A test news snippet</description><pubDate>Fri, 18 Sep 2026 10:00:00 +0500</pubDate></item>
</channel></rss>"""


async def test_ingestion_dedup_and_broadcast(store, settings, scanner):
    fetcher = AsyncMock()
    fetcher.get.return_value = (RSS, "https://www.dawn.com/feeds/home")
    hub = LiveHub()
    queue = hub.subscribe()
    ingestor = Ingestor(store, settings, scanner, TextProcessor(), hub.publish, fetcher)
    source = settings.sources[0]
    assert (await ingestor.ingest_source(source))["changed_articles"] == 1
    event = queue.get_nowait()
    assert event["alert"] is True
    assert event["article"]["flag_level"] == "high"
    assert event["article"]["published_at"] == "2026-09-18T05:00:00+00:00"
    assert (await ingestor.ingest_source(source))["changed_articles"] == 0
    assert queue.empty()


async def test_failure_isolation(store, settings, scanner):
    fetcher = AsyncMock()
    fetcher.get.side_effect = httpx.ConnectError("not logged")
    ingestor = Ingestor(store, settings, scanner, TextProcessor(), LiveHub().publish, fetcher)
    statuses = await ingestor.run_once()
    assert len(statuses) == 6 and all(s["state"] == "error" for s in statuses)
    assert len(store.source_statuses()) == 6


async def test_html_is_not_misreported_as_empty_feed(store, settings, scanner):
    fetcher = AsyncMock()
    fetcher.get.return_value = (b"<html>Access denied</html>", "https://www.dawn.com/")
    ingestor = Ingestor(store, settings, scanner, TextProcessor(), LiveHub().publish, fetcher)
    assert (await ingestor.ingest_source(settings.sources[0]))["state"] == "error"


async def test_oversized_and_redirected_responses(monkeypatch):
    async def handler(request):
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
        return httpx.Response(200, content=b"x" * 3_000_001)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = SafeFetcher(client)

        async def validate(url, hosts):
            if "127.0.0.1" in url:
                raise ValueError("private host")

        monkeypatch.setattr(fetcher, "validate", validate)
        with pytest.raises(ValueError, match="size"):
            await fetcher.get("https://www.dawn.com/large", ["www.dawn.com"])
        with pytest.raises(ValueError, match="private"):
            await fetcher.get("https://www.dawn.com/redirect", ["www.dawn.com"])


async def test_private_dns_and_host_allowlist(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *args: [(2, 1, 6, "", ("127.0.0.1", 443))])
    fetcher = SafeFetcher(None)
    with pytest.raises(ValueError, match="non-public"):
        await fetcher.validate("https://www.dawn.com/a", ["www.dawn.com"])
    with pytest.raises(ValueError, match="allowlist"):
        await fetcher.validate("https://evil.example/a", ["www.dawn.com"])


async def test_backpressure():
    hub = LiveHub()
    q = hub.subscribe()
    for _ in range(101):
        await hub.publish({"type": "article"})
    assert q.qsize() == 1 and q.get_nowait()["type"] == "resync_required"
    hub.unsubscribe(q)
    assert not hub.queues


def test_utc_conversion_and_invalid_dates():
    assert publication_date({"published": "2026-09-18T15:00:00+05:00"}) == "2026-09-18T10:00:00+00:00"
    assert publication_date({"published": "nonsense"}) is None
    assert publication_date({"updated": "2026-09-18"}) is None


async def test_404_feed_falls_back_to_html(store, settings, scanner):
    settings.scraping_enabled = True
    source = settings.sources[0]
    request = httpx.Request("GET", source["feed_url"])
    response = httpx.Response(404, request=request)
    fetcher = AsyncMock()
    fetcher.get.side_effect = [
        httpx.HTTPStatusError("missing", request=request, response=response),
        (
            b'<h2><a href="/news/123">Karachi airport reopens after extensive repairs</a></h2>',
            source["homepage"],
        ),
    ]
    fetcher.can_scrape.return_value = True
    ingestor = Ingestor(store, settings, scanner, TextProcessor(), LiveHub().publish, fetcher)
    entries, mode = await ingestor.entries(source)
    assert mode == "html_fallback" and len(entries) == 1
    assert entries[0]["link"] == "https://www.dawn.com/news/123"


async def test_full_body_flagged_but_only_snippet_stored(store, settings, scanner):
    settings.snippet_max_chars = 50
    raw = RSS.replace(b"A test news snippet", b"Ordinary text. " * 100 + b" hostage")
    raw = raw.replace(b"Bomb explosion reported in Karachi", b"Local report published from Karachi")
    fetcher = AsyncMock()
    fetcher.get.return_value = (raw, "https://www.dawn.com/feeds/home")
    hub = LiveHub()
    q = hub.subscribe()
    ingestor = Ingestor(store, settings, scanner, TextProcessor(), hub.publish, fetcher)
    await ingestor.ingest_source(settings.sources[0])
    saved = q.get_nowait()["article"]
    assert len(saved["snippet"]) == 50 and "hostage" not in saved["snippet"]
    assert saved["matched_keywords"]["high"] == ["hostage"]
    assert "body" not in saved and "content" not in saved


async def test_robots_denial_is_respected():
    async def handler(request):
        return httpx.Response(200, content=b"User-agent: *\nDisallow: /news/\n")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = SafeFetcher(client)
        fetcher.validate = AsyncMock()
        assert not await fetcher.can_scrape("https://www.dawn.com/news/123", ["www.dawn.com"])
