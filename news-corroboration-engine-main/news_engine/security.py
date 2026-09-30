"""Single-process request safeguards; deploy behind a trusted HTTPS proxy."""

import asyncio
import ipaddress
import secrets
import time
from collections import deque

import anyio

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

MAX_BODY_BYTES = 16_384
MAX_WS_MESSAGE_BYTES = 4096


def valid_key(supplied, expected):
    # compare_digest(str, str) raises on non-ASCII attacker input.
    return secrets.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


class RequestLimits:
    def __init__(self):
        self.buckets = {}

    def allow(self, limits):
        now = time.monotonic()
        # Hard bound bookkeeping even when clients rotate addresses.
        for key in list(self.buckets):
            events = self.buckets[key]
            while events and events[0] <= now - 60:
                events.popleft()
            if not events:
                del self.buckets[key]
        new_keys = {key for key, _ in limits} - self.buckets.keys()
        if len(self.buckets) + len(new_keys) > 2048:
            return False
        if any(len(self.buckets.get(key, ())) >= maximum for key, maximum in limits):
            return False
        for key, _ in limits:
            self.buckets.setdefault(key, deque()).append(now)
        return True


class SecurityMiddleware:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.limits = RequestLimits()
        self.active_requests = self.active_websockets = 0

    async def __call__(self, scope, receive, send):
        kind = scope["type"]
        if kind not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        if scope.get("method") == "OPTIONS":
            return await self.app(scope, receive, send)
        settings = self.settings
        path = scope.get("path", "")
        secure = scope.get("scheme") in {"https", "wss"}
        host = (scope.get("client") or ("unknown", 0))[0]
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False

        async def secured_send(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Cache-Control"] = "no-store"
                if settings.public_mode and secure:
                    headers["Strict-Transport-Security"] = "max-age=31536000"
                if path == "/" or path.startswith("/static/"):
                    headers["Content-Security-Policy"] = (
                        "default-src 'self'; script-src 'self'; style-src 'self'; "
                        "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
                        "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
                    )
            await send(message)

        async def reject(status, detail):
            if kind == "websocket":
                await send({"type": "websocket.close", "code": 1013 if status in {429, 503} else 1008})
            else:
                headers = {"Retry-After": "60"} if status in {429, 503} else None
                await JSONResponse({"detail": detail}, status, headers=headers)(scope, receive, secured_send)

        # This uses the ASGI peer/scheme, never untrusted Forwarded headers.
        if not settings.public_mode and not loopback:
            return await reject(403, "Remote access requires PUBLIC_MODE and HTTPS configuration")
        if settings.public_mode and not secure:
            return await reject(403, "HTTPS is required")
        protected = path.startswith("/api/") or kind == "websocket"
        if not protected:
            return await self.app(scope, receive, secured_send)
        limits = [
            ("all", settings.global_requests_per_minute),
            (("client", host), settings.requests_per_minute),
        ]
        if path in {"/api/check", "/api/search"}:
            limits += [
                ("queries", settings.global_queries_per_minute),
                (("queries", host), settings.queries_per_minute),
            ]
        if not self.limits.allow(limits):
            return await reject(429, "Request limit reached; retry after 60 seconds")
        if kind == "websocket":
            if self.active_websockets >= settings.max_websockets:
                return await reject(503, "Too many live connections")
            self.active_websockets += 1

            async def bounded_ws_receive():
                message = await receive()
                if message["type"] == "websocket.receive":
                    payload = message.get("bytes") or (message.get("text") or "").encode("utf-8")
                    if len(payload) > MAX_WS_MESSAGE_BYTES:
                        await send({"type": "websocket.close", "code": 1009})
                        return {"type": "websocket.disconnect", "code": 1009}
                return message

            try:
                return await self.app(scope, bounded_ws_receive, secured_send)
            finally:
                self.active_websockets -= 1
        if settings.api_key and not valid_key(Headers(scope=scope).get("x-api-key", ""), settings.api_key):
            return await reject(401, "Valid X-API-Key required")
        if self.active_requests >= settings.max_active_requests:
            return await reject(503, "Too many active requests")
        self.active_requests += 1
        try:
            body = bytearray()
            try:
                with anyio.fail_after(5):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > MAX_BODY_BYTES:
                            return await reject(413, "Request body exceeds 16 KiB")
                        if not message.get("more_body"):
                            break
            except TimeoutError:
                return await reject(408, "Request body timed out")
            delivered = False

            async def buffered_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            return await self.app(scope, buffered_receive, secured_send)
        finally:
            self.active_requests -= 1
