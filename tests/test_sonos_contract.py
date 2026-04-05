from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api import rate_limit as rate_limit_module  # noqa: E402
from copilot_core.api.v1 import sonos as module  # noqa: E402


def _build_client(monkeypatch, *, sonos_client=None):
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
    rate_limit_module.get_rate_limiter().reset()

    app = Flask(__name__)
    app.config["COPILOT_SERVICES"] = {"sonos_client": sonos_client} if sonos_client is not None else {}
    app.register_blueprint(module.sonos_bp)
    return app.test_client()


def test_sonos_status_surfaces_contract(monkeypatch) -> None:
    sonos_client = MagicMock()
    sonos_client.discover_zones.return_value = [
        {"coordinator": {"roomName": "Wohnzimmer"}, "members": [{"roomName": "Wohnzimmer"}]},
    ]
    sonos_client.get_speakers.return_value = [
        SimpleNamespace(
            room_name="Wohnzimmer",
            uuid="uuid-1",
            state="PLAYING",
            volume=24,
            muted=False,
            track_title="Song A",
            track_artist="Artist A",
            track_album="Album A",
            is_coordinator=True,
            group_members=["Wohnzimmer"],
        )
    ]
    sonos_client.get_summary.return_value = {
        "total_speakers": 1,
        "speakers": [{"room_name": "Wohnzimmer"}],
        "playing": 1,
        "groups": 1,
        "musikwolke_active": False,
    }
    sonos_client.health_check.return_value = True
    client = _build_client(monkeypatch, sonos_client=sonos_client)

    response = client.get("/api/v1/sonos/zones")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "total_speakers": 1,
        "zones": [{"coordinator": {"roomName": "Wohnzimmer"}, "members": [{"roomName": "Wohnzimmer"}]}],
    }

    response = client.get("/api/v1/sonos/speakers")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "speakers": [
            {
                "room_name": "Wohnzimmer",
                "uuid": "uuid-1",
                "state": "PLAYING",
                "volume": 24,
                "muted": False,
                "track": {"title": "Song A", "artist": "Artist A", "album": "Album A"},
                "is_coordinator": True,
                "group_members": ["Wohnzimmer"],
            }
        ],
    }

    response = client.get("/api/v1/sonos/summary")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "total_speakers": 1,
        "speakers": [{"room_name": "Wohnzimmer"}],
        "playing": 1,
        "groups": 1,
        "musikwolke_active": False,
    }

    response = client.get("/api/v1/sonos/health")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "service": "node-sonos-http-api",
    }


def test_sonos_playback_and_volume_contracts(monkeypatch) -> None:
    sonos_client = MagicMock()
    sonos_client.play.return_value = True
    sonos_client.pause.return_value = True
    sonos_client.next_track.return_value = True
    sonos_client.previous_track.return_value = True
    sonos_client.set_volume.return_value = True
    sonos_client.set_mute.return_value = True
    client = _build_client(monkeypatch, sonos_client=sonos_client)

    response = client.post("/api/v1/sonos/play", json={})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Missing 'room'"}

    response = client.post("/api/v1/sonos/play", json={"room": " Wohnzimmer "})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "room": "Wohnzimmer", "action": "play"}
    sonos_client.play.assert_called_once_with("Wohnzimmer")

    response = client.post("/api/v1/sonos/previous", json={})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Missing 'room'"}

    response = client.post("/api/v1/sonos/next", json={"room": "Küche"})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "room": "Küche", "action": "next"}

    response = client.post("/api/v1/sonos/volume", json={"room": "Wohnzimmer"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Missing or invalid 'volume'"}

    response = client.post("/api/v1/sonos/volume", json={"room": "Wohnzimmer", "volume": "30"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Missing or invalid 'volume'"}

    response = client.post("/api/v1/sonos/volume", json={"room": "Wohnzimmer", "volume": 30.8})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "room": "Wohnzimmer", "volume": 30}
    sonos_client.set_volume.assert_called_once_with("Wohnzimmer", 30)

    response = client.post("/api/v1/sonos/mute", json={"room": "Wohnzimmer", "muted": 0})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "room": "Wohnzimmer", "muted": False}
    sonos_client.set_mute.assert_called_once_with("Wohnzimmer", False)


def test_sonos_favorites_playlist_and_tts_contracts(monkeypatch) -> None:
    sonos_client = MagicMock()
    sonos_client.get_favorites.return_value = [{"name": "WDR 2"}]
    sonos_client.play_favorite.return_value = True
    sonos_client.get_playlists.return_value = [{"name": "Morning Mix"}]
    sonos_client.say.return_value = True
    sonos_client.say_all.return_value = True
    client = _build_client(monkeypatch, sonos_client=sonos_client)

    response = client.get("/api/v1/sonos/favorites")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "favorites": [{"name": "WDR 2"}]}

    response = client.post("/api/v1/sonos/favorite/play", json={"room": "Wohnzimmer"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Missing 'room' or 'name'"}

    response = client.post(
        "/api/v1/sonos/favorite/play",
        json={"room": "Wohnzimmer", "name": " WDR 2 "},
    )
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "room": "Wohnzimmer", "favorite": "WDR 2"}
    sonos_client.play_favorite.assert_called_once_with("Wohnzimmer", "WDR 2")

    response = client.get("/api/v1/sonos/playlists")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "playlists": [{"name": "Morning Mix"}]}

    response = client.post("/api/v1/sonos/say", json={"room": "Wohnzimmer", "text": "x" * 501})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Text too long (max 500 chars)"}

    response = client.post(
        "/api/v1/sonos/say",
        json={"room": "Wohnzimmer", "text": " Hallo! ", "language": "de-de", "volume": 40},
    )
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "room": "Wohnzimmer", "action": "say"}
    sonos_client.say.assert_called_once_with("Wohnzimmer", "Hallo!", language="de-de", volume=40)

    response = client.post("/api/v1/sonos/say-all", json={})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Missing 'text'"}

    response = client.post(
        "/api/v1/sonos/say-all",
        json={"text": "Achtung!", "language": "de-de", "volume": 30},
    )
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "action": "say-all"}
    sonos_client.say_all.assert_called_once_with("Achtung!", language="de-de", volume=30)


def test_sonos_grouping_contracts(monkeypatch) -> None:
    sonos_client = MagicMock()
    sonos_client.create_musikwolke.return_value = True
    sonos_client.dissolve_musikwolke.return_value = True
    sonos_client.follow_user.return_value = True
    sonos_client.join.return_value = True
    sonos_client.leave.return_value = True
    client = _build_client(monkeypatch, sonos_client=sonos_client)

    response = client.post("/api/v1/sonos/musikwolke/create", json={"rooms": ["Wohnzimmer"]})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Need at least 2 rooms"}

    response = client.post(
        "/api/v1/sonos/musikwolke/create",
        json={"rooms": ["Wohnzimmer", "Küche"]},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "rooms": ["Wohnzimmer", "Küche"],
        "action": "musikwolke-create",
    }
    sonos_client.create_musikwolke.assert_called_once_with(["Wohnzimmer", "Küche"])

    response = client.post("/api/v1/sonos/musikwolke/dissolve", json={"rooms": []})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Need at least 1 room"}

    response = client.post(
        "/api/v1/sonos/musikwolke/follow",
        json={"previous_room": "Wohnzimmer", "musikwolke_rooms": ["Wohnzimmer", "Küche"]},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Missing 'user_room'"}

    response = client.post(
        "/api/v1/sonos/musikwolke/follow",
        json={
            "user_room": "Küche",
            "previous_room": "Wohnzimmer",
            "musikwolke_rooms": ["Wohnzimmer", "Küche"],
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "user_room": "Küche", "action": "follow"}
    sonos_client.follow_user.assert_called_once_with(
        user_room="Küche",
        previous_room="Wohnzimmer",
        musikwolke_rooms=["Wohnzimmer", "Küche"],
    )

    response = client.post("/api/v1/sonos/join", json={"room": "Küche"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Missing 'room' or 'target'"}

    response = client.post("/api/v1/sonos/join", json={"room": "Küche", "target": "Wohnzimmer"})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "room": "Küche",
        "target": "Wohnzimmer",
        "action": "join",
    }
    sonos_client.join.assert_called_once_with("Küche", "Wohnzimmer")

    response = client.post("/api/v1/sonos/leave", json={})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Missing 'room'"}

    response = client.post("/api/v1/sonos/leave", json={"room": "Küche"})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "room": "Küche", "action": "leave"}
    sonos_client.leave.assert_called_once_with("Küche")


def test_sonos_missing_client_returns_503(monkeypatch) -> None:
    client = _build_client(monkeypatch, sonos_client=None)

    response = client.get("/api/v1/sonos/zones")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "Sonos client not initialized"}

    response = client.post("/api/v1/sonos/play", json={"room": "Wohnzimmer"})
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "Sonos client not initialized"}


def test_sonos_runtime_errors_return_consistent_json(monkeypatch) -> None:
    sonos_client = MagicMock()
    sonos_client.discover_zones.side_effect = RuntimeError("zones failed")
    sonos_client.get_favorites.side_effect = RuntimeError("favorites failed")
    sonos_client.say_all.side_effect = RuntimeError("say-all failed")
    sonos_client.follow_user.side_effect = RuntimeError("follow failed")
    client = _build_client(monkeypatch, sonos_client=sonos_client)

    response = client.get("/api/v1/sonos/zones")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "zones failed"}

    response = client.get("/api/v1/sonos/favorites")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "favorites failed"}

    response = client.post("/api/v1/sonos/say-all", json={"text": "Achtung!"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "say-all failed"}

    response = client.post(
        "/api/v1/sonos/musikwolke/follow",
        json={"user_room": "Küche", "previous_room": "Wohnzimmer", "musikwolke_rooms": ["Wohnzimmer", "Küche"]},
    )
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "follow failed"}
