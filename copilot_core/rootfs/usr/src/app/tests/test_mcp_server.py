"""Tests for MCP server contract stability."""

from __future__ import annotations

from flask import Flask

from copilot_core import __version__ as COPILOT_VERSION
from copilot_core.mcp_server import MCP_SERVER_INFO, mcp_bp


def _make_client():
    app = Flask(__name__)
    app.register_blueprint(mcp_bp)
    return app.test_client()


def test_mcp_server_info_uses_runtime_version() -> None:
    assert MCP_SERVER_INFO["version"] == COPILOT_VERSION


def test_mcp_initialize_returns_server_info() -> None:
    client = _make_client()
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["result"]["serverInfo"]["name"] == "pilotsuite"
    assert payload["result"]["serverInfo"]["version"] == COPILOT_VERSION
    assert payload["result"]["protocolVersion"] == "2025-03-26"


def test_mcp_tools_list_exposes_pilotsuite_tools() -> None:
    client = _make_client()
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert resp.status_code == 200
    payload = resp.get_json()
    tools = payload["result"]["tools"]
    names = {t["name"] for t in tools}
    assert "pilotsuite.get_mood" in names
    assert "pilotsuite.get_brain_graph" in names
    assert "pilotsuite.search_memory" in names


def test_mcp_web_search_tool_exists() -> None:
    """Phase 2: Web search via SearXNG should be available."""
    client = _make_client()
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    assert resp.status_code == 200
    payload = resp.get_json()
    tools = payload["result"]["tools"]
    names = {t["name"] for t in tools}
    assert "pilotsuite.search_web" in names, "MCP Phase 2: search_web tool missing"


def test_mcp_web_search_tool_schema() -> None:
    """Phase 2: Web search tool should have correct schema."""
    client = _make_client()
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 4, "method": "tools/list"})
    assert resp.status_code == 200
    payload = resp.get_json()
    tools = payload["result"]["tools"]
    web_search = next((t for t in tools if t["name"] == "pilotsuite.search_web"), None)
    assert web_search is not None, "search_web tool not found"
    assert "query" in web_search["inputSchema"]["properties"], "query parameter missing"
    assert web_search["inputSchema"]["properties"]["query"]["type"] == "string"
