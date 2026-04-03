"""Action Closure Analytics Contract Tests — Slice 60."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest

from copilot_core.analytics.action_closure_analytics import (
    ActionClosureEventV1,
    ActionClosureHistoryV1,
    ClosureAnalyticsStore,
    ClosureEffectivenessMetricsV1,
    ClosureEventType,
    ClosurePatternEntryV1,
    ClosurePatternsV1,
    ClosureSource,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create temporary database path."""
    return tmp_path / "action_closure_analytics.db"


@pytest.fixture
def store(temp_db: Path) -> ClosureAnalyticsStore:
    """Create analytics store with temp database."""
    return ClosureAnalyticsStore(temp_db)


class TestActionClosureEventV1:
    """Test ActionClosureEventV1 dataclass."""

    def test_event_creation(self) -> None:
        """Test basic event creation."""
        event = ActionClosureEventV1(
            event_id="evt-001",
            closure_id="closure-001",
            zone_id="zone-living",
            module_id="module-light",
            event_type=ClosureEventType.ACCEPTED,
            source=ClosureSource.VOICE,
            timestamp=time.time(),
            revision=1,
        )

        assert event.event_id == "evt-001"
        assert event.closure_id == "closure-001"
        assert event.zone_id == "zone-living"
        assert event.event_type == ClosureEventType.ACCEPTED
        assert event.source == ClosureSource.VOICE

    def test_event_to_dict(self) -> None:
        """Test event serialization."""
        event = ActionClosureEventV1(
            event_id="evt-002",
            closure_id="closure-002",
            zone_id="zone-bedroom",
            module_id=None,
            event_type=ClosureEventType.CREATED,
            source=ClosureSource.PREDICTIVE,
            timestamp=1234567890.0,
            revision=1,
            metadata={"test": "value"},
        )

        d = event.to_dict()
        assert d["event_id"] == "evt-002"
        assert d["closure_id"] == "closure-002"
        assert d["zone_id"] == "zone-bedroom"
        assert d["event_type"] == "created"
        assert d["source"] == "predictive"
        assert d["metadata"] == {"test": "value"}


class TestClosureAnalyticsStore:
    """Test ClosureAnalyticsStore operations."""

    def test_add_closure_event(self, store: ClosureAnalyticsStore) -> None:
        """Test adding a closure event."""
        entry = store.add_closure_event(
            event_id="evt-001",
            closure_id="closure-001",
            zone_id="zone-living",
            module_id="module-light",
            event_type=ClosureEventType.CREATED,
            source=ClosureSource.VOICE,
        )

        assert entry.event_id == "evt-001"
        assert entry.closure_id == "closure-001"
        assert entry.revision == 1

    def test_revision_increments(self, store: ClosureAnalyticsStore) -> None:
        """Test revision increments with each event."""
        store.add_closure_event(
            event_id=str(uuid.uuid4()),
            closure_id="closure-001",
            zone_id="zone-1",
            module_id=None,
            event_type=ClosureEventType.CREATED,
            source=ClosureSource.VOICE,
        )

        entry2 = store.add_closure_event(
            event_id=str(uuid.uuid4()),
            closure_id="closure-002",
            zone_id="zone-2",
            module_id=None,
            event_type=ClosureEventType.ACCEPTED,
            source=ClosureSource.HABITUS,
        )

        assert entry2.revision == 2

    def test_build_closure_history(self, store: ClosureAnalyticsStore) -> None:
        """Test building closure history."""
        for i in range(5):
            store.add_closure_event(
                event_id=f"evt-{i:03d}",
                closure_id=f"closure-{i:03d}",
                zone_id="zone-living",
                module_id=None,
                event_type=ClosureEventType.CREATED,
                source=ClosureSource.VOICE,
            )

        history = store.build_closure_history(limit=10)

        assert isinstance(history, ActionClosureHistoryV1)
        assert history.total_count == 5
        assert len(history.events) == 5
        assert history.revision == 5

    def test_build_closure_history_filtered_by_closure(self, store: ClosureAnalyticsStore) -> None:
        """Test filtering history by closure."""
        store.add_closure_event(
            event_id="evt-001",
            closure_id="closure-001",
            zone_id="zone-living",
            module_id=None,
            event_type=ClosureEventType.CREATED,
            source=ClosureSource.VOICE,
        )
        store.add_closure_event(
            event_id="evt-002",
            closure_id="closure-001",
            zone_id="zone-living",
            module_id=None,
            event_type=ClosureEventType.ACCEPTED,
            source=ClosureSource.VOICE,
        )
        store.add_closure_event(
            event_id="evt-003",
            closure_id="closure-002",
            zone_id="zone-bedroom",
            module_id=None,
            event_type=ClosureEventType.CREATED,
            source=ClosureSource.HABITUS,
        )

        history = store.build_closure_history(closure_id="closure-001")

        assert history.total_count == 2
        assert all(e.closure_id == "closure-001" for e in history.events)

    def test_build_closure_history_with_revision_filter(self, store: ClosureAnalyticsStore) -> None:
        """Test filtering history by revision."""
        for i in range(5):
            store.add_closure_event(
                event_id=f"evt-{i:03d}",
                closure_id=f"closure-{i:03d}",
                zone_id="zone-living",
                module_id=None,
                event_type=ClosureEventType.CREATED,
                source=ClosureSource.VOICE,
            )

        history = store.build_closure_history(since_revision=3)

        assert history.total_count == 2
        assert all(e.revision > 3 for e in history.events)

    def test_build_closure_patterns(self, store: ClosureAnalyticsStore) -> None:
        """Test building closure patterns."""
        for i in range(10):
            store.add_closure_event(
                event_id=f"evt-living-{i:03d}",
                closure_id=f"closure-living-{i:03d}",
                zone_id="zone-living",
                module_id=None,
                event_type=ClosureEventType.CREATED,
                source=ClosureSource.VOICE,
            )

        for i in range(5):
            store.add_closure_event(
                event_id=f"evt-bedroom-{i:03d}",
                closure_id=f"closure-bedroom-{i:03d}",
                zone_id="zone-bedroom",
                module_id=None,
                event_type=ClosureEventType.CREATED,
                source=ClosureSource.HABITUS,
            )

        patterns = store.build_closure_patterns()

        assert isinstance(patterns, ClosurePatternsV1)
        assert patterns.total_entries == 2
        assert len(patterns.patterns) == 2

    def test_build_closure_patterns_with_mixed_events(self, store: ClosureAnalyticsStore) -> None:
        """Test patterns with mixed event types."""
        for i in range(8):
            store.add_closure_event(
                event_id=f"evt-created-{i:03d}",
                closure_id=f"closure-{i:03d}",
                zone_id="zone-kitchen",
                module_id=None,
                event_type=ClosureEventType.CREATED,
                source=ClosureSource.VOICE,
            )

        for i in range(6):
            store.add_closure_event(
                event_id=f"evt-completed-{i:03d}",
                closure_id=f"closure-{i:03d}",
                zone_id="zone-kitchen",
                module_id=None,
                event_type=ClosureEventType.EXECUTION_COMPLETED,
                source=ClosureSource.VOICE,
            )

        for i in range(2):
            store.add_closure_event(
                event_id=f"evt-failed-{i:03d}",
                closure_id=f"closure-{i+6:03d}",
                zone_id="zone-kitchen",
                module_id=None,
                event_type=ClosureEventType.EXECUTION_FAILED,
                source=ClosureSource.VOICE,
            )

        patterns = store.build_closure_patterns()

        kitchen = next(p for p in patterns.patterns if p.zone_id == "zone-kitchen")
        assert kitchen.total_closures == 8
        assert kitchen.completed_count == 6
        assert kitchen.failed_count == 2
        assert abs(kitchen.completion_rate - 0.75) < 0.01

    def test_get_effectiveness_metrics(self, store: ClosureAnalyticsStore) -> None:
        """Test effectiveness metrics calculation."""
        for i in range(70):
            store.add_closure_event(
                event_id=f"evt-created-{i:03d}",
                closure_id=f"closure-{i:03d}",
                zone_id=f"zone-{i % 5}",
                module_id=None,
                event_type=ClosureEventType.CREATED,
                source=ClosureSource.VOICE if i % 2 == 0 else ClosureSource.HABITUS,
            )

        for i in range(50):
            store.add_closure_event(
                event_id=f"evt-completed-{i:03d}",
                closure_id=f"closure-{i:03d}",
                zone_id=f"zone-{i % 5}",
                module_id=None,
                event_type=ClosureEventType.EXECUTION_COMPLETED,
                source=ClosureSource.VOICE if i % 2 == 0 else ClosureSource.HABITUS,
            )

        for i in range(10):
            store.add_closure_event(
                event_id=f"evt-failed-{i:03d}",
                closure_id=f"closure-{i:03d}",
                zone_id=f"zone-{i % 3}",
                module_id=None,
                event_type=ClosureEventType.EXECUTION_FAILED,
                source=ClosureSource.VOICE,
            )

        metrics = store.get_effectiveness_metrics()

        assert isinstance(metrics, ClosureEffectivenessMetricsV1)
        assert metrics.total_closures == 70
        assert metrics.zones_with_closures == 5
        assert abs(metrics.overall_completion_rate - (50 / 70)) < 0.01
        assert "voice" in metrics.closures_by_source
        assert "habitus" in metrics.closures_by_source

    def test_build_summary(self, store: ClosureAnalyticsStore) -> None:
        """Test building complete summary."""
        for i in range(5):
            store.add_closure_event(
                event_id=f"evt-{i:03d}",
                closure_id=f"closure-{i:03d}",
                zone_id="zone-living",
                module_id=None,
                event_type=ClosureEventType.CREATED,
                source=ClosureSource.VOICE,
            )

        summary = store.build_summary()

        assert summary.history is not None
        assert summary.patterns is not None
        assert summary.effectiveness is not None
        assert summary.revision == 5

    def test_build_summary_with_revision_filter(self, store: ClosureAnalyticsStore) -> None:
        """Test summary with revision filter."""
        for i in range(10):
            store.add_closure_event(
                event_id=f"evt-{i:03d}",
                closure_id=f"closure-{i:03d}",
                zone_id="zone-living",
                module_id=None,
                event_type=ClosureEventType.CREATED,
                source=ClosureSource.VOICE,
            )

        summary = store.build_summary(since_revision=7)

        assert summary.history.total_count == 3
        assert summary.revision >= 10


class TestClosureEventType:
    """Test ClosureEventType enum."""

    def test_all_event_types(self) -> None:
        """Test all event type values."""
        assert ClosureEventType.CREATED.value == "created"
        assert ClosureEventType.ACCEPTED.value == "accepted"
        assert ClosureEventType.REJECTED.value == "rejected"
        assert ClosureEventType.EXECUTION_STARTED.value == "execution_started"
        assert ClosureEventType.EXECUTION_COMPLETED.value == "execution_completed"
        assert ClosureEventType.EXECUTION_FAILED.value == "execution_failed"
        assert ClosureEventType.FEEDBACK_PROVIDED.value == "feedback_provided"
        assert ClosureEventType.SETTLED.value == "settled"


class TestClosureSource:
    """Test ClosureSource enum."""

    def test_all_sources(self) -> None:
        """Test all source values."""
        assert ClosureSource.VOICE.value == "voice"
        assert ClosureSource.PREDICTIVE.value == "predictive"
        assert ClosureSource.HABITUS.value == "habitus"
        assert ClosureSource.MULTI_ZONE.value == "multizone"
        assert ClosureSource.MANUAL.value == "manual"


class TestClosurePatternsV1:
    """Test ClosurePatternsV1 serialization."""

    def test_patterns_to_dict(self, store: ClosureAnalyticsStore) -> None:
        """Test patterns serialization."""
        store.add_closure_event(
            event_id="evt-001",
            closure_id="closure-001",
            zone_id="zone-test",
            module_id=None,
            event_type=ClosureEventType.CREATED,
            source=ClosureSource.VOICE,
        )

        patterns = store.build_closure_patterns()
        d = patterns.to_dict()

        assert "patterns" in d
        assert "total_entries" in d
        assert "revision" in d
        assert "generated_at" in d
        assert len(d["patterns"]) == 1


class TestClosureEffectivenessMetricsV1:
    """Test ClosureEffectivenessMetricsV1."""

    def test_metrics_to_dict(self, store: ClosureAnalyticsStore) -> None:
        """Test metrics serialization."""
        store.add_closure_event(
            event_id="evt-001",
            closure_id="closure-001",
            zone_id="zone-test",
            module_id=None,
            event_type=ClosureEventType.CREATED,
            source=ClosureSource.VOICE,
        )

        metrics = store.get_effectiveness_metrics()
        d = metrics.to_dict()

        assert "overall_completion_rate" in d
        assert "overall_failure_rate" in d
        assert "overall_rejection_rate" in d
        assert "closures_by_source" in d
        assert "completions_by_source" in d
        assert "zones_with_closures" in d
