"""Topic/name retrieval kept separate from claim-verdict logic."""

import asyncio
import hashlib
import json
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlsplit

import feedparser
import httpx
import anyio

from .ingestion import publication_date
from .storage import canonical_url, iso, utcnow
from .text import clean_text, normalize

SEARCH_VERSION = "search-v2"
SEARCH_DISCLAIMER = (
    "These are news search results, not a finding that a claim is true or a person committed a crime. "
    "A name may identify a victim, witness, investigator, accused person, or someone else. "
    "Read the original reporting and check identity, context and dates."
)
SEARCH_STOP = {"the", "a", "an", "of", "in", "on", "and", "for", "about", "news", "کے", "کی", "کا", "میں"}


def searchable(text):
    text = normalize(text)
    # C.T.D. and CTD are equivalent; ordinary punctuation becomes word separators.
    text = re.sub(r"\b(?:[a-z]\.){2,}(?:[a-z]\b)?", lambda m: m[0].replace(".", ""), text)
    return " ".join(re.findall(r"\w+", text))


def contains(text, term):
    return f" {term} " in f" {text} "


class SearchAliases:
    def __init__(self, path):
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.entries = []
        self.by_alias = {}
        for group in raw:
            variants = list(dict.fromkeys(searchable(v) for v in group["aliases"] + group.get("related", [])))
            entry = {"name": group["name"], "terms": variants}
            self.entries.append(entry)
            for alias in group["aliases"]:
                self.by_alias.setdefault(searchable(alias), entry)

    def concepts(self, query):
        words = searchable(query).split()
        groups = []
        i = 0
        while i < len(words):
            match = None
            # Longest aliases first: "cyber crime" must not become two independent concepts.
            for end in range(min(len(words), i + 10), i, -1):
                alias = " ".join(words[i:end])
                if alias in self.by_alias:
                    match = (end, self.by_alias[alias])
                    break
            if match:
                i, entry = match
                groups.append(entry)
            else:
                if words[i] not in SEARCH_STOP:
                    groups.append({"name": words[i], "terms": [words[i]]})
                i += 1
        return groups or [{"name": searchable(query), "terms": [searchable(query)]}]

    def provider_query(self, concepts, days, crime_only=False):
        # Build expressions from sanitized words, not raw user-supplied search operators.
        terms = ["(" + " OR ".join('"' + term + '"' for term in c["terms"][:8]) + ")" for c in concepts]
        if any(c["name"] == "CTD" for c in concepts):
            terms.append('(police OR terrorism OR terrorist OR investigation OR arrest OR "سی ٹی ڈی")')
        if crime_only:
            terms.append('(crime OR arrest OR accused OR fraud OR investigation OR "جرائم")')
        return " ".join(terms) + f" when:{days}d"


def rank_articles(articles, concepts, crime_only=False):
    matches = []
    crime_terms = (
        "crime",
        "cybercrime",
        "arrest",
        "arrested",
        "accused",
        "suspect",
        "charged",
        "convicted",
        "investigation",
        "murder",
        "fraud",
        "robbery",
        "kidnapping",
        "قتل",
        "گرفتار",
        "ملزم",
        "جرائم",
    )
    for article in articles:
        title = searchable(article["title"])
        text = searchable(article["title"] + " " + article["snippet"])
        hits = [[t for t in concept["terms"] if contains(text, t)] for concept in concepts]
        if not all(hits):
            continue
        police_terms = (
            "police",
            "terrorism",
            "terrorist",
            "terrorists",
            "counterterrorism",
            "officer",
            "officers",
            "arrest",
            "arrests",
            "arrested",
            "raid",
            "raids",
            "suspect",
            "suspects",
            "investigation",
            "inquiry",
            "department",
            "پولیس",
            "دہشت",
            "گرفتار",
            "تحقیقات",
        )
        if any(
            c["name"] == "CTD" and terms == ["ctd"] for c, terms in zip(concepts, hits)
        ) and not any(contains(text, term) for term in police_terms):
            continue
        # "dos" also occurs in names and other languages. Require a computing
        # context when the abbreviation alone is the only DoS evidence.
        computing_terms = (
            "cyber",
            "cybersecurity",
            "attack",
            "attacks",
            "network",
            "server",
            "servers",
            "traffic",
            "botnet",
            "vulnerability",
            "security",
            "ddos",
            "internet",
            "website",
        )
        if any(
            c["name"] == "DoS" and terms == ["dos"] for c, terms in zip(concepts, hits)
        ) and not any(contains(text, term) for term in computing_terms):
            continue
        if crime_only and not any(contains(text, term) for term in crime_terms):
            continue
        matched_terms = list(dict.fromkeys(t for terms in hits for t in terms))
        title_fraction = sum(any(contains(title, t) for t in terms) for terms in hits) / len(hits)
        matches.append(
            {
                "article": article,
                "score": round(0.65 + 0.35 * title_fraction, 4),
                "stance": "mention",
                "reason": "Matched terms: " + ", ".join(matched_terms),
                "matched_terms": matched_terms,
                "evidence": article["snippet"] or article["title"],
                "retrieved_from": article.get("retrieved_from", "local_index"),
            }
        )
    return sorted(
        matches,
        key=lambda m: (m["score"], m["article"].get("published_at") or m["article"].get("collected_at", "")),
        reverse=True,
    )


class NewsSearch:
    def __init__(self, store, settings, scanner, fetcher):
        self.store, self.settings, self.scanner, self.fetcher = store, settings, scanner, fetcher
        self.aliases = SearchAliases(settings.search_aliases_path)
        self.semaphore = asyncio.Semaphore(3)

    async def live_articles(self, concepts, days, crime_only):
        params = {
            "q": self.aliases.provider_query(concepts, days, crime_only),
            "hl": "en-PK",
            "gl": "PK",
            "ceid": "PK:en",
        }
        url = "https://news.google.com/rss/search?" + urlencode(params)
        async with self.semaphore:
            with anyio.fail_after(20):
                body, _ = await self.fetcher.get(url, ["news.google.com"])
        parsed = await asyncio.to_thread(feedparser.parse, body)
        if not parsed.get("version"):
            raise ValueError("News search returned an invalid feed")
        articles = []
        for entry in parsed.entries[:100]:
            try:
                link = canonical_url(entry.get("link", ""))
                if urlsplit(link).hostname != "news.google.com" or urlsplit(link).scheme != "https":
                    continue
                source = entry.get("source", {})
                name = clean_text(source.get("title", "Publisher via Google News"))[:100]
                title = clean_text(entry.get("title", ""))[:400]
                if not title:
                    continue
                if name and title.endswith(" - " + name):
                    title = title[: -(len(name) + 3)]
                published = publication_date(entry)
                if (
                    published
                    and not utcnow() - timedelta(days=days) <= datetime.fromisoformat(published) <= utcnow()
                ):
                    continue
                snippet = clean_text(entry.get("summary", ""))[: self.settings.snippet_max_chars]
                articles.append(
                    {
                        "id": hashlib.sha256(link.encode()).hexdigest(),
                        "url": link,
                        "source_id": "search:" + (urlsplit(source.get("href", "")).hostname or name),
                        "source_name": name,
                        "title": title,
                        "snippet": snippet,
                        "published_at": published,
                        "collected_at": iso(),
                        "retrieved_from": "google_news",
                        **self.scanner.annotate(title + " " + snippet),
                    }
                )
            except (ValueError, TypeError):
                continue
        return articles

    async def search(self, query, limit=10, days=30, live=False, crime_only=False):
        query = clean_text(query)
        concepts = self.aliases.concepts(query)
        articles = await asyncio.to_thread(
            self.store.articles, days=days, limit=self.settings.max_index_articles
        )
        use_live = live and self.settings.live_search_enabled
        key = hashlib.sha256(
            json.dumps(
                [
                    SEARCH_VERSION,
                    query,
                    limit,
                    days,
                    use_live,
                    crime_only,
                    concepts,
                    [(a["id"], a["updated_at"]) for a in articles],
                ],
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        cached = self.store.cache_get(key) if self.settings.cache_queries else None
        if cached:
            cached["cached"] = True
            if self.settings.save_history:
                self.store.save_query(cached, self.settings.history_retention_days)
            return cached
        live_status = {"state": "disabled"}
        external = []
        if use_live:
            try:
                external = await self.live_articles(concepts, days, crime_only)
                live_status = {"state": "ok", "provider": "Google News", "retrieved_articles": len(external)}
            except (httpx.HTTPError, ValueError, OSError, TimeoutError) as exc:
                live_status = {
                    "state": "unavailable",
                    "provider": "Google News",
                    "error_type": type(exc).__name__,
                }
        ranked = rank_articles(articles + external, concepts, crime_only)
        matches, seen = [], set()
        for match in ranked:
            # RSS aggregator links differ from publisher URLs; deduplicate by publisher and headline.
            a = match["article"]
            identity = (searchable(a["source_name"]), searchable(a["title"]))
            if identity not in seen:
                seen.add(identity)
                matches.append(match)
        explanation = (
            f"Found {len(matches)} matching articles in the searched coverage."
            if matches
            else "No matching articles found in the searched coverage. Try a full name, another spelling, or a wider date range."
        )
        if live_status["state"] == "unavailable":
            explanation += " Live search is unavailable; these results cover the local index only."
        result = {
            "query": query,
            "claim": query,
            "mode": "search",
            "verdict": None,
            "result_label": "Search results" if matches else "No matches",
            "explanation": explanation,
            "matches": matches[:limit],
            "total_matches": len(matches),
            "indexed_articles": len(articles),
            "days": days,
            "crime_only": crime_only,
            "expanded_terms": [c for c in concepts if len(c["terms"]) > 1],
            "live_search": live_status,
            "checked_at": iso(),
            "cached": False,
            "disclaimer": SEARCH_DISCLAIMER,
            **self.scanner.annotate(query),
        }
        if self.settings.cache_queries:
            self.store.cache_put(
                key, result, self.settings.cache_ttl_seconds if live_status["state"] != "unavailable" else 10
            )
        if self.settings.save_history:
            self.store.save_query(result, self.settings.history_retention_days)
        return result
