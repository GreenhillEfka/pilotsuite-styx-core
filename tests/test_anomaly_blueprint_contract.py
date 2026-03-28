"""Regression coverage for anomaly blueprint optional-dependency behavior."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1 import anomaly as anomaly_module  # noqa: E402
from copilot_core.api.v1.anomaly import anomaly_bp  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setattr(anomaly_module, "np", None)
    monkeypatch.setattr(anomaly_module, "create_anomaly_detector", None)
    monkeypatch.setattr(anomaly_module, "AnomalyLevel", None)
    monkeypatch.setattr(anomaly_module, "AnomalyResult", None)
    monkeypatch.setattr(anomaly_module, "ModelStore", None)
    monkeypatch.setattr(anomaly_module, "ModelMetadata", None)
    monkeypatch.setattr(anomaly_module, "TrainingRecord", None)

    app = Flask(__name__)
    app.register_blueprint(anomaly_bp, url_prefix="/api/v1")
    return app.test_client()


def test_anomaly_blueprint_degrades_cleanly_without_ml_dependencies(monkeypatch) -> None:
    client = _client(monkeypatch)

    status_response = client.get("/api/v1/anomaly/model/status")
    assert status_response.status_code == 503
    assert status_response.get_json()["error"] == "anomaly_unavailable"

    detect_response = client.post("/api/v1/anomaly/detect", json={"values": [1, 2, 3]})
    assert detect_response.status_code == 503
    assert detect_response.get_json()["error"] == "anomaly_unavailable"
