"""Regression coverage for MCP REST blueprint optional-dependency behavior."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1 import mcp as mcp_module  # noqa: E402
from copilot_core.api.v1.mcp import bp as mcp_bp  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(mcp_module, "http_requests", None)
    monkeypatch.setattr(
        mcp_module,
        "_MCP_CONNECTIONS",
        {
            "alpha": {
                "server_url": "http://mcp.local",
                "connected": False,
                "timeout": 5,
                "resources": [{"uri": "mcp://alpha/resource"}],
            }
        },
    )

    app = Flask(__name__)
    app.register_blueprint(mcp_bp)
    return app.test_client()


def test_mcp_status_and_resources_stay_available_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    status_resp = client.get("/api/v1/mcp/status", headers=headers)
    assert status_resp.status_code == 200
    status_body = status_resp.get_json()
    assert status_body["ok"] is True
    assert status_body["total_registered"] == 1
    assert "requests" in status_body["servers"]["alpha"]["last_error"]

    resources_resp = client.get("/api/v1/mcp/resources?server_id=alpha", headers=headers)
    assert resources_resp.status_code == 200
    assert resources_resp.get_json()["count"] == 1


def test_mcp_connect_and_query_degrade_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    connect_resp = client.post(
        "/api/v1/mcp/connect",
        headers=headers,
        json={"server_url": "http://mcp.local", "server_id": "beta"},
    )
    assert connect_resp.status_code == 503
    assert connect_resp.get_json()["error"] == "mcp_http_unavailable"

    query_resp = client.post(
        "/api/v1/mcp/query",
        headers=headers,
        json={"server_id": "alpha", "resource_uri": "mcp://alpha/resource"},
    )
    assert query_resp.status_code == 503
    assert query_resp.get_json()["error"] == "mcp_http_unavailable"
