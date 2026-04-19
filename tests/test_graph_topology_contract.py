"""Contract tests for GET /api/v1/graph/topology (VFM-003-A)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Bypass auth before any app imports
mock_security = MagicMock()
mock_security.require_token = lambda f: f
sys.modules["copilot_core.api.security"] = mock_security

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

import types
from flask import Blueprint


def _stub_shared_app_dependencies():
    mcp_stub = types.ModuleType("copilot_core.api.v1.mcp")
    mcp_stub.bp = Blueprint("mcp_stub", __name__, url_prefix="/api/v1/mcp")
    sys.modules["copilot_core.api.v1.mcp"] = mcp_stub

    tags_stub = types.ModuleType("copilot_core.tags")
    tags_stub.TagRegistry = type("TagRegistry", (), {})
    tags_stub.create_tag_service = lambda *a, **k: None
    sys.modules["copilot_core.tags"] = tags_stub

    tags_api_stub = types.ModuleType("copilot_core.tags.api")
    tags_api_stub.init_tags_api = lambda *a, **k: None
    sys.modules["copilot_core.tags.api"] = tags_api_stub


class TestGraphTopology:
    """Verify GET /api/v1/graph/topology returns bounded topology shape."""

    def test_returns_topology_shape(self):
        import importlib

        _stub_shared_app_dependencies()
        sys.modules.pop("main", None)

        main = importlib.import_module("main")
        app = main.create_app(options={})

        client = app.test_client()
        response = client.get("/api/v1/graph/topology")

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()

        assert payload.get("ok") is True
        assert payload.get("version") == 1
        # Structural fields
        assert "total_nodes" in payload
        assert "total_edges" in payload
        assert "nodes_by_kind" in payload
        assert "nodes_by_domain" in payload
        assert "nodes" in payload
        assert "edges" in payload
        assert isinstance(payload["nodes"], list)
        assert isinstance(payload["edges"], list)
        # Each node must have minimal shape
        for node in payload["nodes"]:
            assert "id" in node
            assert "kind" in node
            assert "domain" in node
            assert "label" in node
        # Each edge must have from/to
        for edge in payload["edges"]:
            assert "from" in edge
            assert "to" in edge
