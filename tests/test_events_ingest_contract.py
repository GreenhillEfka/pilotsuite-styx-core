from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
MODULE_PATH = CORE_APP_ROOT / "copilot_core" / "api" / "v1" / "events_ingest.py"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api import security as api_security_module  # noqa: E402

spec = importlib.util.spec_from_file_location("ps_events_ingest_contract_module", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeStore:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.ingest_calls: list[list[dict]] = []
        self.query_calls: list[dict] = []
        self.stats_calls = 0
        self.query_result = [
            {
                "id": "evt-1",
                "kind": "state_changed",
                "entity_id": "light.kitchen",
                "zone_id": "kitchen",
            }
        ]
        self.stats_result = {
            "buffered": 3,
            "persisted": 3,
            "dedup_cache_size": 1,
        }

    def ingest_batch(self, items: list[dict]) -> dict:
        if self.raise_on == "ingest":
            raise RuntimeError("ingest exploded")
        self.ingest_calls.append(items)
        return {
            "accepted": len(items),
            "rejected": 1,
            "deduped": 0,
            "errors": [{"index": 1, "error": "duplicate"}],
            "accepted_events": items[:1],
        }

    def query(self, **kwargs):
        if self.raise_on == "query":
            raise RuntimeError("query exploded")
        self.query_calls.append(kwargs)
        return list(self.query_result)

    def stats(self):
        if self.raise_on == "stats":
            raise RuntimeError("stats exploded")
        self.stats_calls += 1
        return dict(self.stats_result)


def _build_client(monkeypatch, *, authorized: bool = True, store: FakeStore | None = None, callback=None):
    monkeypatch.setattr(api_security_module, "validate_token", lambda _request: authorized)
    module.set_store(store)
    module.set_post_ingest_callback(callback)

    app = Flask(__name__)
    app.register_blueprint(module.bp)
    return app.test_client()


def test_events_ingest_contract_covers_all_routes(monkeypatch) -> None:
    store = FakeStore()
    callback_calls: list[list[dict]] = []

    def callback(events: list[dict]) -> None:
        callback_calls.append(events)
        raise RuntimeError("callback exploded")

    client = _build_client(monkeypatch, store=store, callback=callback)

    response = client.post(
        "/api/v1/events",
        json={
            "items": [
                {
                    "type": "state_changed",
                    "source": "home_assistant",
                    "entity_id": "light.kitchen",
                    "ts": "2026-04-05T07:40:00Z",
                    "zone_id": "kitchen",
                    "attributes": {
                        "domain": "light",
                        "old_state": "off",
                        "new_state": "on",
                        "state_attributes": {"brightness": 255},
                    },
                },
                {
                    "type": "service_call",
                    "source": "ha",
                    "ts": "2026-04-05T07:41:00Z",
                    "attributes": {
                        "domain": "light",
                        "service": "turn_on",
                        "entity_ids": ["light.kitchen"],
                    },
                },
            ]
        },
    )
    assert response.status_code == 207
    assert response.get_json() == {
        "accepted": 2,
        "rejected": 1,
        "deduped": 0,
        "errors": [{"index": 1, "error": "duplicate"}],
    }

    assert len(store.ingest_calls) == 1
    ingested_items = store.ingest_calls[0]
    assert len(ingested_items) == 2
    assert ingested_items[0]["kind"] == "state_changed"
    assert ingested_items[0]["src"] == "ha"
    assert ingested_items[0]["domain"] == "light"
    assert ingested_items[0]["old"] == {"state": "off", "attrs": {}}
    assert ingested_items[0]["new"] == {
        "state": "on",
        "attrs": {"brightness": 255},
    }
    assert ingested_items[0]["zone_ids"] == ["kitchen"]
    assert ingested_items[1]["kind"] == "call_service"
    assert ingested_items[1]["src"] == "ha"
    assert ingested_items[1]["service"] == {
        "domain": "light",
        "service": "turn_on",
        "entity_ids": ["light.kitchen"],
    }
    assert callback_calls == [[ingested_items[0]]]

    response = client.get(
        "/api/v1/events?domain=light&entity_id=light.kitchen&kind=state_changed&zone_id=kitchen&since=2026-04-05T07:00:00Z&limit=2"
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "events": store.query_result,
        "count": 1,
    }
    assert store.query_calls == [
        {
            "domain": "light",
            "entity_id": "light.kitchen",
            "kind": "state_changed",
            "zone_id": "kitchen",
            "since": "2026-04-05T07:00:00Z",
            "limit": 2,
        }
    ]

    response = client.get("/api/v1/events/stats")
    assert response.status_code == 200
    assert response.get_json() == store.stats_result
    assert store.stats_calls == 1


def test_events_ingest_contract_hardens_validation_and_runtime_errors(monkeypatch) -> None:
    store = FakeStore()
    client = _build_client(monkeypatch, store=store)

    response = client.post("/api/v1/events", data="not-json", content_type="application/json")
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "invalid_json",
        "detail": "Request body must be valid JSON",
    }

    response = client.post("/api/v1/events", json=[])
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "invalid_json",
        "detail": "Request body must be a JSON object",
    }

    response = client.post("/api/v1/events", json={"items": [{"source": "ha", "ts": "2026-04-05T07:40:00Z"}]})
    assert response.status_code == 400
    assert response.get_json()["ok"] is False
    assert response.get_json()["error"] == "validation_error"
    assert response.get_json()["detail"][0]["field"] == "items.0.kind"

    response = client.post("/api/v1/events", json={"items": []})
    assert response.status_code == 200
    assert response.get_json() == {"accepted": 0, "rejected": 0, "deduped": 0}

    store.raise_on = "ingest"
    response = client.post(
        "/api/v1/events",
        json={
            "items": [
                {
                    "type": "state_changed",
                    "source": "ha",
                    "entity_id": "light.kitchen",
                    "ts": "2026-04-05T07:40:00Z",
                }
            ]
        },
    )
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "ingest exploded"}

    response = client.get("/api/v1/events?limit=0")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "limit must be a positive integer"}

    response = client.get("/api/v1/events?limit=bad")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "limit must be a positive integer"}

    response = client.get("/api/v1/events?limit=1001")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "limit must be <= 1000"}

    store.raise_on = "query"
    response = client.get("/api/v1/events")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "query exploded"}

    store.raise_on = "stats"
    response = client.get("/api/v1/events/stats")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "stats exploded"}


def test_events_ingest_contract_requires_authentication(monkeypatch) -> None:
    client = _build_client(monkeypatch, authorized=False, store=FakeStore())

    response = client.get("/api/v1/events")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }
