from datetime import timedelta

import numpy as np
from conftest import article

from news_engine.matching import Matcher, stance
from news_engine.storage import iso, utcnow


def test_unverified_not_false(store, settings, scanner):
    matcher = Matcher(store, settings, scanner)
    result = matcher.check("Karachi airport reopened after repairs")
    assert result["verdict"] == "Unverified" and result["confidence"] == 0
    assert matcher.check(result["claim"])["cached"]


def test_four_verdicts_and_cache(store, settings, scanner):
    claim = "Karachi airport reopened after repairs"
    m = Matcher(store, settings, scanner)
    store.upsert_article(article())
    assert m.check(claim)["verdict"] == "Partial"
    store.upsert_article(article(title="After repairs Karachi airport reopened on Monday", source="geo"))
    result = m.check(claim)
    assert result["verdict"] == "Corroborated"
    assert not result["cached"]
    store.upsert_article(article(title="Karachi airport has not reopened after repairs", source="ary"))
    result = m.check(claim, limit=1)
    assert result["verdict"] == "Disputed"
    assert result["matches"][0]["stance"] == "contradicts"


def test_syndicated_titles_not_independent(store, settings, scanner):
    for source in ["dawn", "geo", "ary"]:
        store.upsert_article(article(source=source))
    assert (
        Matcher(store, settings, scanner).check("Karachi airport reopened after repairs")["verdict"]
        == "Partial"
    )


def test_same_publisher_does_not_count_twice(store, settings, scanner):
    store.upsert_article(article())
    store.upsert_article(article(title="After repairs Karachi airport reopened on Monday", slug="two"))
    assert (
        Matcher(store, settings, scanner).check("Karachi airport reopened after repairs")["verdict"]
        == "Partial"
    )


def test_old_news_excluded(store, settings, scanner):
    store.upsert_article(article(published_at=iso(utcnow() - timedelta(days=10))))
    assert (
        Matcher(store, settings, scanner).check("Karachi airport reopened after repairs")["verdict"]
        == "Unverified"
    )


def test_different_places_not_support():
    assert (
        stance("Karachi airport reopened after repairs", "Lahore airport reopened after repairs")[0]
        == "related"
    )


def test_numbers_negation_and_urdu():
    assert stance("Karachi airport has 3 terminals", "Karachi airport has 4 terminals")[0] == "related"
    assert stance("Karachi airport did not reopen", "Karachi airport did not reopen")[0] == "related"
    assert stance("کراچی میں ہوائی اڈہ کھل گیا", "کراچی میں ہوائی اڈہ نہیں کھل گیا")[0] == "contradicts"


def test_semantic_path_with_injected_encoder(store, settings, scanner):
    class Encoder:
        def encode(self, texts, **kwargs):
            return np.array([[1.0, 0.0] for _ in texts])

    store.upsert_article(article())
    matcher = Matcher(store, settings, scanner)
    matcher.model = Encoder()
    result = matcher.check("Karachi airport reopened after repairs")
    assert result["matching_mode"] == "tfidf+multilingual_embeddings"
    assert result["matches"][0]["semantic_score"] == 1


def test_history_opt_out(store, settings, scanner):
    settings.save_history = False
    Matcher(store, settings, scanner).check("Karachi airport reopened")
    assert store.history() == []


def test_snippet_contradiction_not_hidden_by_headline(store, settings, scanner):
    store.upsert_article(article(snippet="Karachi airport has not reopened after repairs."))
    result = Matcher(store, settings, scanner).check("Karachi airport reopened after repairs")
    assert result["verdict"] == "Disputed"


def test_unrelated_coverage(store, settings, scanner):
    store.upsert_article(article(title="Pakistan cricket team wins international championship"))
    result = Matcher(store, settings, scanner).check("Volcanic eruption destroys houses in Iceland")
    assert result["verdict"] == "Unverified"
