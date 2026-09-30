# Validation record

## Security and privacy hardening (22 September 2026)

- **98 automated tests passed** after adding 17 security checks to the existing suite. Coverage includes public-mode startup requirements, remote/Host rejection, HTTPS and API authentication, default query-storage/live-search opt-outs, body limits (including streamed input), rate windows/global limits, WebSocket capacity and oversized authentication messages, non-ASCII credentials, and active-request capacity.
- Ruff checks passed for `news_engine` and `tests`. The two existing upstream Starlette test-client deprecation warnings remain.
- A read-only OSV advisory query for all 46 entries in `requirements-tested.txt` returned no known vulnerabilities on this date. No dependency versions were changed during hardening. Optional semantic packages and deployment infrastructure were outside that scan.
- No public deployment or TLS certificate provisioning was performed. Public mode was tested with simulated HTTPS/remote peers. Real proxy trust, certificates, network policy, and infrastructure limits must be configured and verified on the chosen deployment host.
- Local history/query caching and live Google News queries now require explicit opt-in. Public mode prohibits history/query caching. The earlier report below and PDF describe the implementation before these default changes; [SECURITY.md](SECURITY.md) documents current behavior.

## Earlier functional validation

Checked on 18 September 2026 using Windows and Python 3.12.

- **81 automated tests passed**, covering the original claim/ingestion behavior plus abbreviations, single-word names, cybercrime aliases, Urdu search, exact word boundaries, compound name/topic queries, crime-reporting filters, CTD/DoS ambiguity, date ranges, search caching, authentication, live-search opt-out/failures, and separation of external search results from the claim index.
- Ruff checks passed for the application, tests and diagnostic script.
- JavaScript syntax validation passed with Node.js.
- `pip check` reported no broken requirements.
- Browser verification: dashboard rendered, WebSocket reported connected, recent articles and source status appeared, and a synthetic unmatched claim returned `Unverified` with 0% retrieval similarity.
- Two dependency deprecation warnings occur in Starlette's test client (httpx integration and the AnyIO portal alias). These are not failing tests; versions are recorded in `requirements-tested.txt`.

## Live ingestion smoke test

One complete run stored **86 articles** with bounded snippets:

| Publisher | Observed result | Articles changed |
| --- | --- | ---: |
| DAWN | RSS succeeded | 24 |
| ARY News | RSS succeeded | 30 |
| Geo News | RSS succeeded | 20 |
| Dunya News | RSS URL returned HTML; robots-aware HTML fallback succeeded | 12 |
| Hum News | Publisher returned HTTP 403 | 0 |
| Samaa | Connection failed, including outside the sandbox | 0 |

These are point-in-time integration results, not availability guarantees. The application surfaces errors rather than claiming complete coverage. The portable ZIP excludes the live database and query history; a fresh installation builds its own index.

## Search update verification

The running `/api/check` endpoint accepted CTD, Dos, DDos, cyber, cyber crime, and Babar with HTTP 200. All six example queries returned live search matches during integration checks. Browser checks confirmed that three-letter CTD and cyber crime submit successfully and display search results. CTD is constrained to the police/terrorism context; DoS requires computing context when only the abbreviation is present. The dashboard includes date-range selection, a live-search opt-out, a crime-reporting filter, and a separate full-claim mode.

Live searches use Google's public news RSS search. They are not an exhaustive archive and depend on provider availability. Names are mentions rather than identity verification or guilt findings. No accusation is inferred from a search match. Two-word and five-character minimum validation rules have been removed; empty, markup-only, nonalphabetic, and oversized input remains invalid.

## Remaining limits

The actual sentence-transformer and spaCy model downloads were not installed or run. The optional embedding combination was tested with an injected deterministic encoder. No real-world accuracy percentage, cross-language entailment capability, or guarantee of error-free verdicts is claimed. Stance rules need labeled-domain evaluation and human review. PostgreSQL/Redis deployment adapters and multi-user accounts are outside this SQLite implementation.
