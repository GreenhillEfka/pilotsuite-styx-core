"""Music/Media Analytics Contract Tests — Slice 49."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from copilot_core.media.analytics import (
    MusicUsageEntryV1,
    MusicUsageHistoryV1,
    MusicZonePatternEntryV1,
    MusicZonePatternsV1,
    MusicEffectivenessMetricsV1,
    MusicMediaType,
    MusicSource,
)
from copilot_core.media.analytics_store import MusicAnalyticsStore, get_music_analytics_store


class TestMusicUsageEntryV1:
    """Tests für MusicUsageEntryV1."""

    def test_entry_creation(self):
        """Entry-Erstellung mit allen Feldern."""
        now = datetime.now(timezone.utc).isoformat()
        entry = MusicUsageEntryV1(
            entry_id="entry_001",
            zone_id="living",
            zone_name="Wohnbereich",
            media_type="sonos_favorite",
            media_id="fav_jazz_001",
            media_name="Jazz Radio",
            player_id="sonos_wohnzimmer",
            source="auto_presence",
            volume=40,
            duration_seconds=1800,
            started_at=now,
            ended_at=None,
        )

        assert entry.entry_id == "entry_001"
        assert entry.zone_id == "living"
        assert entry.media_type == "sonos_favorite"
        assert entry.source == "auto_presence"
        assert entry.volume == 40


class TestMusicAnalyticsStore:
    """Tests für MusicAnalyticsStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Store mit temporärer DB."""
        db_path = tmp_path / "music_analytics.db"
        return MusicAnalyticsStore(db_path=str(db_path))

    def test_add_usage_entry(self, store):
        """Usage-Eintrag hinzufügen."""
        now = datetime.now(timezone.utc).isoformat()
        entry = MusicUsageEntryV1(
            entry_id="entry_001",
            zone_id="living",
            zone_name="Wohnbereich",
            media_type="sonos_favorite",
            media_id="fav_jazz_001",
            media_name="Jazz Radio",
            player_id="sonos_wohnzimmer",
            source="auto_presence",
            volume=40,
            duration_seconds=1800,
            started_at=now,
            ended_at=None,
        )

        store.add_usage_entry(entry)

        # Verify entry was added
        history = store.build_usage_history(zone_id="living")
        assert len(history.entries) == 1
        assert history.entries[0].entry_id == "entry_001"
        assert history.total_sessions == 1

    def test_build_usage_history(self, store):
        """Usage-Historie aufbauen."""
        now = datetime.now(timezone.utc)
        base_time = now - timedelta(hours=1)

        for i in range(5):
            entry = MusicUsageEntryV1(
                entry_id=f"entry_{i:03d}",
                zone_id="living",
                zone_name="Wohnbereich",
                media_type="sonos_favorite",
                media_id=f"fav_{i}",
                media_name=f"Favorite {i}",
                player_id="sonos_wohnzimmer",
                source="manual",
                volume=30 + i * 5,
                duration_seconds=600 + i * 100,
                started_at=(base_time + timedelta(minutes=i * 10)).isoformat(),
                ended_at=None,
            )
            store.add_usage_entry(entry)

        history = store.build_usage_history(zone_id="living")

        assert history.total_sessions == 5
        assert history.total_sonos_sessions == 5
        assert history.total_musikwolke_sessions == 0
        assert history.avg_duration_seconds is not None
        assert history.revision == 5

    def test_build_usage_history_with_filters(self, store):
        """Usage-Historie mit Filtern."""
        now = datetime.now(timezone.utc)

        # Add entries for different zones
        for zone in ["living", "kitchen", "bath"]:
            entry = MusicUsageEntryV1(
                entry_id=f"entry_{zone}",
                zone_id=zone,
                zone_name=zone.title(),
                media_type="musikwolke",
                media_id=f"mw_{zone}",
                media_name=f"Musikwolke {zone}",
                player_id=None,
                source="schedule",
                volume=35,
                duration_seconds=1200,
                started_at=now.isoformat(),
                ended_at=None,
            )
            store.add_usage_entry(entry)

        # Filter by zone
        living_history = store.build_usage_history(zone_id="living")
        assert living_history.total_sessions == 1
        assert living_history.entries[0].zone_id == "living"

        # Filter by media type
        musikwolke_history = store.build_usage_history(media_type="musikwolke")
        assert musikwolke_history.total_sessions == 3

    def test_build_zone_patterns(self, store):
        """Zone-Patterns aufbauen."""
        now = datetime.now(timezone.utc)

        # Add multiple entries for living zone
        for i in range(10):
            entry = MusicUsageEntryV1(
                entry_id=f"entry_living_{i}",
                zone_id="living",
                zone_name="Wohnbereich",
                media_type="sonos_favorite",
                media_id="fav_jazz",
                media_name="Jazz Radio",
                player_id="sonos_wohnzimmer",
                source="auto_presence",
                volume=40,
                duration_seconds=1800,
                started_at=now.isoformat(),
                ended_at=None,
            )
            store.add_usage_entry(entry)

        # Add entries for kitchen zone
        for i in range(3):
            entry = MusicUsageEntryV1(
                entry_id=f"entry_kitchen_{i}",
                zone_id="kitchen",
                zone_name="Küche",
                media_type="sonos_radio",
                media_id="fav_pop",
                media_name="Pop Radio",
                player_id="sonos_kuche",
                source="manual",
                volume=30,
                duration_seconds=900,
                started_at=now.isoformat(),
                ended_at=None,
            )
            store.add_usage_entry(entry)

        patterns = store.build_zone_patterns()

        assert patterns.total_zones == 2
        assert patterns.zones_with_music == 2

        living_pattern = next(p for p in patterns.patterns if p.zone_id == "living")
        assert living_pattern.total_sessions == 10
        assert living_pattern.most_used_media_type == "sonos_favorite"
        assert living_pattern.most_common_source == "auto_presence"
        assert living_pattern.avg_volume == 40.0

    def test_get_effectiveness_metrics(self, store):
        """Effectiveness-Metriken berechnen."""
        now = datetime.now(timezone.utc)

        # Add diverse sessions
        sources = ["auto_presence", "manual", "schedule", "voice"]
        for i, source in enumerate(sources):
            for j in range(3):
                entry = MusicUsageEntryV1(
                    entry_id=f"entry_{source}_{j}",
                    zone_id=f"zone_{i}",
                    zone_name=f"Zone {i}",
                    media_type="sonos_favorite",
                    media_id=f"fav_{i}_{j}",
                    media_name=f"Favorite {i}-{j}",
                    player_id=f"player_{i}",
                    source=source,
                    volume=35,
                    duration_seconds=1200,
                    started_at=now.isoformat(),
                    ended_at=None,
                )
                store.add_usage_entry(entry)

        metrics = store.get_effectiveness_metrics()

        assert metrics.total_sessions_analyzed == 12
        assert "auto_presence" in metrics.sessions_by_source
        assert metrics.auto_presence_acceptance_rate == 0.25  # 3/12
        assert 0.0 <= metrics.engagement_score <= 1.0
        assert 0.0 <= metrics.favorite_diversity_score <= 1.0

    def test_revision_tracking(self, store):
        """Revision-Tracking bei Änderungen."""
        now = datetime.now(timezone.utc)

        initial_revision = store._revision

        entry = MusicUsageEntryV1(
            entry_id="entry_001",
            zone_id="living",
            zone_name="Wohnbereich",
            media_type="sonos_favorite",
            media_id="fav_jazz",
            media_name="Jazz Radio",
            player_id="sonos_wohnzimmer",
            source="manual",
            volume=40,
            duration_seconds=1800,
            started_at=now.isoformat(),
            ended_at=None,
        )
        store.add_usage_entry(entry)

        assert store._revision == initial_revision + 1

    def test_build_summary(self, store):
        """Analytics Summary aufbauen."""
        now = datetime.now(timezone.utc)

        # Add some data
        for i in range(5):
            entry = MusicUsageEntryV1(
                entry_id=f"entry_{i}",
                zone_id="living",
                zone_name="Wohnbereich",
                media_type="sonos_favorite",
                media_id=f"fav_{i}",
                media_name=f"Favorite {i}",
                player_id="sonos_wohnzimmer",
                source="manual",
                volume=40,
                duration_seconds=1800,
                started_at=now.isoformat(),
                ended_at=None,
            )
            store.add_usage_entry(entry)

        summary = store.build_summary()

        assert summary.usage.total_sessions == 5
        assert summary.patterns.zones_with_music >= 1
        assert summary.effectiveness.total_sessions_analyzed == 5
        assert summary.summary_revision == summary.usage.revision


class TestMusicMediaType:
    """Tests für MusicMediaType Enum."""

    def test_media_types(self):
        """Alle Media-Typen verfügbar."""
        assert MusicMediaType.SONOS_FAVORITE == "sonos_favorite"
        assert MusicMediaType.SONOS_RADIO == "sonos_radio"
        assert MusicMediaType.SONOS_PLAYLIST == "sonos_playlist"
        assert MusicMediaType.MUSIKWOLKE == "musikwolke"
        assert MusicMediaType.CAMERA_SNAPSHOT == "camera_snapshot"
        assert MusicMediaType.CAMERA_RECORDING == "camera_recording"


class TestMusicSource:
    """Tests für MusicSource Enum."""

    def test_sources(self):
        """Alle Source-Typen verfügbar."""
        assert MusicSource.MANUAL == "manual"
        assert MusicSource.AUTO_PRESENCE == "auto_presence"
        assert MusicSource.SCHEDULE == "schedule"
        assert MusicSource.VOICE == "voice"
        assert MusicSource.PROPOSAL == "proposal"
        assert MusicSource.SCENE == "scene"
        assert MusicSource.ROUTINE == "routine"


class TestMusicAnalyticsStoreIntegration:
    """Integrationstests für MusicAnalyticsStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Store mit temporärer DB."""
        db_path = tmp_path / "music_analytics.db"
        return MusicAnalyticsStore(db_path=str(db_path))

    def test_full_workflow(self, store):
        """Kompletter Workflow: Add → History → Patterns → Metrics → Summary."""
        now = datetime.now(timezone.utc)

        # Add diverse sessions
        for zone in ["living", "kitchen", "bath"]:
            for source in ["manual", "auto_presence", "schedule"]:
                entry = MusicUsageEntryV1(
                    entry_id=f"entry_{zone}_{source}",
                    zone_id=zone,
                    zone_name=zone.title(),
                    media_type="sonos_favorite",
                    media_id=f"fav_{zone}",
                    media_name=f"Favorite {zone}",
                    player_id=f"sonos_{zone}",
                    source=source,
                    volume=35,
                    duration_seconds=1500,
                    started_at=now.isoformat(),
                    ended_at=None,
                )
                store.add_usage_entry(entry)

        # Build all read models
        history = store.build_usage_history()
        patterns = store.build_zone_patterns()
        metrics = store.get_effectiveness_metrics()
        summary = store.build_summary()

        # Verify consistency
        assert history.total_sessions == 9
        assert patterns.total_zones == 3
        assert metrics.total_sessions_analyzed == 9
        assert summary.usage.total_sessions == 9
        assert summary.patterns.zones_with_music == 3

    def test_time_range_filtering(self, store):
        """Zeitbereichs-Filterung."""
        now = datetime.now(timezone.utc)

        # Add entries at different times
        for days_ago in [1, 3, 7, 14, 30]:
            entry = MusicUsageEntryV1(
                entry_id=f"entry_{days_ago}d",
                zone_id="living",
                zone_name="Wohnbereich",
                media_type="sonos_favorite",
                media_id=f"fav_{days_ago}d",
                media_name=f"Favorite {days_ago}d",
                player_id="sonos_wohnzimmer",
                source="manual",
                volume=40,
                duration_seconds=1800,
                started_at=(now - timedelta(days=days_ago)).isoformat(),
                ended_at=None,
            )
            store.add_usage_entry(entry)

        # Last 7 days
        start_7d = (now - timedelta(days=7)).isoformat()
        history_7d = store.build_usage_history(time_range_start=start_7d)
        assert history_7d.total_sessions <= 3  # 1, 3, 7 days ago

        # Last 30 days
        start_30d = (now - timedelta(days=30)).isoformat()
        history_30d = store.build_usage_history(time_range_start=start_30d)
        assert history_30d.total_sessions == 5


class TestGetMusicAnalyticsStore:
    """Tests für Singleton-Getter."""

    def test_singleton_behavior(self):
        """Singleton verhält sich korrekt."""
        store1 = get_music_analytics_store()
        store2 = get_music_analytics_store()

        # Should be same instance (or at least same type)
        assert type(store1) == type(store2)
