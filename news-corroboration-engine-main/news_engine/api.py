from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import Annotated, Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .ingestion import USER_AGENT, Ingestor, SafeFetcher
from .live import LiveHub
from .matching import DISCLAIMER, Matcher
from .search import NewsSearch
from .security import SecurityMiddleware, valid_key
from .settings import ROOT, Settings
from .storage import Store
from .text import KeywordScanner, TextProcessor, clean_text


class ClaimRequest(BaseModel):
    claim: str = Field(min_length=1, max_length=3000)
    limit: int = Field(default=5, ge=1, le=20)
    mode: Literal["auto", "search", "claim"] = "auto"
    days: int = Field(default=30, ge=1, le=365)
    live: bool = False
    crime_only: bool = False

    @field_validator("claim")
    @classmethod
    def validate_claim(cls, value):
        value = clean_text(value)
        if not value or not any(c.isalpha() for c in value):
            raise ValueError("Enter a name, topic, abbreviation, or claim containing at least one letter")
        return value


def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()
    settings.__post_init__()

    @asynccontextmanager
    async def lifespan(app):
        store = Store(settings.database_path)
        task = None
        try:
            scanner = KeywordScanner(settings.keywords_path)
            processor = await run_in_threadpool(TextProcessor, settings.spacy_model)
            matcher = await run_in_threadpool(Matcher, store, settings, scanner)
            hub = LiveHub()
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15),
                headers={"User-Agent": USER_AGENT},
                limits=httpx.Limits(max_connections=10),
                trust_env=False,
            ) as client:
                ingestor = Ingestor(store, settings, scanner, processor, hub.publish, SafeFetcher(client))
                app.state.store, app.state.matcher, app.state.hub = store, matcher, hub
                app.state.ingestor = ingestor
                app.state.search = NewsSearch(store, settings, scanner, SafeFetcher(client))
                if settings.ingestion_enabled:
                    task = asyncio.create_task(ingestor.run_forever())
                try:
                    yield
                finally:
                    if task:
                        task.cancel()
                        with suppress(asyncio.CancelledError):
                            await task
                        task = None
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            store.close()

    app = FastAPI(
        title="News Corroboration Engine",
        version="1.0.0",
        lifespan=lifespan,
        description=DISCLAIMER,
        docs_url=None if settings.public_mode else "/docs",
        redoc_url=None if settings.public_mode else "/redoc",
        openapi_url=None if settings.public_mode else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityMiddleware, settings=settings)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

    def authorize(x_api_key: Annotated[str | None, Header()] = None):
        if settings.api_key and not valid_key(x_api_key or "", settings.api_key):
            raise HTTPException(401, "Valid X-API-Key required")

    protected = [Depends(authorize)]

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(ROOT / "static/index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.get("/health")
    def health():
        states = app.state.store.source_statuses()
        return {
            "status": "ok",
            "matching_mode": app.state.matcher.mode,
            "ingestion_enabled": settings.ingestion_enabled,
            "sources_with_errors": sum(s["state"] != "ok" for s in states.values()),
        }

    @app.post("/api/check", dependencies=protected)
    async def check(request: ClaimRequest):
        if request.mode == "search" or (request.mode == "auto" and len(request.claim.split()) <= 4):
            return await search_response(request)
        result = await run_in_threadpool(app.state.matcher.check, request.claim, request.limit)
        result["mode"] = "claim"
        result["source_status"] = app.state.store.source_statuses()
        return result

    async def search_response(request: ClaimRequest):
        result = await app.state.search.search(
            request.claim, request.limit, request.days, request.live, request.crime_only
        )
        result["source_status"] = app.state.store.source_statuses()
        return result

    @app.post("/api/search", dependencies=protected)
    async def search(request: ClaimRequest):
        return await search_response(request)

    @app.get("/api/sources", dependencies=protected)
    def sources():
        states = app.state.store.source_statuses()
        return [{**s, "status": states.get(s["id"], {"state": "not_polled"})} for s in settings.sources]

    @app.get("/api/articles", dependencies=protected)
    def articles(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        flagged: bool = False,
        source: str | None = None,
    ):
        return app.state.store.articles(
            days=settings.article_max_age_days, limit=limit, offset=offset, flagged=flagged, source=source
        )

    @app.get("/api/history", dependencies=protected)
    def history(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        if not settings.save_history:
            return []
        return app.state.store.history(limit, offset, settings.history_retention_days)

    @app.websocket("/ws/live-feed")
    async def live_feed(websocket: WebSocket):
        origin = websocket.headers.get("origin")
        if origin and origin not in settings.allowed_origins:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        if settings.api_key:
            try:
                # Authenticate in a frame; credentials never appear in URLs/access logs.
                message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
                if not isinstance(message, dict) or not valid_key(
                    str(message.get("api_key", "")), settings.api_key
                ):
                    await websocket.close(code=1008)
                    return
            except WebSocketDisconnect:
                return
            except (TimeoutError, ValueError):
                await websocket.close(code=1008)
                return
        queue = app.state.hub.subscribe()

        async def sender():
            await websocket.send_json({"type": "ready"})
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                except TimeoutError:
                    event = {"type": "heartbeat"}
                await asyncio.wait_for(websocket.send_json(event), timeout=10)

        async def receiver():
            while True:
                await websocket.receive_text()

        tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            app.state.hub.unsubscribe(queue)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    return app


app = create_app()
