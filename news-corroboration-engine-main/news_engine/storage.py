from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None = None) -> str:
    value = value or utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Invalid article URL")
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}
    ]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", urlencode(sorted(query)), "")
    )


class Store:
    """Single-process SQLite store. Every mutation is serialized and transactional."""

    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA busy_timeout=5000;
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY, url TEXT UNIQUE NOT NULL,
                source_id TEXT NOT NULL, title TEXT NOT NULL, snippet TEXT NOT NULL,
                published_at TEXT, collected_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                flag_level TEXT, payload TEXT NOT NULL, content_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS article_dates ON articles(published_at, collected_at);
            CREATE INDEX IF NOT EXISTS article_flags ON articles(flag_level);
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, checked_at TEXT NOT NULL, result TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY, expires_at TEXT NOT NULL, result TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_status (
                source_id TEXT PRIMARY KEY, payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
            INSERT OR IGNORE INTO metadata VALUES ('revision', 0);
        """)
        self.connection.commit()

    @contextmanager
    def transaction(self):
        with self.lock, self.connection:
            yield self.connection

    def close(self):
        with self.lock:
            self.connection.close()

    def revision(self):
        with self.lock:
            return self.connection.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()[0]

    def upsert_article(self, article: dict) -> tuple[dict, bool]:
        article = dict(article)
        article["url"] = canonical_url(article["url"])
        article["id"] = hashlib.sha256(article["url"].encode()).hexdigest()
        content_hash = hashlib.sha256(
            json.dumps(
                {k: v for k, v in article.items() if k not in {"collected_at", "updated_at", "id"}},
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        with self.transaction() as db:
            existing = db.execute("SELECT * FROM articles WHERE id=?", (article["id"],)).fetchone()
            if existing and existing["content_hash"] == content_hash:
                return json.loads(existing["payload"]), False
            article["collected_at"] = existing["collected_at"] if existing else iso()
            article["updated_at"] = iso()
            db.execute(
                """INSERT INTO articles
                (id,url,source_id,title,snippet,published_at,collected_at,updated_at,flag_level,payload,content_hash)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title, snippet=excluded.snippet,
                published_at=excluded.published_at, updated_at=excluded.updated_at,
                flag_level=excluded.flag_level, payload=excluded.payload, content_hash=excluded.content_hash""",
                (
                    article["id"],
                    article["url"],
                    article["source_id"],
                    article["title"],
                    article["snippet"],
                    article.get("published_at"),
                    article["collected_at"],
                    article["updated_at"],
                    article.get("flag_level"),
                    json.dumps(article, ensure_ascii=False),
                    content_hash,
                ),
            )
            db.execute("UPDATE metadata SET value=value+1 WHERE key='revision'")
            db.execute("DELETE FROM cache")
        return article, True

    def articles(self, *, days=7, limit=5000, offset=0, flagged=False, source=None):
        clauses = ["COALESCE(published_at,collected_at)>=?", "COALESCE(published_at,collected_at)<=?"]
        args = [iso(utcnow() - timedelta(days=days)), iso(utcnow())]
        if flagged:
            clauses.append("flag_level IS NOT NULL")
        if source:
            clauses.append("source_id=?")
            args.append(source)
        with self.lock:
            rows = self.connection.execute(
                "SELECT payload FROM articles WHERE "
                + " AND ".join(clauses)
                + " ORDER BY COALESCE(published_at,collected_at) DESC, id LIMIT ? OFFSET ?",
                (*args, limit, offset),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def cache_get(self, key):
        with self.lock:
            row = self.connection.execute(
                "SELECT result FROM cache WHERE key=? AND expires_at>?", (key, iso())
            ).fetchone()
        return json.loads(row[0]) if row else None

    def cache_put(self, key, result, ttl):
        with self.transaction() as db:
            db.execute("DELETE FROM cache WHERE expires_at<=?", (iso(),))
            db.execute(
                "INSERT OR REPLACE INTO cache VALUES (?,?,?)",
                (key, iso(utcnow() + timedelta(seconds=ttl)), json.dumps(result, ensure_ascii=False)),
            )

    def save_query(self, result, retention_days):
        with self.transaction() as db:
            db.execute(
                "DELETE FROM history WHERE checked_at<?", (iso(utcnow() - timedelta(days=retention_days)),)
            )
            db.execute(
                "INSERT INTO history (checked_at,result) VALUES (?,?)",
                (iso(), json.dumps(result, ensure_ascii=False)),
            )

    def history(self, limit=50, offset=0, retention_days=30):
        with self.lock:
            rows = self.connection.execute(
                "SELECT id,checked_at,result FROM history WHERE checked_at>=? ORDER BY id DESC LIMIT ? OFFSET ?",
                (iso(utcnow() - timedelta(days=retention_days)), limit, offset),
            ).fetchall()
        return [{"id": r[0], "checked_at": r[1], "result": json.loads(r[2])} for r in rows]

    def set_source_status(self, source_id, status):
        with self.transaction() as db:
            db.execute("INSERT OR REPLACE INTO source_status VALUES (?,?)", (source_id, json.dumps(status)))

    def source_statuses(self):
        with self.lock:
            return {r[0]: json.loads(r[1]) for r in self.connection.execute("SELECT * FROM source_status")}
