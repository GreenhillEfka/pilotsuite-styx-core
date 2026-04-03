"""Calendar Analytics Contract Tests — Slice 69."""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import os

from copilot_core.analytics.calendar_analytics import (
    CalendarAnalyticsStore,
    CalendarUsageEntry,
    CalendarEventType,
    SuggestionType,
    SuggestionAction,
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def store(temp_db):
    """Create analytics store with temp database."""
    return CalendarAnalyticsStore(db_path=temp_db)


class TestCalendarUsageEntry:
    """Test CalendarUsageEntry dataclass."""

    def test_create_usage_entry(self):
        entry = CalendarUsageEntry(
            entry_id="test-1",
            timestamp=datetime.now().isoformat(),
            event_type="meeting",
            duration_minutes=60,
            source="smart_recommend",
            zone_id="zone-living",
            user_id="user-1",
        )
        assert entry.entry_id == "test-1"
        assert entry.event_type == "meeting"
        assert entry.duration_minutes == 60
        assert entry.source == "smart_recommend"
        assert entry.zone_id == "zone-living"
        assert entry.metadata == {}


class TestCalendarAnalyticsStore:
    """Test CalendarAnalyticsStore operations."""

    def test_init_creates_tables(self, store):
        """Test database initialization creates required tables."""
        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]
            assert "usage_entries" in tables
            assert "suggestion_events" in tables
            assert "analytics_revision" in tables

    def test_add_usage_entry(self, store):
        """Test adding usage entries."""
        entry = CalendarUsageEntry(
            entry_id="test-entry-1",
            timestamp=datetime.now().isoformat(),
            event_type="meeting",
            duration_minutes=60,
            source="smart_recommend",
            zone_id="zone-living",
        )
        store.add_usage_entry(entry)

        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(
                "SELECT entry_id, event_type, duration_minutes, source, zone_id FROM usage_entries"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "test-entry-1"
            assert row[1] == "meeting"
            assert row[2] == 60
            assert row[3] == "smart_recommend"
            assert row[4] == "zone-living"

    def test_add_usage_entry_increments_revision(self, store):
        """Test that adding entries increments revision."""
        initial_revision = store._get_revision()
        entry = CalendarUsageEntry(
            entry_id="test-entry-1",
            timestamp=datetime.now().isoformat(),
            event_type="task",
            duration_minutes=30,
            source="ha_calendar",
        )
        store.add_usage_entry(entry)
        new_revision = store._get_revision()
        assert new_revision > initial_revision

    def test_add_suggestion_event(self, store):
        """Test recording suggestion actions."""
        store.add_suggestion_event(
            suggestion_id="suggestion-1",
            suggestion_type="break_reminder",
            action="accepted",
            zone_id="zone-office",
        )

        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(
                "SELECT suggestion_id, suggestion_type, action, zone_id FROM suggestion_events"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "suggestion-1"
            assert row[1] == "break_reminder"
            assert row[2] == "accepted"
            assert row[3] == "zone-office"

    def test_build_usage_history(self, store):
        """Test building usage history."""
        # Add some test entries
        now = datetime.now()
        for i in range(5):
            entry = CalendarUsageEntry(
                entry_id=f"entry-{i}",
                timestamp=(now - timedelta(hours=i)).isoformat(),
                event_type="meeting" if i % 2 == 0 else "task",
                duration_minutes=30 + i * 10,
                source="smart_recommend",
            )
            store.add_usage_entry(entry)

        history = store.build_usage_history(limit=10)
        assert history.total_count == 5
        assert len(history.entries) == 5
        assert history.revision > 0

    def test_build_usage_history_date_range(self, store):
        """Test usage history with date range filtering."""
        now = datetime.now()
        # Add entries for different dates
        for i in range(3):
            entry = CalendarUsageEntry(
                entry_id=f"entry-{i}",
                timestamp=(now - timedelta(days=i)).isoformat(),
                event_type="meeting",
                duration_minutes=60,
                source="ha_calendar",
            )
            store.add_usage_entry(entry)

        start = (now - timedelta(days=2)).isoformat()
        end = now.isoformat()
        history = store.build_usage_history(start_date=start, end_date=end)
        assert history.total_count >= 1

    def test_build_patterns_by_event_type(self, store):
        """Test pattern analysis by event type."""
        # Add entries with different event types
        now = datetime.now()
        for i in range(10):
            entry = CalendarUsageEntry(
                entry_id=f"entry-{i}",
                timestamp=now.isoformat(),
                event_type="meeting" if i < 6 else "task",
                duration_minutes=60,
                source="smart_recommend",
            )
            store.add_usage_entry(entry)

        patterns = store.build_patterns()
        assert len(patterns.by_event_type) >= 2
        
        # Meeting should be most common
        meeting_pattern = next(
            (p for p in patterns.by_event_type if p.value == "meeting"), None
        )
        assert meeting_pattern is not None
        assert meeting_pattern.count == 6

    def test_build_patterns_by_hour(self, store):
        """Test pattern analysis by hour."""
        now = datetime.now()
        for hour in range(8, 18):
            entry = CalendarUsageEntry(
                entry_id=f"entry-{hour}",
                timestamp=now.replace(hour=hour).isoformat(),
                event_type="focus_block",
                duration_minutes=60,
                source="smart_recommend",
            )
            store.add_usage_entry(entry)

        patterns = store.build_patterns()
        assert len(patterns.by_hour) >= 10

    def test_build_patterns_by_day_of_week(self, store):
        """Test pattern analysis by day of week."""
        now = datetime.now()
        for day in range(7):
            entry = CalendarUsageEntry(
                entry_id=f"entry-{day}",
                timestamp=(now - timedelta(days=day)).isoformat(),
                event_type="meeting",
                duration_minutes=60,
                source="ha_calendar",
            )
            store.add_usage_entry(entry)

        patterns = store.build_patterns()
        assert len(patterns.by_day_of_week) >= 1

    def test_build_patterns_by_zone(self, store):
        """Test pattern analysis by zone."""
        now = datetime.now()
        zones = ["zone-living", "zone-office", "zone-bedroom"]
        for i, zone in enumerate(zones):
            for j in range(3):
                entry = CalendarUsageEntry(
                    entry_id=f"entry-{zone}-{j}",
                    timestamp=now.isoformat(),
                    event_type="task",
                    duration_minutes=30,
                    source="smart_recommend",
                    zone_id=zone,
                )
                store.add_usage_entry(entry)

        patterns = store.build_patterns()
        assert len(patterns.by_zone) == 3

    def test_get_effectiveness_metrics(self, store):
        """Test effectiveness metrics calculation."""
        # Add various entries
        now = datetime.now()
        for i in range(20):
            entry = CalendarUsageEntry(
                entry_id=f"entry-{i}",
                timestamp=now.isoformat(),
                event_type="meeting" if i < 10 else "focus_block",
                duration_minutes=60,
                source="smart_recommend" if i < 5 else "mood_recommend" if i < 10 else "ha_calendar",
            )
            store.add_usage_entry(entry)

        # Add suggestion events
        for i in range(10):
            store.add_suggestion_event(
                suggestion_id=f"suggestion-{i}",
                suggestion_type="break_reminder",
                action="accepted" if i < 7 else "dismissed",
            )

        metrics = store.get_effectiveness_metrics()
        assert metrics.total_events == 20
        assert metrics.smart_recommendations_count == 5
        assert metrics.mood_recommendations_count == 5
        assert metrics.suggestions_generated == 10
        assert metrics.suggestions_accepted == 7
        assert metrics.suggestions_dismissed == 3
        assert metrics.acceptance_rate == 70.0

    def test_build_summary(self, store):
        """Test building complete analytics summary."""
        # Add some data
        now = datetime.now()
        for i in range(5):
            entry = CalendarUsageEntry(
                entry_id=f"entry-{i}",
                timestamp=now.isoformat(),
                event_type="meeting",
                duration_minutes=60,
                source="smart_recommend",
            )
            store.add_usage_entry(entry)

        summary = store.build_summary()
        assert summary.usage.total_count == 5
        assert summary.patterns.revision > 0
        assert summary.effectiveness.revision > 0
        assert summary.generated_at is not None
        assert summary.revision > 0

    def test_revision_tracking(self, store):
        """Test that revision increments correctly."""
        initial = store._get_revision()
        assert initial == 0

        store.add_usage_entry(CalendarUsageEntry(
            entry_id="1", timestamp=datetime.now().isoformat(),
            event_type="meeting", duration_minutes=60, source="test",
        ))
        rev1 = store._get_revision()
        assert rev1 > initial

        store.add_suggestion_event("s1", "break_reminder", "accepted")
        rev2 = store._get_revision()
        assert rev2 > rev1


class TestCalendarAnalyticsAPI:
    """Test Calendar Analytics API endpoints (contract-level)."""

    def test_usage_endpoint_structure(self, store):
        """Test usage endpoint returns correct structure."""
        history = store.build_usage_history()
        
        # Verify structure matches API contract
        assert hasattr(history, "entries")
        assert hasattr(history, "total_count")
        assert hasattr(history, "date_range")
        assert hasattr(history, "revision")
        
        assert isinstance(history.entries, list)
        assert isinstance(history.total_count, int)
        assert isinstance(history.date_range, dict)
        assert "start" in history.date_range
        assert "end" in history.date_range

    def test_patterns_endpoint_structure(self, store):
        """Test patterns endpoint returns correct structure."""
        patterns = store.build_patterns()
        
        assert hasattr(patterns, "by_event_type")
        assert hasattr(patterns, "by_hour")
        assert hasattr(patterns, "by_day_of_week")
        assert hasattr(patterns, "by_zone")
        assert hasattr(patterns, "revision")
        
        assert isinstance(patterns.by_event_type, list)
        assert isinstance(patterns.by_hour, list)

    def test_effectiveness_endpoint_structure(self, store):
        """Test effectiveness endpoint returns correct structure."""
        metrics = store.get_effectiveness_metrics()
        
        assert hasattr(metrics, "total_events")
        assert hasattr(metrics, "suggestions_generated")
        assert hasattr(metrics, "suggestions_accepted")
        assert hasattr(metrics, "acceptance_rate")
        assert hasattr(metrics, "focus_block_utilization")
        assert hasattr(metrics, "break_compliance_rate")
        assert hasattr(metrics, "revision")

    def test_summary_endpoint_structure(self, store):
        """Test summary endpoint returns correct structure."""
        summary = store.build_summary()
        
        assert hasattr(summary, "usage")
        assert hasattr(summary, "patterns")
        assert hasattr(summary, "effectiveness")
        assert hasattr(summary, "generated_at")
        assert hasattr(summary, "revision")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
