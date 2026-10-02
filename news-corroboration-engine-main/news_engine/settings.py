import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).parent


@dataclass
class Settings:
    database_path: str = "data/news.db"
    poll_interval_seconds: int = 120
    ingestion_enabled: bool = True
    scraping_enabled: bool = True
    article_max_age_days: int = 7
    max_index_articles: int = 5000
    cache_ttl_seconds: int = 120
    snippet_max_chars: int = 500
    semantic_enabled: bool = False
    semantic_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    spacy_model: str = ""
    api_key: str = ""
    allowed_origins: tuple[str, ...] = ("http://127.0.0.1:8000", "http://localhost:8000")
    save_history: bool = False
    cache_queries: bool = False
    public_mode: bool = False
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "[::1]")
    requests_per_minute: int = 120
    global_requests_per_minute: int = 600
    queries_per_minute: int = 20
    global_queries_per_minute: int = 60
    max_active_requests: int = 8
    max_websockets: int = 20
    history_retention_days: int = 30
    sources: list[dict] = field(
        default_factory=lambda: json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))
    )
    keywords_path: Path = ROOT / "config/keywords.json"
    search_aliases_path: Path = ROOT / "config/search_aliases.json"
    live_search_enabled: bool = True

    def __post_init__(self):
        if not self.api_key.isascii():
            raise ValueError("API_KEY must contain only ASCII characters")
        for name in (
            "poll_interval_seconds",
            "article_max_age_days",
            "max_index_articles",
            "cache_ttl_seconds",
            "snippet_max_chars",
            "history_retention_days",
            "requests_per_minute",
            "global_requests_per_minute",
            "queries_per_minute",
            "global_queries_per_minute",
            "max_active_requests",
            "max_websockets",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.snippet_max_chars > 1000:
            raise ValueError("snippet_max_chars cannot exceed 1000")
        if not self.allowed_hosts or any("*" in host for host in self.allowed_hosts):
            raise ValueError("ALLOWED_HOSTS must contain explicit hostnames without wildcards")
        if self.public_mode:
            if len(self.api_key) < 32 or len(set(self.api_key)) < 12:
                raise ValueError("PUBLIC_MODE requires a strong random API_KEY of at least 32 characters")
            if self.save_history or self.cache_queries:
                raise ValueError("PUBLIC_MODE requires SAVE_HISTORY=false and CACHE_QUERIES=false")
            if not self.allowed_origins or any(
                urlsplit(origin).scheme != "https"
                or not urlsplit(origin).hostname
                or urlsplit(origin).hostname not in self.allowed_hosts
                or urlsplit(origin).path not in {"", "/"}
                or urlsplit(origin).query
                or urlsplit(origin).fragment
                or urlsplit(origin).username
                or urlsplit(origin).password
                for origin in self.allowed_origins
            ):
                raise ValueError("PUBLIC_MODE requires HTTPS ALLOWED_ORIGINS matching ALLOWED_HOSTS")
        ids = [s["id"] for s in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("Source IDs must be unique")

    @classmethod
    def from_env(cls):
        load_dotenv()
        defaults = cls()
        values = {}
        for name in cls.__dataclass_fields__:
            raw = os.getenv(name.upper())
            if raw is None or name == "sources":
                continue
            default = getattr(defaults, name)
            if isinstance(default, bool):
                if raw.lower() not in {"true", "false", "1", "0"}:
                    raise ValueError(f"Invalid boolean: {name}")
                values[name] = raw.lower() in {"true", "1"}
            elif isinstance(default, int):
                values[name] = int(raw)
            elif isinstance(default, tuple):
                values[name] = tuple(x.strip() for x in raw.split(",") if x.strip())
            elif isinstance(default, Path):
                values[name] = Path(raw)
            else:
                values[name] = raw
        return cls(**values)
