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
from copilot_core.api.v1 import media_zones as module  # noqa: E402


def _build_client(monkeypatch, *, media_mgr=None, proactive_engine=None):
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
    module.init_media_zones_api(media_mgr, proactive_engine)
    rate_limit_module.get_rate_limiter().reset()

    app = Flask(__name__)
    app.register_blueprint(module.media_zones_bp)
    return app.test_client()


def test_media_zones_lookup_and_assignment_contracts(monkeypatch) -> None:
    mgr = MagicMock()
    mgr.get_all_assignments.return_value = {"living": ["media_player.living_room"]}
    mgr.get_zone_players.return_value = ["media_player.living_room"]
    client = _build_client(monkeypatch, media_mgr=mgr, proactive_engine=MagicMock())

    response = client.get("/api/v1/media/zones")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zones": {"living": ["media_player.living_room"]},
    }

    response = client.get("/api/v1/media/zones/living")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "players": ["media_player.living_room"],
    }

    response = client.post(
        "/api/v1/media/zones/living/assign",
        json={"entity_id": " media_player.living_room ", "role": "primary"},
    )
    assert response.status_code == 201
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "entity_id": "media_player.living_room",
    }
    mgr.assign_player.assert_called_once_with(
        zone_id="living",
        entity_id="media_player.living_room",
        role="primary",
    )

    response = client.post(
        "/api/v1/media/zones/living-room.invalid/assign",
        json={"entity_id": "media_player.living_room"},
    )
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "Invalid zone_id format. Must be alphanumeric, max 50 chars.",
    }


def test_media_zones_volume_and_play_media_validation_contracts(monkeypatch) -> None:
    mgr = MagicMock()
    client = _build_client(monkeypatch, media_mgr=mgr, proactive_engine=MagicMock())

    response = client.post("/api/v1/media/zones/living/volume", json={})
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "Missing required field 'volume'",
    }

    response = client.post("/api/v1/media/zones/living/volume", json={"volume": "loud"})
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "'volume' must be a number between 0.0 and 1.0",
    }

    response = client.post("/api/v1/media/zones/living/volume", json={"volume": 1.5})
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "'volume' must be between 0.0 and 1.0",
    }

    response = client.post("/api/v1/media/zones/living/volume", json={"volume": "0.45"})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "volume": 0.45,
    }
    mgr.set_zone_volume.assert_called_once_with("living", 0.45)

    response = client.post(
        "/api/v1/media/zones/living/play-media",
        json={
            "media_content_id": " spotify:track:abc123 ",
            "media_content_type": "music",
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "media_content_id": "spotify:track:abc123",
        "media_content_type": "music",
    }
    mgr.play_media_in_zone.assert_called_once_with(
        zone_id="living",
        media_content_id="spotify:track:abc123",
        media_content_type="music",
    )


def test_media_zones_musikwolke_lifecycle_contracts(monkeypatch) -> None:
    mgr = MagicMock()
    mgr.start_musikwolke.return_value = {"session_id": "mw123"}
    client = _build_client(monkeypatch, media_mgr=mgr, proactive_engine=MagicMock())

    response = client.post(
        "/api/v1/media/musikwolke/start",
        json={"person_id": "person.alice", "source_zone": "living"},
    )
    assert response.status_code == 201
    assert response.get_json() == {
        "ok": True,
        "session_id": "mw123",
        "person_id": "person.alice",
        "source_zone": "living",
    }
    mgr.start_musikwolke.assert_called_once_with(
        person_id="person.alice",
        source_zone="living",
    )

    response = client.post(
        "/api/v1/media/musikwolke/mw.invalid/update",
        json={"entered_zone": "kitchen"},
    )
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "Invalid session_id format. Must be alphanumeric, max 50 chars.",
    }

    response = client.post(
        "/api/v1/media/musikwolke/mw123/update",
        json={"entered_zone": "kitchen"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "session_id": "mw123",
        "entered_zone": "kitchen",
    }
    mgr.update_musikwolke.assert_called_once_with(
        session_id="mw123",
        entered_zone="kitchen",
    )

    response = client.post("/api/v1/media/musikwolke/mw123/stop")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "session_id": "mw123",
        "stopped": True,
    }
    mgr.stop_musikwolke.assert_called_once_with(session_id="mw123")


def test_media_zones_proactive_zone_entry_updates_matching_musikwolke_sessions(monkeypatch) -> None:
    mgr = MagicMock()
    mgr.get_musikwolke_sessions.return_value = [
        {"session_id": "mw123", "person_id": "person.alice"},
        {"session_id": "mw999", "person_id": "person.bob"},
    ]
    engine = MagicMock()
    engine.on_zone_entry.return_value = [{"type": "music_recommendation", "zone_id": "living"}]
    client = _build_client(monkeypatch, media_mgr=mgr, proactive_engine=engine)

    response = client.post(
        "/api/v1/media/proactive/zone-entry",
        json={
            "person_id": "person.alice",
            "zone_id": "living",
            "context": {"mood": "focus"},
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "person_id": "person.alice",
        "zone_id": "living",
        "suggestions": [{"type": "music_recommendation", "zone_id": "living"}],
        "musikwolke_updated": True,
    }
    engine.on_zone_entry.assert_called_once_with(
        person_id="person.alice",
        zone_id="living",
        context={"mood": "focus"},
    )
    mgr.update_musikwolke.assert_called_once_with(
        session_id="mw123",
        entered_zone="living",
    )


def test_media_zones_favorites_and_source_selection_contracts(monkeypatch) -> None:
    mgr = MagicMock()
    mgr.get_zone_favorites.side_effect = RuntimeError("favorites failed")
    mgr.select_source.side_effect = RuntimeError("source failed")
    client = _build_client(monkeypatch, media_mgr=mgr, proactive_engine=MagicMock())

    response = client.get("/api/v1/media/zones/living.invalid/favorites")
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "Invalid zone_id format. Must be alphanumeric, max 50 chars.",
    }

    response = client.get("/api/v1/media/zones/living/favorites")
    assert response.status_code == 500
    assert response.get_json() == {
        "ok": False,
        "error": "favorites failed",
    }

    response = client.post(
        "/api/v1/media/zones/living.invalid/select-source",
        json={"source": "Spotify"},
    )
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "Invalid zone_id format. Must be alphanumeric, max 50 chars.",
    }

    response = client.post(
        "/api/v1/media/zones/living/select-source",
        json={"source": "Spotify"},
    )
    assert response.status_code == 500
    assert response.get_json() == {
        "ok": False,
        "error": "source failed",
    }

    mgr = MagicMock()
    mgr.get_zone_favorites.return_value = {
        "zone_id": "living",
        "favorites": ["Spotify"],
        "players": [{"entity_id": "media_player.living_room", "source_list": ["Spotify"]}],
    }
    mgr.select_source.return_value = {
        "ok": True,
        "zone_id": "living",
        "source": "Spotify",
    }
    client = _build_client(monkeypatch, media_mgr=mgr, proactive_engine=MagicMock())

    response = client.get("/api/v1/media/zones/living/favorites")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "favorites": ["Spotify"],
        "players": [{"entity_id": "media_player.living_room", "source_list": ["Spotify"]}],
    }

    response = client.post(
        "/api/v1/media/zones/living/select-source",
        json={"source": "Spotify"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "source": "Spotify",
    }
    mgr.select_source.assert_called_once_with("living", "Spotify")


def test_media_zones_missing_services_return_503(monkeypatch) -> None:
    client = _build_client(monkeypatch, media_mgr=None, proactive_engine=None)

    response = client.get("/api/v1/media/zones")
    assert response.status_code == 503
    assert response.get_json() == {
        "ok": False,
        "error": "MediaZoneManager not initialized",
    }

    response = client.post(
        "/api/v1/media/proactive/deliver",
        json={"suggestion": {"type": "music_recommendation"}},
    )
    assert response.status_code == 503
    assert response.get_json() == {
        "ok": False,
        "error": "ProactiveContextEngine not initialized",
    }
