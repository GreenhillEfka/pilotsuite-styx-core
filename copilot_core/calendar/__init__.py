"""Calendar module - Smart scheduling with mood awareness and multi-source integration.

This module provides intelligent calendar management that integrates
with the Mood Engine and Habitus system for context-aware scheduling.

Calendar Sources:
- ICS/iCal files and URLs
- Google Calendar API
- CalDAV servers (Nextcloud, ownCloud, iCloud)
- Home Assistant calendars
"""

from .smart_scheduler import SmartScheduler, ScheduleRecommendation
from .mood_aware import MoodAwareScheduler, MoodCalendarConfig
from .suggestions import ScheduleSuggester, ScheduleSuggestion

# Calendar integration
from .ics_calendar import ICSCalendarReader, ICSEvent, get_ics_reader, reset_ics_reader
from .google_calendar import (
    GoogleCalendarClient,
    GoogleCalendarConfig,
    GoogleCalendarEvent,
    get_google_calendar_client,
    reset_google_calendar_client,
)
from .caldav_calendar import (
    CalDAVCalendarClient,
    CalDAVConfig,
    CalDAVCalendarEvent,
    get_caldav_client,
    remove_caldav_client,
    reset_caldav_clients,
)
from .calendar_manager import (
    CalendarManager,
    CalendarSource,
    CalendarSourceConfig,
    CalendarSyncStatus,
    UnifiedCalendarEvent,
    get_calendar_manager,
    reset_calendar_manager,
)

__all__ = [
    # Smart scheduling
    "SmartScheduler",
    "ScheduleRecommendation",
    "MoodAwareScheduler",
    "MoodCalendarConfig",
    "ScheduleSuggester",
    "ScheduleSuggestion",
    # ICS calendar
    "ICSCalendarReader",
    "ICSEvent",
    "get_ics_reader",
    "reset_ics_reader",
    # Google Calendar
    "GoogleCalendarClient",
    "GoogleCalendarConfig",
    "GoogleCalendarEvent",
    "get_google_calendar_client",
    "reset_google_calendar_client",
    # CalDAV
    "CalDAVCalendarClient",
    "CalDAVConfig",
    "CalDAVCalendarEvent",
    "get_caldav_client",
    "remove_caldav_client",
    "reset_caldav_clients",
    # Unified manager
    "CalendarManager",
    "CalendarSource",
    "CalendarSourceConfig",
    "CalendarSyncStatus",
    "UnifiedCalendarEvent",
    "get_calendar_manager",
    "reset_calendar_manager",
]
