"""Regression coverage for metrics blueprint optional-dependency behavior."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1.metrics import metrics_bp  # noqa: E402


def _client():
    app = Flask(__name__)
    app.register_blueprint(metrics_bp, url_prefix="/api/v1")
    return app.test_client()


def test_metrics_blueprint_live_endpoint_stays_available() -> None:
    response = _client().get("/api/v1/live")
    assert response.status_code == 200
    assert response.get_json()["alive"] is True


def test_metrics_blueprint_degrades_cleanly_without_optional_deps() -> None:
    client = _client()

    metrics_response = client.get("/api/v1/metrics")
    assert metrics_response.status_code == 503
    assert metrics_response.get_json()["error"] == "metrics_unavailable"

    health_response = client.get("/api/v1/health")
    assert health_response.status_code == 200
    assert health_response.get_json()["error"] == "health_checker_unavailable"

    ready_response = client.get("/api/v1/ready")
    assert ready_response.status_code == 503
    assert ready_response.get_json()["error"] == "health_checker_unavailable"

    summary_response = client.get("/api/v1/metrics/summary")
    assert summary_response.status_code == 503
    assert summary_response.get_json()["error"] == "metrics_unavailable"
