# News Corroboration Engine

Python implementation of the supplied design by **Shabahat & Nameerah**. FastAPI serves news search, a claim checker, publisher status, query history, article feeds, WebSocket alerts, and a small browser dashboard. No frontend build step is required. See [SECURITY.md](SECURITY.md) for privacy defaults and deployment requirements.

## Search names, topics and abbreviations

The dashboard now defaults to **Search news by name or topic**. Single words and short abbreviations are valid: `CTD`, `DoS`, `DDoS`, `cyber`, `cyber crime`, `Babar`, or an Urdu name. Unknown abbreviations are searched literally. The old five-character/two-word restriction has been removed in both browser and API validation.

Search matches whole words and configurable related terms, independently of the long-claim TF-IDF threshold. For example, CTD also searches Counter Terrorism Department, DDoS searches distributed denial of service, and cyber crime includes cybercrime and online fraud. Full names and compound queries require every query concept to match. `DoS` alone requires a computing context to avoid results about names such as Dos Santos. Acronyms can remain ambiguous; review the displayed expansions and original sources.

Edit `news_engine/config/search_aliases.json` and restart to add abbreviations or topic variants. Entries separate `aliases` (equivalent query forms) from `related` (broader retrieval terms). Expansions help retrieve reporting; they are never evidence that the terms are identical or that a person committed a crime. Some initial definitions follow [Punjab Police's CTD description](https://punjabpolice.gov.pk/ctd) and [Cloudflare's DoS/DDoS terminology](https://www.cloudflare.com/learning/ddos/glossary/denial-of-service/).

**Include live Google News search** is off by default. Check it explicitly for each search session, or send `live: true` in an API request. It sends the entered search words and expansions to Google's public news RSS search and merges up to 100 returned headlines/snippets with local matches. It requires internet access but no API key. Results link through Google News and name the original publisher; external results are not inserted into the corroboration article index or counted as supporting publishers. Search text and bounded result snippets can be retained in local cache/history only when local history/query caching is explicitly enabled. Uncheck the option for local-only searches, or set `LIVE_SEARCH_ENABLED=false` to disable it server-wide. Provider failures leave local search available and show an explicit unavailable status. This RSS integration is best-effort, not a supported availability guarantee.

Choose 7 days, 30 days, or 1 year. This filters available coverage; it does not fill a year's local archive. The optional **Crime-related reporting only** filter requires crime/investigation language in the retrieved title or snippet. A person's mention may be as a witness, victim, officer, accused person, or unrelated namesake. Use a full name and check the reporting before drawing conclusions.

Search results show **Search results** or **No matches**, never a corroboration/guilt verdict. Select **Check a full claim** to use the original verdict workflow. Exact names not present in available snippets, obscure topics, alternate spellings, or unavailable publishers can still produce no matches.

`POST /api/check` now accepts `mode: "auto" | "search" | "claim"`. Auto routes queries of four words or fewer to search; longer inputs use claim checking. Set the mode explicitly when the intent differs. `POST /api/search` always searches and uses the same `claim` text field for compatibility. Validation errors now display their actual explanation in the dashboard.

## Run on Windows

Python 3.11 or newer is required. Install the dependencies in a virtual environment.

```powershell
# For a fresh checkout:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env

# Start from this project directory:
.\.venv\Scripts\python.exe -m uvicorn news_engine.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

Open **http://127.0.0.1:8000** for the dashboard or **http://127.0.0.1:8000/docs** for the API. `run.ps1` starts the localhost server with proxy headers disabled and bounded concurrency/WebSocket settings. Stop with Ctrl+C. The first feed ingestion starts automatically; an empty index returns `Unverified`.

Linux/macOS: use `python3 -m venv .venv`, `.venv/bin/python -m pip install -e '.[dev]'`, and `.venv/bin/python -m uvicorn news_engine.api:app --host 127.0.0.1 --port 8000 --no-access-log`.

`requirements-tested.txt` pins the base and development dependencies used for validation on Windows/Python 3.12. For that same dependency set, install it with `python -m pip install -r requirements-tested.txt` before installing the project. Optional semantic dependencies are not included in this snapshot.

## What is implemented

| Document stage | Implementation |
| --- | --- |
| Live ingestion | Concurrent RSS/Atom parsing for DAWN, ARY, Geo, Hum, Dunya and Samaa; feed discovery and robots-aware HTML fallback; startup fetch and a 120-second wait between completed cycles |
| Keyword flags | Configurable English/Urdu watchlist; whole-word matching; highest severity and all matched terms; scans full transient content before snippet storage |
| NLP | HTML removal, Unicode normalization, Urdu character normalization, YAKE English keyphrases, Urdu frequent terms; optional spaCy entities, explicitly labeled candidate extraction otherwise |
| Matching | Word and character TF-IDF; optional multilingual sentence-transformer embeddings; cached index |
| Verdicts | Corroborated, Partial, Unverified, Disputed; evidence excerpts, source links, component scores, and explanation |
| Backend | FastAPI REST endpoints and authenticated WebSocket feed |
| Database/cache | SQLite WAL transactions, URL deduplication, updates, source health, TTL cache invalidation, history retention |
| Dashboard | Claim form, verdict card, similarity meter, severity filter, live feed, relative UTC timestamps, source health, history |
| Hygiene | `.env` settings, optional API-key authentication, bounded fetch sizes, publisher allowlists, public-address validation, no sensitive application logging |
| Attribution | Bounded snippets (500 characters by default), publisher names, original links, explicit limitations |

The dashboard uses plain JavaScript rather than React because the frontend is optional in the document. An asyncio lifecycle task supplies scheduling without an extra scheduler dependency. This is the **single-process SQLite development deployment**; PostgreSQL and Redis production adapters are not included. Do not use multiple Uvicorn workers: each worker would run ingestion and have its own live subscriber set.

## Matching and interpretation

Default mode is fully local TF-IDF and requires no model download. Retrieval combines word/bigram similarity (75%) with character-ngram similarity (25%). If enabled, multilingual embeddings contribute 45% of the final retrieval score and lexical retrieval contributes 55%.

The optional encoder can retrieve across languages; the conservative stance rules do **not** establish cross-language entailment. Such matches normally remain `Partial`. Default Urdu matching works within Urdu text. To enable the multilingual encoder:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[semantic]"
# Then set SEMANTIC_ENABLED=true in .env and restart.
```

The first semantic startup downloads `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`; allow storage, bandwidth, and startup time. A requested model that cannot load causes startup to fail rather than silently changing mode. To use trained English NER, install a compatible spaCy pipeline (`python -m spacy download en_core_web_sm`) and set `SPACY_MODEL=en_core_web_sm`. The default capitalized-name extractor reports `CANDIDATE`, never a fabricated named-entity type. No trained Urdu NER model is bundled.

Verdict rules:

- **Corroborated:** heuristic support from at least two distinct configured publishers with different normalized titles.
- **Partial:** related coverage, one supporting publisher, insufficient detail, or a mismatch requiring review.
- **Unverified:** no eligible match in the recent index. This does not mean false.
- **Disputed:** closely aligned text with an opposite negation; this is a possible contradiction for human review.

Scores below 0.20 are excluded; scores below 0.35 cannot provide support or contradiction. Stance evaluation requires at least two meaningful overlapping tokens and all meaningful claim tokens in an evidence sentence. Numbers and negation receive additional checks. These deliberately conservative rules can miss paraphrases and misunderstand complex negation, quoted speech, hypothetical language, changed events, dates, or who did what to whom. Exact-title deduplication does not prove editorial independence or detect every syndicated story. Scores are **retrieval similarity, not calibrated truth probabilities**. Test fixtures verify software behavior; they do not establish real-world fact-checking accuracy. Tune against a labeled English/Urdu evaluation dataset before consequential use.

Articles older than `ARTICLE_MAX_AGE_DAYS` (default 7) and future-dated articles are excluded. Missing publication dates remain null; the dashboard labels their collection time explicitly. Matching sees stored snippets, so supporting details beyond the snippet may be unavailable. A 2-minute polling interval is not an instant-news guarantee: cycle duration, publisher delays, network failures, and robots policies affect freshness.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Application and matching-mode health |
| POST | `/api/check` | `{"claim":"Karachi airport reopened after repairs","limit":5}` |
| POST | `/api/search` | `{"claim":"CTD","limit":10,"days":30,"live":true,"crime_only":false}` |
| GET | `/api/sources` | Configured publishers and last ingestion status |
| GET | `/api/articles?flagged=true&limit=50&offset=0` | Recent articles; optional `source` ID filter |
| GET | `/api/history?limit=50&offset=0` | Stored query results |
| WS | `/ws/live-feed` | `ready`, `article`, `heartbeat`, and `resync_required` events |

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/check `
  -ContentType 'application/json' `
  -Body '{"claim":"Karachi airport reopened after repairs"}'
```

When `API_KEY` is set, all `/api/*` routes require `X-API-Key`. Use the dashboard's API access panel to enter it. WebSocket clients send `{"api_key":"..."}` as their first frame within 10 seconds. Browser origins must match `ALLOWED_ORIGINS`. A slow subscriber receives `resync_required` and should reload `/api/articles`. Keys are not put in query strings or browser persistent storage.

The CLI also works without a server:

```powershell
.\.venv\Scripts\python.exe -m news_engine ingest
.\.venv\Scripts\python.exe -m news_engine check "Karachi airport reopened after repairs"
```

## Configuration and operations

Copy `.env.example` to `.env` and adjust settings. Edit `news_engine/config/keywords.json` and `news_engine/config/sources.json`, then restart. Source URLs are publisher integration starting points, not promises of availability. A feed returning HTML, a denied request, or an unusable fallback produces a source-health error rather than a misleading successful empty ingest. HTML fallback runs only when permitted; 403/429 responses are not bypassed.

Full articles are processed transiently and never intentionally stored in the database. Stored titles are limited to 400 characters and snippets to at most 1000 characters. Keyword flags can refer to text outside the retained snippet. Source metadata and extracted terms are retained. Brief excerpts still require compliance with publisher terms; this software does not grant a redistribution license.

History and query caching are off by default (`SAVE_HISTORY=false`, `CACHE_QUERIES=false`). In local mode you may opt into either independently. Enabled history stores submitted queries and results locally, with retention of 30 days; expired history is purged on the next recorded query and excluded from reads. Previously stored rows are not erased merely by disabling history. SQLite cache rows expire and are pruned during cache writes. Back up or remove `data/news.db` only with the service stopped.

Keep the default localhost binding for development. Local mode rejects remote clients. Public mode requires a strong API key, HTTPS, explicit host/origin configuration, and disabled history/query caching. It also enforces body, request, and connection limits. Follow [SECURITY.md](SECURITY.md) to configure the TLS proxy, server limits, and outbound network policy denying private destinations before any external deployment. Application allowlists and DNS checks are defense in depth; they do not replace network enforcement against DNS rebinding. API keys are shared-service credentials; multi-user isolation is not implemented.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check news_engine tests
```

Tests use synthetic reporting and mocked fetches: all verdicts, bilingual keyword boundaries, missing/old/future dates, duplicate updates, cache invalidation, publisher independence, source failures, size bounds, unsafe redirects, API validation/authentication, live broadcast/disconnect, and backpressure. The semantic combination path uses an injected deterministic encoder; real model quality must be evaluated separately.

Implementation follows [FastAPI lifecycle guidance](https://fastapi.tiangolo.com/advanced/events/). Publisher integrations remain configurable because their feed URLs and access policies can change.

See `VALIDATION.md` for the actual test results and observed live-source availability. Each ingestion cycle processes at most 30 feed entries or 12 HTML fallback links per publisher; the source index is not an exhaustive archive.

## Technology guide

[PDF technology guide](output/pdf/News_Corroboration_Engine_Technology_Guide.pdf) describes the implementation before security hardening. Consult [SECURITY.md](SECURITY.md) and `.env.example` for current privacy, authentication, and deployment defaults.
