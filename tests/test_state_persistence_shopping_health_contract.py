from __future__ import annotations

"""Contract tests for status/deep-health persistence surface wiring.

`/api/v1/health/deep` and `/api/v1/status` should report the real
runtime persistence paths used by the shipped storage layers, including
`SHOPPING_DB_PATH`, `CONVERSATION_MEMORY_DB`, and `COPILOT_VECTOR_DB_PATH`
overrides.
"""

import importlib
import sys
import types
from pathlib import Path

from flask import Blueprint
import requests

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))


def _stub_shared_app_dependencies(monkeypatch):
    mcp_stub = types.ModuleType("copilot_core.api.v1.mcp")
    mcp_stub.bp = Blueprint("mcp_stub", __name__, url_prefix="/api/v1/mcp")
    monkeypatch.setitem(sys.modules, "copilot_core.api.v1.mcp", mcp_stub)

    tags_stub = types.ModuleType("copilot_core.tags")

    class _TagRegistry:
        pass

    tags_stub.TagRegistry = _TagRegistry
    tags_stub.create_tag_service = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "copilot_core.tags", tags_stub)

    tags_api_stub = types.ModuleType("copilot_core.tags.api")
    tags_api_stub.init_tags_api = lambda registry: None
    monkeypatch.setitem(sys.modules, "copilot_core.tags.api", tags_api_stub)


def _stub_main_dependencies(monkeypatch):
    _stub_shared_app_dependencies(monkeypatch)


class _DummyHealthChecker:
    async def full_health_check(self):
        return {"status": "healthy", "components": {}}

    async def get_quick_health(self):
        return {"status": "healthy", "components": {}}

    async def get_dependency_health(self):
        return {"status": "healthy", "missing_required": []}


def _stub_lightweight_app_dependencies(monkeypatch):
    _stub_shared_app_dependencies(monkeypatch)
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "pilotclaw-test-token")

    from copilot_core.api.v1 import metrics as metrics_api
    from copilot_core.voice import voice_health

    monkeypatch.setattr(metrics_api, "get_health_checker", lambda: _DummyHealthChecker())
    monkeypatch.setattr(metrics_api, "get_voice_health_block", lambda: {"can_transcribe": True})
    monkeypatch.setattr(voice_health, "get_voice_health_block", lambda: {"can_transcribe": True})


class _FakeResponse:
    ok = True


def test_main_deep_health_uses_runtime_shopping_db_path(monkeypatch, tmp_path):
    _stub_main_dependencies(monkeypatch)

    custom_db_path = tmp_path / "shopping" / "custom-shopping.db"
    monkeypatch.setenv("SHOPPING_DB_PATH", str(custom_db_path))
    sys.modules.pop("main", None)

    main = importlib.import_module("main")
    app = main.create_app(options={})

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: _FakeResponse())

    def _fake_exists(path: str) -> bool:
        if path == str(custom_db_path):
            return True
        return False

    monkeypatch.setattr(main.os.path, "exists", _fake_exists)

    client = app.test_client()
    response = client.get("/api/v1/health/deep")

    assert response.status_code == 503
    payload = response.get_json()
    assert payload["checks"]["shopping_db"] is True
    assert payload["checks"]["conversation_memory_db"] is False
    assert payload["checks"]["vector_store_db"] is False


def test_main_status_exposes_runtime_persistence_truth(monkeypatch, tmp_path):
    _stub_main_dependencies(monkeypatch)

    shopping_db_path = tmp_path / "shopping" / "status-shopping.db"
    conversation_db_path = tmp_path / "memory" / "status-conversation.db"
    vector_db_path = tmp_path / "vector" / "status-store.db"
    monkeypatch.setenv("SHOPPING_DB_PATH", str(shopping_db_path))
    monkeypatch.setenv("CONVERSATION_MEMORY_DB", str(conversation_db_path))
    monkeypatch.setenv("COPILOT_VECTOR_DB_PATH", str(vector_db_path))
    sys.modules.pop("main", None)

    main = importlib.import_module("main")
    app = main.create_app(options={})

    accessible_paths = {str(shopping_db_path), str(vector_db_path)}

    def _fake_exists(path: str) -> bool:
        return path in accessible_paths

    monkeypatch.setattr(main.os.path, "exists", _fake_exists)

    response = app.test_client().get("/api/v1/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["persistence"] == {
        "conversation_memory_db_path": str(conversation_db_path),
        "conversation_memory_db_accessible": False,
        "vector_store_db_path": str(vector_db_path),
        "vector_store_db_accessible": True,
        "shopping_db_path": str(shopping_db_path),
        "shopping_db_accessible": True,
    }


def test_main_deep_health_uses_runtime_conversation_and_vector_db_paths(monkeypatch, tmp_path):
    _stub_main_dependencies(monkeypatch)

    conversation_db_path = tmp_path / "memory" / "conversation.db"
    vector_db_path = tmp_path / "vector" / "store.db"
    monkeypatch.setenv("CONVERSATION_MEMORY_DB", str(conversation_db_path))
    monkeypatch.setenv("COPILOT_VECTOR_DB_PATH", str(vector_db_path))
    sys.modules.pop("main", None)

    main = importlib.import_module("main")
    app = main.create_app(options={})

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: _FakeResponse())

    def _fake_exists(path: str) -> bool:
        return path in {str(conversation_db_path), str(vector_db_path)}

    monkeypatch.setattr(main.os.path, "exists", _fake_exists)

    response = app.test_client().get("/api/v1/health/deep")

    assert response.status_code == 503
    payload = response.get_json()
    assert payload["checks"]["conversation_memory_db"] is True
    assert payload["checks"]["vector_store_db"] is True
    assert payload["checks"]["shopping_db"] is False


def test_lightweight_app_status_exposes_runtime_persistence_truth(monkeypatch, tmp_path):
    _stub_lightweight_app_dependencies(monkeypatch)

    shopping_db_path = tmp_path / "shopping" / "compat-shopping.db"
    conversation_db_path = tmp_path / "memory" / "compat-conversation.db"
    vector_db_path = tmp_path / "vector" / "compat-store.db"
    monkeypatch.setenv("SHOPPING_DB_PATH", str(shopping_db_path))
    monkeypatch.setenv("CONVERSATION_MEMORY_DB", str(conversation_db_path))
    monkeypatch.setenv("COPILOT_VECTOR_DB_PATH", str(vector_db_path))
    sys.modules.pop("copilot_core.app", None)

    app_module = importlib.import_module("copilot_core.app")
    monkeypatch.setattr(
        app_module.os.path,
        "exists",
        lambda path: path in {str(conversation_db_path), str(shopping_db_path)},
    )

    response = app_module.create_app().test_client().get("/api/v1/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["persistence"] == {
        "conversation_memory_db_path": str(conversation_db_path),
        "conversation_memory_db_accessible": True,
        "vector_store_db_path": str(vector_db_path),
        "vector_store_db_accessible": False,
        "shopping_db_path": str(shopping_db_path),
        "shopping_db_accessible": True,
    }


def test_lightweight_app_ready_exposes_runtime_persistence_truth(monkeypatch, tmp_path):
    _stub_lightweight_app_dependencies(monkeypatch)

    shopping_db_path = tmp_path / "shopping" / "ready-shopping.db"
    conversation_db_path = tmp_path / "memory" / "ready-conversation.db"
    vector_db_path = tmp_path / "vector" / "ready-store.db"
    monkeypatch.setenv("SHOPPING_DB_PATH", str(shopping_db_path))
    monkeypatch.setenv("CONVERSATION_MEMORY_DB", str(conversation_db_path))
    monkeypatch.setenv("COPILOT_VECTOR_DB_PATH", str(vector_db_path))
    sys.modules.pop("copilot_core.app", None)

    app_module = importlib.import_module("copilot_core.app")
    from copilot_core.api.v1 import metrics as metrics_api

    monkeypatch.setattr(
        metrics_api.os.path,
        "exists",
        lambda path: path in {str(vector_db_path), str(shopping_db_path)},
    )

    response = app_module.create_app().test_client().get(
        "/api/v1/ready",
        headers={"X-Auth-Token": "pilotclaw-test-token"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ready"] is True
    assert payload["persistence"] == {
        "conversation_memory_db_path": str(conversation_db_path),
        "conversation_memory_db_accessible": False,
        "vector_store_db_path": str(vector_db_path),
        "vector_store_db_accessible": True,
        "shopping_db_path": str(shopping_db_path),
        "shopping_db_accessible": True,
    }
