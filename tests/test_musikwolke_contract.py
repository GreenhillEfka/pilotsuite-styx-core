from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api import rate_limit as rate_limit_module  # noqa: E402
from copilot_core.api.v1 import musikwolke as module  # noqa: E402


def _build_client(monkeypatch, *, bridge=None):
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
    module.init_musikwolke_api(bridge)
    rate_limit_module.get_rate_limiter().reset()

    app = Flask(__name__)
    app.register_blueprint(module.musikwolke_bp)
    return app.test_client()


def test_musikwolke_status_and_zone_map_contracts(monkeypatch) -> None:
    bridge = MagicMock()
    bridge.get_status.return_value = {
        "sonos_connected": True,
        "zone_speaker_map": {"living": "Wohnzimmer"},
        "active_zones": ["living"],
        "last_occupied_zone": "living",
        "sonos": {"total_speakers": 1},
        "media_follow": {"active_sessions": 1},
    }
    bridge.get_zone_speaker_map.return_value = {"living": "Wohnzimmer"}
    client = _build_client(monkeypatch, bridge=bridge)

    response = client.get("/api/v1/musikwolke/status")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "sonos_connected": True,
        "zone_speaker_map": {"living": "Wohnzimmer"},
        "active_zones": ["living"],
        "last_occupied_zone": "living",
        "sonos": {"total_speakers": 1},
        "media_follow": {"active_sessions": 1},
    }

    response = client.get("/api/v1/musikwolke/zone-map")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_speaker_map": {"living": "Wohnzimmer"},
    }


def test_musikwolke_zone_map_validation_and_runtime_errors(monkeypatch) -> None:
    bridge = MagicMock()
    client = _build_client(monkeypatch, bridge=bridge)

    response = client.post("/api/v1/musikwolke/zone-map")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Request body required"}

    response = client.post("/api/v1/musikwolke/zone-map", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.post(
        "/api/v1/musikwolke/zone-map",
        json={"zone_id": "living room", "sonos_room": "Wohnzimmer"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid zone_id format"}

    bridge.set_zone_speaker.side_effect = RuntimeError("map failed")
    response = client.post(
        "/api/v1/musikwolke/zone-map",
        json={"zone_id": "living", "sonos_room": "Wohnzimmer"},
    )
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "map failed"}

    bridge.set_zone_speaker.side_effect = None
    response = client.post(
        "/api/v1/musikwolke/zone-map",
        json={"zone_id": "living", "sonos_room": "Wohnzimmer"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "sonos_room": "Wohnzimmer",
    }
    bridge.set_zone_speaker.assert_called_with("living", "Wohnzimmer")

    bridge.get_zone_speaker_map.side_effect = RuntimeError("zone-map failed")
    response = client.get("/api/v1/musikwolke/zone-map")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "zone-map failed"}


def test_musikwolke_play_pause_and_volume_contracts(monkeypatch) -> None:
    bridge = MagicMock()
    bridge.play_in_zone.return_value = True
    bridge.set_zone_volume.return_value = True
    bridge.pause_in_zone.side_effect = RuntimeError("pause failed")
    client = _build_client(monkeypatch, bridge=bridge)

    response = client.post("/api/v1/musikwolke/play/living.invalid", json={})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid zone_id format"}

    response = client.post("/api/v1/musikwolke/play/living", json={"volume_pct": "loud"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "volume_pct must be an integer"}

    response = client.post("/api/v1/musikwolke/play/living", json={"volume_pct": "25"})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "zone_id": "living", "action": "play"}
    bridge.play_in_zone.assert_called_once_with("living", 25)

    response = client.post("/api/v1/musikwolke/pause/living")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "pause failed"}

    response = client.post("/api/v1/musikwolke/volume/living", json={"volume_pct": 101})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "volume_pct must be between 0 and 100"}

    response = client.post("/api/v1/musikwolke/volume/living", json={"volume_pct": "30"})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "zone_id": "living", "volume_pct": 30}
    bridge.set_zone_volume.assert_called_once_with("living", 30)


def test_musikwolke_lifecycle_and_discovery_contracts(monkeypatch) -> None:
    bridge = MagicMock()
    bridge.auto_discover_mappings.return_value = 2
    bridge.get_zone_speaker_map.return_value = {
        "living": "Wohnzimmer",
        "kitchen": "Küche",
    }
    bridge.create_musikwolke.return_value = True
    bridge.dissolve_musikwolke.return_value = True
    client = _build_client(monkeypatch, bridge=bridge)

    response = client.post("/api/v1/musikwolke/auto-discover")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "mapped": 2,
        "zone_speaker_map": {"living": "Wohnzimmer", "kitchen": "Küche"},
    }

    response = client.post("/api/v1/musikwolke/create", json={"zone_ids": ["living"]})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "need at least 2 zones"}

    response = client.post(
        "/api/v1/musikwolke/create",
        json={"zone_ids": ["living", "kitchen"]},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_ids": ["living", "kitchen"],
    }
    bridge.create_musikwolke.assert_called_once_with(["living", "kitchen"])

    response = client.post("/api/v1/musikwolke/dissolve", json={"zone_ids": "living"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "zone_ids must be a list"}

    response = client.post("/api/v1/musikwolke/dissolve", json={"zone_ids": ["living.invalid"]})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid zone_id in list"}

    response = client.post("/api/v1/musikwolke/dissolve", json={"zone_ids": ["living"]})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "zone_ids": ["living"]}
    bridge.dissolve_musikwolke.assert_called_once_with(["living"])


def test_musikwolke_missing_bridge_and_runtime_errors_return_consistent_json(monkeypatch) -> None:
    client = _build_client(monkeypatch, bridge=None)

    response = client.get("/api/v1/musikwolke/status")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "musikwolke_not_available"}

    response = client.post("/api/v1/musikwolke/create", json={"zone_ids": ["living", "kitchen"]})
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "musikwolke_not_available"}

    bridge = MagicMock()
    bridge.get_status.side_effect = RuntimeError("status failed")
    bridge.auto_discover_mappings.side_effect = RuntimeError("discover failed")
    client = _build_client(monkeypatch, bridge=bridge)

    response = client.get("/api/v1/musikwolke/status")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "status failed"}

    response = client.post("/api/v1/musikwolke/auto-discover")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "discover failed"}


def test_musikwolke_zone_favorites_contracts(monkeypatch) -> None:
    """Test zone favorites API endpoints."""
    bridge = MagicMock()
    bridge.get_zone_favorites.return_value = {"living": "Jazz Radio", "kitchen": "Pop Hits"}
    client = _build_client(monkeypatch, bridge=bridge)

    # GET /favorites - retrieve all zone favorites
    response = client.get("/api/v1/musikwolke/favorites")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_favorites": {"living": "Jazz Radio", "kitchen": "Pop Hits"},
    }

    # POST /favorites/<zone_id> - set favorite for a zone
    response = client.post(
        "/api/v1/musikwolke/favorites/bedroom",
        json={"favorite_name": "Classical Mix"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "bedroom",
        "favorite_name": "Classical Mix",
    }
    bridge.set_zone_favorite.assert_called_with("bedroom", "Classical Mix")

    # DELETE /favorites/<zone_id> - remove favorite
    response = client.delete("/api/v1/musikwolke/favorites/bedroom")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "bedroom",
        "favorite_name": None,
    }
    bridge.set_zone_favorite.assert_called_with("bedroom", "")

    # Validation: invalid zone_id
    response = client.post(
        "/api/v1/musikwolke/favorites/invalid zone!",
        json={"favorite_name": "Test"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid zone_id format"}

    # Validation: missing favorite_name
    response = client.post(
        "/api/v1/musikwolke/favorites/bedroom",
        json={},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "favorite_name required"}
