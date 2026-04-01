"""Calendar Integration — Slice 19.

Calendar integration for PilotSuite Core.

Features:
- Calendar event ingestion (HA, Google, iCal)
- Event-based automations
- Presence prediction from calendar
- Calendar-aware routines
- Event conflict detection
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class EventSensitivity(Enum):
    """How much an event should affect automations."""
    NONE = "none"  # No automation impact
    LOW = "low"  # Minor adjustments
    MEDIUM = "medium"  # Standard adjustments
    HIGH = "high"  # Major automation changes


class EventType(Enum):
    """Type of calendar event."""
    MEETING = "meeting"
    APPOINTMENT = "appointment"
    TRAVEL = "travel"
    VACATION = "vacation"
    WORK = "work"
    PERSONAL = "personal"
    REMINDER = "reminder"
    OTHER = "other"


@dataclass
class CalendarEvent:
    """Calendar event."""
    event_id: str
    calendar_id: str
    summary: str
    description: Optional[str]
    start: datetime
    end: datetime
    all_day: bool
    location: Optional[str] = None
    attendees: List[str] = field(default_factory=list)
    event_type: EventType = EventType.OTHER
    sensitivity: EventSensitivity = EventSensitivity.MEDIUM
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "calendar_id": self.calendar_id,
            "summary": self.summary,
            "description": self.description,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "all_day": self.all_day,
            "location": self.location,
            "attendees": self.attendees,
            "event_type": self.event_type.value,
            "sensitivity": self.sensitivity.value,
        }


@dataclass
class CalendarAutomation:
    """Automation triggered by calendar event."""
    automation_id: str
    event_pattern: str  # Regex pattern to match event summary
    event_type: Optional[EventType]
    time_offset_minutes: int  # Minutes before event to trigger
    actions: List[Dict[str, Any]]
    enabled: bool = True
    last_triggered: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "automation_id": self.automation_id,
            "event_pattern": self.event_pattern,
            "event_type": self.event_type.value if self.event_type else None,
            "time_offset_minutes": self.time_offset_minutes,
            "actions": self.actions,
            "enabled": self.enabled,
            "last_triggered": self.last_triggered,
        }


class CalendarIntegrationEngine:
    """Calendar integration engine."""
    
    def __init__(self):
        self._calendars: Dict[str, Dict[str, Any]] = {}
        self._events: Dict[str, List[CalendarEvent]] = {}  # calendar_id -> events
        self._automations: Dict[str, CalendarAutomation] = {}
        self._automation_counter = 0
        
        # Event type keywords for classification
        self._event_type_keywords = {
            EventType.MEETING: ["meeting", "call", "zoom", "teams", "conference"],
            EventType.APPOINTMENT: ["appointment", "termin", "arzt", "dentist"],
            EventType.TRAVEL: ["travel", "trip", "flight", "zug", "bahn", "airport"],
            EventType.VACATION: ["vacation", "urlaub", "holiday", "reise"],
            EventType.WORK: ["work", "arbeit", "office", "büro"],
            EventType.PERSONAL: ["personal", "privat", "family", "geburtstag"],
        }
    
    def register_calendar(self, calendar_id: str, name: str, source: str,
                         entity_id: Optional[str] = None) -> str:
        """Register a calendar."""
        self._calendars[calendar_id] = {
            "calendar_id": calendar_id,
            "name": name,
            "source": source,  # "ha", "google", "ical", etc.
            "entity_id": entity_id,
            "enabled": True,
        }
        
        if calendar_id not in self._events:
            self._events[calendar_id] = []
        
        return calendar_id
    
    def import_events(self, calendar_id: str, events_data: List[Dict[str, Any]]) -> int:
        """Import events into a calendar."""
        if calendar_id not in self._calendars:
            return 0
        
        imported = 0
        for event_data in events_data:
            event = self._parse_event(calendar_id, event_data)
            if event:
                self._events[calendar_id].append(event)
                imported += 1
        
        # Sort events by start time
        self._events[calendar_id].sort(key=lambda e: e.start)
        
        return imported
    
    def _parse_event(self, calendar_id: str, data: Dict[str, Any]) -> Optional[CalendarEvent]:
        """Parse event data into CalendarEvent."""
        try:
            # Parse start/end
            start = self._parse_datetime(data.get("start"))
            end = self._parse_datetime(data.get("end"))
            
            if not start or not end:
                return None
            
            # Detect event type from summary
            summary = data.get("summary", "").lower()
            event_type = self._detect_event_type(summary)
            
            # Detect sensitivity
            sensitivity = self._detect_sensitivity(event_type, data)
            
            return CalendarEvent(
                event_id=data.get("event_id", f"evt_{len(self._events.get(calendar_id, [])) + 1}"),
                calendar_id=calendar_id,
                summary=data.get("summary", "Unknown Event"),
                description=data.get("description"),
                start=start,
                end=end,
                all_day=data.get("all_day", False),
                location=data.get("location"),
                attendees=data.get("attendees", []),
                event_type=event_type,
                sensitivity=sensitivity,
            )
        except Exception as exc:
            logger.warning("Failed to parse event: %s", exc)
            return None
    
    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime from various formats."""
        if value is None:
            return None
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        return None
    
    def _detect_event_type(self, summary: str) -> EventType:
        """Detect event type from summary."""
        for event_type, keywords in self._event_type_keywords.items():
            if any(kw in summary for kw in keywords):
                return event_type
        return EventType.OTHER
    
    def _detect_sensitivity(self, event_type: EventType, data: Dict[str, Any]) -> EventSensitivity:
        """Detect event sensitivity."""
        # High sensitivity events
        if event_type in (EventType.TRAVEL, EventType.VACATION):
            return EventSensitivity.HIGH
        
        # Medium sensitivity
        if event_type in (EventType.MEETING, EventType.APPOINTMENT, EventType.WORK):
            return EventSensitivity.MEDIUM
        
        # Low sensitivity
        if event_type == EventType.REMINDER:
            return EventSensitivity.LOW
        
        return EventSensitivity.NONE
    
    def create_automation(self, event_pattern: str, actions: List[Dict[str, Any]],
                         event_type: Optional[EventType] = None,
                         time_offset_minutes: int = 15) -> str:
        """Create calendar-based automation."""
        self._automation_counter += 1
        
        automation = CalendarAutomation(
            automation_id=f"cal_auto_{self._automation_counter}",
            event_pattern=event_pattern,
            event_type=event_type,
            time_offset_minutes=time_offset_minutes,
            actions=actions,
        )
        
        self._automations[automation.automation_id] = automation
        return automation.automation_id
    
    def get_upcoming_events(self, calendar_id: Optional[str] = None,
                           hours_ahead: int = 24) -> List[Dict[str, Any]]:
        """Get upcoming events."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours_ahead)
        
        events = []
        
        calendars = [calendar_id] if calendar_id else list(self._calendars.keys())
        
        for cal_id in calendars:
            if cal_id not in self._events:
                continue
            
            for event in self._events[cal_id]:
                if now <= event.start <= cutoff:
                    events.append(event)
        
        # Sort by start time
        events.sort(key=lambda e: e.start)
        
        return [e.to_dict() for e in events]
    
    def get_events_by_type(self, event_type: EventType,
                          hours_ahead: int = 168) -> List[Dict[str, Any]]:
        """Get events of specific type."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours_ahead)
        
        events = []
        
        for cal_events in self._events.values():
            for event in cal_events:
                if event.event_type == event_type and now <= event.start <= cutoff:
                    events.append(event)
        
        events.sort(key=lambda e: e.start)
        return [e.to_dict() for e in events]
    
    def check_automations(self) -> List[Dict[str, Any]]:
        """Check and trigger pending automations."""
        now = datetime.now(timezone.utc)
        triggered = []
        
        for automation in self._automations.values():
            if not automation.enabled:
                continue
            
            for event in self._get_all_events():
                # Check if event matches automation
                if not self._event_matches_automation(event, automation):
                    continue
                
                # Check if automation should trigger now
                trigger_time = event.start - timedelta(minutes=automation.time_offset_minutes)
                
                # Allow 5 minute window for trigger
                if trigger_time - timedelta(minutes=5) <= now <= trigger_time + timedelta(minutes=5):
                    triggered.append({
                        "automation_id": automation.automation_id,
                        "event_id": event.event_id,
                        "event_summary": event.summary,
                        "trigger_time": trigger_time.isoformat(),
                        "actions": automation.actions,
                    })
                    
                    automation.last_triggered = now.isoformat()
        
        return triggered
    
    def _get_all_events(self) -> List[CalendarEvent]:
        """Get all events from all calendars."""
        events = []
        for cal_events in self._events.values():
            events.extend(cal_events)
        return events
    
    def _event_matches_automation(self, event: CalendarEvent,
                                  automation: CalendarAutomation | str) -> bool:
        """Check if event matches automation criteria."""
        import re

        if isinstance(automation, str):
            automation = self._automations.get(automation)
            if automation is None:
                return False
        
        # Check event type
        if automation.event_type and event.event_type != automation.event_type:
            return False
        
        # Check pattern
        if automation.event_pattern:
            if not re.search(automation.event_pattern, event.summary, re.IGNORECASE):
                return False
        
        return True
    
    def get_presence_prediction(self, hours_ahead: int = 4) -> Dict[str, Any]:
        """Predict presence based on calendar events."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours_ahead)
        
        away_events = []
        
        for event in self._get_all_events():
            if not now <= event.start <= cutoff:
                continue
            
            # Events that indicate absence
            if event.event_type in (EventType.WORK, EventType.TRAVEL, EventType.APPOINTMENT):
                away_events.append(event)
        
        # Calculate presence probability
        if not away_events:
            presence_probability = 0.8  # Default: likely home
        else:
            # More away events = lower presence probability
            presence_probability = max(0.1, 0.8 - (len(away_events) * 0.2))
        
        return {
            "presence_probability": presence_probability,
            "away_events": [e.to_dict() for e in away_events],
            "prediction_until": cutoff.isoformat(),
        }
    
    def get_calendar_summary(self) -> Dict[str, Any]:
        """Get calendar integration summary."""
        total_events = sum(len(events) for events in self._events.values())
        upcoming_24h = len(self.get_upcoming_events(hours_ahead=24))
        active_automations = len([a for a in self._automations.values() if a.enabled])
        
        return {
            "total_calendars": len(self._calendars),
            "total_events": total_events,
            "upcoming_24h": upcoming_24h,
            "active_automations": active_automations,
        }


def create_calendar_integration_engine() -> CalendarIntegrationEngine:
    """Factory function to create calendar integration engine."""
    return CalendarIntegrationEngine()
