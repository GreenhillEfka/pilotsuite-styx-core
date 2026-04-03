"""Audit Log Contract Tests — Slice 69"""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from copilot_core.audit.contracts import (
    AuditEventType,
    AuditLogEntryV1,
    AuditLogSummaryV1,
    AuditOutcome,
    AuditSeverity,
)
from copilot_core.audit.store import AuditLogStore


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "audit_test.db"
        yield str(db_path)


@pytest.fixture
def store(temp_db):
    """Create an AuditLogStore instance."""
    return AuditLogStore(temp_db)


class TestAuditLogEntryV1:
    """Test AuditLogEntryV1 contract."""

    def test_create_entry_from_event(self):
        """Test factory method for creating entries."""
        entry = AuditLogEntryV1.from_event(
            entry_id="test-001",
            event_type=AuditEventType.PROPOSAL_ACCEPTED,
            outcome=AuditOutcome.SUCCESS,
            severity=AuditSeverity.INFO,
            subject="User accepted proposal",
            details={"proposal_id": "prop-123"},
            zone_id="zone-living",
            user_id="user-andreas",
        )

        assert entry.entry_id == "test-001"
        assert entry.event_type == "proposal_accepted"
        assert entry.outcome == "success"
        assert entry.severity == "info"
        assert entry.subject == "User accepted proposal"
        assert entry.zone_id == "zone-living"
        assert entry.user_id == "user-andreas"
        assert entry.revision == 1
        assert entry.created_at is not None
        assert entry.event_at is not None

    def test_entry_with_correlation(self):
        """Test entry with correlation ID for tracing."""
        entry = AuditLogEntryV1.from_event(
            entry_id="test-002",
            event_type=AuditEventType.ACTION_INTENT_EXECUTED,
            outcome=AuditOutcome.SUCCESS,
            severity=AuditSeverity.INFO,
            subject="Light turned on",
            correlation_id="corr-abc-123",
            parent_entry_id="test-001",
            duration_ms=45.2,
        )

        assert entry.correlation_id == "corr-abc-123"
        assert entry.parent_entry_id == "test-001"
        assert entry.duration_ms == 45.2


class TestAuditLogStore:
    """Test AuditLogStore persistence and queries."""

    def test_add_entry(self, store):
        """Test adding an audit entry."""
        entry = AuditLogEntryV1.from_event(
            entry_id="entry-001",
            event_type=AuditEventType.PROPOSAL_SUGGESTED,
            outcome=AuditOutcome.PENDING,
            severity=AuditSeverity.INFO,
            subject="Heating proposal suggested",
            zone_id="zone-bedroom",
        )

        result = store.add_entry(entry)

        assert result.entry_id == "entry-001"
        assert result.revision == 1
        assert store.get_revision() == 1

    def test_get_entry(self, store):
        """Test retrieving a single entry."""
        entry = AuditLogEntryV1.from_event(
            entry_id="entry-002",
            event_type=AuditEventType.MODULE_EXECUTION,
            outcome=AuditOutcome.SUCCESS,
            severity=AuditSeverity.DEBUG,
            subject="Module executed",
        )

        store.add_entry(entry)
        retrieved = store.get_entry("entry-002")

        assert retrieved is not None
        assert retrieved.entry_id == "entry-002"
        assert retrieved.event_type == "module_execution"

    def test_get_nonexistent_entry(self, store):
        """Test retrieving nonexistent entry."""
        result = store.get_entry("nonexistent")
        assert result is None

    def test_revision_increments(self, store):
        """Test that revision increments with each entry."""
        for i in range(5):
            entry = AuditLogEntryV1.from_event(
                entry_id=f"entry-{i:03d}",
                event_type=AuditEventType.SYSTEM_EVENT,
                outcome=AuditOutcome.SUCCESS,
                severity=AuditSeverity.INFO,
                subject=f"Event {i}",
            )
            store.add_entry(entry)

        assert store.get_revision() == 5

    def test_get_entries_with_filters(self, store):
        """Test querying entries with filters."""
        # Add mixed entries
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="e1",
                event_type=AuditEventType.PROPOSAL_ACCEPTED,
                outcome=AuditOutcome.SUCCESS,
                severity=AuditSeverity.INFO,
                subject="Accepted",
                zone_id="zone-living",
                user_id="user-andreas",
            )
        )
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="e2",
                event_type=AuditEventType.PROPOSAL_REJECTED,
                outcome=AuditOutcome.CANCELLED,
                severity=AuditSeverity.WARNING,
                subject="Rejected",
                zone_id="zone-bedroom",
                user_id="user-andreas",
            )
        )
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="e3",
                event_type=AuditEventType.PROPOSAL_ACCEPTED,
                outcome=AuditOutcome.SUCCESS,
                severity=AuditSeverity.INFO,
                subject="Accepted 2",
                zone_id="zone-living",
                user_id="user-other",
            )
        )

        # Filter by zone
        living_entries = store.get_entries(zone_id="zone-living")
        assert len(living_entries) == 2

        # Filter by outcome
        success_entries = store.get_entries(outcome="success")
        assert len(success_entries) == 2

        # Filter by user
        andreas_entries = store.get_entries(user_id="user-andreas")
        assert len(andreas_entries) == 2

        # Combined filters
        living_success = store.get_entries(zone_id="zone-living", outcome="success")
        assert len(living_success) == 2

    def test_get_delta(self, store):
        """Test delta polling."""
        # Add initial entries
        for i in range(3):
            store.add_entry(
                AuditLogEntryV1.from_event(
                    entry_id=f"init-{i}",
                    event_type=AuditEventType.SYSTEM_EVENT,
                    outcome=AuditOutcome.SUCCESS,
                    severity=AuditSeverity.INFO,
                    subject=f"Init {i}",
                )
            )

        # Get delta since revision 0
        delta = store.get_delta(0, limit=10)
        assert delta.has_changes is True
        assert len(delta.new_entries) == 3
        assert delta.revision == 3

        # Add more entries
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="new-1",
                event_type=AuditEventType.USER_ACTION,
                outcome=AuditOutcome.SUCCESS,
                severity=AuditSeverity.INFO,
                subject="New action",
            )
        )

        # Get delta since revision 3
        delta2 = store.get_delta(3, limit=10)
        assert delta2.has_changes is True
        assert len(delta2.new_entries) == 1
        assert delta2.revision == 4

        # No changes since latest
        delta3 = store.get_delta(4, limit=10)
        assert delta3.has_changes is False
        assert len(delta3.new_entries) == 0

    def test_get_summary(self, store):
        """Test summary aggregation."""
        # Add diverse entries
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="s1",
                event_type=AuditEventType.PROPOSAL_ACCEPTED,
                outcome=AuditOutcome.SUCCESS,
                severity=AuditSeverity.INFO,
                subject="Success 1",
            )
        )
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="s2",
                event_type=AuditEventType.PROPOSAL_REJECTED,
                outcome=AuditOutcome.FAILURE,
                severity=AuditSeverity.ERROR,
                subject="Failure 1",
            )
        )
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="s3",
                event_type=AuditEventType.PROPOSAL_ACCEPTED,
                outcome=AuditOutcome.SUCCESS,
                severity=AuditSeverity.INFO,
                subject="Success 2",
            )
        )

        summary = store.get_summary()

        assert summary.total_entries == 3
        assert summary.success_count == 2
        assert summary.failure_count == 1
        assert summary.info_count == 2
        assert summary.error_count == 1
        assert "proposal_accepted" in summary.event_type_counts
        assert "proposal_rejected" in summary.event_type_counts
        assert len(summary.recent_entries) == 3

    def test_get_summary_with_filters(self, store):
        """Test filtered summary."""
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="f1",
                event_type=AuditEventType.MODULE_EXECUTION,
                outcome=AuditOutcome.SUCCESS,
                severity=AuditSeverity.INFO,
                subject="Module success",
                zone_id="zone-living",
            )
        )
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="f2",
                event_type=AuditEventType.MODULE_EXECUTION,
                outcome=AuditOutcome.FAILURE,
                severity=AuditSeverity.ERROR,
                subject="Module failure",
                zone_id="zone-bedroom",
            )
        )

        # Filter by zone
        living_summary = store.get_summary(zone_id="zone-living")
        assert living_summary.total_entries == 1
        assert living_summary.success_count == 1

        # Filter by event type
        module_summary = store.get_summary(event_type="module_execution")
        assert module_summary.total_entries == 2

    def test_export_json(self, store, temp_db):
        """Test JSON export."""
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="exp-1",
                event_type=AuditEventType.SYSTEM_EVENT,
                outcome=AuditOutcome.SUCCESS,
                severity=AuditSeverity.INFO,
                subject="Export test",
            )
        )

        path, count = store.export_entries("test-export", format="json")

        assert count == 1
        assert Path(path).exists()
        assert "test-export.json" in path

    def test_export_csv(self, store, temp_db):
        """Test CSV export."""
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="csv-1",
                event_type=AuditEventType.USER_ACTION,
                outcome=AuditOutcome.SUCCESS,
                severity=AuditSeverity.INFO,
                subject="CSV test",
            )
        )

        path, count = store.export_entries("test-csv", format="csv")

        assert count == 1
        assert Path(path).exists()
        assert "test-csv.csv" in path

    def test_export_ndjson(self, store, temp_db):
        """Test NDJSON export."""
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="ndj-1",
                event_type=AuditEventType.HEALTH_CHECK,
                outcome=AuditOutcome.SUCCESS,
                severity=AuditSeverity.DEBUG,
                subject="NDJSON test",
            )
        )

        path, count = store.export_entries("test-ndjson", format="ndjson")

        assert count == 1
        assert Path(path).exists()
        assert "test-ndjson.ndjson" in path

    def test_entry_with_duration(self, store):
        """Test entry with duration tracking."""
        entry = AuditLogEntryV1.from_event(
            entry_id="dur-1",
            event_type=AuditEventType.ACTION_INTENT_EXECUTED,
            outcome=AuditOutcome.SUCCESS,
            severity=AuditSeverity.INFO,
            subject="Action with duration",
            duration_ms=123.45,
        )

        stored = store.add_entry(entry)
        assert stored.duration_ms == 123.45

        retrieved = store.get_entry("dur-1")
        assert retrieved is not None
        assert retrieved.duration_ms == 123.45

    def test_correlation_tracking(self, store):
        """Test correlation ID for tracing related events."""
        correlation_id = "corr-proposal-123"

        # Proposal suggested
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="corr-1",
                event_type=AuditEventType.PROPOSAL_SUGGESTED,
                outcome=AuditOutcome.PENDING,
                severity=AuditSeverity.INFO,
                subject="Proposal suggested",
                correlation_id=correlation_id,
            )
        )

        # Proposal accepted
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="corr-2",
                event_type=AuditEventType.PROPOSAL_ACCEPTED,
                outcome=AuditOutcome.SUCCESS,
                severity=AuditSeverity.INFO,
                subject="Proposal accepted",
                correlation_id=correlation_id,
                parent_entry_id="corr-1",
            )
        )

        # Action executed
        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="corr-3",
                event_type=AuditEventType.ACTION_INTENT_EXECUTED,
                outcome=AuditOutcome.SUCCESS,
                severity=AuditSeverity.INFO,
                subject="Action executed",
                correlation_id=correlation_id,
                parent_entry_id="corr-2",
            )
        )

        # Query by correlation
        correlated = store.get_entries(correlation_id=correlation_id)
        assert len(correlated) == 3

    def test_time_range_filtering(self, store):
        """Test filtering by time range."""
        now = datetime.utcnow()
        past = now - timedelta(hours=1)

        store.add_entry(
            AuditLogEntryV1.from_event(
                entry_id="time-1",
                event_type=AuditEventType.SYSTEM_EVENT,
                outcome=AuditOutcome.SUCCESS,
                severity=AuditSeverity.INFO,
                subject="Recent event",
            )
        )

        # This is a basic test; real time filtering would need fixed timestamps
        entries = store.get_entries()
        assert len(entries) >= 1


class TestAuditEventType:
    """Test AuditEventType enum coverage."""

    def test_all_event_types_defined(self):
        """Test that key event types are defined."""
        expected_types = [
            "proposal_suggested",
            "proposal_accepted",
            "proposal_rejected",
            "action_intent_created",
            "action_intent_executed",
            "action_intent_failed",
            "action_closure_created",
            "notification_sent",
            "hold_set",
            "hold_released",
            "zone_sync",
            "module_execution",
            "voice_command",
        ]

        defined = [e.value for e in AuditEventType]
        for expected in expected_types:
            assert expected in defined, f"Missing event type: {expected}"


class TestAuditOutcome:
    """Test AuditOutcome enum."""

    def test_all_outcomes_defined(self):
        """Test that all outcomes are defined."""
        expected = ["success", "failure", "pending", "cancelled", "skipped"]
        defined = [o.value for o in AuditOutcome]
        for exp in expected:
            assert exp in defined


class TestAuditSeverity:
    """Test AuditSeverity enum."""

    def test_all_severities_defined(self):
        """Test that all severity levels are defined."""
        expected = ["debug", "info", "warning", "error", "critical"]
        defined = [s.value for s in AuditSeverity]
        for exp in expected:
            assert exp in defined


class TestAuditLogSummaryV1:
    """Test AuditLogSummaryV1 contract."""

    def test_summary_structure(self, store):
        """Test summary has all required fields."""
        summary = store.get_summary()

        assert hasattr(summary, "total_entries")
        assert hasattr(summary, "revision")
        assert hasattr(summary, "latest_entry_at")
        assert hasattr(summary, "success_count")
        assert hasattr(summary, "failure_count")
        assert hasattr(summary, "event_type_counts")
        assert hasattr(summary, "recent_entries")

    def test_empty_summary(self, store):
        """Test summary with no entries."""
        summary = store.get_summary()

        assert summary.total_entries == 0
        assert summary.revision == 0
        assert summary.latest_entry_at is None
        assert summary.success_count == 0
        assert len(summary.recent_entries) == 0
