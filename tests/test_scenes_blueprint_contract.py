"""Regression coverage for scenes optional-dependency behavior."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1 import scenes as scenes_module  # noqa: E402
from copilot_core.api.v1.scenes import get_scene_context_for_llm, scenes_bp  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(scenes_module, "http_requests", None)
    monkeypatch.setattr(
        scenes_module,
        "_scene_cache",
        {
            "scene-1": {
                "scene_id": "scene-1",
                "zone_id": "wohnbereich",
                "zone_name": "Wohnbereich",
                "name": "Abend",
                "entity_states": {},
            }
        },
    )

    app = Flask(__name__)
    app.register_blueprint(scenes_bp)
    return app.test_client()


def test_scenes_read_endpoints_stay_available_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    list_response = client.get("/api/v1/scenes", headers=headers)
    assert list_response.status_code == 200
    assert list_response.get_json()["count"] == 1

    presets_response = client.get("/api/v1/scenes/presets", headers=headers)
    assert presets_response.status_code == 200
    assert len(presets_response.get_json()["presets"]) >= 1


def test_scenes_write_endpoints_degrade_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    create_response = client.post(
        "/api/v1/scenes/create",
        headers=headers,
        json={
            "zone_id": "wohnbereich",
            "zone_name": "Wohnbereich",
            "entity_ids": ["light.wohnzimmer_decke"],
        },
    )
    assert create_response.status_code == 503
    assert create_response.get_json()["error"] == "scenes_unavailable"

    apply_response = client.post("/api/v1/scenes/scene-1/apply", headers=headers)
    assert apply_response.status_code == 503
    assert apply_response.get_json()["error"] == "scenes_unavailable"


def test_scene_context_still_reads_cache_without_requests(monkeypatch) -> None:
    _client(monkeypatch)
    ctx = get_scene_context_for_llm()
    assert "Wohnbereich" in ctx
