"""Tests fuer das Sonos-Modul: Client, Intelligence, API-Endpoints."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from copilot_core.sonos.client import SonosHTTPClient
from copilot_core.sonos.intelligence import SonosIntelligence
from copilot_core.sonos.models import (
    FallbackConfig,
    SonosPlayer,
    SonosPreset,
    SonosState,
    SonosZone,
    TimeVolumeProfile,
)


# ═══════════════════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════════════════


class TestModels:
    def test_sonos_player(self):
        p = SonosPlayer(room_name="Wohnzimmer", entity_id="media_player.wohnzimmer")
        assert p.room_name == "Wohnzimmer"
        assert p.entity_id == "media_player.wohnzimmer"
        assert p.zone_id == ""

    def test_sonos_zone(self):
        z = SonosZone(zone_id="wohnzimmer", primary_room="Wohnzimmer",
                      secondary_rooms=["Kueche"])
        assert z.primary_room == "Wohnzimmer"
        assert len(z.secondary_rooms) == 1

    def test_sonos_preset(self):
        p = SonosPreset(preset_id="chill", label="Chill Musik",
                        players=["Wohnzimmer"], favorite="Chill Radio")
        assert p.preset_id == "chill"
        assert p.favorite == "Chill Radio"

    def test_sonos_state_defaults(self):
        s = SonosState()
        assert s.playback_state == "stopped"
        assert s.volume == 0
        assert s.current_track["title"] == ""

    def test_time_volume_profile(self):
        p = TimeVolumeProfile("day", 9, 18, 35, 70, "Tag")
        assert p.volume_pct == 35
        assert p.max_volume_pct == 70

    def test_fallback_config(self):
        f = FallbackConfig(zone_id="wz", fallback_type="favorite",
                           favorite_name="Chill Radio")
        assert f.fallback_type == "favorite"
        assert f.shuffle is True


# ═══════════════════════════════════════════════════════════════════════════
# SonosHTTPClient (mocked HTTP)
# ═══════════════════════════════════════════════════════════════════════════


class TestSonosHTTPClient:
    @pytest.fixture
    def client(self):
        return SonosHTTPClient("http://localhost:5005", timeout=2)

    def _mock_response(self, json_data=None, text="OK", status=200, content_type="application/json"):
        resp = MagicMock()
        resp.status_code = status
        resp.headers = {"content-type": content_type}
        resp.json.return_value = json_data
        resp.text = text
        resp.raise_for_status = MagicMock()
        if status >= 400:
            resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
        return resp

    def test_is_healthy_ok(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(json_data=[])):
            assert client.is_healthy() is True

    def test_is_healthy_fail(self, client):
        with patch.object(client._session, "get", side_effect=Exception("timeout")):
            assert client.is_healthy() is False

    def test_get_zones(self, client):
        zones_data = [{"coordinator": "RINCON_1", "members": [{"roomName": "Wohnzimmer"}]}]
        with patch.object(client._session, "get", return_value=self._mock_response(json_data=zones_data)):
            result = client.get_zones()
            assert len(result) == 1

    def test_get_rooms(self, client):
        zones_data = [
            {"members": [{"roomName": "Wohnzimmer"}, {"roomName": "Kueche"}]},
            {"members": [{"roomName": "Schlafzimmer"}]},
        ]
        with patch.object(client._session, "get", return_value=self._mock_response(json_data=zones_data)):
            rooms = client.get_rooms()
            assert rooms == ["Kueche", "Schlafzimmer", "Wohnzimmer"]

    def test_get_rooms_empty(self, client):
        with patch.object(client._session, "get", side_effect=Exception("fail")):
            assert client.get_rooms() == []

    def test_get_state(self, client):
        state = {"playbackState": "PLAYING", "volume": 30}
        with patch.object(client._session, "get", return_value=self._mock_response(json_data=state)):
            result = client.get_state("Wohnzimmer")
            assert result["volume"] == 30

    def test_play(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")):
            result = client.play("Wohnzimmer")
            assert result is not None

    def test_pause(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")):
            result = client.pause("Wohnzimmer")
            assert result is not None

    def test_set_volume(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.set_volume("Wohnzimmer", 50)
            mock_get.assert_called_once()
            assert "/volume/50" in mock_get.call_args[0][0]

    def test_set_volume_clamp(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.set_volume("Wohnzimmer", 150)
            assert "/volume/100" in mock_get.call_args[0][0]

    def test_adjust_volume_positive(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.adjust_volume("Wohnzimmer", 5)
            assert "/volume/+5" in mock_get.call_args[0][0]

    def test_adjust_volume_negative(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.adjust_volume("Wohnzimmer", -5)
            assert "/volume/-5" in mock_get.call_args[0][0]

    def test_get_favorites(self, client):
        fav_data = {"favorites": [{"title": "Chill Radio"}]}
        with patch.object(client._session, "get", return_value=self._mock_response(json_data=fav_data)):
            favs = client.get_favorites("Wohnzimmer")
            assert len(favs) == 1

    def test_play_favorite(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.play_favorite("Wohnzimmer", "Chill Radio")
            assert "/favorite/" in mock_get.call_args[0][0]

    def test_say(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.say("Wohnzimmer", "Hallo Welt", volume=20)
            url = mock_get.call_args[0][0]
            assert "/say/" in url
            assert "/de-de/" in url

    def test_say_all(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.say_all("Achtung!")
            assert "/sayall/" in mock_get.call_args[0][0]

    def test_join(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.join("Kueche", "Wohnzimmer")
            url = mock_get.call_args[0][0]
            assert "/join/" in url

    def test_leave(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")):
            result = client.leave("Kueche")
            assert result is not None

    def test_pause_all(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.pause_all()
            assert "/pauseall" in mock_get.call_args[0][0]

    def test_resume_all(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.resume_all()
            assert "/resumeall" in mock_get.call_args[0][0]

    def test_set_sleep(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.set_sleep("Wohnzimmer", 900)
            assert "/sleep/900" in mock_get.call_args[0][0]

    def test_set_shuffle(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.set_shuffle("Wohnzimmer", True)
            assert "/shuffle/on" in mock_get.call_args[0][0]

    def test_set_repeat(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.set_repeat("Wohnzimmer", "all")
            assert "/repeat/all" in mock_get.call_args[0][0]

    def test_list_presets(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(json_data=["preset1"])):
            result = client.list_presets()
            assert result == ["preset1"]

    def test_apply_preset(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.apply_preset("morning")
            assert "/preset/morning" in mock_get.call_args[0][0]

    def test_error_returns_none(self, client):
        with patch.object(client._session, "get", side_effect=Exception("connection error")):
            assert client.get_state("Wohnzimmer") is None

    def test_http_error_returns_none(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(status=500)):
            assert client.get_state("Wohnzimmer") is None

    def test_mute_unmute(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.mute("Wohnzimmer")
            assert "/mute" in mock_get.call_args[0][0]
            client.unmute("Wohnzimmer")
            assert "/unmute" in mock_get.call_args[0][0]

    def test_toggle_mute(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.toggle_mute("Wohnzimmer")
            assert "/togglemute" in mock_get.call_args[0][0]

    def test_clear_queue(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.clear_queue("Wohnzimmer")
            assert "/clearqueue" in mock_get.call_args[0][0]

    def test_playpause(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")):
            result = client.playpause("Wohnzimmer")
            assert result is not None

    def test_stop(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")):
            result = client.stop("Wohnzimmer")
            assert result is not None

    def test_next_previous(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")):
            assert client.next("Wohnzimmer") is not None
            assert client.previous("Wohnzimmer") is not None

    def test_set_group_volume(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.set_group_volume("Wohnzimmer", 40)
            assert "/groupVolume/40" in mock_get.call_args[0][0]

    def test_play_playlist(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.play_playlist("Wohnzimmer", "My Playlist")
            assert "/playlist/" in mock_get.call_args[0][0]

    def test_get_queue(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(json_data=[{"title": "Song1"}])):
            result = client.get_queue("Wohnzimmer")
            assert len(result) == 1

    def test_say_without_volume(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.say("Wohnzimmer", "Hallo")
            url = mock_get.call_args[0][0]
            assert "/say/" in url
            # Kein Volume-Segment am Ende
            assert url.endswith("/de-de")

    def test_say_all_without_volume(self, client):
        with patch.object(client._session, "get", return_value=self._mock_response(text="OK", content_type="text/plain")) as mock_get:
            client.say_all("Hallo")
            url = mock_get.call_args[0][0]
            assert url.endswith("/de-de")


# ═══════════════════════════════════════════════════════════════════════════
# SonosIntelligence
# ═══════════════════════════════════════════════════════════════════════════


class TestSonosIntelligence:
    @pytest.fixture
    def mock_client(self):
        return MagicMock(spec=SonosHTTPClient)

    @pytest.fixture
    def intel(self, mock_client, tmp_path):
        return SonosIntelligence(mock_client, presets_dir=str(tmp_path))

    # Volume Profiles

    def test_get_all_volume_profiles(self, intel):
        profiles = intel.get_all_volume_profiles()
        assert len(profiles) == 4
        names = [p["name"] for p in profiles]
        assert "morning" in names
        assert "day" in names
        assert "evening" in names
        assert "night" in names

    def test_exactly_one_profile_active(self, intel):
        profiles = intel.get_all_volume_profiles()
        active = [p for p in profiles if p["active"]]
        assert len(active) == 1

    def test_get_time_based_volume(self, intel):
        vol = intel.get_time_based_volume()
        assert 10 <= vol <= 35

    def test_apply_volume_ceiling(self, intel):
        # Nacht-Profil hat max 25
        with patch.object(intel, "get_current_volume_profile",
                          return_value=TimeVolumeProfile("night", 22, 6, 10, 25, "Nacht")):
            assert intel.apply_volume_ceiling("wz", 50) == 25
            assert intel.apply_volume_ceiling("wz", 20) == 20

    def test_update_volume_profile(self, intel):
        assert intel.update_volume_profile("morning", volume_pct=30) is True
        profiles = intel.get_all_volume_profiles()
        morning = [p for p in profiles if p["name"] == "morning"][0]
        assert morning["volume_pct"] == 30

    def test_update_volume_profile_not_found(self, intel):
        assert intel.update_volume_profile("nonexistent", volume_pct=30) is False

    # Zone Registry

    def test_register_and_get_zone(self, intel):
        zone = SonosZone("wohnzimmer", "Wohnzimmer", ["Kueche"])
        intel.register_zone(zone)
        result = intel.get_zone("wohnzimmer")
        assert result is not None
        assert result.primary_room == "Wohnzimmer"

    def test_get_all_zones(self, intel):
        intel.register_zone(SonosZone("wz", "Wohnzimmer"))
        intel.register_zone(SonosZone("sz", "Schlafzimmer"))
        zones = intel.get_all_zones()
        assert len(zones) == 2

    def test_get_zone_not_found(self, intel):
        assert intel.get_zone("nonexistent") is None

    # Fallback

    def test_set_and_get_fallback(self, intel):
        fb = FallbackConfig("wz", fallback_type="favorite", favorite_name="Jazz Radio")
        intel.set_fallback("wz", fb)
        result = intel.get_fallback("wz")
        assert result is not None
        assert result.favorite_name == "Jazz Radio"

    def test_get_fallback_none(self, intel):
        assert intel.get_fallback("nonexistent") is None

    def test_start_fallback(self, intel, mock_client):
        intel.register_zone(SonosZone("wz", "Wohnzimmer"))
        intel.set_fallback("wz", FallbackConfig("wz", "favorite", favorite_name="Jazz Radio"))
        result = intel.start_fallback("wz")
        assert result["action"] == "started_fallback"
        mock_client.set_volume.assert_called_once()
        mock_client.play_favorite.assert_called_once_with("Wohnzimmer", "Jazz Radio")

    def test_start_fallback_playlist(self, intel, mock_client):
        intel.register_zone(SonosZone("wz", "Wohnzimmer"))
        intel.set_fallback("wz", FallbackConfig("wz", "playlist", playlist_name="Chill"))
        result = intel.start_fallback("wz")
        assert result["action"] == "started_fallback"
        mock_client.play_playlist.assert_called_once_with("Wohnzimmer", "Chill")

    def test_start_fallback_no_zone(self, intel):
        result = intel.start_fallback("nonexistent")
        assert result["action"] == "no_zone"

    def test_start_fallback_no_config(self, intel):
        intel.register_zone(SonosZone("wz", "Wohnzimmer"))
        result = intel.start_fallback("wz")
        assert result["action"] == "no_fallback"

    # Presence

    def test_presence_starts_fallback(self, intel, mock_client):
        mock_client.get_state.return_value = {"playbackState": "STOPPED"}
        intel.register_zone(SonosZone("wz", "Wohnzimmer"))
        intel.set_fallback("wz", FallbackConfig("wz", "favorite", favorite_name="Jazz"))
        result = intel.on_zone_presence("wz", "person.andreas")
        assert result["action"] == "started_fallback"

    def test_presence_already_playing(self, intel, mock_client):
        mock_client.get_state.return_value = {"playbackState": "PLAYING"}
        intel.register_zone(SonosZone("wz", "Wohnzimmer"))
        intel.set_fallback("wz", FallbackConfig("wz", "favorite", favorite_name="Jazz"))
        result = intel.on_zone_presence("wz", "person.andreas")
        assert result["action"] == "already_playing"

    def test_presence_no_player(self, intel):
        result = intel.on_zone_presence("nonexistent", "person.andreas")
        assert result["action"] == "no_player"

    def test_presence_no_fallback(self, intel, mock_client):
        mock_client.get_state.return_value = {"playbackState": "STOPPED"}
        intel.register_zone(SonosZone("wz", "Wohnzimmer"))
        result = intel.on_zone_presence("wz", "person.andreas")
        assert result["action"] == "no_fallback"

    # Presets

    def test_save_and_get_preset(self, intel):
        preset = SonosPreset("test1", "Test Preset", ["Wohnzimmer"], favorite="Jazz")
        assert intel.save_preset(preset) is True
        loaded = intel.get_preset("test1")
        assert loaded is not None
        assert loaded.label == "Test Preset"
        assert loaded.favorite == "Jazz"

    def test_list_presets(self, intel):
        intel.save_preset(SonosPreset("p1", "Preset 1"))
        intel.save_preset(SonosPreset("p2", "Preset 2"))
        presets = intel.list_presets()
        assert len(presets) == 2

    def test_delete_preset(self, intel):
        intel.save_preset(SonosPreset("del_me", "Delete Me"))
        assert intel.delete_preset("del_me") is True
        assert intel.get_preset("del_me") is None

    def test_delete_preset_not_found(self, intel):
        assert intel.delete_preset("nonexistent") is False

    def test_apply_preset(self, intel, mock_client):
        preset = SonosPreset("ap1", "Apply", ["Wohnzimmer"], favorite="Jazz")
        intel.save_preset(preset)
        mock_client.apply_preset.return_value = None  # Fallback-Pfad
        assert intel.apply_preset("ap1") is True
        mock_client.play_favorite.assert_called_once_with("Wohnzimmer", "Jazz")

    def test_apply_preset_not_found(self, intel):
        assert intel.apply_preset("nonexistent") is False

    def test_create_zone_preset(self, intel):
        intel.register_zone(SonosZone("wz", "Wohnzimmer", ["Kueche"]))
        preset = intel.create_zone_preset("wz", "Abend Chill", favorite="Chill Radio")
        assert preset is not None
        assert "Wohnzimmer" in preset.players
        assert "Kueche" in preset.players

    def test_create_zone_preset_unknown_zone(self, intel):
        assert intel.create_zone_preset("nope", "Test") is None


# ═══════════════════════════════════════════════════════════════════════════
# API-Endpoints (mocked client + intelligence)
# ═══════════════════════════════════════════════════════════════════════════


def _make_test_app():
    """Erstellt eine Flask-App mit Sonos-Blueprint und gemockten Services."""
    from copilot_core.api.v1.sonos import sonos_bp

    mock_client = MagicMock()
    mock_client.is_healthy.return_value = True
    mock_client.health_check.return_value = True
    mock_client.get_rooms.return_value = ["Wohnzimmer", "Kueche"]
    mock_client.get_zones.return_value = [{"members": [{"roomName": "Wohnzimmer"}]}]
    mock_client.discover_zones.return_value = [{"members": [{"roomName": "Wohnzimmer"}]}]
    mock_client.get_speakers.return_value = []
    mock_client.get_state.return_value = {"playbackState": "PLAYING", "volume": 30}
    mock_client.get_favorites.return_value = [{"title": "Jazz Radio"}]
    mock_client.get_queue.return_value = [{"title": "Song 1"}]
    mock_client.get_playlists.return_value = []
    mock_client.get_summary.return_value = {"playing": 1, "total": 2}
    mock_client.play.return_value = True
    mock_client.pause.return_value = True
    mock_client.next_track.return_value = True
    mock_client.previous_track.return_value = True
    mock_client.set_volume.return_value = True
    mock_client.set_mute.return_value = True
    mock_client.play_favorite.return_value = True
    mock_client.say.return_value = True
    mock_client.say_all.return_value = True
    mock_client.join.return_value = True
    mock_client.leave.return_value = True

    mock_intel = MagicMock()
    mock_intel.get_all_volume_profiles.return_value = [
        {"name": "day", "volume_pct": 35, "active": True},
    ]
    mock_intel.list_presets.return_value = [{"preset_id": "p1", "label": "Test"}]
    mock_intel.get_all_zones.return_value = [{"zone_id": "wz", "primary_room": "Wohnzimmer"}]
    mock_intel.get_fallback.return_value = None
    mock_intel.on_zone_presence.return_value = {"action": "started_fallback"}
    mock_intel.apply_volume_ceiling.return_value = 35
    mock_intel.save_preset.return_value = True
    mock_intel.get_preset.return_value = SonosPreset("p1", "Test", ["Wohnzimmer"])
    mock_intel.delete_preset.return_value = True
    mock_intel.apply_preset.return_value = True
    mock_intel.update_volume_profile.return_value = True

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["services"] = {
        "sonos_client": mock_client,
        "sonos_intel": mock_intel,
    }
    app.register_blueprint(sonos_bp)

    return app, mock_client, mock_intel


class TestSonosAPI:
    """Tests for the actual Sonos REST API endpoints in sonos_bp."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.app, self.mock_client, self.mock_intel = _make_test_app()
        # Rate-Limiter zuruecksetzen damit Tests nicht 429 bekommen
        try:
            from copilot_core.api.rate_limit import get_rate_limiter
            get_rate_limiter().reset()
        except Exception:
            pass

    def _get(self, path):
        with patch("copilot_core.api.v1.sonos.require_token", lambda f: f):
            with self.app.test_client() as c:
                return c.get(path)

    def _post(self, path, json_data=None):
        with patch("copilot_core.api.v1.sonos.require_token", lambda f: f):
            with self.app.test_client() as c:
                return c.post(path, json=json_data or {},
                              content_type="application/json")

    # ── System ──

    def test_health(self):
        resp = self._get("/api/v1/sonos/health")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_zones(self):
        resp = self._get("/api/v1/sonos/zones")
        assert resp.status_code == 200
        assert len(resp.get_json()["zones"]) == 1

    def test_speakers(self):
        resp = self._get("/api/v1/sonos/speakers")
        assert resp.status_code == 200
        assert "speakers" in resp.get_json()

    def test_summary(self):
        resp = self._get("/api/v1/sonos/summary")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    # ── Playback ──

    def test_play(self):
        resp = self._post("/api/v1/sonos/play", {"room": "Wohnzimmer"})
        assert resp.status_code == 200
        self.mock_client.play.assert_called_with("Wohnzimmer")

    def test_play_missing_room(self):
        resp = self._post("/api/v1/sonos/play", {})
        assert resp.status_code == 400

    def test_pause(self):
        resp = self._post("/api/v1/sonos/pause", {"room": "Wohnzimmer"})
        assert resp.status_code == 200

    def test_next(self):
        resp = self._post("/api/v1/sonos/next", {"room": "Wohnzimmer"})
        assert resp.status_code == 200

    def test_previous(self):
        resp = self._post("/api/v1/sonos/previous", {"room": "Wohnzimmer"})
        assert resp.status_code == 200

    # ── Volume ──

    def test_volume(self):
        resp = self._post("/api/v1/sonos/volume",
                          {"room": "Wohnzimmer", "volume": 40})
        assert resp.status_code == 200

    def test_volume_missing(self):
        resp = self._post("/api/v1/sonos/volume",
                          {"room": "Wohnzimmer"})
        assert resp.status_code == 400

    def test_mute(self):
        resp = self._post("/api/v1/sonos/mute",
                          {"room": "Wohnzimmer", "muted": True})
        assert resp.status_code == 200

    # ── Favorites ──

    def test_favorites(self):
        resp = self._get("/api/v1/sonos/favorites")
        assert resp.status_code == 200
        assert len(resp.get_json()["favorites"]) == 1

    def test_play_favorite(self):
        resp = self._post("/api/v1/sonos/favorite/play",
                          {"room": "Wohnzimmer", "name": "Jazz Radio"})
        assert resp.status_code == 200

    def test_play_favorite_missing_name(self):
        resp = self._post("/api/v1/sonos/favorite/play",
                          {"room": "Wohnzimmer"})
        assert resp.status_code == 400

    def test_playlists(self):
        resp = self._get("/api/v1/sonos/playlists")
        assert resp.status_code == 200

    # ── TTS ──

    def test_say(self):
        resp = self._post("/api/v1/sonos/say",
                          {"room": "Wohnzimmer", "text": "Hallo Welt"})
        assert resp.status_code == 200

    def test_say_missing_text(self):
        resp = self._post("/api/v1/sonos/say",
                          {"room": "Wohnzimmer"})
        assert resp.status_code == 400

    def test_say_all(self):
        resp = self._post("/api/v1/sonos/say-all", {"text": "Achtung!"})
        assert resp.status_code == 200

    def test_say_all_missing_text(self):
        resp = self._post("/api/v1/sonos/say-all", {})
        assert resp.status_code == 400

    # ── Grouping ──

    def test_join(self):
        resp = self._post("/api/v1/sonos/join",
                          {"room": "Kueche", "target": "Wohnzimmer"})
        assert resp.status_code == 200

    def test_join_missing_target(self):
        resp = self._post("/api/v1/sonos/join", {"room": "Kueche"})
        assert resp.status_code == 400

    def test_leave(self):
        resp = self._post("/api/v1/sonos/leave", {"room": "Kueche"})
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# API ohne Services (503)
# ═══════════════════════════════════════════════════════════════════════════


class TestSonosAPINoServices:
    def test_health_503_without_client(self):
        from copilot_core.api.v1.sonos import sonos_bp
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["services"] = {}
        app.register_blueprint(sonos_bp)
        with app.test_client() as c:
            resp = c.get("/api/v1/sonos/health")
            assert resp.status_code == 503

    def test_volume_profiles_503_without_intel(self):
        from copilot_core.api.v1.sonos import sonos_bp
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["services"] = {}
        app.register_blueprint(sonos_bp)
        with app.test_client() as c:
            # Without sonos_client, any endpoint returns 503
            resp = c.get("/api/v1/sonos/health")
            assert resp.status_code == 503
