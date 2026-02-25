"""Tests for MediaZoneManager Musikwolke + favorites/search helpers."""

from __future__ import annotations

from pathlib import Path

from copilot_core.media_zone_manager import MediaZoneManager


def _assign_players(mgr: MediaZoneManager, zone_id: str, entity_ids: list[str]) -> None:
    for entity_id in entity_ids:
        mgr.assign_player(zone_id=zone_id, entity_id=entity_id, role="primary")


def test_start_musikwolke_group_mode_tracks_leader(tmp_path, monkeypatch):
    mgr = MediaZoneManager(db_path=str(Path(tmp_path) / "media.db"))
    _assign_players(mgr, "zone:living", ["media_player.living_1", "media_player.living_2"])

    calls: list[tuple[str, str, dict]] = []

    def _fake_call(domain: str, service: str, data: dict, timeout: int = 10):  # noqa: ARG001
        calls.append((domain, service, data))
        return {"ok": True, "status": 200}

    monkeypatch.setattr(mgr, "_call_service", _fake_call)

    result = mgr.start_musikwolke(
        person_id="person.alice",
        source_zone="zone:living",
        mode="group",
        degroup_on_leave=True,
        leader_entity_id="media_player.living_1",
    )

    assert result["ok"] is True
    assert result["leader_entity_id"] == "media_player.living_1"
    assert any(service == "join" for _, service, _ in calls)

    sessions = mgr.get_musikwolke_sessions()
    assert len(sessions) == 1
    assert sessions[0]["mode"] == "group"
    assert sessions[0]["leader_entity_id"] == "media_player.living_1"


def test_update_musikwolke_degroups_previous_zone(tmp_path, monkeypatch):
    mgr = MediaZoneManager(db_path=str(Path(tmp_path) / "media.db"))
    _assign_players(mgr, "zone:living", ["media_player.living_1", "media_player.living_2"])
    _assign_players(mgr, "zone:kitchen", ["media_player.kitchen_1"])

    calls: list[tuple[str, str, dict]] = []

    def _fake_call(domain: str, service: str, data: dict, timeout: int = 10):  # noqa: ARG001
        calls.append((domain, service, data))
        return {"ok": True, "status": 200}

    monkeypatch.setattr(mgr, "_call_service", _fake_call)
    started = mgr.start_musikwolke(
        person_id="person.alice",
        source_zone="zone:living",
        mode="group",
        degroup_on_leave=True,
        leader_entity_id="media_player.living_1",
    )
    calls.clear()

    updated = mgr.update_musikwolke(started["session_id"], "zone:kitchen")
    assert updated["ok"] is True

    # Join new zone member to leader.
    assert any(service == "join" for _, service, _ in calls)
    # Leaving-zone member (non-leader) should be ungrouped.
    assert any(
        service == "unjoin" and "media_player.living_2" in str(data.get("entity_id"))
        for _, service, data in calls
    )


def test_get_zone_favorites_reads_source_list(tmp_path, monkeypatch):
    mgr = MediaZoneManager(db_path=str(Path(tmp_path) / "media.db"))
    _assign_players(mgr, "zone:living", ["media_player.living_1"])

    monkeypatch.setattr(
        mgr,
        "_get_entity_state",
        lambda entity_id: {  # noqa: ARG005
            "attributes": {
                "source_list": ["Jazz Mix", "News Radio"],
                "sonos_favorites": ["Jazz Mix", "Chill Lounge"],
            }
        },
    )

    result = mgr.get_zone_favorites("zone:living")
    assert result["ok"] is True
    assert result["favorites"] == ["Jazz Mix", "News Radio", "Chill Lounge"]


def test_search_and_play_uses_zone_leader(tmp_path, monkeypatch):
    mgr = MediaZoneManager(db_path=str(Path(tmp_path) / "media.db"))
    _assign_players(mgr, "zone:living", ["media_player.living_1", "media_player.living_2"])

    calls: list[tuple[str, str, dict]] = []

    def _fake_call(domain: str, service: str, data: dict, timeout: int = 10):  # noqa: ARG001
        calls.append((domain, service, data))
        return {"ok": True, "status": 200}

    monkeypatch.setattr(mgr, "_call_service", _fake_call)

    result = mgr.search_and_play("zone:living", "lofi focus")
    assert result["ok"] is True
    assert calls
    domain, service, payload = calls[0]
    assert domain == "media_player"
    assert service == "play_media"
    assert payload["entity_id"] == "media_player.living_1"
    assert payload["media_content_id"] == "lofi focus"
