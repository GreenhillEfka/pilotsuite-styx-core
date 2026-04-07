"""Unified Calendar Manager for PilotSuite.

Provides a unified API for managing multiple calendar sources:
- ICS/iCal files and URLs
- Google Calendar
- CalDAV servers (Nextcloud, ownCloud, iCloud, etc.)

Features:
- Multi-source calendar aggregation
- Unified event querying
- Sync management
- Presence prediction from calendar
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

from .ics_calendar import ICSCalendarReader, get_ics_reader, ICSEvent
from .google_calendar import (
    GoogleCalendarClient,
    GoogleCalendarConfig,
    GoogleCalendarEvent,
    get_google_calendar_client,
)
from .caldav_calendar import (
    CalDAVCalendarClient,
    CalDAVConfig,
    CalDAVCalendarEvent,
    get_caldav_client,
)


class CalendarSource(str, Enum):
    """Calendar source types."""
    ICS = "ics"
    GOOGLE = "google"
    CALDAV = "caldav"
    HA = "homeassistant"


class CalendarSyncStatus(str, Enum):
    """Calendar sync status."""
    PENDING = "pending"
    SYNCING = "syncing"
    READY = "ready"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class CalendarSourceConfig:
    """Configuration for a calendar source."""
    source_id: str
    source_type: CalendarSource
    name: str
    enabled: bool = True
    
    # ICS-specific
    ics_path: Optional[str] = None
    ics_url: Optional[str] = None
    
    # Google-specific
    google_credentials_path: Optional[str] = None
    google_token_path: Optional[str] = None
    google_service_account_path: Optional[str] = None
    google_calendar_ids: List[str] = field(default_factory=list)
    
    # CalDAV-specific
    caldav_url: Optional[str] = None
    caldav_username: Optional[str] = None
    caldav_password: Optional[str] = None
    caldav_calendar_url: Optional[str] = None
    caldav_calendar_name: Optional[str] = None
    caldav_ssl_verify: bool = True
    
    # Sync settings
    sync_interval_minutes: int = 15
    last_sync: Optional[datetime] = None
    sync_status: CalendarSyncStatus = CalendarSyncStatus.PENDING
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "name": self.name,
            "enabled": self.enabled,
            "sync_interval_minutes": self.sync_interval_minutes,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "sync_status": self.sync_status.value,
        }


@dataclass
class UnifiedCalendarEvent:
    """Unified calendar event from any source."""
    event_id: str
    source_id: str
    source_type: CalendarSource
    calendar_id: str
    calendar_name: str
    summary: str
    description: Optional[str]
    start: datetime
    end: datetime
    all_day: bool
    location: Optional[str] = None
    organizer: Optional[str] = None
    attendees: List[str] = field(default_factory=list)
    url: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "calendar_id": self.calendar_id,
            "calendar_name": self.calendar_name,
            "summary": self.summary,
            "description": self.description,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "all_day": self.all_day,
            "location": self.location,
            "organizer": self.organizer,
            "attendees": self.attendees,
            "url": self.url,
        }
    
    @classmethod
    def from_ics(cls, source_id: str, calendar_name: str,
                 event: ICSEvent) -> "UnifiedCalendarEvent":
        """Create from ICS event."""
        return cls(
            event_id=f"ics_{event.uid}",
            source_id=source_id,
            source_type=CalendarSource.ICS,
            calendar_id=calendar_name,
            calendar_name=calendar_name,
            summary=event.summary,
            description=event.description,
            start=event.start,
            end=event.end,
            all_day=event.all_day,
            location=event.location,
            organizer=event.organizer,
            attendees=event.attendees,
            raw_data=event.to_dict(),
        )
    
    @classmethod
    def from_google(cls, source_id: str, calendar_name: str,
                    event: GoogleCalendarEvent) -> "UnifiedCalendarEvent":
        """Create from Google Calendar event."""
        return cls(
            event_id=f"google_{event.event_id}",
            source_id=source_id,
            source_type=CalendarSource.GOOGLE,
            calendar_id=event.calendar_id,
            calendar_name=calendar_name,
            summary=event.summary,
            description=event.description,
            start=event.start,
            end=event.end,
            all_day=event.all_day,
            location=event.location,
            organizer=event.organizer,
            attendees=[a.get("email", "") for a in event.attendees if a.get("email")],
            url=event.html_link,
            raw_data=event.to_dict(),
        )
    
    @classmethod
    def from_caldav(cls, source_id: str, calendar_name: str,
                    event: CalDAVCalendarEvent) -> "UnifiedCalendarEvent":
        """Create from CalDAV event."""
        return cls(
            event_id=f"caldav_{event.uid}",
            source_id=source_id,
            source_type=CalendarSource.CALDAV,
            calendar_id=event.calendar_url,
            calendar_name=calendar_name,
            summary=event.summary,
            description=event.description,
            start=event.start,
            end=event.end,
            all_day=event.all_day,
            location=event.location,
            organizer=event.organizer,
            attendees=event.attendees,
            raw_data=event.to_dict(),
        )


class CalendarManager:
    """Unified calendar manager for PilotSuite."""
    
    def __init__(self):
        self._sources: Dict[str, CalendarSourceConfig] = {}
        self._events: Dict[str, List[UnifiedCalendarEvent]] = {}  # source_id -> events
        self._ics_reader = get_ics_reader()
        self._google_client: Optional[GoogleCalendarClient] = None
        self._caldav_clients: Dict[str, CalDAVCalendarClient] = {}
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize the calendar manager.
        
        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True
        
        try:
            # Initialize ICS reader
            self._ics_reader = get_ics_reader()
            
            # Try to initialize Google client (may fail if not configured)
            self._google_client = get_google_calendar_client()
            
            self._initialized = True
            logger.info("Calendar manager initialized")
            return True
        except Exception as exc:
            logger.error("Failed to initialize calendar manager: %s", exc)
            return False
    
    def add_source(self, config: CalendarSourceConfig) -> bool:
        """Add a calendar source.
        
        Args:
            config: Source configuration
            
        Returns:
            True if added successfully
        """
        if config.source_id in self._sources:
            logger.warning("Source %s already exists", config.source_id)
            return False
        
        self._sources[config.source_id] = config
        self._events[config.source_id] = []
        
        logger.info("Added calendar source: %s (%s)", config.name, config.source_type.value)
        return True
    
    def remove_source(self, source_id: str) -> bool:
        """Remove a calendar source.
        
        Args:
            source_id: Source identifier
            
        Returns:
            True if removed
        """
        if source_id not in self._sources:
            return False
        
        del self._sources[source_id]
        if source_id in self._events:
            del self._events[source_id]
        
        logger.info("Removed calendar source: %s", source_id)
        return True
    
    def sync_source(self, source_id: str) -> int:
        """Sync events from a specific source.
        
        Args:
            source_id: Source identifier
            
        Returns:
            Number of events synced
        """
        config = self._sources.get(source_id)
        if not config or not config.enabled:
            return 0
        
        config.sync_status = CalendarSyncStatus.SYNCING
        
        try:
            count = 0
            
            if config.source_type == CalendarSource.ICS:
                count = self._sync_ics(config)
            elif config.source_type == CalendarSource.GOOGLE:
                count = self._sync_google(config)
            elif config.source_type == CalendarSource.CALDAV:
                count = self._sync_caldav(config)
            elif config.source_type == CalendarSource.HA:
                count = self._sync_ha(config)
            
            config.last_sync = datetime.now(timezone.utc)
            config.sync_status = CalendarSyncStatus.READY
            
            logger.info("Synced %d events from source %s", count, source_id)
            return count
            
        except Exception as exc:
            logger.error("Failed to sync source %s: %s", source_id, exc)
            config.sync_status = CalendarSyncStatus.ERROR
            return 0
    
    def _sync_ics(self, config: CalendarSourceConfig) -> int:
        """Sync ICS calendar."""
        if config.ics_path:
            return self._ics_reader.load_file(
                config.source_id,
                config.ics_path,
                config.name,
            )
        elif config.ics_url:
            return self._ics_reader.load_url(
                config.source_id,
                config.ics_url,
                config.name,
            )
        return 0
    
    def _sync_google(self, config: CalendarSourceConfig) -> int:
        """Sync Google Calendar."""
        if not self._google_client:
            # Try to initialize
            google_config = GoogleCalendarConfig(
                credentials_path=config.google_credentials_path,
                token_path=config.google_token_path,
                service_account_path=config.google_service_account_path,
                calendar_ids=config.google_calendar_ids,
            )
            self._google_client = get_google_calendar_client(google_config)
        
        if not self._google_client:
            return 0
        
        # Authenticate if needed
        if config.google_credentials_path:
            if not self._google_client.authenticate_with_oauth():
                return 0
        elif config.google_service_account_path:
            if not self._google_client.authenticate_with_service_account():
                return 0
        
        # Get calendars
        calendars = self._google_client.list_calendars()
        
        count = 0
        for cal in calendars:
            cal_id = cal.get("calendar_id")
            if config.google_calendar_ids and cal_id not in config.google_calendar_ids:
                continue
            
            events = self._google_client.get_events(cal_id)
            for event in events:
                unified = UnifiedCalendarEvent.from_google(
                    config.source_id,
                    cal.get("summary", cal_id),
                    event,
                )
                self._events[config.source_id].append(unified)
                count += 1
        
        return count
    
    def _sync_caldav(self, config: CalendarSourceConfig) -> int:
        """Sync CalDAV calendar."""
        if not config.caldav_url:
            return 0
        
        caldav_config = CalDAVConfig(
            url=config.caldav_url,
            username=config.caldav_username,
            password=config.caldav_password,
            ssl_verify=config.caldav_ssl_verify,
            calendar_url=config.caldav_calendar_url,
            calendar_name=config.caldav_calendar_name,
        )
        
        client = get_caldav_client(config.source_id, caldav_config)
        if not client:
            return 0
        
        self._caldav_clients[config.source_id] = client
        
        # Get events
        events = client.get_events(
            calendar_url=config.caldav_calendar_url,
            calendar_name=config.caldav_calendar_name,
        )
        
        count = 0
        for event in events:
            # Get calendar name
            cal_name = config.caldav_calendar_name or config.caldav_calendar_url or "CalDAV"
            
            unified = UnifiedCalendarEvent.from_caldav(
                config.source_id,
                cal_name,
                event,
            )
            self._events[config.source_id].append(unified)
            count += 1
        
        return count
    
    def _sync_ha(self, config: CalendarSourceConfig) -> int:
        """Sync Home Assistant calendar."""
        # TODO: Implement HA calendar integration
        logger.debug("HA calendar sync not yet implemented")
        return 0
    
    def sync_all(self) -> Dict[str, int]:
        """Sync all enabled sources.
        
        Returns:
            Dict mapping source_id to event count
        """
        results = {}
        
        for source_id, config in self._sources.items():
            if config.enabled:
                count = self.sync_source(source_id)
                results[source_id] = count
        
        return results
    
    def get_events(self, source_id: Optional[str] = None,
                   start: Optional[datetime] = None,
                   end: Optional[datetime] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        """Get calendar events.
        
        Args:
            source_id: Filter to specific source (None for all)
            start: Start of time range
            end: End of time range
            limit: Maximum events to return
            
        Returns:
            List of event dictionaries
        """
        events = []
        
        sources = [source_id] if source_id else list(self._sources.keys())
        
        for src_id in sources:
            if src_id not in self._events:
                continue
            
            for event in self._events[src_id]:
                # Apply date range filter
                if start and event.end and event.end < start:
                    continue
                if end and event.start and event.start > end:
                    continue
                
                events.append(event)
        
        # Sort by start time
        events.sort(key=lambda e: e.start or datetime.min.replace(tzinfo=timezone.utc))
        
        # Apply limit
        events = events[:limit]
        
        return [e.to_dict() for e in events]
    
    def get_upcoming_events(self, hours_ahead: int = 24,
                            source_id: Optional[str] = None,
                            limit: int = 50) -> List[Dict[str, Any]]:
        """Get upcoming events.
        
        Args:
            hours_ahead: Hours to look ahead
            source_id: Filter to specific source
            limit: Maximum events to return
            
        Returns:
            List of event dictionaries
        """
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=hours_ahead)
        
        return self.get_events(
            source_id=source_id,
            start=now,
            end=end,
            limit=limit,
        )
    
    def get_events_today(self, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get today's events."""
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        return self.get_events(
            source_id=source_id,
            start=start,
            end=end,
            limit=100,
        )
    
    def get_presence_prediction(self, hours_ahead: int = 4) -> Dict[str, Any]:
        """Predict presence based on calendar events.
        
        Args:
            hours_ahead: Hours to predict
            
        Returns:
            Presence prediction with probability and away events
        """
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=hours_ahead)
        
        # Get events that indicate absence
        away_keywords = ["meeting", "appointment", "work", "office", 
                        "travel", "flight", "train", "doctor", "dentist"]
        
        away_events = []
        all_events = self.get_events(start=now, end=end, limit=200)
        
        for event in all_events:
            summary_lower = (event.get("summary") or "").lower()
            
            # Check if event indicates absence
            if any(kw in summary_lower for kw in away_keywords):
                away_events.append(event)
        
        # Calculate presence probability
        if not away_events:
            presence_probability = 0.85  # Default: likely home
        else:
            # More away events = lower probability
            presence_probability = max(0.1, 0.85 - (len(away_events) * 0.15))
        
        return {
            "presence_probability": round(presence_probability, 3),
            "away_events": away_events,
            "away_event_count": len(away_events),
            "prediction_until": end.isoformat(),
            "generated_at": now.isoformat(),
        }
    
    def get_calendar_summary(self) -> Dict[str, Any]:
        """Get calendar system summary."""
        total_events = sum(len(events) for events in self._events.values())
        
        sources_info = []
        for source_id, config in self._sources.items():
            sources_info.append({
                **config.to_dict(),
                "event_count": len(self._events.get(source_id, [])),
            })
        
        upcoming_24h = len(self.get_upcoming_events(hours_ahead=24))
        
        return {
            "total_sources": len(self._sources),
            "enabled_sources": len([s for s in self._sources.values() if s.enabled]),
            "total_events": total_events,
            "upcoming_24h": upcoming_24h,
            "sources": sources_info,
        }
    
    def list_sources(self) -> List[Dict[str, Any]]:
        """List all calendar sources."""
        return [
            {
                **config.to_dict(),
                "event_count": len(self._events.get(config.source_id, [])),
            }
            for config in self._sources.values()
        ]
    
    def enable_source(self, source_id: str) -> bool:
        """Enable a calendar source."""
        if source_id not in self._sources:
            return False
        
        self._sources[source_id].enabled = True
        self._sources[source_id].sync_status = CalendarSyncStatus.PENDING
        return True
    
    def disable_source(self, source_id: str) -> bool:
        """Disable a calendar source."""
        if source_id not in self._sources:
            return False
        
        self._sources[source_id].enabled = False
        self._sources[source_id].sync_status = CalendarSyncStatus.DISABLED
        return True


# Global instance
_calendar_manager: Optional[CalendarManager] = None


def get_calendar_manager() -> CalendarManager:
    """Get or create calendar manager instance."""
    global _calendar_manager
    
    if _calendar_manager is None:
        _calendar_manager = CalendarManager()
        _calendar_manager.initialize()
    
    return _calendar_manager


def reset_calendar_manager() -> None:
    """Reset the calendar manager instance."""
    global _calendar_manager
    
    if _calendar_manager:
        _calendar_manager = None
    
    # Reset sub-components
    from .ics_calendar import reset_ics_reader
    from .google_calendar import reset_google_calendar_client
    from .caldav_calendar import reset_caldav_clients
    
    reset_ics_reader()
    reset_google_calendar_client()
    reset_caldav_clients()
