import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from news_engine.api import create_app


def test_api_end_to_end(settings):
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/health").json()["status"] == "ok"
        assert len(client.get("/api/sources").json()) == 6
        result = client.post("/api/check", json={"claim": "A new airport opened in Karachi"})
        assert result.status_code == 200 and result.json()["verdict"] == "Unverified"
        assert len(client.get("/api/history").json()) == 1
        assert client.get("/api/articles?limit=0").status_code == 422
        assert client.get("/api/history?offset=-1").status_code == 422


@pytest.mark.parametrize("claim", ["", "     ", "<script>x</script>", "123456", "x" * 3001])
def test_bad_claims(settings, claim):
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client:
        assert client.post("/api/check", json={"claim": claim}).status_code == 422


def test_auth_and_websocket(settings):
    settings.api_key = "test-secret"
    app = create_app(settings)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/history").status_code == 401
        assert client.get("/api/history", headers={"X-API-Key": "test-secret"}).status_code == 200
        with client.websocket_connect("/ws/live-feed") as ws:
            ws.send_json({"api_key": "test-secret"})
            assert ws.receive_json() == {"type": "ready"}
            client.portal.call(app.state.hub.publish, {"type": "article", "alert": True})
            assert ws.receive_json()["alert"] is True
        assert not app.state.hub.queues
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect("/ws/live-feed", headers={"origin": "https://evil.example"}),
        ):
            pass
        with client.websocket_connect("/ws/live-feed") as ws:
            ws.send_json({"api_key": "wrong"})
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()
