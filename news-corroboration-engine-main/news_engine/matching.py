"""Evidence retrieval plus deliberately conservative, explainable stance heuristics.

Similarity is not entailment. These rules flag possible contradictions, not proven falsehoods.
"""

import hashlib
import json
import re
import threading

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .storage import iso
from .text import clean_text, normalize, tokens

DISCLAIMER = (
    "This tool finds corroborating coverage, not absolute truth. Scores measure retrieval similarity, "
    "not the probability a claim is true. Review the linked sources and publication dates."
)
STOP = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "of",
    "in",
    "at",
    "on",
    "to",
    "for",
    "by",
    "and",
    "or",
    "as",
    "with",
    "from",
    "has",
    "have",
    "had",
    "it",
    "this",
    "that",
    "there",
    "said",
    "says",
    "reported",
    "reports",
    "news",
    "breaking",
    "not",
    "no",
    "never",
    "did",
    "does",
    "do",
    "deny",
    "denied",
    "denies",
    "false",
    "hoax",
    "ہے",
    "ہیں",
    "تھا",
    "تھی",
    "تھے",
    "میں",
    "کے",
    "کی",
    "کا",
    "کو",
    "سے",
    "اور",
    "ایک",
    "نہیں",
    "خبر",
}
NEGATION = re.compile(r"(?<!\w)(?:no|not|never|denied|denies|deny|false|hoax|نہیں|تردید|جھوٹی)(?!\w)")


def stance(claim: str, evidence: str) -> tuple[str, str, float]:
    """Require substantial lexical alignment; cross-language retrieval stays 'related'."""
    c, e = tokens(claim) - STOP, tokens(evidence) - STOP
    coverage = len(c & e) / max(1, len(c))
    if len(c & e) < 2 or coverage < 0.72:
        return "related", "Related wording; insufficient alignment to establish support.", coverage
    if c - e:
        return "related", "Some claim details are missing or differ; manual review is required.", coverage
    claim_numbers = {str(int(n)) for n in re.findall(r"\b\d+\b", normalize(claim))}
    evidence_numbers = {str(int(n)) for n in re.findall(r"\b\d+\b", normalize(evidence))}
    if claim_numbers and evidence_numbers and claim_numbers != evidence_numbers:
        return "related", "Numbers differ; the snippets may describe different details or events.", coverage
    c_neg = bool(NEGATION.search(normalize(claim)))
    e_neg = bool(NEGATION.search(normalize(evidence)))
    if c_neg != e_neg:
        return (
            "contradicts",
            "Closely aligned wording has opposite negation; possible contradiction.",
            coverage,
        )
    if c_neg:
        return "related", "Negated statements require manual review of their scope.", coverage
    return "supports", "Substantial claim wording appears in this coverage; heuristic support.", coverage


class Matcher:
    def __init__(self, store, settings, scanner):
        self.store, self.settings, self.scanner = store, settings, scanner
        self.lock = threading.RLock()
        self.model = None
        self.signature = None
        self.word = self.char = self.word_matrix = self.char_matrix = self.embeddings = None
        if settings.semantic_enabled:
            from sentence_transformers import SentenceTransformer

            # Explicit opt-in: no silent failure or hidden model download in lexical mode.
            self.model = SentenceTransformer(settings.semantic_model)

    @property
    def mode(self):
        return "tfidf+multilingual_embeddings" if self.model is not None else "tfidf"

    def _index(self, articles):
        signature = tuple((a["id"], a["updated_at"]) for a in articles)
        if signature == self.signature:
            return
        texts = [normalize(a["title"] + ". " + a["snippet"]) for a in articles]
        self.word = TfidfVectorizer(ngram_range=(1, 2), token_pattern=r"(?u)\b\w+\b", max_features=60000)
        self.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=80000)
        self.word_matrix = self.word.fit_transform(texts)
        self.char_matrix = self.char.fit_transform(texts)
        if self.model is not None:
            self.embeddings = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        self.signature = signature

    def check(self, claim: str, limit=5):
        claim = clean_text(claim)
        with self.lock:
            articles = self.store.articles(
                days=self.settings.article_max_age_days, limit=self.settings.max_index_articles
            )
            # IDs and update times also invalidate cached results when articles age out.
            fingerprint = [(a["id"], a["updated_at"]) for a in articles]
            key = hashlib.sha256(
                json.dumps([claim, limit, self.mode, fingerprint], ensure_ascii=False).encode()
            ).hexdigest()
            cached = self.store.cache_get(key) if self.settings.cache_queries else None
            if cached:
                cached["cached"] = True
                if self.settings.save_history:
                    self.store.save_query(cached, self.settings.history_retention_days)
                return cached
            matches = []
            if articles:
                self._index(articles)
                q = [normalize(claim)]
                lexical = (
                    0.75 * cosine_similarity(self.word.transform(q), self.word_matrix)[0]
                    + 0.25 * cosine_similarity(self.char.transform(q), self.char_matrix)[0]
                )
                semantic = np.zeros(len(articles))
                scores = lexical.copy()
                if self.model is not None:
                    embedding = self.model.encode(q, normalize_embeddings=True, show_progress_bar=False)
                    semantic = np.clip(cosine_similarity(embedding, self.embeddings)[0], 0, 1)
                    scores = 0.55 * lexical + 0.45 * semantic
                for i in np.argsort(-scores)[:50]:
                    if scores[i] < 0.20:
                        continue
                    article = articles[i]
                    # Judge individual sentences so unrelated negations in a long snippet do not dominate.
                    units = [article["title"], *re.split(r"[.!?۔！？]+", article["snippet"])]
                    assessed = [(unit, stance(claim, unit)) for unit in units if unit.strip()]
                    priority = {"related": 0, "supports": 1, "contradicts": 2}
                    unit, (label, reason, coverage) = max(
                        assessed, key=lambda pair: (pair[1][2], priority[pair[1][0]])
                    )
                    if scores[i] < 0.35:
                        label, reason = "related", "Weak retrieval match; insufficient evidence."
                    matches.append(
                        {
                            "article": article,
                            "score": round(float(scores[i]), 4),
                            "lexical_score": round(float(lexical[i]), 4),
                            "semantic_score": round(float(semantic[i]), 4) if self.model else None,
                            "stance": label,
                            "reason": reason,
                            "evidence": unit.strip(),
                            "claim_coverage": round(coverage, 4),
                        }
                    )
            # Count distinct publishers AND distinct normalized titles. Syndicated copies do not add votes.
            supporters, titles = set(), set()
            for match in matches:
                if match["stance"] == "supports":
                    title = normalize(match["article"]["title"])
                    if title not in titles:
                        supporters.add(match["article"]["source_id"])
                        titles.add(title)
            contradictions = [m for m in matches if m["stance"] == "contradicts"]
            if contradictions:
                verdict, explanation = (
                    "Disputed",
                    "Coverage contains a possible contradiction. Review its context.",
                )
            elif len(supporters) >= 2:
                verdict, explanation = (
                    "Corroborated",
                    "Aligned coverage was found from at least two configured publishers.",
                )
            elif matches:
                verdict, explanation = (
                    "Partial",
                    "Some related coverage was found, but corroboration is insufficient.",
                )
            else:
                verdict, explanation = (
                    "Unverified",
                    "No sufficiently related coverage was found in the current index.",
                )
            # Always expose contradictory evidence even when the requested result limit is small.
            visible = matches[:limit]
            if contradictions and contradictions[0] not in visible:
                visible[-1:] = [contradictions[0]]
            result = {
                "claim": claim,
                "verdict": verdict,
                "explanation": explanation,
                "confidence": max((m["score"] for m in matches), default=0.0),
                "confidence_meaning": "retrieval_similarity_not_truth_probability",
                "supporting_publishers": sorted(supporters),
                "matches": visible,
                "evaluated_matches": len(matches),
                "indexed_articles": len(articles),
                "matching_mode": self.mode,
                "stance_method": "conservative_lexical_heuristic",
                "checked_at": iso(),
                "cached": False,
                "disclaimer": DISCLAIMER,
                **self.scanner.annotate(claim),
            }
            if self.settings.cache_queries:
                self.store.cache_put(key, result, self.settings.cache_ttl_seconds)
            if self.settings.save_history:
                self.store.save_query(result, self.settings.history_retention_days)
            return result
