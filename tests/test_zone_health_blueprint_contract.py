"""Regression coverage for zone health blueprint optional-dependency behavior."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1 import zone_health as zone_health_module  # noqa: E402
from copilot_core.api.v1.zone_health import init_zone_health_api, zone_health_bp  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(zone_health_module, "http_requests", None)
    monkeypatch.setattr(zone_health_module, "_checker", None)
    init_zone_health_api(zone_automation=None, module_registry=None)

    app = Flask(__name__)
    app.register_blueprint(zone_health_bp)
    return app.test_client()


def test_zone_health_blueprint_degrades_cleanly_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.get("/api/v1/zone/health", headers=headers)
    assert response.status_code == 503
    assert response.get_json()["error"] == "zone_health_unavailable"

    detail_response = client.get("/api/v1/zone/health/wohnzimmer", headers=headers)
    assert detail_response.status_code == 503
    assert detail_response.get_json()["error"] == "zone_health_unavailable"
