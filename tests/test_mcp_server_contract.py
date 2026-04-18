"""Contract tests for the MCP Server module.

Verifies:
- mcp_bp is importable from copilot_core.mcp_server
- mcp_bp has url_prefix /mcp
- /mcp POST route exists on the blueprint
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))


class TestMCPServerModule:
    """MCP Server module is importable and exports mcp_bp."""

    def test_mcp_server_importable(self):
        from copilot_core import mcp_server
        assert mcp_server is not None

    def test_mcp_bp_importable(self):
        from copilot_core.mcp_server import mcp_bp
        assert mcp_bp is not None

    def test_mcp_bp_has_url_prefix(self):
        from copilot_core.mcp_server import mcp_bp
        assert mcp_bp.url_prefix == "/mcp"

    def test_mcp_bp_has_post_route(self):
        from flask import Flask
        from copilot_core.mcp_server import mcp_bp

        app = Flask(__name__)
        app.register_blueprint(mcp_bp)
        routes = {str(r): r.methods for r in app.url_map.iter_rules()}
        assert "/mcp" in routes
        assert "POST" in routes["/mcp"]