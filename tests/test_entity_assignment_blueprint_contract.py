"""Regression coverage for entity assignment optional-dependency behavior."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1 import entity_assignment as entity_assignment_module  # noqa: E402
from copilot_core.api.v1.entity_assignment import entity_assignment_bp  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(entity_assignment_module, "requests", None)

    app = Flask(__name__)
    app.register_blueprint(entity_assignment_bp)
    return app.test_client()


def test_entity_assignment_degrades_cleanly_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.get("/api/v1/entity-assignment/suggestions", headers=headers)
    assert response.status_code == 503
    body = response.get_json()
    assert body["error"] == "entity_assignment_unavailable"
    assert body["suggestions"] == []
