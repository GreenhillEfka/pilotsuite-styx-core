"""Tests for Media Follow / Musikwolke engine (v6.7.0)."""

import pytest
from copilot_core.hub.media_follow import (
    MediaFollowEngine,
    MediaSource,
    PlaybackSession,
    ZoneMediaState,
    MediaTransfer,
    MediaDashboard,
)


@pytest.fixture
def engine():
    e = MediaFollowEngine()
    e.register_source("media_player.wohnzimmer_speaker", "Wohnzimmer Speaker", "wohnzimmer", "music")
    e.register_source("media_player.schlafzimmer_speaker", "Schlafzimmer Speaker", "schlafzimmer", "music")
    e.register_source("media_player.küche_radio", "Küche Radio", "küche", "radio")
    e.register_source("media_player.wohnzimmer_tv", "Wohnzimmer TV", "wohnzimmer", "tv")
    return e


# ── Source management ──────────────────────────────────────────────────────


class TestSourceManagement:
    def test_register_source(self, engine):
        sources = engine.get_sources()
        assert len(sources) == 4

    def test_register_source_details(self, engine):
        sources = engine.get_sources()
        wz = next(s for s in sources if s["entity_id"] == "media_player.wohnzimmer_speaker")
        assert wz["name"] == "Wohnzimmer Speaker"
        assert wz["zone_id"] == "wohnzimmer"
        assert wz["media_type"] == "music"

    def test_unregister_source(self, engine):
        result = engine.unregister_source("media_player.küche_radio")
        assert result is True
        sources = engine.get_sources()
        assert len(sources) == 3

    def test_unregister_nonexistent(self, engine):
        result = engine.unregister_source("nonexistent")
        assert result is False

    def test_unregister_removes_sessions(self, engine):
        engine.update_playback("media_player.küche_radio", "playing", "Song 1")
        assert len(engine.get_active_sessions()) == 1
        engine.unregister_source("media_player.küche_radio")
        assert len(engine.get_active_sessions()) == 0


# ── Playback tracking ─────────────────────────────────────────────────────


class TestPlaybackTracking:
    def test_start_playback(self, engine):
        session = engine.update_playback(
            "media_player.wohnzimmer_speaker", "playing",
            title="Bohemian Rhapsody", artist="Queen", album="A Night at the Opera",
        )
        assert session is not None
        assert session.title == "Bohemian Rhapsody"
        assert session.artist == "Queen"
        assert session.state == "playing"

    def test_update_playback_title(self, engine):
        engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song 1", "Artist 1")
        session = engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song 2", "Artist 2")
        assert session.title == "Song 2"
        assert session.artist == "Artist 2"
        # Should still be same session
        assert len(engine.get_active_sessions()) == 1

    def test_pause_playback(self, engine):
        engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song 1")
        session = engine.update_playback("media_player.wohnzimmer_speaker", "paused", "Song 1")
        assert session.state == "paused"
        assert len(engine.get_active_sessions()) == 1

    def test_stop_playback(self, engine):
        engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song 1")
        engine.update_playback("media_player.wohnzimmer_speaker", "idle")
        assert len(engine.get_active_sessions()) == 0

    def test_unknown_source(self, engine):
        result = engine.update_playback("unknown_entity", "playing", "Song")
        assert result is None

    def test_multiple_sessions(self, engine):
        engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Music")
        engine.update_playback("media_player.wohnzimmer_tv", "playing", "TV Show")
        engine.update_playback("media_player.küche_radio", "playing", "Radio")
        sessions = engine.get_active_sessions()
        assert len(sessions) == 3

    def test_volume_update(self, engine):
        engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song", volume_pct=75)
        sessions = engine.get_active_sessions()
        assert sessions[0]["volume_pct"] == 75


# ── Follow mode ────────────────────────────────────────────────────────────


class TestFollowMode:
    def test_enable_follow_zone(self, engine):
        engine.set_follow_zone("wohnzimmer", True)
        zm = engine.get_zone_media("wohnzimmer")
        assert zm.follow_enabled is True

    def test_disable_follow_zone(self, engine):
        engine.set_follow_zone("wohnzimmer", True)
        engine.set_follow_zone("wohnzimmer", False)
        zm = engine.get_zone_media("wohnzimmer")
        assert zm.follow_enabled is False

    def test_global_follow(self, engine):
        engine.set_global_follow(True)
        zm = engine.get_zone_media("wohnzimmer")
        assert zm.follow_enabled is True
        zm2 = engine.get_zone_media("schlafzimmer")
        assert zm2.follow_enabled is True

    def test_session_inherits_follow(self, engine):
        engine.set_follow_zone("wohnzimmer", True)
        session = engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song")
        assert session.follow_enabled is True

    def test_session_no_follow_by_default(self, engine):
        session = engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song")
        assert session.follow_enabled is False


# ── Transfer ───────────────────────────────────────────────────────────────


class TestTransfer:
    def test_transfer_playback(self, engine):
        session = engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song")
        transfer = engine.transfer_playback(session.session_id, "schlafzimmer")
        assert transfer is not None
        assert transfer.from_zone == "wohnzimmer"
        assert transfer.to_zone == "schlafzimmer"

    def test_transfer_updates_session_zone(self, engine):
        session = engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song")
        engine.transfer_playback(session.session_id, "schlafzimmer")
        sessions = engine.get_active_sessions()
        assert sessions[0]["zone_id"] == "schlafzimmer"

    def test_transfer_same_zone_noop(self, engine):
        session = engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song")
        transfer = engine.transfer_playback(session.session_id, "wohnzimmer")
        assert transfer is None

    def test_transfer_nonexistent_session(self, engine):
        transfer = engine.transfer_playback("nonexistent", "schlafzimmer")
        assert transfer is None

    def test_on_zone_enter_transfers_follow(self, engine):
        engine.set_follow_zone("wohnzimmer", True)
        engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song")
        transfers = engine.on_zone_enter("schlafzimmer")
        assert len(transfers) == 1
        assert transfers[0].to_zone == "schlafzimmer"

    def test_on_zone_enter_no_follow(self, engine):
        engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song")
        transfers = engine.on_zone_enter("schlafzimmer")
        assert len(transfers) == 0

    def test_on_zone_enter_global_follow(self, engine):
        engine.set_global_follow(True)
        engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song")
        transfers = engine.on_zone_enter("küche")
        assert len(transfers) == 1


# ── Zone media state ──────────────────────────────────────────────────────


class TestZoneMedia:
    def test_empty_zone(self, engine):
        zm = engine.get_zone_media("wohnzimmer")
        assert zm.active_sessions == 0
        assert zm.primary_session is None

    def test_zone_with_playback(self, engine):
        engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song 1", "Artist 1")
        zm = engine.get_zone_media("wohnzimmer")
        assert zm.active_sessions == 1
        assert zm.primary_session is not None
        assert zm.primary_session["title"] == "Song 1"

    def test_zone_sources_listed(self, engine):
        zm = engine.get_zone_media("wohnzimmer")
        assert len(zm.sources) == 2  # speaker + TV

    def test_zone_primary_is_playing(self, engine):
        engine.update_playback("media_player.wohnzimmer_speaker", "paused", "Paused Song")
        engine.update_playback("media_player.wohnzimmer_tv", "playing", "TV Show")
        zm = engine.get_zone_media("wohnzimmer")
        assert zm.primary_session["title"] == "TV Show"


# ── Dashboard ──────────────────────────────────────────────────────────────


class TestDashboard:
    def test_empty_dashboard(self, engine):
        db = engine.get_dashboard()
        assert db.total_sources == 4
        assert db.active_sessions == 0
        assert db.zones_with_playback == 0

    def test_dashboard_with_playback(self, engine):
        engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song")
        engine.update_playback("media_player.küche_radio", "playing", "Radio Stream")
        db = engine.get_dashboard()
        assert db.active_sessions == 2
        assert db.zones_with_playback == 2
        assert len(db.sessions) == 2

    def test_dashboard_zone_states(self, engine):
        engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song")
        db = engine.get_dashboard()
        wz = next(z for z in db.zone_states if z["zone_id"] == "wohnzimmer")
        assert wz["primary_title"] == "Song"
        assert wz["primary_state"] == "playing"

    def test_dashboard_transfers(self, engine):
        engine.set_global_follow(True)
        engine.update_playback("media_player.wohnzimmer_speaker", "playing", "Song")
        engine.on_zone_enter("schlafzimmer")
        db = engine.get_dashboard()
        assert len(db.recent_transfers) == 1

    def test_dashboard_follow_count(self, engine):
        engine.set_follow_zone("wohnzimmer", True)
        engine.set_follow_zone("schlafzimmer", True)
        db = engine.get_dashboard()
        assert db.follow_enabled_zones == 2
