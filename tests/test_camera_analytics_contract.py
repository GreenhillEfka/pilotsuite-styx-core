"""Camera Analytics Contract Tests — Slice 50."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from copilot_core.camera.analytics import (
    CameraUsageEntryV1,
    CameraUsageHistoryV1,
    CameraZonePatternEntryV1,
    CameraZonePatternsV1,
    CameraEffectivenessMetricsV1,
    CameraAnalyticsSummaryV1,
    CameraEventType,
    CameraSource,
)
from copilot_core.camera.analytics_store import (
    CameraAnalyticsStore,
    get_camera_analytics_store,
)


class TestCameraUsageEntryV1:
    """Tests für CameraUsageEntryV1."""

    def test_create_entry(self):
        """Entry kann erstellt werden."""
        entry = CameraUsageEntryV1(
            entry_id="cam-entry-001",
            zone_id="zone-wohnzimmer",
            zone_name="Wohnzimmer",
            camera_id="cam-001",
            camera_name="Front Door Cam",
            event_type="motion_detected",
            source="auto_motion",
            snapshot_taken=True,
            recording_started=True,
            recording_duration_seconds=30,
            thumbnail_generated=True,
            notification_sent=True,
            processed_at=datetime.now(timezone.utc).isoformat(),
        )

        assert entry.entry_id == "cam-entry-001"
        assert entry.zone_id == "zone-wohnzimmer"
        assert entry.event_type == "motion_detected"
        assert entry.snapshot_taken is True
        assert entry.recording_duration_seconds == 30

    def test_entry_without_recording(self):
        """Entry ohne Recording."""
        entry = CameraUsageEntryV1(
            entry_id="cam-entry-002",
            zone_id="zone-garten",
            zone_name="Garten",
            camera_id="cam-002",
            camera_name="Garden Cam",
            event_type="person_detected",
            source="auto_person",
            snapshot_taken=True,
            recording_started=False,
            recording_duration_seconds=None,
            thumbnail_generated=True,
            notification_sent=True,
            processed_at=datetime.now(timezone.utc).isoformat(),
        )

        assert entry.recording_started is False
        assert entry.recording_duration_seconds is None


class TestCameraAnalyticsStore:
    """Tests für CameraAnalyticsStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Store mit temporärer DB."""
        db_path = tmp_path / "camera_analytics.db"
        return CameraAnalyticsStore(db_path=str(db_path))

    def test_add_and_retrieve_entry(self, store):
        """Entry hinzufügen und abrufen."""
        entry = CameraUsageEntryV1(
            entry_id="test-entry-001",
            zone_id="zone-test",
            zone_name="Test Zone",
            camera_id="cam-test",
            camera_name="Test Cam",
            event_type="motion_detected",
            source="auto_motion",
            snapshot_taken=True,
            recording_started=True,
            recording_duration_seconds=45,
            thumbnail_generated=True,
            notification_sent=True,
            processed_at=datetime.now(timezone.utc).isoformat(),
        )

        store.add_usage_entry(entry)
        usage = store.build_usage_history(limit=10)

        assert usage.total_events == 1
        assert usage.total_snapshots == 1
        assert usage.total_recordings == 1
        assert usage.total_recording_duration_seconds == 45

    def test_usage_history_with_filters(self, store):
        """Usage-Historie mit Filtern."""
        now = datetime.now(timezone.utc)

        # Entries für verschiedene Zonen und Event-Typen
        entries = [
            CameraUsageEntryV1(
                entry_id=f"entry-{i}",
                zone_id="zone-a" if i % 2 == 0 else "zone-b",
                zone_name="Zone A" if i % 2 == 0 else "Zone B",
                camera_id="cam-001",
                camera_name="Cam 1",
                event_type="motion_detected" if i % 3 == 0 else "person_detected",
                source="auto_motion",
                snapshot_taken=True,
                recording_started=i % 2 == 0,
                recording_duration_seconds=30 if i % 2 == 0 else None,
                thumbnail_generated=True,
                notification_sent=True,
                processed_at=(now - timedelta(hours=i)).isoformat(),
            )
            for i in range(10)
        ]

        for entry in entries:
            store.add_usage_entry(entry)

        # Filter nach Zone
        usage_zone_a = store.build_usage_history(zone_id="zone-a", limit=10)
        assert usage_zone_a.total_events <= 5

        # Filter nach Event-Typ
        usage_motion = store.build_usage_history(event_type="motion_detected", limit=10)
        assert usage_motion.total_events <= 4

    def test_zone_patterns(self, store):
        """Zone-Patterns aufbauen."""
        now = datetime.now(timezone.utc)

        # Mehrere Entries für eine Zone
        for i in range(15):
            entry = CameraUsageEntryV1(
                entry_id=f"pattern-entry-{i}",
                zone_id="zone-pattern-test",
                zone_name="Pattern Test Zone",
                camera_id="cam-001",
                camera_name="Test Cam",
                event_type="motion_detected" if i % 2 == 0 else "person_detected",
                source="auto_motion",
                snapshot_taken=True,
                recording_started=True,
                recording_duration_seconds=30,
                thumbnail_generated=True,
                notification_sent=True,
                processed_at=(now - timedelta(hours=i)).isoformat(),
            )
            store.add_usage_entry(entry)

        patterns = store.build_zone_patterns()

        assert patterns.total_zones >= 1
        assert patterns.zones_with_camera_activity >= 1

        if patterns.patterns:
            pattern = patterns.patterns[0]
            assert pattern.total_events >= 15
            assert pattern.motion_events > 0 or pattern.person_events > 0
            assert pattern.snapshots_taken >= 15
            assert pattern.recordings_started >= 15

    def test_effectiveness_metrics(self, store):
        """Effectiveness-Metriken berechnen."""
        now = datetime.now(timezone.utc)

        # Verschiedene Event-Typen hinzufügen
        event_types = [
            "motion_detected", "person_detected", "vehicle_detected",
            "sound_detected", "doorbell_pressed"
        ]
        sources = ["auto_motion", "auto_person", "schedule", "manual"]

        for i in range(50):
            entry = CameraUsageEntryV1(
                entry_id=f"effect-entry-{i}",
                zone_id=f"zone-{i % 5}",
                zone_name=f"Zone {i % 5}",
                camera_id="cam-001",
                camera_name="Test Cam",
                event_type=event_types[i % len(event_types)],
                source=sources[i % len(sources)],
                snapshot_taken=i % 2 == 0,
                recording_started=i % 3 == 0,
                recording_duration_seconds=30 if i % 3 == 0 else None,
                thumbnail_generated=True,
                notification_sent=i % 4 != 0,
                processed_at=(now - timedelta(minutes=i)).isoformat(),
            )
            store.add_usage_entry(entry)

        metrics = store.get_effectiveness_metrics()

        assert metrics.total_events_analyzed == 50
        assert len(metrics.events_by_type) > 0
        assert len(metrics.events_by_source) > 0
        assert 0.0 <= metrics.notification_delivery_rate <= 1.0
        assert 0.0 <= metrics.snapshot_capture_rate <= 1.0
        assert 0.0 <= metrics.recording_trigger_rate <= 1.0
        assert 0.0 <= metrics.engagement_score <= 1.0

    def test_revision_tracking(self, store):
        """Revisionstracking bei Änderungen."""
        initial_revision = store._revision

        entry = CameraUsageEntryV1(
            entry_id="rev-entry-001",
            zone_id="zone-rev",
            zone_name="Rev Zone",
            camera_id="cam-001",
            camera_name="Rev Cam",
            event_type="motion_detected",
            source="auto_motion",
            snapshot_taken=True,
            recording_started=False,
            recording_duration_seconds=None,
            thumbnail_generated=True,
            notification_sent=True,
            processed_at=datetime.now(timezone.utc).isoformat(),
        )

        store.add_usage_entry(entry)

        assert store._revision > initial_revision

    def test_build_summary(self, store):
        """Zusammenfassung aller Analytics."""
        now = datetime.now(timezone.utc)

        # Einige Test-Einträge
        for i in range(5):
            entry = CameraUsageEntryV1(
                entry_id=f"summary-entry-{i}",
                zone_id="zone-summary",
                zone_name="Summary Zone",
                camera_id="cam-001",
                camera_name="Summary Cam",
                event_type="motion_detected",
                source="auto_motion",
                snapshot_taken=True,
                recording_started=True,
                recording_duration_seconds=30,
                thumbnail_generated=True,
                notification_sent=True,
                processed_at=(now - timedelta(hours=i)).isoformat(),
            )
            store.add_usage_entry(entry)

        summary = store.build_summary()

        assert summary.usage.total_events == 5
        assert summary.patterns.zones_with_camera_activity >= 1
        assert summary.effectiveness.total_events_analyzed == 5
        assert summary.summary_revision == store._revision


class TestCameraAnalyticsSingleton:
    """Tests für Singleton-Getter."""

    @patch("copilot_core.camera.analytics_store.CameraAnalyticsStore")
    def test_get_camera_analytics_store(self, mock_store_class):
        """Singleton-Getter liefert Store."""
        mock_instance = MagicMock()
        mock_store_class.return_value = mock_instance

        # Reset global variable
        import copilot_core.camera.analytics_store as mod
        mod._camera_analytics_store = None

        store1 = get_camera_analytics_store()
        store2 = get_camera_analytics_store()

        assert store1 is store2
        mock_store_class.assert_called_once()


class TestCameraEventTypes:
    """Tests für CameraEventType Enum."""

    def test_all_event_types(self):
        """Alle Event-Typen verfügbar."""
        expected_types = [
            "motion_detected",
            "person_detected",
            "vehicle_detected",
            "sound_detected",
            "snapshot_captured",
            "recording_started",
            "recording_stopped",
            "doorbell_pressed",
            "package_detected",
        ]

        for event_type in expected_types:
            assert event_type in [e.value for e in CameraEventType]


class TestCameraSources:
    """Tests für CameraSource Enum."""

    def test_all_sources(self):
        """Alle Source-Typen verfügbar."""
        expected_sources = [
            "manual",
            "auto_motion",
            "auto_person",
            "schedule",
            "voice",
            "proposal",
            "scene",
            "routine",
            "alert_trigger",
        ]

        for source in expected_sources:
            assert source in [s.value for s in CameraSource]


class TestCameraZonePatternsV1:
    """Tests für CameraZonePatternsV1."""

    def test_empty_patterns(self):
        """Leere Patterns."""
        patterns = CameraZonePatternsV1(
            patterns=[],
            total_zones=0,
            zones_with_camera_activity=0,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        assert patterns.total_zones == 0
        assert patterns.zones_with_camera_activity == 0
        assert len(patterns.patterns) == 0


class TestCameraEffectivenessMetricsV1:
    """Tests für CameraEffectivenessMetricsV1."""

    def test_metrics_with_zero_events(self):
        """Metriken mit null Events."""
        metrics = CameraEffectivenessMetricsV1(
            total_events_analyzed=0,
            events_by_type={},
            events_by_source={},
            motion_to_person_ratio=0.0,
            false_positive_rate=None,
            notification_delivery_rate=0.0,
            snapshot_capture_rate=0.0,
            recording_trigger_rate=0.0,
            avg_events_per_zone=0.0,
            zones_with_regular_activity=0,
            zones_with_rare_activity=0,
            peak_activity_time=None,
            engagement_score=0.0,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        assert metrics.total_events_analyzed == 0
        assert metrics.engagement_score == 0.0
        assert metrics.false_positive_rate is None
