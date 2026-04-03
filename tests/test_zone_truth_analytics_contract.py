"""Zone Truth Analytics Contract Tests — Slice 58."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest

from copilot_core.analytics.zone_truth_analytics import (
    ZoneAnalyticsStore,
    ZoneEffectivenessMetricsV1,
    ZonePatternEntryV1,
    ZonePatternsV1,
    ZoneSyncEventEntryV1,
    ZoneSyncEventType,
    ZoneSyncHistoryV1,
    ZoneSyncStatus,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create temporary database path."""
    return tmp_path / "zone_truth_analytics.db"


@pytest.fixture
def store(temp_db: Path) -> ZoneAnalyticsStore:
    """Create analytics store with temp database."""
    return ZoneAnalyticsStore(temp_db)


class TestZoneSyncEventEntryV1:
    """Test ZoneSyncEventEntryV1 dataclass."""

    def test_entry_creation(self) -> None:
        """Test basic entry creation."""
        entry = ZoneSyncEventEntryV1(
            event_id="evt-001",
            zone_id="zone-living",
            event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
            status=ZoneSyncStatus.SUCCESS,
            entity_count_before=10,
            entity_count_after=12,
            entities_changed=2,
            timestamp=time.time(),
            source="ha_topology_sync",
            revision=1,
        )

        assert entry.event_id == "evt-001"
        assert entry.zone_id == "zone-living"
        assert entry.event_type == ZoneSyncEventType.TOPOLOGY_SYNC
        assert entry.status == ZoneSyncStatus.SUCCESS
        assert entry.entities_changed == 2

    def test_entry_to_dict(self) -> None:
        """Test entry serialization."""
        entry = ZoneSyncEventEntryV1(
            event_id="evt-002",
            zone_id="zone-bedroom",
            event_type=ZoneSyncEventType.ENTITY_ADDED,
            status=ZoneSyncStatus.SUCCESS,
            entity_count_before=5,
            entity_count_after=6,
            entities_changed=1,
            timestamp=1234567890.0,
            source="test",
            revision=1,
            metadata={"test": "value"},
        )

        d = entry.to_dict()
        assert d["event_id"] == "evt-002"
        assert d["zone_id"] == "zone-bedroom"
        assert d["event_type"] == "entity_added"
        assert d["status"] == "success"
        assert d["metadata"] == {"test": "value"}


class TestZoneAnalyticsStore:
    """Test ZoneAnalyticsStore operations."""

    def test_add_sync_event(self, store: ZoneAnalyticsStore) -> None:
        """Test adding a sync event."""
        entry = store.add_sync_event(
            event_id="evt-001",
            zone_id="zone-living",
            event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
            status=ZoneSyncStatus.SUCCESS,
            entity_count_before=10,
            entity_count_after=12,
            entities_changed=2,
            source="test",
        )

        assert entry.event_id == "evt-001"
        assert entry.zone_id == "zone-living"
        assert entry.revision == 1

    def test_add_sync_event_auto_id(self, store: ZoneAnalyticsStore) -> None:
        """Test adding event with auto-generated ID."""
        entry = store.add_sync_event(
            event_id=str(uuid.uuid4()),
            zone_id=None,
            event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
            status=ZoneSyncStatus.SUCCESS,
            entity_count_before=0,
            entity_count_after=10,
            entities_changed=10,
        )

        assert entry.event_id is not None
        assert entry.revision == 1

    def test_revision_increments(self, store: ZoneAnalyticsStore) -> None:
        """Test revision increments with each event."""
        store.add_sync_event(
            event_id=str(uuid.uuid4()),
            zone_id="zone-1",
            event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
            status=ZoneSyncStatus.SUCCESS,
            entity_count_before=0,
            entity_count_after=5,
            entities_changed=5,
        )

        entry2 = store.add_sync_event(
            event_id=str(uuid.uuid4()),
            zone_id="zone-2",
            event_type=ZoneSyncEventType.ENTITY_ADDED,
            status=ZoneSyncStatus.SUCCESS,
            entity_count_before=5,
            entity_count_after=6,
            entities_changed=1,
        )

        assert entry2.revision == 2

    def test_build_sync_history(self, store: ZoneAnalyticsStore) -> None:
        """Test building sync history."""
        # Add multiple events
        for i in range(5):
            store.add_sync_event(
                event_id=f"evt-{i:03d}",
                zone_id="zone-living",
                event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
                status=ZoneSyncStatus.SUCCESS,
                entity_count_before=i * 5,
                entity_count_after=(i + 1) * 5,
                entities_changed=5,
            )

        history = store.build_sync_history(limit=10)

        assert isinstance(history, ZoneSyncHistoryV1)
        assert history.total_count == 5
        assert len(history.events) == 5
        assert history.revision == 5

    def test_build_sync_history_filtered_by_zone(self, store: ZoneAnalyticsStore) -> None:
        """Test filtering history by zone."""
        # Add events for different zones
        store.add_sync_event(
            event_id="evt-001",
            zone_id="zone-living",
            event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
            status=ZoneSyncStatus.SUCCESS,
            entity_count_before=0,
            entity_count_after=5,
            entities_changed=5,
        )
        store.add_sync_event(
            event_id="evt-002",
            zone_id="zone-bedroom",
            event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
            status=ZoneSyncStatus.SUCCESS,
            entity_count_before=0,
            entity_count_after=3,
            entities_changed=3,
        )
        store.add_sync_event(
            event_id="evt-003",
            zone_id="zone-living",
            event_type=ZoneSyncEventType.ENTITY_ADDED,
            status=ZoneSyncStatus.SUCCESS,
            entity_count_before=5,
            entity_count_after=6,
            entities_changed=1,
        )

        history = store.build_sync_history(zone_id="zone-living")

        assert history.total_count == 2
        assert all(e.zone_id == "zone-living" for e in history.events)

    def test_build_sync_history_with_revision_filter(self, store: ZoneAnalyticsStore) -> None:
        """Test filtering history by revision."""
        # Add multiple events
        for i in range(5):
            store.add_sync_event(
                event_id=f"evt-{i:03d}",
                zone_id="zone-living",
                event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
                status=ZoneSyncStatus.SUCCESS,
                entity_count_before=i,
                entity_count_after=i + 1,
                entities_changed=1,
            )

        # Get only events after revision 3
        history = store.build_sync_history(since_revision=3)

        assert history.total_count == 2
        assert all(e.revision > 3 for e in history.events)

    def test_build_zone_patterns(self, store: ZoneAnalyticsStore) -> None:
        """Test building zone patterns."""
        # Add events for multiple zones
        for i in range(10):
            store.add_sync_event(
                event_id=f"evt-living-{i:03d}",
                zone_id="zone-living",
                event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
                status=ZoneSyncStatus.SUCCESS,
                entity_count_before=i * 5,
                entity_count_after=(i + 1) * 5,
                entities_changed=5,
            )

        for i in range(5):
            store.add_sync_event(
                event_id=f"evt-bedroom-{i:03d}",
                zone_id="zone-bedroom",
                event_type=ZoneSyncEventType.ENTITY_ADDED,
                status=ZoneSyncStatus.SUCCESS,
                entity_count_before=i * 3,
                entity_count_after=(i + 1) * 3,
                entities_changed=3,
            )

        patterns = store.build_zone_patterns()

        assert isinstance(patterns, ZonePatternsV1)
        assert patterns.total_zones == 2
        assert len(patterns.patterns) == 2

        living_pattern = next(p for p in patterns.patterns if p.zone_id == "zone-living")
        assert living_pattern.total_syncs == 10
        assert living_pattern.successful_syncs == 10

    def test_build_zone_patterns_with_failures(self, store: ZoneAnalyticsStore) -> None:
        """Test patterns with mixed success/failure statuses."""
        # Add successful events
        for i in range(8):
            store.add_sync_event(
                event_id=f"evt-success-{i:03d}",
                zone_id="zone-kitchen",
                event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
                status=ZoneSyncStatus.SUCCESS,
                entity_count_before=0,
                entity_count_after=5,
                entities_changed=5,
            )

        # Add failed events
        for i in range(2):
            store.add_sync_event(
                event_id=f"evt-fail-{i:03d}",
                zone_id="zone-kitchen",
                event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
                status=ZoneSyncStatus.FAILED,
                entity_count_before=5,
                entity_count_after=5,
                entities_changed=0,
            )

        patterns = store.build_zone_patterns()

        kitchen = next(p for p in patterns.patterns if p.zone_id == "zone-kitchen")
        assert kitchen.total_syncs == 10
        assert kitchen.successful_syncs == 8
        assert kitchen.failed_syncs == 2

    def test_get_effectiveness_metrics(self, store: ZoneAnalyticsStore) -> None:
        """Test effectiveness metrics calculation."""
        # Add mixed events
        for i in range(70):
            store.add_sync_event(
                event_id=f"evt-success-{i:03d}",
                zone_id=f"zone-{i % 5}",
                event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
                status=ZoneSyncStatus.SUCCESS,
                entity_count_before=0,
                entity_count_after=10,
                entities_changed=2,
            )

        for i in range(20):
            store.add_sync_event(
                event_id=f"evt-conflict-{i:03d}",
                zone_id=f"zone-{i % 3}",
                event_type=ZoneSyncEventType.CONFLICT_RESOLVED,
                status=ZoneSyncStatus.CONFLICT,
                entity_count_before=10,
                entity_count_after=10,
                entities_changed=0,
            )

        for i in range(10):
            store.add_sync_event(
                event_id=f"evt-fail-{i:03d}",
                zone_id=f"zone-{i % 2}",
                event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
                status=ZoneSyncStatus.FAILED,
                entity_count_before=0,
                entity_count_after=0,
                entities_changed=0,
            )

        metrics = store.get_effectiveness_metrics()

        assert isinstance(metrics, ZoneEffectivenessMetricsV1)
        assert metrics.total_zones == 5  # zone-0 through zone-4
        assert metrics.zones_healthy == 5
        assert metrics.zones_with_conflicts == 3  # zone-0, zone-1, zone-2
        assert abs(metrics.overall_sync_success_rate - 0.70) < 0.01
        assert abs(metrics.overall_conflict_rate - 0.20) < 0.01

    def test_build_summary(self, store: ZoneAnalyticsStore) -> None:
        """Test building complete summary."""
        # Add some events
        for i in range(5):
            store.add_sync_event(
                event_id=f"evt-{i:03d}",
                zone_id="zone-living",
                event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
                status=ZoneSyncStatus.SUCCESS,
                entity_count_before=i * 5,
                entity_count_after=(i + 1) * 5,
                entities_changed=5,
            )

        summary = store.build_summary()

        assert summary.history is not None
        assert summary.patterns is not None
        assert summary.effectiveness is not None
        assert summary.revision == 5

    def test_build_summary_with_revision_filter(self, store: ZoneAnalyticsStore) -> None:
        """Test summary with revision filter."""
        # Add events
        for i in range(10):
            store.add_sync_event(
                event_id=f"evt-{i:03d}",
                zone_id="zone-living",
                event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
                status=ZoneSyncStatus.SUCCESS,
                entity_count_before=i,
                entity_count_after=i + 1,
                entities_changed=1,
            )

        # Get summary with only recent events
        summary = store.build_summary(since_revision=7)

        assert summary.history.total_count == 3
        assert summary.revision >= 10


class TestZoneSyncEventTypes:
    """Test ZoneSyncEventType enum."""

    def test_all_event_types(self) -> None:
        """Test all event type values."""
        assert ZoneSyncEventType.ZONE_CREATED.value == "zone_created"
        assert ZoneSyncEventType.ZONE_UPDATED.value == "zone_updated"
        assert ZoneSyncEventType.ZONE_DELETED.value == "zone_deleted"
        assert ZoneSyncEventType.ENTITY_ADDED.value == "entity_added"
        assert ZoneSyncEventType.ENTITY_REMOVED.value == "entity_removed"
        assert ZoneSyncEventType.ENTITY_UPDATED.value == "entity_updated"
        assert ZoneSyncEventType.TOPOLOGY_SYNC.value == "topology_sync"
        assert ZoneSyncEventType.CONFLICT_RESOLVED.value == "conflict_resolved"


class TestZoneSyncStatus:
    """Test ZoneSyncStatus enum."""

    def test_all_statuses(self) -> None:
        """Test all status values."""
        assert ZoneSyncStatus.SUCCESS.value == "success"
        assert ZoneSyncStatus.PARTIAL.value == "partial"
        assert ZoneSyncStatus.FAILED.value == "failed"
        assert ZoneSyncStatus.CONFLICT.value == "conflict"


class TestZonePatternsV1:
    """Test ZonePatternsV1 serialization."""

    def test_patterns_to_dict(self, store: ZoneAnalyticsStore) -> None:
        """Test patterns serialization."""
        store.add_sync_event(
            event_id="evt-001",
            zone_id="zone-test",
            event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
            status=ZoneSyncStatus.SUCCESS,
            entity_count_before=0,
            entity_count_after=5,
            entities_changed=5,
        )

        patterns = store.build_zone_patterns()
        d = patterns.to_dict()

        assert "patterns" in d
        assert "total_zones" in d
        assert "revision" in d
        assert "generated_at" in d
        assert len(d["patterns"]) == 1


class TestZoneEffectivenessMetricsV1:
    """Test ZoneEffectivenessMetricsV1."""

    def test_metrics_to_dict(self, store: ZoneAnalyticsStore) -> None:
        """Test metrics serialization."""
        store.add_sync_event(
            event_id="evt-001",
            zone_id="zone-test",
            event_type=ZoneSyncEventType.TOPOLOGY_SYNC,
            status=ZoneSyncStatus.SUCCESS,
            entity_count_before=0,
            entity_count_after=5,
            entities_changed=5,
        )

        metrics = store.get_effectiveness_metrics()
        d = metrics.to_dict()

        assert "overall_sync_success_rate" in d
        assert "overall_conflict_rate" in d
        assert "topology_stability_score" in d
        assert "entity_churn_rate" in d
        assert "zones_healthy" in d
        assert "zones_with_conflicts" in d
