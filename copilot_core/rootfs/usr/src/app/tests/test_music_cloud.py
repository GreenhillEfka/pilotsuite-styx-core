"""Tests for MusicCloudService -- Sonos zone-following via motion sensors."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from copilot_core.music_cloud import MusicCloudService, MusicCloudConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeMediaZoneManager:
    """Minimal stub of MediaZoneManager for testing."""

    def __init__(self):
        self._zone_players: dict[str, list[dict[str, Any]]] = {}
        self._zone_states: dict[str, dict[str, Any]] = {}
        self._join_calls: list[tuple[str, list[str]]] = []
        self._unjoin_calls: list[list[str]] = []
        self._favorites: dict[str, list[str]] = {}

    def assign_player(self, zone_id: str, entity_id: str, role: str = "primary") -> dict:
        self._zone_players.setdefault(zone_id, []).append(
            {"entity_id": entity_id, "role": role, "assigned_at": "now"}
        )
        return {"ok": True}

    def get_zone_players(self, zone_id: str) -> list[dict[str, Any]]:
        return list(self._zone_players.get(zone_id, []))

    def get_all_assignments(self) -> dict[str, list[dict[str, Any]]]:
        return dict(self._zone_players)

    def get_zone_media_state(self, zone_id: str) -> dict[str, Any]:
        return self._zone_states.get(zone_id, {"zone_id": zone_id, "state": "idle", "players": []})

    def _join_players(self, leader: str, members: list[str]) -> dict:
        clean = [m for m in members if m != leader]
        self._join_calls.append((leader, clean))
        return {"ok": True, "joined": clean, "leader": leader}

    def _unjoin_players(self, members: list[str]) -> dict:
        self._unjoin_calls.append(list(members))
        return {"ok": True, "ungrouped": members}

    def get_zone_favorites(self, zone_id: str) -> dict:
        return {"ok": True, "favorites": list(self._favorites.get(zone_id, []))}

    def set_zone_playing(self, zone_id: str, entity_id: str | None = None):
        """Test helper: mark zone as playing."""
        players = []
        for p in self._zone_players.get(zone_id, []):
            state = "playing" if (entity_id is None or p["entity_id"] == entity_id) else "idle"
            players.append({"entity_id": p["entity_id"], "state": state})
        self._zone_states[zone_id] = {
            "zone_id": zone_id,
            "state": "playing",
            "players": players,
        }


@pytest.fixture
def fake_mgr():
    """A FakeMediaZoneManager with two zones."""
    mgr = FakeMediaZoneManager()
    mgr.assign_player("living_room", "media_player.sonos_living", "primary")
    mgr.assign_player("living_room", "media_player.sonos_living_sub", "secondary")
    mgr.assign_player("kitchen", "media_player.sonos_kitchen", "primary")
    mgr.assign_player("bedroom", "media_player.sonos_bedroom", "primary")
    return mgr


@pytest.fixture
def svc(tmp_path, fake_mgr):
    """A MusicCloudService with a temp config path."""
    config_path = str(tmp_path / "music_cloud.json")
    return MusicCloudService(
        media_zone_manager=fake_mgr,
        config_path=config_path,
    )


# ===================================================================
# Config
# ===================================================================

class TestConfig:

    def test_default_config(self, svc):
        config = svc.get_config()
        assert config["enabled"] is True
        assert config["follow_timeout_sec"] == 300
        assert config["auto_follow_on_motion"] is True
        assert config["auto_ungroup_on_idle"] is True

    def test_update_config(self, svc):
        result = svc.update_config(
            enabled=False,
            follow_timeout_sec=120,
        )
        assert result["enabled"] is False
        assert result["follow_timeout_sec"] == 120

    def test_config_persists(self, tmp_path, fake_mgr):
        config_path = str(tmp_path / "music_cloud.json")
        svc1 = MusicCloudService(media_zone_manager=fake_mgr, config_path=config_path)
        svc1.update_config(follow_timeout_sec=180, enabled=False)

        # Create a new instance that loads from the same file
        svc2 = MusicCloudService(media_zone_manager=fake_mgr, config_path=config_path)
        config = svc2.get_config()
        assert config["follow_timeout_sec"] == 180
        assert config["enabled"] is False

    def test_config_timeout_bounds(self, svc):
        # Below minimum
        result = svc.update_config(follow_timeout_sec=5)
        assert result["follow_timeout_sec"] == 30

        # Above maximum
        result = svc.update_config(follow_timeout_sec=9999)
        assert result["follow_timeout_sec"] == 3600

    def test_set_follow_enabled(self, svc):
        result = svc.set_follow_enabled(False)
        assert result["enabled"] is False

        result = svc.set_follow_enabled(True)
        assert result["enabled"] is True


# ===================================================================
# Motion Detection -> Grouping
# ===================================================================

class TestMotionDetection:

    def test_motion_no_active_playback(self, svc, fake_mgr):
        """Motion detected but no zone is playing -> no action."""
        result = svc.on_motion_detected(zone_id="kitchen")
        assert result["ok"] is True
        assert result["action"] == "no_active_playback"
        assert len(fake_mgr._join_calls) == 0

    def test_motion_groups_to_playing_zone(self, svc, fake_mgr):
        """Motion in kitchen while living room is playing -> groups kitchen speakers."""
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        result = svc.on_motion_detected(zone_id="kitchen")
        assert result["ok"] is True
        assert result["action"] == "grouped"
        assert result["source_zone"] == "living_room"
        assert result["target_zone"] == "kitchen"
        assert "media_player.sonos_kitchen" in result["joined_entities"]
        assert len(fake_mgr._join_calls) == 1
        leader, members = fake_mgr._join_calls[0]
        assert leader == "media_player.sonos_living"
        assert "media_player.sonos_kitchen" in members

    def test_motion_already_grouped(self, svc, fake_mgr):
        """Second motion in kitchen when already grouped -> no-op."""
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        svc.on_motion_detected(zone_id="kitchen")
        result = svc.on_motion_detected(zone_id="kitchen")
        assert result["ok"] is True
        assert result["action"] == "already_grouped"

    def test_motion_disabled_globally(self, svc, fake_mgr):
        """Follow disabled globally -> no action on motion."""
        svc.update_config(enabled=False)
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        result = svc.on_motion_detected(zone_id="kitchen")
        assert result["ok"] is True
        assert result["action"] == "none"
        assert result["reason"] == "zone_follow_disabled"

    def test_motion_disabled_auto_follow(self, svc, fake_mgr):
        """auto_follow_on_motion disabled -> no action on motion."""
        svc.update_config(auto_follow_on_motion=False)
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        result = svc.on_motion_detected(zone_id="kitchen")
        assert result["ok"] is True
        assert result["action"] == "none"
        assert result["reason"] == "auto_follow_disabled"

    def test_motion_zone_override_disabled(self, svc, fake_mgr):
        """Zone-level override disables follow -> no action."""
        svc.update_config(zone_overrides={"kitchen": {"enabled": False}})
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        result = svc.on_motion_detected(zone_id="kitchen")
        assert result["ok"] is True
        assert result["action"] == "none"
        assert result["reason"] == "zone_follow_disabled"

    def test_motion_multiple_zones_group_to_same_source(self, svc, fake_mgr):
        """Motion in kitchen then bedroom, both group to living room."""
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        r1 = svc.on_motion_detected(zone_id="kitchen")
        r2 = svc.on_motion_detected(zone_id="bedroom")
        assert r1["action"] == "grouped"
        assert r2["action"] == "grouped"
        assert r1["group_id"] == r2["group_id"]
        assert len(fake_mgr._join_calls) == 2

    def test_motion_missing_zone_id(self, svc):
        """Missing zone_id returns error."""
        result = svc.on_motion_detected(zone_id="")
        assert result["ok"] is False

    def test_motion_records_person_id(self, svc, fake_mgr):
        """Motion with person_id is tracked in presence state."""
        fake_mgr.set_zone_playing("living_room")
        svc.on_motion_detected(zone_id="kitchen", person_id="person.alice")
        status = svc.get_zones_status()
        kitchen = status["zones"].get("kitchen", {})
        presence = kitchen.get("presence", {})
        assert presence.get("active") is True
        assert "person.alice" in presence.get("person_ids", [])


# ===================================================================
# Zone Idle -> Ungrouping
# ===================================================================

class TestZoneIdle:

    def test_idle_ungroups(self, svc, fake_mgr):
        """Zone idle -> ungrouped."""
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        svc.on_motion_detected(zone_id="kitchen")
        assert len(fake_mgr._join_calls) == 1

        result = svc.on_zone_idle(zone_id="kitchen")
        assert result["ok"] is True
        assert result["action"] == "ungrouped"
        assert "media_player.sonos_kitchen" in result["ungrouped_entities"]
        assert len(fake_mgr._unjoin_calls) == 1

    def test_idle_not_grouped(self, svc, fake_mgr):
        """Idle event for a zone that's not grouped -> no-op."""
        result = svc.on_zone_idle(zone_id="kitchen")
        assert result["ok"] is True
        assert result["action"] == "not_grouped"

    def test_idle_auto_ungroup_disabled(self, svc, fake_mgr):
        """auto_ungroup_on_idle disabled -> no action."""
        svc.update_config(auto_ungroup_on_idle=False)
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        svc.on_motion_detected(zone_id="kitchen")

        result = svc.on_zone_idle(zone_id="kitchen")
        assert result["ok"] is True
        assert result["action"] == "none"

    def test_idle_removes_group_when_last_zone(self, svc, fake_mgr):
        """When the last grouped zone goes idle, the group is removed."""
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        svc.on_motion_detected(zone_id="kitchen")
        svc.on_zone_idle(zone_id="kitchen")
        groups = svc.get_active_groups()
        assert len(groups) == 0

    def test_idle_keeps_group_when_other_zones_remain(self, svc, fake_mgr):
        """Ungrouping one zone keeps the group if others remain."""
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        svc.on_motion_detected(zone_id="kitchen")
        svc.on_motion_detected(zone_id="bedroom")
        svc.on_zone_idle(zone_id="kitchen")
        groups = svc.get_active_groups()
        assert len(groups) == 1
        assert "bedroom" in groups[0]["grouped_zones"]
        assert "kitchen" not in groups[0]["grouped_zones"]


# ===================================================================
# Check Idle Zones (timer-based)
# ===================================================================

class TestCheckIdleZones:

    def test_check_idle_zones_times_out(self, svc, fake_mgr, monkeypatch):
        """Zone with expired motion timeout is ungrouped."""
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        svc.on_motion_detected(zone_id="kitchen")

        # Force the presence timestamp to the past
        svc._zone_presence["kitchen"].last_motion_ts = 0.0

        actions = svc.check_idle_zones()
        assert len(actions) == 1
        assert actions[0]["action"] == "ungrouped"

    def test_check_idle_zones_respects_timeout(self, svc, fake_mgr):
        """Zone with recent motion is not timed out."""
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        svc.on_motion_detected(zone_id="kitchen")

        actions = svc.check_idle_zones()
        assert len(actions) == 0

    def test_check_idle_zones_zone_override_timeout(self, svc, fake_mgr):
        """Zone override timeout is respected."""
        svc.update_config(
            follow_timeout_sec=300,
            zone_overrides={"kitchen": {"timeout": 30}},
        )
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        svc.on_motion_detected(zone_id="kitchen")

        # Set last motion to 35 seconds ago (past the 30s override, but within 300s global)
        import time
        svc._zone_presence["kitchen"].last_motion_ts = time.time() - 35

        actions = svc.check_idle_zones()
        assert len(actions) == 1


# ===================================================================
# Manual Group / Ungroup
# ===================================================================

class TestManualGroupUngroup:

    def test_manual_group(self, svc, fake_mgr):
        """Manual group groups target zones."""
        result = svc.manual_group(
            source_zone="living_room",
            target_zones=["kitchen", "bedroom"],
        )
        assert result["ok"] is True
        assert result["coordinator"] == "media_player.sonos_living"
        assert len(result["results"]) == 2
        assert len(fake_mgr._join_calls) == 2

    def test_manual_group_with_coordinator(self, svc, fake_mgr):
        """Manual group with explicit coordinator."""
        result = svc.manual_group(
            source_zone="living_room",
            target_zones=["kitchen"],
            coordinator_entity="media_player.sonos_living_sub",
        )
        assert result["ok"] is True
        assert result["coordinator"] == "media_player.sonos_living_sub"

    def test_manual_group_missing_source(self, svc):
        """Missing source_zone returns error."""
        result = svc.manual_group(source_zone="", target_zones=["kitchen"])
        assert result["ok"] is False

    def test_manual_group_missing_targets(self, svc):
        """Missing target_zones returns error."""
        result = svc.manual_group(source_zone="living_room", target_zones=[])
        assert result["ok"] is False

    def test_manual_ungroup(self, svc, fake_mgr):
        """Manual ungroup ungroups specified zones."""
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        svc.on_motion_detected(zone_id="kitchen")

        result = svc.manual_ungroup(zone_ids=["kitchen"])
        assert result["ok"] is True
        assert len(result["results"]) == 1
        assert result["results"][0]["action"] == "ungrouped"

    def test_manual_ungroup_empty(self, svc):
        """Empty zone_ids returns error."""
        result = svc.manual_ungroup(zone_ids=[])
        assert result["ok"] is False


# ===================================================================
# Status and Zones Query
# ===================================================================

class TestStatusQuery:

    def test_get_zones_status(self, svc, fake_mgr):
        """get_zones_status returns all zones with assignments."""
        status = svc.get_zones_status()
        assert status["ok"] is True
        assert "living_room" in status["zones"]
        assert "kitchen" in status["zones"]
        assert "bedroom" in status["zones"]

    def test_get_zones_status_with_presence(self, svc, fake_mgr):
        """Zones with recent motion show presence info."""
        fake_mgr.set_zone_playing("living_room")
        svc.on_motion_detected(zone_id="kitchen", person_id="person.bob")
        status = svc.get_zones_status()
        kitchen = status["zones"]["kitchen"]
        assert kitchen["presence"]["active"] is True
        assert "person.bob" in kitchen["presence"]["person_ids"]

    def test_get_playback_status(self, svc, fake_mgr):
        """get_playback_status returns per-zone states."""
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        result = svc.get_playback_status()
        assert result["ok"] is True
        assert "living_room" in result["zone_states"]
        assert result["follow_enabled"] is True

    def test_get_active_groups_empty(self, svc):
        """No active groups when nothing is grouped."""
        groups = svc.get_active_groups()
        assert len(groups) == 0

    def test_get_active_groups_after_grouping(self, svc, fake_mgr):
        """Active groups after motion-based grouping."""
        fake_mgr.set_zone_playing("living_room", "media_player.sonos_living")
        svc.on_motion_detected(zone_id="kitchen")
        groups = svc.get_active_groups()
        assert len(groups) == 1
        assert groups[0]["source_zone"] == "living_room"
        assert "kitchen" in groups[0]["grouped_zones"]


# ===================================================================
# Favorites
# ===================================================================

class TestFavorites:

    def test_get_zone_favorites_empty(self, svc, fake_mgr):
        """Empty favorites for a zone."""
        result = svc.get_zone_favorites("living_room")
        assert result["ok"] is True
        assert result["favorites"] == []

    def test_set_zone_favorites(self, svc, fake_mgr):
        """Set and get zone favorites."""
        svc.set_zone_favorites("living_room", ["Jazz Mix", "Chill Lounge"])
        result = svc.get_zone_favorites("living_room")
        assert result["ok"] is True
        assert result["favorites"] == ["Jazz Mix", "Chill Lounge"]
        assert result["local_count"] == 2

    def test_favorites_merge_with_ha(self, svc, fake_mgr):
        """Local favorites merged with HA favorites, deduplicated."""
        fake_mgr._favorites["living_room"] = ["Jazz Mix", "News Radio"]
        svc.set_zone_favorites("living_room", ["Jazz Mix", "Focus Beats"])
        result = svc.get_zone_favorites("living_room")
        # Local first, then HA, deduplicated
        assert result["favorites"] == ["Jazz Mix", "Focus Beats", "News Radio"]

    def test_favorites_persist(self, tmp_path, fake_mgr):
        """Favorites persist across service restarts."""
        config_path = str(tmp_path / "music_cloud.json")
        svc1 = MusicCloudService(media_zone_manager=fake_mgr, config_path=config_path)
        svc1.set_zone_favorites("kitchen", ["Morning Coffee"])

        svc2 = MusicCloudService(media_zone_manager=fake_mgr, config_path=config_path)
        result = svc2.get_zone_favorites("kitchen")
        assert "Morning Coffee" in result["favorites"]

    def test_get_all_favorites(self, svc, fake_mgr):
        """Get favorites for all zones."""
        svc.set_zone_favorites("living_room", ["Jazz"])
        svc.set_zone_favorites("bedroom", ["Sleep Sounds"])
        result = svc.get_all_favorites()
        assert result["ok"] is True
        assert "living_room" in result["zones"]
        assert "bedroom" in result["zones"]

    def test_set_favorites_strips_whitespace(self, svc, fake_mgr):
        """Whitespace in favorite names is stripped."""
        svc.set_zone_favorites("kitchen", ["  Jazz Mix  ", "", "  "])
        result = svc.get_zone_favorites("kitchen")
        assert result["favorites"] == ["Jazz Mix"]


# ===================================================================
# Event Log
# ===================================================================

class TestEventLog:

    def test_event_log_records_motion(self, svc, fake_mgr):
        """Motion events are recorded in the event log."""
        fake_mgr.set_zone_playing("living_room")
        svc.on_motion_detected(zone_id="kitchen")
        events = svc.get_event_log()
        assert len(events) >= 1
        # Most recent first
        assert events[0]["event_type"] in ("zone_grouped", "motion_detected")

    def test_event_log_limit(self, svc, fake_mgr):
        """Event log respects limit parameter."""
        for i in range(10):
            svc.on_motion_detected(zone_id=f"zone_{i}")
        events = svc.get_event_log(limit=3)
        assert len(events) == 3

    def test_event_log_records_idle(self, svc, fake_mgr):
        """Idle events are recorded in the event log."""
        svc.on_zone_idle(zone_id="kitchen")
        events = svc.get_event_log()
        assert any(e["event_type"] == "zone_idle" for e in events)


# ===================================================================
# No MediaZoneManager
# ===================================================================

class TestNoMediaManager:

    def test_service_works_without_manager(self, tmp_path):
        """Service initializes without a MediaZoneManager."""
        config_path = str(tmp_path / "music_cloud.json")
        svc = MusicCloudService(config_path=config_path)
        config = svc.get_config()
        assert config["enabled"] is True

    def test_motion_without_manager(self, tmp_path):
        """Motion detection gracefully fails without manager."""
        config_path = str(tmp_path / "music_cloud.json")
        svc = MusicCloudService(config_path=config_path)
        result = svc.on_motion_detected(zone_id="kitchen")
        assert result["ok"] is True
        assert result["action"] == "no_active_playback"

    def test_manual_group_without_manager(self, tmp_path):
        """Manual group fails gracefully without manager."""
        config_path = str(tmp_path / "music_cloud.json")
        svc = MusicCloudService(config_path=config_path)
        result = svc.manual_group(source_zone="living", target_zones=["kitchen"])
        assert result["ok"] is False


# ===================================================================
# Blueprint integration (light smoke test)
# ===================================================================

class TestBlueprint:

    @pytest.fixture
    def app(self, svc, fake_mgr):
        from flask import Flask
        from copilot_core.api.v1.music_cloud import media_cloud_bp, init_music_cloud_api

        app = Flask(__name__)
        app.config["TESTING"] = True
        init_music_cloud_api(svc, fake_mgr)
        app.register_blueprint(media_cloud_bp)
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def test_get_zones(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.get("/api/v1/media/cloud/zones")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "zones" in data

    def test_get_status(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.get("/api/v1/media/cloud/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_post_follow(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.post(
            "/api/v1/media/cloud/follow",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["config"]["enabled"] is False

    def test_post_motion(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.post(
            "/api/v1/media/cloud/motion",
            json={"zone_id": "kitchen"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_post_motion_missing_zone(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.post(
            "/api/v1/media/cloud/motion",
            json={},
        )
        assert resp.status_code == 400

    def test_get_config(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.get("/api/v1/media/cloud/config")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "config" in data

    def test_get_favorites(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.get("/api/v1/media/cloud/favorites")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_get_groups(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.get("/api/v1/media/cloud/groups")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "groups" in data

    def test_get_events(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.get("/api/v1/media/cloud/events")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "events" in data

    def test_post_group_manual(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.post(
            "/api/v1/media/cloud/group",
            json={
                "source_zone": "living_room",
                "target_zones": ["kitchen"],
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_post_ungroup_manual(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.post(
            "/api/v1/media/cloud/ungroup",
            json={"zone_ids": ["kitchen"]},
        )
        assert resp.status_code == 200

    def test_post_idle(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.post(
            "/api/v1/media/cloud/idle",
            json={"zone_id": "kitchen"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_assign_player(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.post(
            "/api/v1/media/cloud/zones/garage/assign",
            json={"entity_id": "media_player.garage_speaker"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["ok"] is True
        assert data["zone_id"] == "garage"

    def test_set_zone_favorites(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.post(
            "/api/v1/media/cloud/favorites/living_room",
            json={"favorites": ["Jazz", "Rock"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["favorites"] == ["Jazz", "Rock"]

    def test_update_config(self, client, monkeypatch):
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
        resp = client.post(
            "/api/v1/media/cloud/config",
            json={"follow_timeout_sec": 60},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["config"]["follow_timeout_sec"] == 60

    def test_requires_auth_when_enabled(self, client, monkeypatch):
        """Verify endpoints require auth when auth is required."""
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "true")
        monkeypatch.setenv("COPILOT_AUTH_TOKEN", "secret_token_123")
        resp = client.get("/api/v1/media/cloud/zones")
        assert resp.status_code == 401

        # With correct token
        resp = client.get(
            "/api/v1/media/cloud/zones",
            headers={"X-Auth-Token": "secret_token_123"},
        )
        assert resp.status_code == 200
