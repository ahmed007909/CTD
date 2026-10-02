import json
import re
import unicodedata
from collections import Counter

import yake
from bs4 import BeautifulSoup


def clean_text(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    value = unicodedata.normalize("NFKC", soup.get_text(" "))
    value = "".join(c for c in value if not unicodedata.category(c).startswith("C") or c.isspace())
    return " ".join(value.split())


def normalize(value: str) -> str:
    value = clean_text(value).casefold().translate(str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک"}))
    return "".join(c for c in value if not "\u064b" <= c <= "\u065f" and c != "\u0640")


def tokens(value: str) -> set[str]:
    return set(re.findall(r"\w+", normalize(value)))


class KeywordScanner:
    def __init__(self, path):
        words = json.loads(path.read_text(encoding="utf-8"))
        self.patterns = {}
        for level in ("high", "medium", "low"):
            if not isinstance(words.get(level), list) or not all(
                isinstance(w, str) and w.strip() for w in words[level]
            ):
                raise ValueError(f"Invalid keyword list: {level}")
            self.patterns[level] = [
                (w, re.compile(r"(?<!\w)" + re.escape(normalize(w)) + r"(?!\w)")) for w in words[level]
            ]

    def scan(self, text: str) -> dict:
        text = normalize(text)
        return {
            level: hits
            for level, patterns in self.patterns.items()
            if (hits := [word for word, pattern in patterns if pattern.search(text)])
        }

    def annotate(self, text: str) -> dict:
        hits = self.scan(text)
        return {"flag_level": next(iter(hits), None), "matched_keywords": hits}


class TextProcessor:
    def __init__(self, spacy_model=""):
        self.nlp = None
        if spacy_model:
            import spacy

            self.nlp = spacy.load(spacy_model)
        self.keywords = yake.KeywordExtractor(lan="en", n=2, top=8)

    def extract(self, text: str) -> dict:
        if self.nlp:
            entities = [{"text": e.text, "label": e.label_} for e in self.nlp(text).ents]
        else:
            # Candidates only: do not pretend this is trained Urdu/English NER.
            candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", text)
            entities = [{"text": s, "label": "CANDIDATE"} for s in dict.fromkeys(candidates)][:20]
        if re.search(r"[\u0600-\u06ff]", text):
            words = re.findall(r"[\u0600-\u06ff]{3,}", normalize(text))
            phrases = [w for w, _ in Counter(words).most_common(8)]
        else:
            phrases = [word for word, _ in self.keywords.extract_keywords(text)]
        return {
            "entities": entities,
            "keyphrases": phrases,
            "entity_method": "spacy" if self.nlp else "rule_based_candidates",
        }
