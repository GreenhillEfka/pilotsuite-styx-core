"""Proposal Lifecycle Analytics Contract Tests — Slice 59."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest

from copilot_core.analytics.proposal_lifecycle_analytics import (
    ProposalAnalyticsStore,
    ProposalEffectivenessMetricsV1,
    ProposalLifecycleEventV1,
    ProposalLifecycleHistoryV1,
    ProposalEventType,
    ProposalPatternEntryV1,
    ProposalPatternsV1,
    ProposalSource,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create temporary database path."""
    return tmp_path / "proposal_lifecycle_analytics.db"


@pytest.fixture
def store(temp_db: Path) -> ProposalAnalyticsStore:
    """Create analytics store with temp database."""
    return ProposalAnalyticsStore(temp_db)


class TestProposalLifecycleEventV1:
    """Test ProposalLifecycleEventV1 dataclass."""

    def test_event_creation(self) -> None:
        """Test basic event creation."""
        event = ProposalLifecycleEventV1(
            event_id="evt-001",
            proposal_id="prop-001",
            zone_id="zone-living",
            module_id="module-light",
            event_type=ProposalEventType.ACCEPTED,
            source=ProposalSource.PREDICTIVE,
            timestamp=time.time(),
            revision=1,
        )

        assert event.event_id == "evt-001"
        assert event.proposal_id == "prop-001"
        assert event.zone_id == "zone-living"
        assert event.event_type == ProposalEventType.ACCEPTED
        assert event.source == ProposalSource.PREDICTIVE

    def test_event_to_dict(self) -> None:
        """Test event serialization."""
        event = ProposalLifecycleEventV1(
            event_id="evt-002",
            proposal_id="prop-002",
            zone_id="zone-bedroom",
            module_id=None,
            event_type=ProposalEventType.PROPOSED,
            source=ProposalSource.HABITUS,
            timestamp=1234567890.0,
            revision=1,
            metadata={"test": "value"},
        )

        d = event.to_dict()
        assert d["event_id"] == "evt-002"
        assert d["proposal_id"] == "prop-002"
        assert d["zone_id"] == "zone-bedroom"
        assert d["event_type"] == "proposed"
        assert d["source"] == "habitus"
        assert d["metadata"] == {"test": "value"}


class TestProposalAnalyticsStore:
    """Test ProposalAnalyticsStore operations."""

    def test_add_lifecycle_event(self, store: ProposalAnalyticsStore) -> None:
        """Test adding a lifecycle event."""
        entry = store.add_lifecycle_event(
            event_id="evt-001",
            proposal_id="prop-001",
            zone_id="zone-living",
            module_id="module-light",
            event_type=ProposalEventType.PROPOSED,
            source=ProposalSource.PREDICTIVE,
        )

        assert entry.event_id == "evt-001"
        assert entry.proposal_id == "prop-001"
        assert entry.revision == 1

    def test_revision_increments(self, store: ProposalAnalyticsStore) -> None:
        """Test revision increments with each event."""
        store.add_lifecycle_event(
            event_id=str(uuid.uuid4()),
            proposal_id="prop-001",
            zone_id="zone-1",
            module_id=None,
            event_type=ProposalEventType.PROPOSED,
            source=ProposalSource.PREDICTIVE,
        )

        entry2 = store.add_lifecycle_event(
            event_id=str(uuid.uuid4()),
            proposal_id="prop-002",
            zone_id="zone-2",
            module_id=None,
            event_type=ProposalEventType.ACCEPTED,
            source=ProposalSource.HABITUS,
        )

        assert entry2.revision == 2

    def test_build_lifecycle_history(self, store: ProposalAnalyticsStore) -> None:
        """Test building lifecycle history."""
        # Add multiple events
        for i in range(5):
            store.add_lifecycle_event(
                event_id=f"evt-{i:03d}",
                proposal_id=f"prop-{i:03d}",
                zone_id="zone-living",
                module_id=None,
                event_type=ProposalEventType.PROPOSED,
                source=ProposalSource.PREDICTIVE,
            )

        history = store.build_lifecycle_history(limit=10)

        assert isinstance(history, ProposalLifecycleHistoryV1)
        assert history.total_count == 5
        assert len(history.events) == 5
        assert history.revision == 5

    def test_build_lifecycle_history_filtered_by_proposal(self, store: ProposalAnalyticsStore) -> None:
        """Test filtering history by proposal."""
        # Add events for different proposals
        store.add_lifecycle_event(
            event_id="evt-001",
            proposal_id="prop-001",
            zone_id="zone-living",
            module_id=None,
            event_type=ProposalEventType.PROPOSED,
            source=ProposalSource.PREDICTIVE,
        )
        store.add_lifecycle_event(
            event_id="evt-002",
            proposal_id="prop-001",
            zone_id="zone-living",
            module_id=None,
            event_type=ProposalEventType.ACCEPTED,
            source=ProposalSource.PREDICTIVE,
        )
        store.add_lifecycle_event(
            event_id="evt-003",
            proposal_id="prop-002",
            zone_id="zone-bedroom",
            module_id=None,
            event_type=ProposalEventType.PROPOSED,
            source=ProposalSource.HABITUS,
        )

        history = store.build_lifecycle_history(proposal_id="prop-001")

        assert history.total_count == 2
        assert all(e.proposal_id == "prop-001" for e in history.events)

    def test_build_lifecycle_history_with_revision_filter(self, store: ProposalAnalyticsStore) -> None:
        """Test filtering history by revision."""
        # Add multiple events
        for i in range(5):
            store.add_lifecycle_event(
                event_id=f"evt-{i:03d}",
                proposal_id=f"prop-{i:03d}",
                zone_id="zone-living",
                module_id=None,
                event_type=ProposalEventType.PROPOSED,
                source=ProposalSource.PREDICTIVE,
            )

        # Get only events after revision 3
        history = store.build_lifecycle_history(since_revision=3)

        assert history.total_count == 2
        assert all(e.revision > 3 for e in history.events)

    def test_build_proposal_patterns(self, store: ProposalAnalyticsStore) -> None:
        """Test building proposal patterns."""
        # Add events for multiple zones and sources
        for i in range(10):
            store.add_lifecycle_event(
                event_id=f"evt-living-{i:03d}",
                proposal_id=f"prop-living-{i:03d}",
                zone_id="zone-living",
                module_id=None,
                event_type=ProposalEventType.PROPOSED,
                source=ProposalSource.PREDICTIVE,
            )

        for i in range(5):
            store.add_lifecycle_event(
                event_id=f"evt-bedroom-{i:03d}",
                proposal_id=f"prop-bedroom-{i:03d}",
                zone_id="zone-bedroom",
                module_id=None,
                event_type=ProposalEventType.PROPOSED,
                source=ProposalSource.HABITUS,
            )

        patterns = store.build_proposal_patterns()

        assert isinstance(patterns, ProposalPatternsV1)
        assert patterns.total_entries == 2  # 2 zone/source combinations
        assert len(patterns.patterns) == 2

    def test_build_proposal_patterns_with_mixed_events(self, store: ProposalAnalyticsStore) -> None:
        """Test patterns with mixed event types."""
        # Add proposed events
        for i in range(8):
            store.add_lifecycle_event(
                event_id=f"evt-prop-{i:03d}",
                proposal_id=f"prop-{i:03d}",
                zone_id="zone-kitchen",
                module_id=None,
                event_type=ProposalEventType.PROPOSED,
                source=ProposalSource.PREDICTIVE,
            )

        # Add accepted events (some of the proposals)
        for i in range(6):
            store.add_lifecycle_event(
                event_id=f"evt-accept-{i:03d}",
                proposal_id=f"prop-{i:03d}",
                zone_id="zone-kitchen",
                module_id=None,
                event_type=ProposalEventType.ACCEPTED,
                source=ProposalSource.PREDICTIVE,
            )

        # Add rejected events
        for i in range(2):
            store.add_lifecycle_event(
                event_id=f"evt-reject-{i:03d}",
                proposal_id=f"prop-{i+6:03d}",
                zone_id="zone-kitchen",
                module_id=None,
                event_type=ProposalEventType.REJECTED,
                source=ProposalSource.PREDICTIVE,
            )

        patterns = store.build_proposal_patterns()

        kitchen = next(p for p in patterns.patterns if p.zone_id == "zone-kitchen")
        # total_proposals counts all events (proposed + accepted + rejected)
        assert kitchen.total_proposals == 16  # 8 proposed + 6 accepted + 2 rejected
        assert kitchen.accepted_count == 6
        assert kitchen.rejected_count == 2
        assert abs(kitchen.acceptance_rate - (6 / 16)) < 0.01

    def test_get_effectiveness_metrics(self, store: ProposalAnalyticsStore) -> None:
        """Test effectiveness metrics calculation."""
        # Add mixed events
        for i in range(70):
            store.add_lifecycle_event(
                event_id=f"evt-prop-{i:03d}",
                proposal_id=f"prop-{i:03d}",
                zone_id=f"zone-{i % 5}",
                module_id=None,
                event_type=ProposalEventType.PROPOSED,
                source=ProposalSource.PREDICTIVE if i % 2 == 0 else ProposalSource.HABITUS,
            )

        for i in range(50):
            store.add_lifecycle_event(
                event_id=f"evt-accept-{i:03d}",
                proposal_id=f"prop-{i:03d}",
                zone_id=f"zone-{i % 5}",
                module_id=None,
                event_type=ProposalEventType.ACCEPTED,
                source=ProposalSource.PREDICTIVE if i % 2 == 0 else ProposalSource.HABITUS,
            )

        for i in range(10):
            store.add_lifecycle_event(
                event_id=f"evt-reject-{i:03d}",
                proposal_id=f"prop-{i:03d}",
                zone_id=f"zone-{i % 3}",
                module_id=None,
                event_type=ProposalEventType.REJECTED,
                source=ProposalSource.PREDICTIVE,
            )

        metrics = store.get_effectiveness_metrics()

        assert isinstance(metrics, ProposalEffectivenessMetricsV1)
        assert metrics.total_proposals == 130  # 70 proposed + 50 accepted + 10 rejected
        assert metrics.zones_with_proposals == 5
        assert abs(metrics.overall_acceptance_rate - (50 / 130)) < 0.01
        assert "predictive" in metrics.proposals_by_source
        assert "habitus" in metrics.proposals_by_source

    def test_build_summary(self, store: ProposalAnalyticsStore) -> None:
        """Test building complete summary."""
        # Add some events
        for i in range(5):
            store.add_lifecycle_event(
                event_id=f"evt-{i:03d}",
                proposal_id=f"prop-{i:03d}",
                zone_id="zone-living",
                module_id=None,
                event_type=ProposalEventType.PROPOSED,
                source=ProposalSource.PREDICTIVE,
            )

        summary = store.build_summary()

        assert summary.history is not None
        assert summary.patterns is not None
        assert summary.effectiveness is not None
        assert summary.revision == 5

    def test_build_summary_with_revision_filter(self, store: ProposalAnalyticsStore) -> None:
        """Test summary with revision filter."""
        # Add events
        for i in range(10):
            store.add_lifecycle_event(
                event_id=f"evt-{i:03d}",
                proposal_id=f"prop-{i:03d}",
                zone_id="zone-living",
                module_id=None,
                event_type=ProposalEventType.PROPOSED,
                source=ProposalSource.PREDICTIVE,
            )

        # Get summary with only recent events
        summary = store.build_summary(since_revision=7)

        assert summary.history.total_count == 3
        assert summary.revision >= 10


class TestProposalEventType:
    """Test ProposalEventType enum."""

    def test_all_event_types(self) -> None:
        """Test all event type values."""
        assert ProposalEventType.PROPOSED.value == "proposed"
        assert ProposalEventType.ACCEPTED.value == "accepted"
        assert ProposalEventType.REJECTED.value == "rejected"
        assert ProposalEventType.SNOOZED.value == "snoozed"
        assert ProposalEventType.EXECUTED.value == "executed"
        assert ProposalEventType.FAILED.value == "failed"
        assert ProposalEventType.EXPIRED.value == "expired"


class TestProposalSource:
    """Test ProposalSource enum."""

    def test_all_sources(self) -> None:
        """Test all source values."""
        assert ProposalSource.PREDICTIVE.value == "predictive"
        assert ProposalSource.HABITUS.value == "habitus"
        assert ProposalSource.VOICE.value == "voice"
        assert ProposalSource.MULTI_ZONE.value == "multizone"
        assert ProposalSource.MANUAL.value == "manual"
        assert ProposalSource.SYSTEM.value == "system"


class TestProposalPatternsV1:
    """Test ProposalPatternsV1 serialization."""

    def test_patterns_to_dict(self, store: ProposalAnalyticsStore) -> None:
        """Test patterns serialization."""
        store.add_lifecycle_event(
            event_id="evt-001",
            proposal_id="prop-001",
            zone_id="zone-test",
            module_id=None,
            event_type=ProposalEventType.PROPOSED,
            source=ProposalSource.PREDICTIVE,
        )

        patterns = store.build_proposal_patterns()
        d = patterns.to_dict()

        assert "patterns" in d
        assert "total_entries" in d
        assert "revision" in d
        assert "generated_at" in d
        assert len(d["patterns"]) == 1


class TestProposalEffectivenessMetricsV1:
    """Test ProposalEffectivenessMetricsV1."""

    def test_metrics_to_dict(self, store: ProposalAnalyticsStore) -> None:
        """Test metrics serialization."""
        store.add_lifecycle_event(
            event_id="evt-001",
            proposal_id="prop-001",
            zone_id="zone-test",
            module_id=None,
            event_type=ProposalEventType.PROPOSED,
            source=ProposalSource.PREDICTIVE,
        )

        metrics = store.get_effectiveness_metrics()
        d = metrics.to_dict()

        assert "overall_acceptance_rate" in d
        assert "overall_execution_rate" in d
        assert "overall_failure_rate" in d
        assert "proposals_by_source" in d
        assert "acceptances_by_source" in d
        assert "zones_with_proposals" in d
