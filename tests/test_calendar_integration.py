"""Tests for Calendar Integration Engine — Slice 19."""
import pytest
from copilot_core.calendar.integration_engine import (
    CalendarIntegrationEngine,
    EventType,
    EventSensitivity,
    create_calendar_integration_engine,
)
from datetime import datetime, timezone, timedelta


class TestCalendarIntegrationEngine:
    """Test calendar integration engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_calendar_integration_engine()
        assert engine is not None
    
    def test_register_calendar(self):
        """Test calendar registration."""
        engine = CalendarIntegrationEngine()
        
        cal_id = engine.register_calendar(
            calendar_id="cal_home",
            name="Home Calendar",
            source="ha",
            entity_id="calendar.home",
        )
        
        assert cal_id == "cal_home"
        assert cal_id in engine._calendars
        assert engine._calendars[cal_id]["name"] == "Home Calendar"
    
    def test_import_events(self):
        """Test event import."""
        engine = CalendarIntegrationEngine()
        engine.register_calendar("cal_test", "Test", "ha")
        
        events = [
            {
                "event_id": "evt_1",
                "summary": "Team Meeting",
                "start": "2026-03-31T10:00:00Z",
                "end": "2026-03-31T11:00:00Z",
            },
            {
                "event_id": "evt_2",
                "summary": "Lunch",
                "start": "2026-03-31T12:00:00Z",
                "end": "2026-03-31T13:00:00Z",
            },
        ]
        
        imported = engine.import_events("cal_test", events)
        
        assert imported == 2
        assert len(engine._events["cal_test"]) == 2
    
    def test_event_type_detection(self):
        """Test event type detection from summary."""
        engine = CalendarIntegrationEngine()
        
        # Meeting
        assert engine._detect_event_type("team meeting") == EventType.MEETING
        assert engine._detect_event_type("zoom call") == EventType.MEETING
        
        # Travel
        assert engine._detect_event_type("flight to Berlin") == EventType.TRAVEL
        assert engine._detect_event_type("train trip") == EventType.TRAVEL
        
        # Vacation
        assert engine._detect_event_type("vacation") == EventType.VACATION
        assert engine._detect_event_type("urlaub") == EventType.VACATION
        
        # Work
        assert engine._detect_event_type("office day") == EventType.WORK
        assert engine._detect_event_type("arbeit") == EventType.WORK
    
    def test_sensitivity_detection(self):
        """Test event sensitivity detection."""
        engine = CalendarIntegrationEngine()
        
        # High sensitivity
        assert engine._detect_sensitivity(EventType.TRAVEL, {}) == EventSensitivity.HIGH
        assert engine._detect_sensitivity(EventType.VACATION, {}) == EventSensitivity.HIGH
        
        # Medium sensitivity
        assert engine._detect_sensitivity(EventType.MEETING, {}) == EventSensitivity.MEDIUM
        assert engine._detect_sensitivity(EventType.WORK, {}) == EventSensitivity.MEDIUM
        
        # Low sensitivity
        assert engine._detect_sensitivity(EventType.REMINDER, {}) == EventSensitivity.LOW
    
    def test_create_automation(self):
        """Test automation creation."""
        engine = CalendarIntegrationEngine()
        
        auto_id = engine.create_automation(
            event_pattern="meeting",
            actions=[{"domain": "light", "service": "turn_off"}],
            event_type=EventType.MEETING,
            time_offset_minutes=5,
        )
        
        assert auto_id is not None
        assert auto_id in engine._automations
        assert engine._automations[auto_id].event_pattern == "meeting"
    
    def test_get_upcoming_events(self):
        """Test getting upcoming events."""
        engine = CalendarIntegrationEngine()
        engine.register_calendar("cal_test", "Test", "ha")
        
        now = datetime.now(timezone.utc)
        
        events = [
            {
                "event_id": "evt_1",
                "summary": "Soon",
                "start": (now + timedelta(hours=1)).isoformat(),
                "end": (now + timedelta(hours=2)).isoformat(),
            },
            {
                "event_id": "evt_2",
                "summary": "Later",
                "start": (now + timedelta(hours=10)).isoformat(),
                "end": (now + timedelta(hours=11)).isoformat(),
            },
        ]
        
        engine.import_events("cal_test", events)
        
        upcoming = engine.get_upcoming_events(hours_ahead=24)
        assert len(upcoming) >= 1
    
    def test_get_events_by_type(self):
        """Test getting events by type."""
        engine = CalendarIntegrationEngine()
        engine.register_calendar("cal_test", "Test", "ha")
        
        now = datetime.now(timezone.utc)
        
        events = [
            {
                "event_id": "evt_1",
                "summary": "Team Meeting",
                "start": (now + timedelta(hours=1)).isoformat(),
                "end": (now + timedelta(hours=2)).isoformat(),
            },
            {
                "event_id": "evt_2",
                "summary": "Vacation",
                "start": (now + timedelta(days=1)).isoformat(),
                "end": (now + timedelta(days=7)).isoformat(),
            },
        ]
        
        engine.import_events("cal_test", events)
        
        meetings = engine.get_events_by_type(EventType.MEETING)
        vacations = engine.get_events_by_type(EventType.VACATION)
        
        assert len(meetings) >= 1
        assert len(vacations) >= 1
    
    def test_presence_prediction_with_away_events(self):
        """Test presence prediction with away events."""
        engine = CalendarIntegrationEngine()
        engine.register_calendar("cal_test", "Test", "ha")
        
        now = datetime.now(timezone.utc)
        
        # Add work event (indicates absence)
        events = [
            {
                "event_id": "evt_1",
                "summary": "Office Day",
                "start": (now + timedelta(hours=1)).isoformat(),
                "end": (now + timedelta(hours=9)).isoformat(),
            },
        ]
        
        engine.import_events("cal_test", events)
        
        prediction = engine.get_presence_prediction(hours_ahead=4)
        
        assert "presence_probability" in prediction
        assert prediction["presence_probability"] < 0.8  # Reduced due to work event
        assert len(prediction["away_events"]) >= 1
    
    def test_presence_prediction_no_away_events(self):
        """Test presence prediction without away events."""
        engine = CalendarIntegrationEngine()
        engine.register_calendar("cal_test", "Test", "ha")
        
        # No events imported
        
        prediction = engine.get_presence_prediction(hours_ahead=4)
        
        assert prediction["presence_probability"] == 0.8  # Default
    
    def test_get_calendar_summary(self):
        """Test calendar summary."""
        engine = CalendarIntegrationEngine()
        
        # Register calendars
        engine.register_calendar("cal_1", "Calendar 1", "ha")
        engine.register_calendar("cal_2", "Calendar 2", "google")
        
        # Create automation
        engine.create_automation("meeting", [])
        
        summary = engine.get_calendar_summary()
        
        assert summary["total_calendars"] == 2
        assert summary["active_automations"] == 1
    
    def test_event_to_dict(self):
        """Test event serialization."""
        from copilot_core.calendar.integration_engine import CalendarEvent
        
        now = datetime.now(timezone.utc)
        
        event = CalendarEvent(
            event_id="evt_test",
            calendar_id="cal_test",
            summary="Test Event",
            description="Test description",
            start=now,
            end=now + timedelta(hours=1),
            all_day=False,
            event_type=EventType.MEETING,
            sensitivity=EventSensitivity.MEDIUM,
        )
        
        d = event.to_dict()
        
        assert d["event_id"] == "evt_test"
        assert d["summary"] == "Test Event"
        assert d["event_type"] == "meeting"
        assert d["sensitivity"] == "medium"
        assert "start" in d
        assert "end" in d
    
    def test_automation_to_dict(self):
        """Test automation serialization."""
        from copilot_core.calendar.integration_engine import CalendarAutomation
        
        auto = CalendarAutomation(
            automation_id="auto_test",
            event_pattern="meeting",
            event_type=EventType.MEETING,
            time_offset_minutes=10,
            actions=[{"domain": "light", "service": "turn_off"}],
            enabled=True,
        )
        
        d = auto.to_dict()
        
        assert d["automation_id"] == "auto_test"
        assert d["event_pattern"] == "meeting"
        assert d["event_type"] == "meeting"
        assert d["time_offset_minutes"] == 10
        assert d["enabled"] is True
    
    def test_datetime_parsing_iso(self):
        """Test ISO datetime parsing."""
        engine = CalendarIntegrationEngine()
        
        dt = engine._parse_datetime("2026-03-31T10:00:00Z")
        
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 31
    
    def test_datetime_parsing_already_datetime(self):
        """Test datetime parsing when already datetime."""
        engine = CalendarIntegrationEngine()
        
        now = datetime.now(timezone.utc)
        dt = engine._parse_datetime(now)
        
        assert dt == now
    
    def test_datetime_parsing_none(self):
        """Test datetime parsing of None."""
        engine = CalendarIntegrationEngine()
        
        dt = engine._parse_datetime(None)
        
        assert dt is None
    
    def test_events_sorted_by_start_time(self):
        """Test that events are sorted by start time."""
        engine = CalendarIntegrationEngine()
        engine.register_calendar("cal_test", "Test", "ha")
        
        now = datetime.now(timezone.utc)
        
        # Import events in random order
        events = [
            {"summary": "Third", "start": (now + timedelta(hours=3)).isoformat(), "end": (now + timedelta(hours=4)).isoformat()},
            {"summary": "First", "start": (now + timedelta(hours=1)).isoformat(), "end": (now + timedelta(hours=2)).isoformat()},
            {"summary": "Second", "start": (now + timedelta(hours=2)).isoformat(), "end": (now + timedelta(hours=3)).isoformat()},
        ]
        
        engine.import_events("cal_test", events)
        
        # Get upcoming and verify order
        upcoming = engine.get_upcoming_events(hours_ahead=24)
        
        assert upcoming[0]["summary"] == "First"
        assert upcoming[1]["summary"] == "Second"
        assert upcoming[2]["summary"] == "Third"
    
    def test_automation_pattern_matching(self):
        """Test automation pattern matching."""
        engine = CalendarIntegrationEngine()
        
        auto = engine.create_automation(
            event_pattern="meeting|call",
            actions=[],
        )
        
        from copilot_core.calendar.integration_engine import CalendarEvent
        
        # Matching event
        event_match = CalendarEvent(
            event_id="evt_1",
            calendar_id="cal_test",
            summary="Team Meeting",
            description=None,
            start=datetime.now(timezone.utc),
            end=datetime.now(timezone.utc),
            all_day=False,
        )
        
        # Non-matching event
        event_no_match = CalendarEvent(
            event_id="evt_2",
            calendar_id="cal_test",
            summary="Lunch",
            description=None,
            start=datetime.now(timezone.utc),
            end=datetime.now(timezone.utc),
            all_day=False,
        )
        
        assert engine._event_matches_automation(event_match, auto) is True
        assert engine._event_matches_automation(event_no_match, auto) is False
