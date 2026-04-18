from __future__ import annotations

"""Contract tests for shopping/reminders persistence surface wiring.

`/api/v1/health/deep` and `/api/v1/status` should report the real
shopping/reminders database path used by the shipped runtime, including
`SHOPPING_DB_PATH` overrides.
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


def _stub_main_dependencies(monkeypatch):
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


def test_main_status_exposes_runtime_shopping_persistence_truth(monkeypatch, tmp_path):
    _stub_main_dependencies(monkeypatch)

    custom_db_path = tmp_path / "shopping" / "status-shopping.db"
    monkeypatch.setenv("SHOPPING_DB_PATH", str(custom_db_path))
    sys.modules.pop("main", None)

    main = importlib.import_module("main")
    app = main.create_app(options={})

    def _fake_exists(path: str) -> bool:
        return path == str(custom_db_path)

    monkeypatch.setattr(main.os.path, "exists", _fake_exists)

    response = app.test_client().get("/api/v1/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["persistence"] == {
        "shopping_db_path": str(custom_db_path),
        "shopping_db_accessible": True,
    }
