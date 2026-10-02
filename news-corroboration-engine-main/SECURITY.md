# Security and deployment

## Supported use

The default configuration is for a local, single-process research tool. Public source code does not expose a running server or publish a user's local database. The application rejects remote peers in local mode, checks the Host header, and `run.ps1` binds to 127.0.0.1 with proxy headers disabled.

Publishing a repository does make its files, commit identities, and reachable history public. Keep `.env`, databases, news collections, queries, logs, and credentials out of Git. `.gitignore` protects common paths but cannot remove files already committed. Use your GitHub noreply email for both author and committer. Rewriting history does not revoke downloaded copies or guarantee deletion of GitHub's retained commit objects.

## Query privacy

- `SAVE_HISTORY=false` and `CACHE_QUERIES=false` are the defaults. Neither search nor claim results are written to SQLite with these settings. The history API returns an empty list when history is off.
- Public mode requires both settings to remain false. This application has no per-user accounts; an API key is a shared service credential.
- The dashboard and request schema default to local-only search. Explicitly checking Google News or sending `live: true` transmits the query and expanded terms to Google. `LIVE_SEARCH_ENABLED=false` disables this capability server-wide.
- Publisher polling still downloads public news in the background. Its article index is separate from query history.
- Turning storage off does not delete older SQLite rows or existing backups. Preserve needed records securely; retire old databases only after stopping the server and deciding what must be retained. Application settings cannot erase provider-side records.
- API responses use `Cache-Control: no-store`. Keys are kept in page memory, never URLs or browser persistent storage. Do not put a key in source code or a public deployment configuration.

## Public deployment configuration

No internet-facing deployment is included or activated. Obtain a domain, configure a TLS reverse proxy, and restrict the backend and outbound network before enabling public mode. Public mode refuses HTTP and insecure settings at startup; this is a guard, not a TLS certificate installer.

Example private `.env` values (replace the domain and generate a real secret):

```dotenv
PUBLIC_MODE=true
API_KEY=<generate-a-random-secret-locally>
ALLOWED_HOSTS=news.example.com
ALLOWED_ORIGINS=https://news.example.com
SAVE_HISTORY=false
CACHE_QUERIES=false
```

Generate the key locally using `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Store it only in the private environment or a secret manager. Public mode requires at least 32 ASCII characters with basic diversity validation; that validation cannot prove randomness. Do not use the example placeholder as a key.

Terminate HTTPS at a trusted proxy on the same host and forward only to loopback. Have the proxy replace forwarded headers rather than trust values supplied by clients. For that architecture, start one Uvicorn worker with:

```powershell
.\.venv\Scripts\python.exe -m uvicorn news_engine.api:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1 --no-access-log --limit-concurrency 32 --backlog 64 --timeout-keep-alive 5 --ws-max-size 4096 --ws-max-queue 4
```

Trust only the actual proxy's address; never use `--forwarded-allow-ips=*`. Restrict port 8000 to loopback. The security middleware uses the ASGI peer and scheme and does not parse `X-Forwarded-*` itself. An incorrect server trust configuration can invalidate peer-based restrictions. See [Uvicorn proxy settings](https://www.uvicorn.org/settings/#http).

Set the proxy's request-body limit to 16 KiB or less, enforce read/header timeouts and rate limits there, and allow WebSocket upgrades only over HTTPS. Install TLS certificates and configure the network firewall on the deployment host; these steps depend on the selected provider and domain and have not been performed for this repository. Restrict outbound connections from the application to public destinations, denying loopback, private, link-local, and cloud metadata networks. DNS validation in the fetcher is not a replacement for egress filtering.

## Application controls and limits

- All API endpoints require the configured key; WebSockets authenticate in their first frame. Invalid non-ASCII keys are rejected without server errors. Public mode hides interactive API documentation and the OpenAPI schema.
- Per rolling 60 seconds: 120 API requests/WebSocket attempts per peer, 600 overall; search/check requests additionally allow 20 per peer and 60 overall. Limits include failed authentication attempts. `429` includes `Retry-After: 60`.
- At most 8 active API requests and 20 WebSocket connections, including connections waiting for authentication. Overload returns `503` or a WebSocket refusal. Body reads have a 5-second deadline, a 16 KiB application limit, and WebSocket messages have a 4 KiB application limit. Configure server/proxy limits as above to reject large frames/bodies before allocating them.
- Limit state is bounded and held in one process; restarting clears it. These controls are not a distributed rate limiter or DDoS protection. Do not run multiple workers; ingestion, SQLite access, and broadcast queues are designed for one process.
- Dashboard content is rendered as text, external URLs are restricted to HTTP(S), SQL uses bound parameters, and outbound publisher fetches use host/redirect checks and bounded responses. Response headers include frame restrictions, a dashboard CSP, MIME-sniffing prevention, no-referrer, and HSTS on public HTTPS responses.
- Authentication uses a shared key, not separate users, roles, or isolated histories. Grant access only to trusted users. A publicly accessible multi-user service requires a separate authentication design and production review.

## Validation and reporting

Run `python -m pytest -q` and `python -m ruff check news_engine tests` in the project's virtual environment. Security tests cover remote/Host rejection, HTTPS, authentication, query privacy, request sizes, rate limits, and connection/concurrency bounds. These tests verify behavior, not the absence of all vulnerabilities.

The September 2026 PDF technology guide describes the earlier implementation. This file and the current code define the security/privacy defaults after hardening. Check dependencies regularly against an advisory service; the earlier scan covered the 46 pinned base/development packages, not optional semantic dependencies or the deployment OS.

Do not post credentials or private search data in public issues. For a suspected vulnerability, contact the repository owner privately with a minimal reproduction and affected version.
