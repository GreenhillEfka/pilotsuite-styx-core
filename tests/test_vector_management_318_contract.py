"""VECTOR-MANAGEMENT-CONTRACT-318 focused contract coverage."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Blueprint, Flask

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

import copilot_core.api.v1.vector as vector_api
from copilot_core.api.v1.vector import bp as vector_bp


class FakeVectorStore:
    def __init__(self):
        self.by_type_calls: list[tuple[str, int]] = []
        self.get_calls: list[str] = []
        self.delete_calls: list[str] = []
        self.clear_calls: list[str | None] = []
        self.stats_calls = 0
        self.by_type: dict[str, list[object]] = {
            "entity": [],
            "user_preference": [],
            "pattern": [],
        }
        self.entries: dict[str, object] = {}
        self.delete_results: dict[str, bool] = {}
        self.stats_result: dict[str, object] = {
            "cache_size": 0,
            "persist": False,
            "db_path": None,
            "by_type": {},
            "total_entries": 0,
        }
        self.clear_result = 0

    async def get_by_type(self, entry_type: str, limit: int = 100):
        self.by_type_calls.append((entry_type, limit))
        return list(self.by_type.get(entry_type, []))[:limit]

    async def get(self, entry_id: str):
        self.get_calls.append(entry_id)
        return self.entries.get(entry_id)

    async def delete(self, entry_id: str):
        self.delete_calls.append(entry_id)
        return self.delete_results.get(entry_id, False)

    async def stats(self):
        self.stats_calls += 1
        return self.stats_result

    async def clear(self, entry_type: str | None = None):
        self.clear_calls.append(entry_type)
        return self.clear_result


def _entry(entry_id: str, entry_type: str, *, vector: list[float] | None = None, metadata: dict | None = None):
    return SimpleNamespace(
        id=entry_id,
        entry_type=entry_type,
        vector=vector or [0.1, 0.2, 0.3],
        created_at="2026-04-25T10:00:00+00:00",
        updated_at="2026-04-25T10:05:00+00:00",
        metadata=metadata or {},
    )


def _make_app():
    app = Flask(__name__)
    api_v1 = Blueprint("api_v1_test_vector", __name__, url_prefix="/api/v1")
    api_v1.register_blueprint(vector_bp)
    app.register_blueprint(api_v1)
    return app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(vector_api, "_validate_token", lambda request: True)
    return _make_app().test_client()


@pytest.fixture
def fake_store(monkeypatch):
    store = FakeVectorStore()
    monkeypatch.setattr(vector_api, "_store", lambda: store)
    return store


class TestVectorManagementRoutes:
    def test_live_management_routes_exist(self):
        app = _make_app()
        rules = {rule.rule for rule in app.url_map.iter_rules() if "/vector/" in rule.rule}

        assert "/api/v1/vector/vectors" in rules
        assert "/api/v1/vector/vectors/<path:entry_id>" in rules
        assert "/api/v1/vector/stats" in rules

    def test_auth_posture_is_unchanged(self):
        response = _make_app().test_client().get("/api/v1/vector/vectors")

        assert response.status_code == 401
        assert response.get_json() == {
            "error": "unauthorized",
            "message": "Valid X-Auth-Token or Bearer token required",
        }


class TestVectorListContract:
    def test_list_vectors_by_type_keeps_limit_bounded(self, client, fake_store):
        fake_store.by_type["entity"] = [
            _entry("entity:lamp", "entity", metadata={"zone": "living_room"}),
            _entry("entity:desk", "entity", metadata={"zone": "office"}),
        ]

        response = client.get("/api/v1/vector/vectors?type=entity&limit=999")

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["ok"] is True
        assert payload["count"] == 2
        assert [entry["id"] for entry in payload["entries"]] == ["entity:lamp", "entity:desk"]
        assert fake_store.by_type_calls == [("entity", 200)]

    def test_list_vectors_without_type_stays_bounded_to_requested_limit(self, client, fake_store):
        fake_store.by_type["entity"] = [_entry("entity:lamp", "entity")]
        fake_store.by_type["user_preference"] = [_entry("user_pref:anna", "user_preference")]
        fake_store.by_type["pattern"] = [_entry("pattern:morning", "pattern")]

        response = client.get("/api/v1/vector/vectors?limit=2")

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["count"] == 2
        assert [entry["id"] for entry in payload["entries"]] == ["entity:lamp", "user_pref:anna"]
        assert fake_store.by_type_calls == [
            ("entity", 2),
            ("user_preference", 2),
            ("pattern", 2),
        ]


class TestVectorGetContract:
    def test_get_vector_normalizes_bare_entry_id_explicitly(self, client, fake_store):
        fake_store.entries["user_pref:anna"] = _entry(
            "user_pref:anna",
            "user_preference",
            vector=[0.4, 0.5],
            metadata={"topic": "music"},
        )

        response = client.get("/api/v1/vector/vectors/anna")

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["ok"] is True
        assert payload["found"] is True
        assert payload["requested_id"] == "anna"
        assert payload["lookup_id"] == "user_pref:anna"
        assert payload["entry"]["id"] == "user_pref:anna"
        assert payload["entry"]["type"] == "user_preference"
        assert payload["entry"]["dimension"] == 2
        assert fake_store.get_calls == ["entity:anna", "user_pref:anna"]

    def test_get_vector_missing_keeps_attempted_ids_machine_checkable(self, client, fake_store):
        response = client.get("/api/v1/vector/vectors/missing-item")

        assert response.status_code == 404
        payload = response.get_json()
        assert payload == {
            "ok": False,
            "found": False,
            "requested_id": "missing-item",
            "attempted_ids": [
                "entity:missing-item",
                "user_pref:missing-item",
                "pattern:missing-item",
            ],
            "error": "Entry not found: missing-item",
        }
        assert fake_store.get_calls == [
            "entity:missing-item",
            "user_pref:missing-item",
            "pattern:missing-item",
        ]


class TestVectorDeleteContract:
    def test_delete_vector_reports_normalized_deleted_id_and_count(self, client, fake_store):
        fake_store.delete_results["pattern:quiet-hours"] = True

        response = client.delete("/api/v1/vector/vectors/quiet-hours")

        assert response.status_code == 200
        payload = response.get_json()
        assert payload == {
            "ok": True,
            "found": True,
            "requested_id": "quiet-hours",
            "deleted": "pattern:quiet-hours",
            "deleted_count": 1,
        }
        assert fake_store.delete_calls == [
            "entity:quiet-hours",
            "user_pref:quiet-hours",
            "pattern:quiet-hours",
        ]

    def test_delete_vector_missing_is_honest(self, client, fake_store):
        response = client.delete("/api/v1/vector/vectors/not-here")

        assert response.status_code == 404
        payload = response.get_json()
        assert payload == {
            "ok": False,
            "found": False,
            "requested_id": "not-here",
            "attempted_ids": [
                "entity:not-here",
                "user_pref:not-here",
                "pattern:not-here",
            ],
            "deleted": None,
            "deleted_count": 0,
            "error": "Entry not found: not-here",
        }


class TestVectorStatsAndClearContract:
    def test_stats_route_returns_bounded_store_truth(self, client, fake_store):
        fake_store.stats_result = {
            "cache_size": 3,
            "persist": True,
            "db_path": "/tmp/vector.db",
            "by_type": {"entity": 2, "pattern": 1},
            "total_entries": 3,
        }

        response = client.get("/api/v1/vector/stats")

        assert response.status_code == 200
        payload = response.get_json()
        assert payload == {
            "ok": True,
            "stats": {
                "cache_size": 3,
                "persist": True,
                "db_path": "/tmp/vector.db",
                "by_type": {"entity": 2, "pattern": 1},
                "total_entries": 3,
            },
        }
        assert fake_store.stats_calls == 1

    def test_clear_vectors_by_type_keeps_deleted_count_explicit(self, client, fake_store):
        fake_store.clear_result = 4

        response = client.delete("/api/v1/vector/vectors?type=entity")

        assert response.status_code == 200
        assert response.get_json() == {
            "ok": True,
            "deleted_count": 4,
            "type": "entity",
        }
        assert fake_store.clear_calls == ["entity"]

    def test_clear_all_vectors_reports_all_scope(self, client, fake_store):
        fake_store.clear_result = 7

        response = client.delete("/api/v1/vector/vectors")

        assert response.status_code == 200
        assert response.get_json() == {
            "ok": True,
            "deleted_count": 7,
            "type": "all",
        }
        assert fake_store.clear_calls == [None]
