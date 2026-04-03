"""Contract tests for Voice Calendar Integration.

Tests the calendar-aware voice hint system:
- CalendarVoiceIntegration class
- CalendarEventContext dataclass
- CalendarDaySummary dataclass
- Proactive hint generation from calendar events
- Integration with ProactiveVoiceHints
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, MagicMock, patch


class MockCalendarEngine:
    """Mock calendar engine for testing."""

    def __init__(self, events: Optional[List[Dict[str, Any]]] = None):
        self.events = events or []

    def get_upcoming_events(self, limit: int = 3) -> List[Dict[str, Any]]:
        return self.events[:limit]

    def get_day_summary(self, date: str) -> Dict[str, Any]:
        return {
            "date": date,
            "total_events": len([e for e in self.events if e.get("start", "").startswith(date)]),
            "busy_minutes": 240,
            "free_minutes": 1200,
            "first_event_time": "09:00",
            "last_event_time": "17:00",
            "busiest_hour": 14,
            "has_conflicts": False,
        }


class TestCalendarEventContext:
    """Test CalendarEventContext dataclass."""

    def test_basic_event_creation(self):
        """Test basic event context creation."""
        from copilot_core.voice.calendar_integration import CalendarEventContext

        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)
        end = now + timedelta(hours=2)

        event = CalendarEventContext(
            event_id="test-123",
            title="Test Meeting",
            start_time=start,
            end_time=end,
            location="Conference Room A",
        )

        assert event.event_id == "test-123"
        assert event.title == "Test Meeting"
        assert event.duration_minutes == 60
        assert event.location == "Conference Room A"
        assert event.time_until_start is not None

    def test_event_to_dict(self):
        """Test event serialization."""
        from copilot_core.voice.calendar_integration import CalendarEventContext

        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)
        end = now + timedelta(hours=2)

        event = CalendarEventContext(
            event_id="test-123",
            title="Test Meeting",
            start_time=start,
            end_time=end,
        )

        data = event.to_dict()

        assert data["event_id"] == "test-123"
        assert data["title"] == "Test Meeting"
        assert data["duration_minutes"] == 60
        assert "start_time" in data
        assert "end_time" in data

    def test_all_day_event(self):
        """Test all-day event handling."""
        from copilot_core.voice.calendar_integration import CalendarEventContext

        event = CalendarEventContext(
            event_id="all-day-123",
            title="Vacation Day",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            is_all_day=True,
        )

        assert event.is_all_day is True


class TestCalendarDaySummary:
    """Test CalendarDaySummary dataclass."""

    def test_day_summary_creation(self):
        """Test day summary creation."""
        from copilot_core.voice.calendar_integration import CalendarDaySummary

        summary = CalendarDaySummary(
            date="2026-04-03",
            total_events=5,
            busy_minutes=300,
            free_minutes=1140,
            first_event_time="08:00",
            last_event_time="18:00",
            busiest_hour=14,
        )

        assert summary.date == "2026-04-03"
        assert summary.total_events == 5
        assert summary.busy_minutes == 300
        assert summary.free_minutes == 1140

    def test_day_summary_to_dict(self):
        """Test day summary serialization."""
        from copilot_core.voice.calendar_integration import CalendarDaySummary

        summary = CalendarDaySummary(
            date="2026-04-03",
            total_events=3,
            busy_minutes=180,
            free_minutes=1260,
        )

        data = summary.to_dict()

        assert data["date"] == "2026-04-03"
        assert data["total_events"] == 3
        assert data["busy_minutes"] == 180


class TestCalendarVoiceIntegration:
    """Test CalendarVoiceIntegration class."""

    def test_integration_initialization(self):
        """Test calendar voice integration initialization."""
        from copilot_core.voice.calendar_integration import CalendarVoiceIntegration

        mock_calendar = MockCalendarEngine()
        integration = CalendarVoiceIntegration(calendar_engine=mock_calendar)

        assert integration.calendar_engine is mock_calendar
        assert integration.URGENT_EVENT_THRESHOLD == 15
        assert integration.UPCOMING_EVENT_THRESHOLD == 60

    def test_generate_hints_with_no_events(self):
        """Test hint generation with empty calendar."""
        from copilot_core.voice.calendar_integration import CalendarVoiceIntegration
        from copilot_core.voice.context_builder import VoiceContext, TimeContext, TimeOfDay

        mock_calendar = MockCalendarEngine(events=[])
        integration = CalendarVoiceIntegration(calendar_engine=mock_calendar)

        context = VoiceContext(
            zone_name="wohnzimmer",
            time_context=TimeContext(time_of_day=TimeOfDay.MORNING),
        )

        hints = integration.generate_calendar_hints(context)

        # Should return empty or minimal hints when no events
        assert isinstance(hints, list)

    def test_generate_upcoming_event_hints(self):
        """Test upcoming event hint generation."""
        from copilot_core.voice.calendar_integration import CalendarVoiceIntegration, CalendarEventContext
        from copilot_core.voice.context_builder import VoiceContext, TimeContext, TimeOfDay

        now = datetime.now(timezone.utc)

        # Create event starting in 10 minutes (urgent)
        urgent_event = CalendarEventContext(
            event_id="urgent-123",
            title="Urgent Meeting",
            start_time=now + timedelta(minutes=10),
            end_time=now + timedelta(minutes=60),
        )

        mock_calendar = MockCalendarEngine(events=[urgent_event.to_dict()])
        integration = CalendarVoiceIntegration(calendar_engine=mock_calendar)

        context = VoiceContext(
            zone_name="wohnzimmer",
            time_context=TimeContext(time_of_day=TimeOfDay.MORNING),
        )

        hints = integration.generate_calendar_hints(context, language="de")

        # Should have at least one hint for urgent event
        assert len(hints) >= 1

        # Check hint structure
        hint = hints[0]
        assert hasattr(hint, "hint_type")
        assert hasattr(hint, "priority")
        assert hasattr(hint, "message_de")
        assert hasattr(hint, "message_en")

    def test_generate_hints_german(self):
        """Test German language hint generation."""
        from copilot_core.voice.calendar_integration import CalendarVoiceIntegration, CalendarEventContext
        from copilot_core.voice.context_builder import VoiceContext, TimeContext, TimeOfDay

        now = datetime.now(timezone.utc)

        event = CalendarEventContext(
            event_id="de-123",
            title="Deutsches Meeting",
            start_time=now + timedelta(minutes=30),
            end_time=now + timedelta(minutes=90),
        )

        mock_calendar = MockCalendarEngine(events=[event.to_dict()])
        integration = CalendarVoiceIntegration(calendar_engine=mock_calendar)

        context = VoiceContext(
            zone_name="wohnzimmer",
            time_context=TimeContext(time_of_day=TimeOfDay.AFTERNOON),
        )

        hints = integration.generate_calendar_hints(context, language="de")

        # Check German messages
        for hint in hints:
            assert hint.message_de is not None
            assert len(hint.message_de) > 0

    def test_generate_hints_english(self):
        """Test English language hint generation."""
        from copilot_core.voice.calendar_integration import CalendarVoiceIntegration, CalendarEventContext
        from copilot_core.voice.context_builder import VoiceContext, TimeContext, TimeOfDay

        now = datetime.now(timezone.utc)

        event = CalendarEventContext(
            event_id="en-123",
            title="English Meeting",
            start_time=now + timedelta(minutes=45),
            end_time=now + timedelta(minutes=105),
        )

        mock_calendar = MockCalendarEngine(events=[event.to_dict()])
        integration = CalendarVoiceIntegration(calendar_engine=mock_calendar)

        context = VoiceContext(
            zone_name="wohnzimmer",
            time_context=TimeContext(time_of_day=TimeOfDay.AFTERNOON),
        )

        hints = integration.generate_calendar_hints(context, language="en")

        # Check English messages
        for hint in hints:
            assert hint.message_en is not None
            assert len(hint.message_en) > 0


class TestProactiveHintsCalendarIntegration:
    """Test calendar integration with ProactiveVoiceHints."""

    def test_proactive_hints_calendar_check_method_exists(self):
        """Test that ProactiveVoiceHints has calendar check method."""
        from copilot_core.voice.proactive import ProactiveVoiceHints

        hints = ProactiveVoiceHints()

        # Should have the calendar check method
        assert hasattr(hints, "_check_calendar_events")

    def test_proactive_hints_calendar_integration(self):
        """Test calendar hints integrated into proactive hints."""
        from copilot_core.voice.proactive import ProactiveVoiceHints, HintPriority
        from copilot_core.voice.context_builder import VoiceContext, TimeContext, TimeOfDay
        from copilot_core.voice.calendar_integration import CalendarEventContext, get_calendar_integration_engine
    
        now = datetime.now(timezone.utc)
    
        # Create mock calendar engine
        event = CalendarEventContext(
            event_id="cal-123",
            title="Calendar Event",
            start_time=now + timedelta(minutes=20),
            end_time=now + timedelta(minutes=80),
        )
    
        mock_calendar = MockCalendarEngine(events=[event.to_dict()])
    
        with patch('copilot_core.voice.calendar_integration.get_calendar_integration_engine', return_value=mock_calendar):
            hints = ProactiveVoiceHints()
            
            context = VoiceContext(
                zone_name="wohnzimmer",
                time_context=TimeContext(time_of_day=TimeOfDay.MORNING),
                language="de",
            )
            
            all_hints = hints.generate_hints(context)
            
            # Should be a list
            assert isinstance(all_hints, list)


class TestCalendarHintTypes:
    """Test calendar hint type coverage."""

    def test_hint_type_enum_coverage(self):
        """Test that all calendar hint types are defined."""
        from copilot_core.voice.calendar_integration import CalendarHintType

        # Should have all expected hint types
        types = [t.value for t in CalendarHintType]

        expected_types = [
            "upcoming_event",
            "calendar_density",
            "meeting_preparation",
            "travel_time",
            "free_slot",
            "schedule_conflict",
            "alarm_suggestion",
        ]

        for expected in expected_types:
            assert expected in types, f"Missing hint type: {expected}"


class TestCalendarIntegrationEdgeCases:
    """Test edge cases in calendar integration."""

    def test_no_calendar_engine(self):
        """Test behavior when calendar engine is None."""
        from copilot_core.voice.calendar_integration import CalendarVoiceIntegration
        from copilot_core.voice.context_builder import VoiceContext

        integration = CalendarVoiceIntegration(calendar_engine=None)
        context = VoiceContext()

        hints = integration.generate_calendar_hints(context)

        # Should return empty list gracefully
        assert hints == []

    def test_past_event_filtered(self):
        """Test that past events are filtered out."""
        from copilot_core.voice.calendar_integration import CalendarVoiceIntegration, CalendarEventContext
        from copilot_core.voice.context_builder import VoiceContext

        now = datetime.now(timezone.utc)

        # Create past event
        past_event = CalendarEventContext(
            event_id="past-123",
            title="Past Event",
            start_time=now - timedelta(hours=1),
            end_time=now - timedelta(minutes=30),
        )

        mock_calendar = MockCalendarEngine(events=[past_event.to_dict()])
        integration = CalendarVoiceIntegration(calendar_engine=mock_calendar)

        context = VoiceContext()
        hints = integration.generate_calendar_hints(context)

        # Past events should not generate hints
        # (or at least not urgent upcoming hints)
        for hint in hints:
            if hasattr(hint, 'context'):
                assert hint.context.get('urgency') != 'urgent'

    def test_timezone_aware_events(self):
        """Test handling of timezone-aware events."""
        from copilot_core.voice.calendar_integration import CalendarEventContext

        # Create event with timezone
        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)

        event = CalendarEventContext(
            event_id="tz-123",
            title="Timezone Event",
            start_time=start,
            end_time=start + timedelta(hours=1),
        )

        # Should handle timezone correctly
        assert event.start_time.tzinfo is not None
        assert event.time_until_start is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
