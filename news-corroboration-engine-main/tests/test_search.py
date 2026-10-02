from datetime import timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from conftest import article
from fastapi.testclient import TestClient

from news_engine.api import create_app
from news_engine.search import NewsSearch, SearchAliases, rank_articles
from news_engine.storage import iso, utcnow


@pytest.mark.parametrize(
    "query,title",
    [
        ("CTD", "Counter-Terrorism Department opens investigation"),
        ("counter terrorism department", "CTD announces an investigation"),
        ("C.T.D.", "CTD announces an investigation"),
        ("Dos", "Denial-of-service incident disrupts online portal"),
        ("DDos", "Distributed denial of service disrupts banking"),
        ("cyber crime", "Cybercrime investigation begins"),
        ("cyber", "Ransomware incident under investigation"),
        ("cyber crime", "Police investigate online fraud"),
        ("FIA", "Federal Investigation Agency announces inquiry"),
        ("NCCIA", "National Cyber Crime Investigation Agency opens case"),
        ("سائبر کرائم", "آن لائن فراڈ کی تحقیقات"),
        ("Babar", "Babar appears as a witness in court"),
        ("ZXY", "ZXY issues a statement"),
    ],
)
def test_aliases_names_and_unknown_abbreviations(settings, query, title):
    aliases = SearchAliases(settings.search_aliases_path)
    matches = rank_articles([article(title=title)], aliases.concepts(query))
    assert len(matches) == 1 and matches[0]["stance"] == "mention"


def test_short_word_in_long_snippet_is_not_lost(settings):
    a = article(snippet="An ordinary report. " * 20 + " Babar attended the hearing.")
    assert rank_articles([a], SearchAliases(settings.search_aliases_path).concepts("Babar"))


def test_person_name_and_topic_are_both_required(settings):
    concepts = SearchAliases(settings.search_aliases_path).concepts("Babar cyber crime")
    rows = [
        article(title="Babar won a cricket match", slug="one"),
        article(title="Cybercrime suspect Ali arrested", slug="two"),
        article(title="Babar gives testimony in online fraud inquiry", slug="three"),
    ]
    matches = rank_articles(rows, concepts)
    assert len(matches) == 1 and matches[0]["article"]["url"].endswith("three")


def test_word_boundaries_and_full_names(settings):
    aliases = SearchAliases(settings.search_aliases_path)
    assert not rank_articles([article(title="Babaristan regional news")], aliases.concepts("Babar"))
    assert not rank_articles([article(title="Babar appears in court")], aliases.concepts("Babar Ali"))
    assert not rank_articles([article(title="Microdosage research published")], aliases.concepts("DoS"))
    assert not rank_articles([article(title="Dos Santos wins football award")], aliases.concepts("DoS"))
    assert rank_articles([article(title="Server suffers DoS attack")], aliases.concepts("DoS"))
    assert not rank_articles(
        [article(title="CTD ASX shares rise after travel contract")], aliases.concepts("CTD")
    )
    assert not rank_articles(
        [article(title="CTD connective tissue disease study published")], aliases.concepts("CTD")
    )
    assert rank_articles([article(title="CTD police arrest suspect")], aliases.concepts("CTD"))


@pytest.mark.parametrize("query", ["CTD", "Dos", "DDos", "cyber", "cyber crime", "Babar", "علی", "Q"])
def test_short_queries_no_longer_return_422(settings, query):
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client:
        for path in ("/api/check", "/api/search"):
            response = client.post(path, json={"claim": query})
            assert response.status_code == 200
            assert response.json()["mode"] == "search"
            assert response.json()["verdict"] is None


def test_search_api_and_crime_filter(settings):
    app = create_app(settings)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        app.state.store.upsert_article(article(title="Babar wins cricket match", slug="sport"))
        app.state.store.upsert_article(
            article(title="Babar testifies as witness in fraud case", slug="court")
        )
        result = client.post("/api/search", json={"claim": "Babar", "crime_only": True}).json()
        assert result["total_matches"] == 1
        assert result["matches"][0]["stance"] == "mention"
        assert result["verdict"] is None
        assert "witness" in result["disclaimer"]


def test_explicit_claim_mode_and_api_auth(settings):
    settings.api_key = "secret"
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client:
        assert client.post("/api/search", json={"claim": "CTD"}).status_code == 401
        r = client.post(
            "/api/check", json={"claim": "airport reopened", "mode": "claim"}, headers={"X-API-Key": "secret"}
        )
        assert r.status_code == 200 and r.json()["mode"] == "claim"


@pytest.mark.parametrize(
    "payload",
    [
        {"claim": "!!!"},
        {"claim": "<script>CTD</script>"},
        {"claim": "cyber", "days": 0},
        {"claim": "cyber", "days": 366},
        {"claim": "cyber", "mode": "invalid"},
    ],
)
def test_search_validation(settings, payload):
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client:
        assert client.post("/api/search", json=payload).status_code == 422


async def test_search_date_range_cache_and_updates(store, settings, scanner):
    store.upsert_article(
        article(title="CTD opens investigation", published_at=iso(utcnow() - timedelta(days=20)))
    )
    service = NewsSearch(store, settings, scanner, AsyncMock())
    assert (await service.search("CTD", days=7))["total_matches"] == 0
    assert (await service.search("CTD", days=30))["total_matches"] == 1
    assert (await service.search("CTD", days=30))["cached"]
    store.upsert_article(article(title="CTD closes inquiry", slug="two"))
    assert (await service.search("CTD", days=30))["total_matches"] == 2


def feed_xml():
    return f"""<rss version="2.0"><channel><title>Search</title><item>
    <title>Cybercrime inquiry opens - Example News</title>
    <link>https://news.google.com/rss/articles/example</link>
    <source url="https://example.com">Example News</source>
    <description>Investigators examine cybercrime reports.</description>
    <pubDate>{utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")}</pubDate>
    </item></channel></rss>""".encode()


async def test_live_search_is_bounded_attributed_and_not_in_claim_index(store, settings, scanner):
    settings.live_search_enabled = True
    fetcher = AsyncMock()
    fetcher.get.return_value = (feed_xml(), "https://news.google.com/rss/search")
    service = NewsSearch(store, settings, scanner, fetcher)
    result = await service.search("cyber crime", live=True)
    assert result["live_search"]["state"] == "ok" and result["total_matches"] == 1
    a = result["matches"][0]["article"]
    assert a["source_name"] == "Example News" and a["retrieved_from"] == "google_news"
    assert result["verdict"] is None and not store.articles()
    assert fetcher.get.call_args.args[1] == ["news.google.com"]
    assert "when%3A30d" in fetcher.get.call_args.args[0]


async def test_live_failure_preserves_local_results(store, settings, scanner):
    settings.live_search_enabled = True
    store.upsert_article(article(title="CTD starts inquiry"))
    fetcher = AsyncMock()
    fetcher.get.side_effect = httpx.ConnectError("network")
    result = await NewsSearch(store, settings, scanner, fetcher).search("CTD", live=True)
    assert result["live_search"]["state"] == "unavailable" and result["total_matches"] == 1
    assert "local index only" in result["explanation"]


async def test_live_opt_out(store, settings, scanner):
    settings.live_search_enabled = True
    fetcher = AsyncMock()
    result = await NewsSearch(store, settings, scanner, fetcher).search("cyber", live=False)
    assert result["live_search"]["state"] == "disabled"
    fetcher.get.assert_not_called()


async def test_invalid_live_feed_is_not_success(store, settings, scanner):
    settings.live_search_enabled = True
    fetcher = AsyncMock()
    fetcher.get.return_value = (b"<html>Denied</html>", "https://news.google.com")
    result = await NewsSearch(store, settings, scanner, fetcher).search("cyber", live=True)
    assert result["live_search"]["state"] == "unavailable"
