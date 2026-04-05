from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api import security  # noqa: E402
from copilot_core.api.v1 import ha_events as module  # noqa: E402


BASE_PATH = "/api/v1/ha-events/api/v1/ha/events"


class FakeWebSocketClient:
    def __init__(self, *, connected: bool = True, messages_received: int = 7, last_error: str | None = None) -> None:
        self.connected = connected
        self.disconnected = False
        self.status = SimpleNamespace(
            state=module.ConnectionState.CONNECTED if connected else module.ConnectionState.DISCONNECTED,
            messages_received=messages_received,
            last_error=last_error,
        )

    @property
    def is_connected(self) -> bool:
        return self.connected

    async def disconnect(self) -> None:
        self.connected = False
        self.disconnected = True
        self.status.state = module.ConnectionState.DISCONNECTED


class FakeEventHandler:
    def __init__(self) -> None:
        self.subscriptions: list[str] = []
        self.history_payload = [
            {
                "event_type": "state_changed",
                "data": {"entity_id": "light.kitchen", "state": "on"},
                "origin": "LOCAL",
                "time_fired": "2026-04-05T00:00:00+00:00",
                "received_at": "2026-04-05T00:00:01+00:00",
            },
            {
                "event_type": "call_service",
                "data": {"domain": "light", "service": "turn_on"},
                "origin": "LOCAL",
                "time_fired": "2026-04-05T00:00:10+00:00",
                "received_at": "2026-04-05T00:00:11+00:00",
            },
        ]
        self.queue_size = 2
        self.throttle_ms = 100
        self.raise_on: str | None = None
        self.clear_calls = 0

    @property
    def active_subscriptions(self) -> list[str]:
        return list(self.subscriptions)

    @property
    def history_size(self) -> int:
        return len(self.history_payload)

    async def subscribe(self, event_type: str, handler=None, throttle_ms: int = 100) -> None:
        if self.raise_on == "subscribe":
            raise RuntimeError("subscribe exploded")
        self.throttle_ms = throttle_ms
        if event_type not in self.subscriptions:
            self.subscriptions.append(event_type)

    async def unsubscribe(self, event_type: str, handler=None) -> None:
        if event_type in self.subscriptions:
            self.subscriptions.remove(event_type)

    async def get_history(self, limit: int = 100, event_type: str | None = None):
        if self.raise_on == "get_history":
            raise RuntimeError("history exploded")
        rows = [dict(row) for row in self.history_payload]
        if event_type:
            rows = [row for row in rows if row["event_type"] == event_type]
        return rows[:limit]

    async def clear_history(self) -> None:
        self.clear_calls += 1
        self.history_payload.clear()


def _build_client(monkeypatch, *, authorized: bool = True, ws_client=None, event_handler=None, ensure_connection=None):
    monkeypatch.setattr(security, "validate_token", lambda _request: authorized)
    module._ws_client = ws_client
    module._event_handler = event_handler
    module._listening_task = None
    module._socketio = None
    if ensure_connection is not None:
        monkeypatch.setattr(module, "_ensure_connection", ensure_connection)
    app = Flask(__name__)
    app.register_blueprint(module.ha_events_bp)
    return app.test_client()


def test_ha_events_contract_covers_all_routes(monkeypatch) -> None:
    ws_client = FakeWebSocketClient(connected=True, messages_received=12)
    event_handler = FakeEventHandler()
    ensure_calls: list[tuple[str, str]] = []

    async def fake_ensure_connection(access_token: str, base_url: str) -> bool:
        ensure_calls.append((access_token, base_url))
        return True

    monkeypatch.setattr(module, "_flask_sock_available", lambda: True)
    client = _build_client(
        monkeypatch,
        ws_client=ws_client,
        event_handler=event_handler,
        ensure_connection=fake_ensure_connection,
    )

    response = client.get(f"{BASE_PATH}/subscribe")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "message": "Use Socket.IO for real-time events",
        "socketio_endpoint": "/socket.io/",
        "socketio_room": "ha_events",
        "note": "Connect via Socket.IO client to receive ha_event messages",
    }

    response = client.post(
        f"{BASE_PATH}/subscribe",
        json={
            "access_token": "token-1",
            "base_url": "ws://ha.local:8123",
            "event_types": ["state_changed", "call_service"],
            "throttle_ms": 150,
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "subscribed": ["state_changed", "call_service"],
        "failed": [],
        "throttle_ms": 150,
        "connected": True,
        "active_subscriptions": ["state_changed", "call_service"],
    }
    assert ensure_calls == [("token-1", "ws://ha.local:8123")]
    assert event_handler.throttle_ms == 150

    response = client.get(f"{BASE_PATH}/history?event_type=state_changed&include_data=false&limit=5")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "count": 1,
        "events": [
            {
                "event_type": "state_changed",
                "origin": "LOCAL",
                "time_fired": "2026-04-05T00:00:00+00:00",
                "received_at": "2026-04-05T00:00:01+00:00",
            }
        ],
    }

    response = client.post(f"{BASE_PATH}/unsubscribe", json={"event_types": ["call_service"]})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "unsubscribed": ["call_service"],
        "remaining_subscriptions": ["state_changed"],
    }

    response = client.get(f"{BASE_PATH}/status")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "connected": True,
        "websocket_state": "connected",
        "active_subscriptions": ["state_changed"],
        "queue_size": 2,
        "history_size": 2,
        "throttle_ms": 150,
        "messages_received": 12,
    }

    response = client.post(f"{BASE_PATH}/clear")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "Event history cleared"}
    assert event_handler.clear_calls == 1
    assert event_handler.history_payload == []

    response = client.post(
        f"{BASE_PATH}/connect",
        json={
            "access_token": "token-2",
            "base_url": "ws://ha.second:8123",
            "auto_subscribe": True,
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "connected": True,
        "base_url": "ws://ha.second:8123",
        "subscribed_events": module.STANDARD_EVENT_TYPES,
        "websocket_state": "connected",
    }
    assert ensure_calls[-1] == ("token-2", "ws://ha.second:8123")

    response = client.post(f"{BASE_PATH}/unsubscribe", json={"clear_all": True})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "unsubscribed": module.STANDARD_EVENT_TYPES,
        "remaining_subscriptions": [],
    }

    response = client.post(f"{BASE_PATH}/disconnect")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "Disconnected"}
    assert ws_client.disconnected is True
    assert module._ws_client is None


def test_ha_events_contract_hardens_validation_and_runtime_edges(monkeypatch) -> None:
    monkeypatch.setattr(module, "_flask_sock_available", lambda: False)
    client = _build_client(monkeypatch)

    response = client.get(f"{BASE_PATH}/subscribe")
    assert response.status_code == 503
    assert response.get_json() == {
        "ok": False,
        "error": "WebSocket support not available. Install flask-sock.",
    }

    response = client.post(f"{BASE_PATH}/subscribe")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No JSON body provided"}

    response = client.post(f"{BASE_PATH}/subscribe", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.post(f"{BASE_PATH}/subscribe", json={"event_types": "state_changed"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "event_types must be a list"}

    response = client.post(f"{BASE_PATH}/subscribe", json={"event_types": [1]})
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "event_types must contain only non-empty strings",
    }

    response = client.post(f"{BASE_PATH}/subscribe", json={"event_types": ["state_changed"], "access_token": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "access_token must be a string"}

    response = client.post(f"{BASE_PATH}/subscribe", json={"event_types": ["state_changed"], "base_url": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "base_url must be a string"}

    response = client.post(f"{BASE_PATH}/subscribe", json={"event_types": ["state_changed"], "throttle_ms": "100"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "throttle_ms must be an integer"}

    response = client.post(f"{BASE_PATH}/subscribe", json={"event_types": ["state_changed"]})
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "Not connected. Provide access_token to establish connection.",
    }

    async def fake_ensure_connection(_access_token: str, _base_url: str) -> bool:
        return False

    handler = FakeEventHandler()
    client = _build_client(monkeypatch, event_handler=handler, ensure_connection=fake_ensure_connection)

    response = client.post(
        f"{BASE_PATH}/subscribe",
        json={"access_token": "token", "event_types": ["state_changed"]},
    )
    assert response.status_code == 503
    assert response.get_json() == {
        "ok": False,
        "error": "Failed to connect to HomeAssistant WebSocket",
    }

    response = client.post(f"{BASE_PATH}/unsubscribe", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.post(f"{BASE_PATH}/unsubscribe", json={"clear_all": "yes"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "clear_all must be a boolean"}

    response = client.post(f"{BASE_PATH}/unsubscribe", json={"event_types": [1]})
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "event_types must contain only non-empty strings",
    }

    handler.raise_on = "get_history"
    response = client.get(f"{BASE_PATH}/history")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "history exploded"}

    response = client.post(f"{BASE_PATH}/connect")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No JSON body provided"}

    response = client.post(f"{BASE_PATH}/connect", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.post(f"{BASE_PATH}/connect", json={"access_token": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "access_token must be a string"}

    response = client.post(f"{BASE_PATH}/connect", json={"access_token": "token", "base_url": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "base_url must be a string"}

    response = client.post(f"{BASE_PATH}/connect", json={"access_token": "token", "auto_subscribe": "yes"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "auto_subscribe must be a boolean"}

    response = client.post(f"{BASE_PATH}/connect", json={})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "access_token is required"}

    response = client.post(f"{BASE_PATH}/connect", json={"access_token": "token"})
    assert response.status_code == 503
    assert response.get_json() == {
        "ok": False,
        "error": "Failed to connect to HomeAssistant WebSocket",
    }

    no_handler_client = _build_client(monkeypatch, event_handler=None)

    response = no_handler_client.post(f"{BASE_PATH}/unsubscribe", json={})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No active subscriptions"}

    response = no_handler_client.get(f"{BASE_PATH}/history")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No event history available"}

    response = no_handler_client.post(f"{BASE_PATH}/clear")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No event handler initialized"}


def test_ha_events_contract_requires_authentication(monkeypatch) -> None:
    client = _build_client(monkeypatch, authorized=False, ws_client=FakeWebSocketClient(), event_handler=FakeEventHandler())

    response = client.get(f"{BASE_PATH}/status")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }
