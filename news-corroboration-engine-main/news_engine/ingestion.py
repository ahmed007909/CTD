from __future__ import annotations

import asyncio
import calendar
import ipaddress
import logging
import re
import socket
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

UTC = timezone.utc

import feedparser
import httpx
from bs4 import BeautifulSoup

from .storage import canonical_url, iso, utcnow
from .text import clean_text

logger = logging.getLogger(__name__)
USER_AGENT = "NewsCorroborationEngine/1.0"
MAX_RESPONSE_BYTES = 3_000_000


def publication_date(entry):
    # 'updated' is not necessarily the original publication date.
    parsed = entry.get("published_parsed")
    if parsed:
        try:
            return iso(datetime.fromtimestamp(calendar.timegm(parsed), UTC))
        except (ValueError, OverflowError, OSError):
            return None
    value = entry.get("published")
    if value:
        for parser in (datetime.fromisoformat, parsedate_to_datetime):
            try:
                return iso(parser(value))
            except (ValueError, TypeError, OverflowError):
                continue
    return None


class SafeFetcher:
    """Only fetch configured publisher hosts; validate every redirect and bound responses."""

    def __init__(self, client):
        self.client = client
        self.robots = {}

    async def validate(self, url, hosts):
        parts = urlsplit(url)
        if (
            parts.scheme not in {"http", "https"}
            or parts.hostname not in hosts
            or parts.username
            or parts.password
            or parts.port not in {None, 80, 443}
        ):
            raise ValueError("URL outside the configured publisher allowlist")
        addresses = await asyncio.to_thread(socket.getaddrinfo, parts.hostname, parts.port or 443)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("Publisher resolved to a non-public address")

    async def get(self, url, hosts):
        for _ in range(5):
            await self.validate(url, hosts)
            for attempt in range(3):
                try:
                    async with self.client.stream("GET", url, follow_redirects=False) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                raise ValueError("Redirect missing location")
                            url = urljoin(url, location)
                            break
                        response.raise_for_status()
                        body = bytearray()
                        async for part in response.aiter_bytes():
                            body.extend(part)
                            if len(body) > MAX_RESPONSE_BYTES:
                                raise ValueError("Publisher response exceeds size limit")
                        return bytes(body), url
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt == 2:
                        raise
                    await asyncio.sleep(0.25 * 2**attempt)
            else:
                raise ValueError("Unable to fetch publisher")
        raise ValueError("Too many redirects")

    async def can_scrape(self, url, hosts):
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        cached = self.robots.get(origin)
        if not cached or (utcnow() - cached[0]).total_seconds() > 3600:
            parser = RobotFileParser()
            try:
                body, _ = await self.get(origin + "/robots.txt", hosts)
                parser.parse(body.decode("utf-8", errors="replace").splitlines())
            except httpx.HTTPStatusError as exc:
                # Missing robots permits crawling; denial and server errors fail closed.
                parser.parse(
                    ["User-agent: *", "Disallow: " if exc.response.status_code == 404 else "Disallow: /"]
                )
            except (httpx.HTTPError, ValueError, OSError):
                parser.parse(["User-agent: *", "Disallow: /"])
            self.robots[origin] = (utcnow(), parser)
        parser = self.robots[origin][1]
        return parser.can_fetch(USER_AGENT, url) and (parser.crawl_delay(USER_AGENT) or 0) <= 2


class Ingestor:
    def __init__(self, store, settings, scanner, processor, broadcaster, fetcher):
        self.store, self.settings = store, settings
        self.scanner, self.processor = scanner, processor
        self.broadcast, self.fetcher = broadcaster, fetcher
        self.lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(3)

    async def scrape_article(self, url, source):
        if not self.settings.scraping_enabled or not await self.fetcher.can_scrape(
            url, source["allowed_hosts"]
        ):
            return "", None
        body, _ = await self.fetcher.get(url, source["allowed_hosts"])
        soup = BeautifulSoup(body, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        article = soup.select_one("article") or soup.select_one("main")
        text = " ".join(p.get_text(" ", strip=True) for p in article.select("p")) if article else ""
        if not text:
            meta = soup.select_one('meta[property="og:description"], meta[name="description"]')
            text = meta.get("content", "") if meta else ""
        meta = soup.select_one('meta[property="article:published_time"]')
        date = publication_date({"published": meta.get("content", "")}) if meta else None
        return clean_text(text)[:40000], date

    async def entries(self, source):
        try:
            body, final_url = await self.fetcher.get(source["feed_url"], source["allowed_hosts"])
        except httpx.HTTPStatusError as exc:
            if not self.settings.scraping_enabled or exc.response.status_code not in {404, 410}:
                raise
            body, final_url = b"", ""
        parsed = await asyncio.to_thread(feedparser.parse, body)
        if parsed.entries:
            return parsed.entries[:30], "rss"
        if parsed.get("version") and not parsed.bozo:
            return [], "rss"
        if not self.settings.scraping_enabled:
            raise ValueError("No valid RSS/Atom feed; scraping disabled")
        home = source["homepage"]
        if not await self.fetcher.can_scrape(home, source["allowed_hosts"]):
            raise ValueError("No valid feed; robots policy disallows fallback")
        if final_url != home:
            body, final_url = await self.fetcher.get(home, source["allowed_hosts"])
        soup = BeautifulSoup(body, "html.parser")
        alternate = soup.select_one('link[type="application/rss+xml"], link[type="application/atom+xml"]')
        if alternate and alternate.get("href"):
            feed_url = urljoin(final_url, alternate["href"])
            raw, _ = await self.fetcher.get(feed_url, source["allowed_hosts"])
            discovered = await asyncio.to_thread(feedparser.parse, raw)
            if discovered.entries:
                return discovered.entries[:30], "discovered_rss"
        entries, seen = [], set()
        for link in soup.select("article a[href], h2 a[href], h3 a[href]"):
            title = clean_text(link.get_text(" ", strip=True))
            url = urljoin(final_url, link["href"])
            if len(title) < 25 or url in seen or urlsplit(url).hostname not in source["allowed_hosts"]:
                continue
            seen.add(url)
            entries.append({"title": title, "link": url, "summary": ""})
            if len(entries) == 12:
                break
        if not entries:
            raise ValueError("No valid feed or usable fallback article links")
        return entries, "html_fallback"

    async def ingest_source(self, source):
        async with self.semaphore:
            inserted, skipped, errors = 0, 0, 0
            try:
                entries, mode = await self.entries(source)
                for entry in entries:
                    try:
                        url = canonical_url(urljoin(source["homepage"], entry.get("link", "")))
                        if not entry.get("link") or urlsplit(url).hostname not in source["allowed_hosts"]:
                            skipped += 1
                            continue
                        title = clean_text(entry.get("title", ""))[:400]
                        if not title or not re.search(r"\w", title):
                            skipped += 1
                            continue
                        body = clean_text(entry.get("summary", ""))
                        if entry.get("content"):
                            body = clean_text(entry["content"][0].get("value", body))
                        published = publication_date(entry)
                        if len(body) < 100 and self.settings.scraping_enabled:
                            try:
                                scraped, scraped_date = await self.scrape_article(url, source)
                                body = scraped or body
                                published = published or scraped_date
                                await asyncio.sleep(2)  # bounded, polite per-publisher pacing
                            except (httpx.HTTPError, ValueError, OSError):
                                errors += 1
                        # Body is transient. Only a bounded snippet and extracted metadata are persisted.
                        full_text = title + ". " + body[:40000]
                        snippet = body[: self.settings.snippet_max_chars]
                        metadata = await asyncio.to_thread(self.processor.extract, title + ". " + snippet)
                        article = {
                            "url": url,
                            "source_id": source["id"],
                            "source_name": source["name"],
                            "title": title,
                            "snippet": snippet,
                            "published_at": published,
                            **self.scanner.annotate(full_text),
                            **metadata,
                        }
                        saved, changed = await asyncio.to_thread(self.store.upsert_article, article)
                        if changed:
                            inserted += 1
                            await self.broadcast(
                                {"type": "article", "article": saved, "alert": saved["flag_level"] == "high"}
                            )
                    except (ValueError, TypeError, KeyError, OSError):
                        errors += 1
                status = {
                    "state": "degraded" if errors else "ok",
                    "checked_at": iso(),
                    "mode": mode,
                    "changed_articles": inserted,
                    "skipped": skipped,
                    "errors": errors,
                }
            except Exception as exc:  # noqa: BLE001 - isolate publisher failures at the job boundary
                # Log only source ID and error type, never claim/article text, credentials or response bodies.
                logger.warning("Source %s failed: %s", source["id"], type(exc).__name__)
                status = {"state": "error", "checked_at": iso(), "error_type": type(exc).__name__}
                if isinstance(exc, httpx.HTTPStatusError):
                    status["http_status"] = exc.response.status_code
            self.store.set_source_status(source["id"], status)
            return status

    async def run_once(self):
        async with self.lock:
            return await asyncio.gather(
                *(self.ingest_source(s) for s in self.settings.sources if s["enabled"])
            )

    async def run_forever(self):
        while True:
            await self.run_once()
            await asyncio.sleep(self.settings.poll_interval_seconds)
