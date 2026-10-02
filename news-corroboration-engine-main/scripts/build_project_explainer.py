"""Build the code-grounded project technology report (PDF tooling is separate from app deps)."""
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf/News_Corroboration_Engine_Technology_Guide.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

FONT_DIR = Path("C:/Windows/Fonts")
for name, filename in [("Guide", "arial.ttf"), ("GuideBold", "arialbd.ttf"), ("GuideItalic", "ariali.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))
pdfmetrics.registerFontFamily("Guide", normal="Guide", bold="GuideBold", italic="GuideItalic", boldItalic="GuideBold")
INK = colors.HexColor("#163A35")
TEAL = colors.HexColor("#26715E")
MUTED = colors.HexColor("#586B66")
LIGHT = colors.HexColor("#EDF4F0")
LINE = colors.HexColor("#D9E5DE")
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleG", fontName="GuideBold", fontSize=29, leading=33, textColor=INK, spaceAfter=16))
styles.add(ParagraphStyle(name="SubG", fontName="Guide", fontSize=15, leading=20, textColor=TEAL, spaceAfter=16))
styles.add(ParagraphStyle(name="H1G", fontName="GuideBold", fontSize=22, leading=27, textColor=INK, spaceAfter=14))
styles.add(ParagraphStyle(name="H2G", fontName="GuideBold", fontSize=12, leading=16, textColor=TEAL, spaceBefore=14, spaceAfter=7))
styles.add(ParagraphStyle(name="BodyG", fontName="Guide", fontSize=10, leading=14.3, textColor=INK, spaceAfter=9))
styles.add(ParagraphStyle(name="SmallG", fontName="Guide", fontSize=8.3, leading=11.5, textColor=MUTED, spaceAfter=7))
styles.add(ParagraphStyle(name="CellG", fontName="Guide", fontSize=9, leading=12.5, textColor=INK))
styles.add(ParagraphStyle(name="HeadG", fontName="GuideBold", fontSize=8.5, leading=11, textColor=colors.white))
styles.add(ParagraphStyle(name="LabelG", fontName="GuideBold", fontSize=8.5, leading=12, textColor=TEAL, spaceAfter=10))


def p(text, style="BodyG"):
    return Paragraph(text, styles[style])


def table(headers, rows, widths, size="CellG"):
    cells = [[p(escape(h), "HeadG") for h in headers]]
    cells += [[p(cell, size) for cell in row] for row in rows]
    t = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LINEBELOW", (0, 0), (-1, 0), .5, INK),
        ("LINEBELOW", (0, 1), (-1, -1), .4, LINE),
    ]))
    return t


def note(title, text):
    box = Table([[p(title, "H2G")], [p(text, "SmallG")]], colWidths=[507])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), .5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 6), ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
    ]))
    return box


class FlowDiagram(Flowable):
    def __init__(self, labels):
        super().__init__()
        self.labels = labels
        self.width = 507
        self.height = 66

    def draw(self):
        c = self.canv
        width, gap = 116, 14
        for i, label in enumerate(self.labels):
            x = i * (width + gap)
            c.setFillColor(LIGHT)
            c.setStrokeColor(LINE)
            c.roundRect(x, 10, width, 46, 6, fill=1, stroke=1)
            text = p(label, "CellG")
            _, h = text.wrap(width - 18, 45)
            text.drawOn(c, x + 9, 33 - h / 2)
            if i < len(self.labels) - 1:
                c.setStrokeColor(TEAL)
                c.line(x + width + 3, 33, x + width + gap - 3, 33)
                c.line(x + width + gap - 6, 36, x + width + gap - 3, 33)
                c.line(x + width + gap - 6, 30, x + width + gap - 3, 33)


def footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setStrokeColor(LINE)
    canvas.line(44, h - 37, w - 44, h - 37)
    canvas.setFont("GuideBold", 8)
    canvas.setFillColor(TEAL)
    canvas.drawString(44, h - 27, "NEWS CORROBORATION ENGINE")
    canvas.setFont("Guide", 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(w - 44, h - 27, "Technology guide | 22 September 2026")
    canvas.line(44, 38, w - 44, 38)
    canvas.drawString(44, 25, "Code-grounded documentation | Design: Shabahat & Nameerah")
    canvas.drawRightString(w - 44, 25, str(doc.page))
    canvas.restoreState()


story = []
def add(*items):
    story.extend(items)

def page(label, title):
    if story:
        add(PageBreak())
    add(p(label, "LabelG"), p(title, "H1G"))

# Page 1
add(p("PROJECT REFERENCE / IMPLEMENTED SYSTEM", "LabelG"), Spacer(1, 7),
    p("News Corroboration<br/>Engine", "TitleG"),
    p("Libraries, database and news sources", "SubG"),
    p("An explanation of what the original design proposed, what the first Python version used, and what the later news-search update added."),
    p("Prepared from the project code and installed package metadata on <b>22 September 2026</b>. Historical integration and test results are dated separately; this report does not claim that publisher availability was rechecked today.", "SmallG"))
add(table(["Environment", "Verified project setup"], [
    ["Language", "Python <b>3.12.14</b> in the project environment; package requires Python 3.11 or newer."],
    ["Application", "FastAPI backend, Uvicorn server, plain HTML/CSS/JavaScript dashboard."],
    ["Persistence", "One local SQLite database; SQLite library <b>3.53.1</b>. Default file: <b>data/news.db</b>."],
    ["News inputs", "Six configured publisher integrations, plus on-demand Google News RSS search."],
], [112, 395]))
add(p("How the project evolved", "H2G"))
add(table(["Stage", "What was used or added"], [
    ["Original PDF design", "Proposed a Python pipeline with RSS, NLP, matching, FastAPI, live alerts, SQLite for development and possible production technologies."],
    ["First Python version", "Implemented feed ingestion, keyword flags, TF-IDF claim matching, SQLite storage/cache, API, WebSocket updates and a dashboard."],
    ["Search update", "Added names and short abbreviations, configurable aliases, Google News lookup, date filters and a crime-reporting filter. The existing backend, database and core libraries stayed in place."],
], [112, 395]))
add(Spacer(1, 12), note("Two different jobs", "<b>Claim checking</b> compares a statement with locally indexed reporting and returns a heuristic verdict. <b>News search</b> finds mentions and related coverage; it does not decide whether a person is guilty or a claim is true."))

# Page 2
page("01 / APPLICATION LIBRARIES", "What the Python libraries do")
add(p("These packages are used by the implemented application. Versions below were read from the project's installed environment and match its recorded dependency snapshot.", "SmallG"))
add(table(["Library / version", "Purpose in this project"], [
    ["<b>FastAPI</b> 0.141.1", "Defines REST routes for searches, claim checks, sources, articles and history; provides the WebSocket endpoint and serves dashboard files."],
    ["<b>Uvicorn</b> 0.53.0", "Runs the FastAPI application as an ASGI web server. The development launcher binds to 127.0.0.1:8000."],
    ["<b>HTTPX</b> 0.28.1", "Makes asynchronous HTTP requests to publisher sites and Google News. Used with timeouts, size bounds and redirect checks."],
    ["<b>feedparser</b> 6.0.14", "Parses RSS/Atom entries into titles, URLs, descriptions and publication metadata, including the Google News search feed."],
    ["<b>Beautiful Soup</b><br/>beautifulsoup4 4.15.0", "Removes HTML/script markup, discovers feed links and extracts article text for the HTML fallback. Imported as bs4."],
    ["<b>scikit-learn</b> 1.9.1", "Weights words and character sequences with TF-IDF (term frequency-inverse document frequency), then measures cosine similarity to rank claim matches."],
    ["<b>YAKE</b> 0.7.3", "Extracts up to eight English keyphrases, with phrases up to two words. Urdu text instead uses normalized word frequencies."],
    ["<b>python-dotenv</b> 1.2.3", "Loads local .env settings for the database path, polling, optional models, API key and other configuration."],
    ["<b>NumPy</b> 2.5.3", "Handles arrays, score combinations and ranked indices in the matching engine."],
    ["<b>Pydantic</b> 2.13.5", "Validates request fields, length limits, search mode, date range and result limits before executing a request."],
    ["<b>Starlette</b> 1.6.0", "Supplies FastAPI's web infrastructure, static-file support and thread-pool helper for blocking work."],
], [155, 352]))
add(Spacer(1, 10), p("<b>Dependency declaration:</b> the first eight packages are explicitly listed under project dependencies in pyproject.toml. NumPy, Pydantic and Starlette are imported directly by project code but currently arrive through those dependencies. requirements-tested.txt records exact installed versions.", "SmallG"))
add(p("<b>Terms in plain language:</b> RSS/Atom are machine-readable news feeds. An API lets the dashboard request data from the backend. ASGI is the interface connecting an asynchronous Python web server to its application. WebSocket keeps a connection open so new articles can be pushed to the browser.", "SmallG"))

# Page 3
page("02 / STORAGE", "One database, five tables")
add(p("The project uses <b>SQLite</b> through Python's built-in <b>sqlite3</b> module. It does not require a separate database server. SQL statements are written directly in storage.py; no ORM such as SQLAlchemy is used."))
add(table(["Table", "What it stores and why"], [
    ["<b>articles</b>", "Canonical URL and hash ID, publisher, title, short snippet, publication/collection/update times, severity and JSON metadata. Supports retrieval, deduplication and article updates."],
    ["<b>history</b>", "Timestamped query results, including submitted text, matches and claim verdicts or search labels. Used by the Recent checks view."],
    ["<b>cache</b>", "A hashed lookup key, expiry time and JSON result. Reuses repeated claim checks and searches without a Redis service."],
    ["<b>source_status</b>", "The last recorded ingestion status for each configured publisher, including errors or HTTP status when available."],
    ["<b>metadata</b>", "An article revision counter, increased on changed article writes. Query caches are invalidated when articles change."],
], [102, 405]))
add(p("Storage rules and defaults", "H2G"),
    p("<b>Snippets, not full articles:</b> ingestion may examine longer content in memory for keyword scanning, but stores a title of up to 400 characters and a snippet of 500 characters by default (configuration maximum: 1,000). Links, extracted terms and flags remain attached."),
    p("<b>Cache lifetime:</b> normally 120 seconds. A failed live-search result is cached for 10 seconds. Expired entries are removed during cache writes; article changes clear the cache."),
    p("<b>History:</b> saving is enabled by default, with 30-day retention. Old history is filtered on reads and purged on subsequent recorded queries. Turning saving off does not delete old records."),
    p("<b>Concurrency:</b> SQLite uses write-ahead logging (WAL), transactions, a busy timeout and a thread lock. The application is designed for a single server process; multiple workers would each start their own ingestion loop and live-client list."))
add(note("Where live-search results go", "Google News results are <b>not inserted into the articles table</b> and do not become supporting publishers for claim verdicts. Their bounded snippets can still appear in <b>cache</b> and, when enabled, <b>history</b>. TF-IDF matrices and optional embeddings are held in memory, not in a separate vector database."))

# Page 4
page("03 / NEWS INPUTS", "Which sources are used?")
add(p("Six publisher integrations remain configured and enabled in <b>news_engine/config/sources.json</b>. They are the same core publisher set as in the first implementation. The listed outcomes come from the recorded <b>18 September 2026</b> ingestion test, not a fresh availability check.", "SmallG"))
feeds = [
    ("DAWN", "https://www.dawn.com/feeds/home", "RSS succeeded; 24 articles changed."),
    ("ARY News", "https://arynews.tv/feed/", "RSS succeeded; 30 articles changed."),
    ("Geo News", "https://www.geo.tv/rss/1/1", "RSS succeeded; 20 articles changed."),
    ("Hum News", "https://humnews.pk/feed/", "HTTP 403 from publisher; no articles added."),
    ("Dunya News", "https://dunyanews.tv/en/rss", "Feed URL returned HTML; HTML fallback succeeded with 12 articles."),
    ("Samaa", "https://www.samaa.tv/feed/", "Connection failed; no articles added."),
]
add(table(["Publisher / configured endpoint", "Recorded outcome"], [
    [f'<b>{name}</b><br/><link href="{url}" color="#26715E">{url}</link>', result]
    for name, url, result in feeds
], [295, 212]))
add(p("How publisher ingestion works", "H2G"),
    p("HTTPX fetches a configured feed and feedparser reads its entries. When suitable, Beautiful Soup discovers a feed or extracts links/text from publisher pages. Scraping checks robots.txt; allowed publisher hosts, public IP checks and bounded responses limit outbound fetching.", "BodyG"),
    p("A cycle takes up to 30 feed entries or 12 HTML fallback links per publisher, then waits 120 seconds before the next completed-cycle run. New or changed articles are stored and pushed to connected browsers. This is periodic collection, not an exhaustive or instantaneous news archive.", "SmallG"))
add(p("Added in the search update: Google News", "H2G"),
    p('<b>Endpoint:</b> <link href="https://news.google.com/rss/search" color="#26715E">https://news.google.com/rss/search</link><br/>The query is sent with related terms, a date window and Pakistan/English edition settings (hl=en-PK, gl=PK, ceid=PK:en). Up to 100 returned feed entries are examined.'),
    p("Google News is a <b>discovery/aggregation source</b>, not the author of every article. Each result displays the publisher reported by the feed and links through Google News. Results can come from publishers beyond the six fixed integrations, including international outlets.", "SmallG"),
    p("Live search is enabled by default, requires internet access and currently needs no API key in this implementation. The user can disable it. If it fails, the response says so and retains local-index results. The public RSS route has no availability guarantee in this project.", "SmallG"))

# Page 5
page("04 / PROCESSING & DESIGN CHOICES", "What happens to the text?")
add(p("Full-claim checking", "H2G"),
    FlowDiagram(["Claim text", "Recent SQLite<br/>snippets", "TF-IDF<br/>ranking", "Heuristic verdict<br/>+ sources"]),
    p("Word/bigram similarity contributes 75% and character-ngram similarity 25% to the default lexical score. The heuristic checks overlapping details, numbers and negation; at least two distinct publishers with different normalized headlines are required for Corroborated. Claim retrieval uses a 7-day window and at most 5,000 indexed articles by default.", "SmallG"),
    p("Name, topic and abbreviation search", "H2G"),
    FlowDiagram(["Search text", "Alias expansion<br/>+ date window", "Local + live<br/>news retrieval", "Matched mentions<br/>+ source links"]),
    p("Whole-word matching and search_aliases.json support terms such as CTD, DoS, DDoS and cyber crime without the long-claim score threshold. All query concepts must match. CTD-only matches need a police context; DoS-only matches need a computing context. Search defaults to 30 days; the dashboard also offers 7 days and 1 year. These are filters over available coverage, not promises of a complete archive.", "SmallG"))
add(p("Optional or proposed: not part of the default runtime", "H2G"))
add(table(["Technology", "Actual status / replacement"], [
    ["sentence-transformers", "Optional integration; not installed. Can add multilingual sentence embeddings after explicit installation and enablement."],
    ["spaCy", "Optional integration; not installed. Default named-entity output is explicitly labeled rule-based candidates."],
    ["PostgreSQL / Redis", "Proposed production choices only. No adapters are implemented; SQLite handles data and result caching."],
    ["APScheduler", "Proposed scheduler; not used. Python asyncio starts and repeats the ingestion task within the API lifecycle."],
    ["Scrapy / aiohttp / RAKE", "Not used. The selected alternatives are Beautiful Soup, HTTPX and YAKE respectively."],
    ["React", "Proposed optional frontend; not used. The dashboard is plain HTML/CSS/JavaScript served by FastAPI."],
], [140, 367]))
add(Spacer(1, 8), p("The optional encoder is sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2. When enabled, embeddings contribute 45% and lexical scores 55%. A separate spaCy model must also be installed to use trained NER. No trained Urdu NER model, hosted LLM API, paid news API or external vector database is used by default.", "SmallG"))

# Page 6
page("05 / SUPPORT & EVIDENCE", "Supporting tools and references")
add(p("Built-in Python components", "H2G"),
    p("<b>asyncio</b> handles scheduling, bounded concurrency and live-client queues. <b>sqlite3</b> provides database access; <b>threading</b> protects shared operations. <b>re</b>, <b>unicodedata</b> and <b>collections.Counter</b> clean and match text. <b>hashlib</b> creates stable URL/cache hashes; <b>json</b> serializes payloads and configuration. <b>datetime</b>, <b>calendar</b> and <b>email.utils</b> normalize dates. <b>urllib.parse</b> builds/checks URLs; <b>urllib.robotparser</b> reads robots rules; <b>socket</b> and <b>ipaddress</b> check destinations. <b>secrets</b> compares API keys. <b>argparse</b>, <b>pathlib</b>, <b>dataclasses</b>, <b>os</b>, <b>typing</b>, <b>contextlib</b> and <b>logging</b> support the CLI, settings and lifecycle.", "SmallG"))
add(table(["Development tool", "Role / verified version"], [
    ["pytest / pytest-asyncio", "Synchronous and asynchronous tests; 9.1.1 / 1.4.0. The last recorded suite passed 81 tests on 18 September."],
    ["Ruff", "Python linting/formatting; 0.16.8. Existing validation records report passing checks."],
    ["setuptools / pip / venv", "Package building, dependency installation and environment isolation. setuptools >=75 is the declared build requirement."],
    ["Node.js / browser", "Node.js checked dashboard JavaScript syntax; browser checks verified the UI. Neither requires a Node-based production frontend server."],
], [148, 359]))
add(p("Indirect packages in the recorded environment", "H2G"),
    p("<b>Networking/server:</b> anyio, httpcore, h11, httptools, websockets, watchfiles, certifi, idna, click, colorama, PyYAML. <b>Parsing/keyphrases:</b> feedparser-sgmllib, soupsieve, jellyfish, networkx, segtok, regex, tabulate. <b>Numerical/model support:</b> scipy, joblib, threadpoolctl, narwhals, cloudpickle. <b>Validation/typing:</b> pydantic_core, annotated-types, annotated-doc, typing-inspection, typing_extensions. <b>Test/tool support:</b> iniconfig, pluggy, Pygments, packaging. Exact pins are in requirements-tested.txt; not every installed helper is directly imported by application code.", "SmallG"))
add(p("Evidence used for this report", "H2G"),
    p("""<b>Original design:</b> News_Corroboration_Engine_Implementation (1).pdf, supplied by the user, especially its architecture and technology summary.<br/>
<b>Dependencies:</b> pyproject.toml; requirements-tested.txt; read-only checks of the project's installed package metadata, Python and SQLite versions.<br/>
<b>Application code:</b> news_engine/api.py, ingestion.py, matching.py, search.py, text.py, storage.py, live.py and settings.py; static/index.html and static/app.js.<br/>
<b>Configuration:</b> news_engine/config/sources.json, keywords.json, search_aliases.json and .env.example. Reported settings are code defaults, not a disclosure of private .env values.<br/>
<b>Historical evidence:</b> README.md and VALIDATION.md, including the 18 September test results and 86-article ingestion run. No new test-suite or publisher-availability run was needed to author this report.""", "SmallG"))
add(note("Interpretation", "A retrieval score is not a truth probability. A name match does not verify identity or guilt. Optional packages and proposed production technologies are clearly separated from what the code currently uses. ReportLab, pypdf and Poppler were used only to create and inspect <b>this PDF</b>; they are not application dependencies."))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=38, leftMargin=38,
                        topMargin=57, bottomMargin=53, title="News Corroboration Engine - Technology Guide",
                        author="News Corroboration Engine project", subject="Libraries, database, sources and implementation history")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(OUT)
