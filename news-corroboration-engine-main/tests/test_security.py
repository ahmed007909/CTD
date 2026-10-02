from dataclasses import replace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from news_engine.api import create_app
from news_engine.security import RequestLimits, SecurityMiddleware
from news_engine.settings import Settings

KEY = "Test-only-key-1234567890-AbCdEfGhIjKlMn"


def public_settings(settings):
    return replace(
        settings,
        public_mode=True,
        api_key=KEY,
        save_history=False,
        cache_queries=False,
        allowed_origins=("https://testserver",),
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"api_key": ""},
        {"api_key": "a" * 64},
        {"save_history": True},
        {"cache_queries": True},
        {"allowed_origins": ("http://testserver",)},
        {"allowed_hosts": ("*",)},
        {"allowed_origins": ("https://unlisted.example",)},
    ],
)
def test_public_mode_fails_closed(settings, changes):
    with pytest.raises(ValueError):
        replace(public_settings(settings), **changes)


def test_local_mode_blocks_remote_peers_and_untrusted_hosts(settings):
    with TestClient(create_app(settings), client=("203.0.113.1", 50000)) as client:
        assert client.get("/").status_code == 403
        assert client.get("/", headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 403
        with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws/live-feed"):
            pass
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client:
        assert client.get("/", headers={"Host": "evil.example"}).status_code == 400
        assert client.get("/").status_code == 200


def test_public_https_auth_history_and_headers(settings):
    config = public_settings(settings)
    with TestClient(create_app(config), client=("203.0.113.1", 50000)) as client:
        assert client.get("/").status_code == 403
        assert client.get("/", headers={"X-Forwarded-Proto": "https"}).status_code == 403
    with TestClient(
        create_app(config), base_url="https://testserver", client=("203.0.113.1", 50000)
    ) as client:
        assert client.get("/api/history").status_code == 401
        assert client.get("/api/history", headers={"X-API-Key": KEY}).json() == []
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        response = client.get("/")
        assert response.headers["strict-transport-security"] == "max-age=31536000"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert response.headers["cache-control"] == "no-store"
        with client.websocket_connect("wss://testserver/ws/live-feed") as ws:
            ws.send_json({"api_key": KEY})
            assert ws.receive_json() == {"type": "ready"}


def test_rate_limits_reject_excess_queries(settings):
    settings.queries_per_minute = 2
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client:
        for _ in range(2):
            assert client.post("/api/search", json={"claim": "CTD"}).status_code == 200
        response = client.post("/api/search", json={"claim": "CTD"})
        assert response.status_code == 429 and response.headers["retry-after"] == "60"
        # Cheap source-status requests can still work after query capacity is exhausted.
        assert client.get("/api/sources").status_code == 200


def test_rate_window_expires_and_global_limit_spans_clients(monkeypatch):
    monkeypatch.setattr("news_engine.security.time.monotonic", lambda: 100)
    limiter = RequestLimits()
    assert limiter.allow([("global", 2), (("client", "a"), 1)])
    assert not limiter.allow([("global", 2), (("client", "a"), 1)])
    assert limiter.allow([("global", 2), (("client", "b"), 1)])
    assert not limiter.allow([("global", 2), (("client", "c"), 1)])
    monkeypatch.setattr("news_engine.security.time.monotonic", lambda: 161)
    assert limiter.allow([("global", 2), (("client", "a"), 1)])


def test_oversized_body_is_rejected_before_json_parsing(settings):
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client:
        response = client.post(
            "/api/search", content=b"x" * 16385, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 413


async def test_streamed_body_limit_without_content_length(settings):
    app = create_app(settings)

    async def body():
        yield b"x" * 8192
        yield b"y" * 8193

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1)), base_url="http://testserver"
    ) as client:
        response = await client.post("/api/search", content=body())
        assert response.status_code == 413


def test_queries_not_stored_or_sent_to_google_by_default(settings):
    settings.save_history = settings.cache_queries = False
    settings.live_search_enabled = True
    app = create_app(settings)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        fetcher = AsyncMock()
        app.state.search.fetcher = fetcher
        for payload in ({"claim": "CTD"}, {"claim": "A new airport opens", "mode": "claim"}):
            assert client.post("/api/check", json=payload).status_code == 200
        fetcher.get.assert_not_called()
        assert app.state.store.history() == []
        assert app.state.store.connection.execute("SELECT COUNT(*) FROM cache").fetchone()[0] == 0
    assert not Settings().save_history and not Settings().cache_queries


def test_websocket_capacity_and_oversized_auth_frame(settings):
    settings.max_websockets = 1
    settings.api_key = KEY
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client:
        with client.websocket_connect("/ws/live-feed") as first:
            first.send_json({"api_key": KEY})
            assert first.receive_json()["type"] == "ready"
            with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws/live-feed"):
                pass
        with client.websocket_connect("/ws/live-feed") as ws:
            ws.send_text("x" * 4097)
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
            assert exc.value.code == 1009


def test_non_ascii_websocket_key_is_rejected(settings):
    settings.api_key = KEY
    with (
        TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client,
        client.websocket_connect("/ws/live-feed") as ws,
    ):
        ws.send_json({"api_key": "غلط"})
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 1008


async def test_active_request_capacity_rejects_before_calling_app(settings):
    downstream = AsyncMock()
    middleware = SecurityMiddleware(downstream, settings)
    middleware.active_requests = settings.max_active_requests
    send = AsyncMock()
    await middleware(
        {"type": "http", "path": "/api/search", "client": ("127.0.0.1", 1), "scheme": "http", "headers": []},
        AsyncMock(),
        send,
    )
    downstream.assert_not_called()
    assert send.call_args_list[0].args[0]["status"] == 503
    assert middleware.active_requests == settings.max_active_requests
