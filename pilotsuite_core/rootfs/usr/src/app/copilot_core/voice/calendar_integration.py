"""Calendar Integration for Voice Hints.

Provides calendar-aware voice hints:
- Upcoming events
- Calendar density
- Schedule suggestions
- Alarm adjustments
- Meeting preparation

Features:
- Integration mit Calendar Smart Scheduler
- DE/EN Sprachunterstützung
- Kontextbewusste Terminhinweise
- Mood-aware scheduling suggestions
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from .context_builder import VoiceContext
from .proactive import ProactiveHint, HintType, HintPriority

_LOGGER = logging.getLogger(__name__)


class CalendarHintType(str, Enum):
    """Calendar-specific hint types."""
    
    UPCOMING_EVENT = "upcoming_event"
    CALENDAR_DENSITY = "calendar_density"
    MEETING_PREPARATION = "meeting_preparation"
    TRAVEL_TIME = "travel_time"
    FREE_SLOT = "free_slot"
    SCHEDULE_CONFLICT = "schedule_conflict"
    ALARM_SUGGESTION = "alarm_suggestion"


@dataclass
class CalendarEventContext:
    """Calendar event context for voice hints."""
    
    event_id: str
    title: str
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    description: Optional[str] = None
    attendees: List[str] = field(default_factory=list)
    is_all_day: bool = False
    calendar_name: str = "default"
    
    # Computed fields
    time_until_start: Optional[timedelta] = None
    duration_minutes: int = 0
    
    def __post_init__(self):
        if self.start_time and self.end_time:
            self.duration_minutes = int((self.end_time - self.start_time).total_seconds() / 60)
        
        if self.start_time:
            now = datetime.now(timezone.utc)
            if self.start_time.tzinfo is None:
                self.start_time = self.start_time.replace(tzinfo=timezone.utc)
            self.time_until_start = self.start_time - now
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "location": self.location,
            "description": self.description,
            "attendees": self.attendees,
            "is_all_day": self.is_all_day,
            "calendar_name": self.calendar_name,
            "time_until_start_minutes": (
                int(self.time_until_start.total_seconds() / 60)
                if self.time_until_start else None
            ),
            "duration_minutes": self.duration_minutes,
        }


@dataclass
class CalendarDaySummary:
    """Summary of a calendar day for voice hints."""
    
    date: str  # ISO date
    total_events: int
    busy_minutes: int
    free_minutes: int
    first_event_time: Optional[str] = None
    last_event_time: Optional[str] = None
    busiest_hour: Optional[int] = None  # 0-23
    has_conflicts: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "total_events": self.total_events,
            "busy_minutes": self.busy_minutes,
            "free_minutes": self.free_minutes,
            "first_event_time": self.first_event_time,
            "last_event_time": self.last_event_time,
            "busiest_hour": self.busiest_hour,
            "has_conflicts": self.has_conflicts,
        }


class CalendarVoiceIntegration:
    """Integrates calendar context into voice hints.
    
    Usage:
    ```python
    calendar_voice = CalendarVoiceIntegration(calendar_engine)
    hints = calendar_voice.generate_calendar_hints(context)
    ```
    """
    
    # Time thresholds for hints (minutes)
    URGENT_EVENT_THRESHOLD = 15  # Hint if event starts within 15 min
    UPCOMING_EVENT_THRESHOLD = 60  # Hint if event starts within 60 min
    TRAVEL_TIME_THRESHOLD = 30  # Hint travel time if >30 min away
    
    # Calendar hint messages (DE)
    UPCOMING_EVENT_DE = {
        "urgent": (
            "Nächster Termin in {minutes} Minuten",
            "Dein nächster Termin '{title}' beginnt in {minutes} Minuten.",
        ),
        "soon": (
            "Termin in {minutes} Minuten",
            "In {minutes} Minuten startet '{title}'.",
        ),
        "today": (
            "Heutiger Termin",
            "Heute steht '{title}' um {time} an.",
        ),
    }
    
    # Calendar hint messages (EN)
    UPCOMING_EVENT_EN = {
        "urgent": (
            "Next event in {minutes} minutes",
            "Your next event '{title}' starts in {minutes} minutes.",
        ),
        "soon": (
            "Event in {minutes} minutes",
            "'{title}' starts in {minutes} minutes.",
        ),
        "today": (
            "Today's event",
            "Today you have '{title}' at {time}.",
        ),
    }
    
    # Calendar density messages (DE)
    DENSITY_DE = {
        "heavy": (
            "Voller Terminkalender",
            "Heute sind {count} Termine geplant ({busy_minutes} Minuten belegt).",
        ),
        "moderate": (
            "Mittlere Auslastung",
            "Heute stehen {count} Termine an.",
        ),
        "light": (
            "Entspannter Tag",
            "Heute ist wenig geplant - nur {count} Termine.",
        ),
    }
    
    # Calendar density messages (EN)
    DENSITY_EN = {
        "heavy": (
            "Busy day",
            "You have {count} events scheduled today ({busy_minutes} minutes busy).",
        ),
        "moderate": (
            "Moderate schedule",
            "You have {count} events today.",
        ),
        "light": (
            "Light day",
            "Today is relaxed - only {count} events.",
        ),
    }
    
    # Alarm suggestion messages (DE)
    ALARM_DE = {
        "earlier": (
            "Wecker-Empfehlung",
            "Bei deinem ersten Termin um {time} solltest du um {suggested_time} aufstehen.",
        ),
        "later": (
            "Ausschlafen möglich",
            "Dein erster Termin ist erst um {time}. Du kannst bis {suggested_time} schlafen.",
        ),
    }
    
    # Alarm suggestion messages (EN)
    ALARM_EN = {
        "earlier": (
            "Alarm suggestion",
            "With your first event at {time}, you should wake up at {suggested_time}.",
        ),
        "later": (
            "Sleep in possible",
            "Your first event is at {time}. You can sleep until {suggested_time}.",
        ),
    }
    
    def __init__(
        self,
        calendar_engine: Optional[Any] = None,
        mood_engine: Optional[Any] = None,
    ):
        """Initialize calendar voice integration.
        
        Args:
            calendar_engine: Calendar integration engine
            mood_engine: Mood engine for mood-aware suggestions
        """
        self.calendar_engine = calendar_engine
        self.mood_engine = mood_engine
    
    def generate_calendar_hints(
        self,
        context: VoiceContext,
        language: str = "de",
    ) -> List[ProactiveHint]:
        """Generate calendar-aware voice hints.
        
        Args:
            context: Current voice context
            language: Language code (de/en)
            
        Returns:
            List of calendar-related ProactiveHint
        """
        hints = []
        
        if self.calendar_engine is None:
            return hints
        
        # Check upcoming events
        hints.extend(self._check_upcoming_events(context, language))
        
        # Check calendar density
        hints.extend(self._check_calendar_density(context, language))
        
        # Check alarm suggestions
        hints.extend(self._check_alarm_suggestions(context, language))
        
        # Check meeting preparation
        hints.extend(self._check_meeting_preparation(context, language))
        
        return hints
    
    def _check_upcoming_events(
        self,
        context: VoiceContext,
        language: str,
    ) -> List[ProactiveHint]:
        """Check for upcoming events and generate hints."""
        hints = []
        
        try:
            # Get upcoming events from calendar engine
            upcoming = self._get_upcoming_events(limit=3)
            
            for event in upcoming:
                if event.time_until_start is None:
                    continue
                
                minutes_until = int(event.time_until_start.total_seconds() / 60)
                
                # Skip past events
                if minutes_until < 0:
                    continue
                
                # Determine urgency level
                if minutes_until <= self.URGENT_EVENT_THRESHOLD:
                    urgency = "urgent"
                    priority = HintPriority.HIGH
                elif minutes_until <= self.UPCOMING_EVENT_THRESHOLD:
                    urgency = "soon"
                    priority = HintPriority.MEDIUM
                else:
                    urgency = "today"
                    priority = HintPriority.LOW
                
                # Get localized messages
                if language == "de":
                    templates = self.UPCOMING_EVENT_DE
                else:
                    templates = self.UPCOMING_EVENT_EN
                
                title_template = templates[urgency][0]
                message_template = templates[urgency][1]
                
                # Format time
                start_time_str = event.start_time.strftime("%H:%M") if event.start_time else ""
                
                title = title_template.format(minutes=minutes_until)
                message = message_template.format(
                    minutes=minutes_until,
                    title=event.title,
                    time=start_time_str,
                )
                
                hint = ProactiveHint(
                    hint_type=HintType.REMINDER,
                    priority=priority,
                    title_de=title,
                    title_en=title,  # English title same for simplicity
                    message_de=message if language == "de" else message,
                    message_en=message,
                    suggested_action={
                        "kind": "calendar_event_review",
                        "event_id": event.event_id,
                        "time_until_start_minutes": minutes_until,
                    },
                    context={
                        "contract": "CalendarEventVoiceHintV1",
                        "event": event.to_dict(),
                        "urgency": urgency,
                    },
                )
                hints.append(hint)
        
        except Exception as e:
            _LOGGER.debug("Failed to check upcoming events: %s", e)
        
        return hints
    
    def _check_calendar_density(
        self,
        context: VoiceContext,
        language: str,
    ) -> List[ProactiveHint]:
        """Check calendar density and generate hints."""
        hints = []
        
        try:
            # Get today's summary
            today_summary = self._get_day_summary()
            
            if today_summary is None:
                return hints
            
            # Determine density level
            if today_summary.busy_minutes > 480:  # >8 hours
                density = "heavy"
                priority = HintPriority.MEDIUM
            elif today_summary.busy_minutes > 240:  # >4 hours
                density = "moderate"
                priority = HintPriority.LOW
            else:
                density = "light"
                priority = HintPriority.LOW
            
            # Get localized messages
            if language == "de":
                templates = self.DENSITY_DE
            else:
                templates = self.DENSITY_EN
            
            title_template = templates[density][0]
            message_template = templates[density][1]
            
            title = title_template
            message = message_template.format(
                count=today_summary.total_events,
                busy_minutes=today_summary.busy_minutes,
            )
            
            hint = ProactiveHint(
                hint_type=HintType.REMINDER,
                priority=priority,
                title_de=title,
                title_en=title,
                message_de=message if language == "de" else message,
                message_en=message,
                context={
                    "contract": "CalendarDensityVoiceHintV1",
                    "day_summary": today_summary.to_dict(),
                    "density": density,
                },
            )
            hints.append(hint)
        
        except Exception as e:
            _LOGGER.debug("Failed to check calendar density: %s", e)
        
        return hints
    
    def _check_alarm_suggestions(
        self,
        context: VoiceContext,
        language: str,
    ) -> List[ProactiveHint]:
        """Generate alarm adjustment suggestions based on calendar."""
        hints = []
        
        try:
            # Get first event of tomorrow
            tomorrow_first = self._get_first_event_tomorrow()
            
            if tomorrow_first is None:
                return hints
            
            # Calculate suggested wake-up time (2 hours before first event)
            if tomorrow_first.start_time:
                suggested_wake = tomorrow_first.start_time - timedelta(hours=2)
                suggested_time_str = suggested_wake.strftime("%H:%M")
                event_time_str = tomorrow_first.start_time.strftime("%H:%M")
                
                # Determine if earlier or later than typical 7am
                typical_wake = tomorrow_first.start_time.replace(hour=7, minute=0)
                if suggested_wake < typical_wake:
                    suggestion_type = "earlier"
                else:
                    suggestion_type = "later"
                
                # Get localized messages
                if language == "de":
                    templates = self.ALARM_DE
                else:
                    templates = self.ALARM_EN
                
                title_template = templates[suggestion_type][0]
                message_template = templates[suggestion_type][1]
                
                title = title_template
                message = message_template.format(
                    time=event_time_str,
                    suggested_time=suggested_time_str,
                )
                
                hint = ProactiveHint(
                    hint_type=HintType.REMINDER,
                    priority=HintPriority.LOW,
                    title_de=title,
                    title_en=title,
                    message_de=message if language == "de" else message,
                    message_en=message,
                    suggested_action={
                        "kind": "alarm_adjustment",
                        "suggested_wake_time": suggested_wake.isoformat(),
                        "first_event_time": tomorrow_first.start_time.isoformat(),
                        "first_event_title": tomorrow_first.title,
                    },
                    context={
                        "contract": "AlarmSuggestionVoiceHintV1",
                        "first_event": tomorrow_first.to_dict(),
                        "suggestion_type": suggestion_type,
                    },
                )
                hints.append(hint)
        
        except Exception as e:
            _LOGGER.debug("Failed to check alarm suggestions: %s", e)
        
        return hints
    
    def _check_meeting_preparation(
        self,
        context: VoiceContext,
        language: str,
    ) -> List[ProactiveHint]:
        """Check for meetings that need preparation."""
        hints = []
        
        try:
            # Get meetings in next 2 hours
            upcoming_meetings = self._get_upcoming_events(limit=5)
            
            for event in upcoming_meetings:
                if event.time_until_start is None:
                    continue
                
                minutes_until = int(event.time_until_start.total_seconds() / 60)
                
                # Only hint for meetings 30-60 min away (preparation time)
                if 30 <= minutes_until <= 60:
                    # Check if meeting has location (might need travel time)
                    if event.location:
                        hint = ProactiveHint(
                            hint_type=HintType.REMINDER,
                            priority=HintPriority.MEDIUM,
                            title_de="Vorbereitung für Termin",
                            title_en="Meeting Preparation",
                            message_de=(
                                f"Termin '{event.title}' beginnt in {minutes_until} Minuten "
                                f"{'bei ' + event.location if event.location else ''}."
                            ),
                            message_en=(
                                f"Meeting '{event.title}' starts in {minutes_until} minutes"
                                f"{' at ' + event.location if event.location else ''}."
                            ),
                            suggested_action={
                                "kind": "meeting_preparation",
                                "event_id": event.event_id,
                                "travel_time_hint": True,
                            },
                            context={
                                "contract": "MeetingPrepVoiceHintV1",
                                "event": event.to_dict(),
                            },
                        )
                        hints.append(hint)
        
        except Exception as e:
            _LOGGER.debug("Failed to check meeting preparation: %s", e)
        
        return hints
    
    def _get_upcoming_events(self, limit: int = 3) -> List[CalendarEventContext]:
        """Get upcoming events from calendar engine."""
        if self.calendar_engine is None:
            return []
        
        try:
            # Try to call calendar engine's get_upcoming method
            if hasattr(self.calendar_engine, "get_upcoming_events"):
                events_data = self.calendar_engine.get_upcoming_events(limit=limit)
            elif hasattr(self.calendar_engine, "upcoming"):
                events_data = self.calendar_engine.upcoming(limit=limit)
            else:
                return []
            
            events = []
            for evt in events_data[:limit]:
                event = CalendarEventContext(
                    event_id=evt.get("event_id", evt.get("id", "")),
                    title=evt.get("title", evt.get("summary", "")),
                    start_time=self._parse_datetime(evt.get("start")),
                    end_time=self._parse_datetime(evt.get("end")),
                    location=evt.get("location"),
                    description=evt.get("description"),
                    attendees=evt.get("attendees", []),
                    is_all_day=evt.get("is_all_day", False),
                    calendar_name=evt.get("calendar_name", "default"),
                )
                events.append(event)
            
            return events
        
        except Exception as e:
            _LOGGER.debug("Error fetching upcoming events: %s", e)
            return []
    
    def _get_day_summary(self, date: Optional[str] = None) -> Optional[CalendarDaySummary]:
        """Get calendar day summary."""
        if self.calendar_engine is None:
            return None
        
        try:
            if date is None:
                date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
            # Try to call calendar engine's day summary method
            if hasattr(self.calendar_engine, "get_day_summary"):
                summary_data = self.calendar_engine.get_day_summary(date=date)
            elif hasattr(self.calendar_engine, "day_summary"):
                summary_data = self.calendar_engine.day_summary(date=date)
            else:
                return None
            
            return CalendarDaySummary(
                date=summary_data.get("date", date),
                total_events=summary_data.get("total_events", 0),
                busy_minutes=summary_data.get("busy_minutes", 0),
                free_minutes=summary_data.get("free_minutes", 0),
                first_event_time=summary_data.get("first_event_time"),
                last_event_time=summary_data.get("last_event_time"),
                busiest_hour=summary_data.get("busiest_hour"),
                has_conflicts=summary_data.get("has_conflicts", False),
            )
        
        except Exception as e:
            _LOGGER.debug("Error fetching day summary: %s", e)
            return None
    
    def _get_first_event_tomorrow(self) -> Optional[CalendarEventContext]:
        """Get first event tomorrow."""
        if self.calendar_engine is None:
            return None
        
        try:
            tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
            summary = self._get_day_summary(tomorrow)
            
            if summary is None or summary.total_events == 0:
                return None
            
            # Get events for tomorrow
            events = self._get_upcoming_events(limit=10)
            
            # Filter to tomorrow's events and find first
            tomorrow_date = datetime.strptime(tomorrow, "%Y-%m-%d").date()
            for event in events:
                if event.start_time and event.start_time.date() == tomorrow_date:
                    return event
            
            return None
        
        except Exception as e:
            _LOGGER.debug("Error fetching first event tomorrow: %s", e)
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
    
    def integrate_with_proactive_hints(
        self,
        proactive_hints: ProactiveVoiceHints,
        context: VoiceContext,
        language: str = "de",
    ) -> List[ProactiveHint]:
        """Integrate calendar hints into proactive hints stream.
        
        This is a helper method to merge calendar hints with other proactive hints.
        """
        calendar_hints = self.generate_calendar_hints(context, language)
        
        # Merge and sort by priority
        all_hints = list(proactive_hints.generate_hints(context)) + calendar_hints
        
        priority_order = {
            HintPriority.CRITICAL: 0,
            HintPriority.HIGH: 1,
            HintPriority.MEDIUM: 2,
            HintPriority.LOW: 3,
        }
        all_hints.sort(key=lambda h: priority_order.get(h.priority, 99))
        
        return all_hints


# Lazy import to avoid circular dependencies
def _get_proactive_hints_class():
    from .proactive import ProactiveVoiceHints
    return ProactiveVoiceHints


# Global integration instance (lazy-initialized)
_calendar_integration_engine = None


def get_calendar_integration_engine():
    """Get or create calendar integration engine instance.
    
    Returns the CalendarIntegrationEngine from the calendar module
    or None if not available.
    """
    global _calendar_integration_engine
    
    if _calendar_integration_engine is None:
        try:
            from copilot_core.calendar.integration_engine import CalendarIntegrationEngine
            _calendar_integration_engine = CalendarIntegrationEngine()
        except ImportError:
            _LOGGER.debug("CalendarIntegrationEngine not available")
            return None
        except Exception as e:
            _LOGGER.debug("Failed to initialize calendar integration engine: %s", e)
            return None
    
    return _calendar_integration_engine
