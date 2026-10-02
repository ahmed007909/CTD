import pytest

from news_engine.text import TextProcessor, clean_text, normalize


@pytest.mark.parametrize(
    "text,level",
    [
        ("Bomb explosion and robbery reported", "high"),
        ("Police investigate a murder", "medium"),
        ("A peaceful protest", "low"),
        ("کراچی میں دھماکہ ہوا", "high"),
        ("لاہور میں قتل کی تحقیقات", "medium"),
        ("A bombastic performance with a crimewave subplot", None),
        ("The football team won", None),
    ],
)
def test_keywords(scanner, text, level):
    assert scanner.annotate(text)["flag_level"] == level


def test_all_keyword_levels(scanner):
    assert set(scanner.scan("BOMB, murder and protest")) == {"high", "medium", "low"}


def test_html_and_unicode():
    assert clean_text("<script>bad()</script><b>Hello</b>\x00 world") == "Hello world"
    assert normalize("كراچی يہ") == "کراچی یہ"


def test_processor():
    p = TextProcessor()
    assert p.extract("Karachi airport reopened after repairs")["keyphrases"]
    assert p.extract("کراچی میں ہوائی اڈے کی تعمیر مکمل")["keyphrases"]
    assert p.extract("Karachi airport")["entity_method"] == "rule_based_candidates"
