"""CalDAV Calendar Integration for PilotSuite.

Provides CalDAV protocol support for calendar integration with
self-hosted and cloud calendar servers (Nextcloud, ownCloud, iCloud, etc.).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

try:
    import caldav
    from caldav import DAVClient, Calendar, Event
    CALDAV_AVAILABLE = True
except ImportError:
    CALDAV_AVAILABLE = False
    logger.debug("caldav library not available - CalDAV support disabled")

try:
    import icalendar
    ICAL_AVAILABLE = True
except ImportError:
    ICAL_AVAILABLE = False


@dataclass
class CalDAVConfig:
    """Configuration for CalDAV connection."""
    url: str
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_verify: bool = True
    timeout: int = 30
    calendar_url: Optional[str] = None
    calendar_name: Optional[str] = None


@dataclass
class CalDAVCalendarEvent:
    """CalDAV calendar event representation."""
    uid: str
    calendar_url: str
    summary: str
    description: Optional[str]
    start: datetime
    end: datetime
    all_day: bool
    location: Optional[str] = None
    organizer: Optional[str] = None
    attendees: List[str] = field(default_factory=list)
    recurrence: Optional[str] = None
    ics_data: Optional[str] = None
    etag: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uid": self.uid,
            "calendar_url": self.calendar_url,
            "summary": self.summary,
            "description": self.description,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "all_day": self.all_day,
            "location": self.location,
            "organizer": self.organizer,
            "attendees": self.attendees,
            "recurrence": self.recurrence,
            "etag": self.etag,
        }


class CalDAVCalendarClient:
    """CalDAV calendar client."""
    
    def __init__(self, config: CalDAVConfig):
        if not CALDAV_AVAILABLE:
            raise ImportError("caldav library not installed")
        
        self.config = config
        self._client: Optional[DAVClient] = None
        self._principal = None
        self._calendars: Dict[str, Calendar] = {}
        self._calendar_info: Dict[str, Dict[str, Any]] = {}
    
    def connect(self) -> bool:
        """Connect to CalDAV server."""
        try:
            parsed = urlparse(self.config.url)
            if not parsed.scheme or not parsed.netloc:
                logger.error("Invalid CalDAV URL: %s", self.config.url)
                return False
            
            self._client = DAVClient(
                url=self.config.url,
                username=self.config.username,
                password=self.config.password,
                ssl_verify_cert=self.config.ssl_verify,
                timeout=self.config.timeout,
            )
            
            self._principal = self._client.principal()
            logger.info("Connected to CalDAV server: %s", self.config.url)
            return True
            
        except Exception as exc:
            logger.error("CalDAV connection error: %s", exc)
            return False
    
    def list_calendars(self) -> List[Dict[str, Any]]:
        """List available calendars."""
        if not self._principal:
            return []
        
        try:
            calendars = self._principal.calendars()
            result = []
            
            for cal in calendars:
                try:
                    cal_data = cal.get_properties(
                        ["{DAV:}displayname", "{http://calendarserver.org/ns/}getctag"]
                    )
                    
                    result.append({
                        "calendar_url": cal.url,
                        "name": cal_data.get("{DAV:}displayname", "Unknown"),
                        "description": cal_data.get("{http://calendarserver.org/ns/}getctag", ""),
                        "id": cal.url.split("/")[-1].rstrip("/"),
                    })
                except Exception as exc:
                    logger.warning("Failed to get calendar info: %s", exc)
            
            return result
        except Exception as exc:
            logger.error("Failed to list calendars: %s", exc)
            return []
    
    def get_calendar(self, calendar_url: Optional[str] = None,
                     calendar_name: Optional[str] = None) -> Optional[Calendar]:
        """Get a specific calendar."""
        if not self._principal:
            return None
        
        try:
            if calendar_url:
                cal = self._client.calendar(url=calendar_url)
                self._calendars[calendar_url] = cal
                return cal
            
            if calendar_name:
                calendars = self._principal.calendars()
                for cal in calendars:
                    try:
                        display_name = cal.get_property("{DAV:}displayname")
                        if display_name == calendar_name:
                            self._calendars[cal.url] = cal
                            return cal
                    except Exception:
                        continue
            
            return None
        except Exception as exc:
            logger.error("Failed to get calendar: %s", exc)
            return None
    
    def get_events(self, calendar_url: Optional[str] = None,
                   calendar_name: Optional[str] = None,
                   start: Optional[datetime] = None,
                   end: Optional[datetime] = None,
                   expand: bool = True) -> List[CalDAVCalendarEvent]:
        """Get events from a calendar."""
        cal = self.get_calendar(calendar_url, calendar_name)
        if not cal:
            return []
        
        try:
            kwargs = {}
            if start and end:
                kwargs["start"] = start
                kwargs["end"] = end
            elif start:
                kwargs["start"] = start
            elif end:
                kwargs["end"] = end
            
            if expand and start and end:
                events = cal.date_search(start, end, expand=True)
            else:
                events = cal.events()
            
            result = []
            for event in events:
                try:
                    parsed = self._parse_event(cal.url, event)
                    if parsed:
                        result.append(parsed)
                except Exception as exc:
                    logger.warning("Failed to parse event: %s", exc)
            
            result.sort(key=lambda e: e.start or datetime.min.replace(tzinfo=timezone.utc))
            return result
            
        except Exception as exc:
            logger.error("Failed to get events: %s", exc)
            return []
    
    def _parse_event(self, calendar_url: str, event: Event) -> Optional[CalDAVCalendarEvent]:
        """Parse a CalDAV event."""
        try:
            ics_data = event.data
            uid = event.id or event.uid
            
            if not uid:
                import re
                match = re.search(r"UID:(.+?)(?:\r?\n|$)", ics_data)
                if match:
                    uid = match.group(1).strip()
                else:
                    uid = f"unknown_{id(event)}"
            
            if ICAL_AVAILABLE:
                return self._parse_with_icalendar(calendar_url, uid, ics_data, event)
            else:
                return self._parse_basic(calendar_url, uid, ics_data, event)
                
        except Exception as exc:
            logger.warning("Failed to parse event: %s", exc)
            return None
    
    def _parse_with_icalendar(self, calendar_url: str, uid: str, 
                               ics_data: str, event: Event) -> Optional[CalDAVCalendarEvent]:
        """Parse event using icalendar library."""
        try:
            from icalendar import Calendar as IcalCalendar
            
            cal = IcalCalendar.from_ical(ics_data)
            
            for component in cal.walk("VEVENT"):
                summary = str(component.get("SUMMARY", "Untitled Event"))
                description = str(component.get("DESCRIPTION", "")) or None
                location = str(component.get("LOCATION", "")) or None
                
                dt_start = component.get("DTSTART")
                dt_end = component.get("DTEND")
                
                if not dt_start:
                    continue
                
                start = dt_start.dt
                if not isinstance(start, datetime):
                    start = datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc)
                    all_day = True
                else:
                    all_day = False
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                
                if dt_end:
                    end = dt_end.dt
                    if not isinstance(end, datetime):
                        end = datetime.combine(end, datetime.min.time()).replace(tzinfo=timezone.utc)
                    elif end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                else:
                    end = start + timedelta(hours=1)
                
                organizer = None
                org = component.get("ORGANIZER")
                if org:
                    organizer = str(org).replace("mailto:", "")
                
                attendees = []
                for att in component.get("ATTENDEE", []):
                    attendees.append(str(att).replace("mailto:", ""))
                
                recurrence = None
                rrule = component.get("RRULE")
                if rrule:
                    recurrence = str(rrule)
                
                etag = None
                try:
                    etag = event.get_property("getetag")
                except Exception:
                    pass
                
                return CalDAVCalendarEvent(
                    uid=uid,
                    calendar_url=calendar_url,
                    summary=summary,
                    description=description,
                    start=start,
                    end=end,
                    all_day=all_day,
                    location=location,
                    organizer=organizer,
                    attendees=attendees,
                    recurrence=recurrence,
                    ics_data=ics_data,
                    etag=etag,
                )
            
            return None
        except Exception as exc:
            logger.warning("icalendar parsing failed: %s", exc)
            return self._parse_basic(calendar_url, uid, ics_data, event)
    
    def _parse_basic(self, calendar_url: str, uid: str,
                     ics_data: str, event: Event) -> CalDAVCalendarEvent:
        """Basic ICS parsing without icalendar library."""
        import re
        
        def extract_prop(pattern: str, default: str = "") -> Optional[str]:
            match = re.search(pattern, ics_data, re.IGNORECASE | re.MULTILINE)
            return match.group(1).strip() if match else default
        
        summary = extract_prop(r"SUMMARY:(.+?)(?:\r?\n|$)", "Untitled Event")
        description = extract_prop(r"DESCRIPTION:(.+?)(?:\r?\n|$)")
        location = extract_prop(r"LOCATION:(.+?)(?:\r?\n|$)")
        
        start_match = re.search(r"DTSTART(?:;[^:]+)?:([0-9TZ]+)", ics_data)
        end_match = re.search(r"DTEND(?:;[^:]+)?:([0-9TZ]+)", ics_data)
        
        all_day = False
        start = None
        end = None
        
        if start_match:
            dt_str = start_match.group(1)
            if len(dt_str) == 8:
                all_day = True
                start = datetime(
                    year=int(dt_str[0:4]),
                    month=int(dt_str[4:6]),
                    day=int(dt_str[6:8]),
                    tzinfo=timezone.utc
                )
            elif "T" in dt_str:
                dt_str = dt_str.replace("Z", "+00:00")
                start = datetime.fromisoformat(dt_str)
        
        if end_match:
            dt_str = end_match.group(1)
            if len(dt_str) == 8:
                end = datetime(
                    year=int(dt_str[0:4]),
                    month=int(dt_str[4:6]),
                    day=int(dt_str[6:8]),
                    tzinfo=timezone.utc
                )
            elif "T" in dt_str:
                dt_str = dt_str.replace("Z", "+00:00")
                end = datetime.fromisoformat(dt_str)
        
        if not start:
            start = datetime.now(timezone.utc)
        if not end:
            end = start + timedelta(hours=1)
        
        organizer = extract_prop(r"ORGANIZER(?:;[^:]+)?:mailto:([^;\r\n]+)")
        
        attendees = []
        for match in re.finditer(r"ATTENDEE(?:;[^:]+)?:mailto:([^;\r\n]+)", ics_data, re.IGNORECASE):
            attendees.append(match.group(1).strip())
        
        recurrence = extract_prop(r"RRULE:(.+?)(?:\r?\n|$)")
        
        etag = None
        try:
            etag = event.get_property("getetag")
        except Exception:
            pass
        
        return CalDAVCalendarEvent(
            uid=uid,
            calendar_url=calendar_url,
            summary=summary,
            description=description,
            start=start,
            end=end,
            all_day=all_day,
            location=location,
            organizer=organizer,
            attendees=attendees,
            recurrence=recurrence,
            ics_data=ics_data,
            etag=etag,
        )
    
    def get_upcoming_events(self, hours_ahead: int = 24,
                            calendar_url: Optional[str] = None,
                            calendar_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get upcoming events."""
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=hours_ahead)
        
        events = self.get_events(
            calendar_url=calendar_url,
            calendar_name=calendar_name,
            start=now,
            end=end,
        )
        
        return [e.to_dict() for e in events]
    
    def disconnect(self) -> None:
        """Disconnect from CalDAV server."""
        self._client = None
        self._principal = None
        self._calendars.clear()


_caldav_clients: Dict[str, CalDAVCalendarClient] = {}


def get_caldav_client(config_id: str, config: CalDAVConfig) -> Optional[CalDAVCalendarClient]:
    """Get or create a CalDAV client."""
    global _caldav_clients
    
    if not CALDAV_AVAILABLE:
        logger.warning("CalDAV library not available")
        return None
    
    if config_id not in _caldav_clients:
        try:
            client = CalDAVCalendarClient(config)
            if client.connect():
                _caldav_clients[config_id] = client
            else:
                return None
        except ImportError:
            return None
    
    return _caldav_clients.get(config_id)


def remove_caldav_client(config_id: str) -> bool:
    """Remove a CalDAV client."""
    global _caldav_clients
    
    if config_id in _caldav_clients:
        client = _caldav_clients[config_id]
        client.disconnect()
        del _caldav_clients[config_id]
        return True
    
    return False


def reset_caldav_clients() -> None:
    """Reset all CalDAV clients."""
    global _caldav_clients
    
    for client in _caldav_clients.values():
        client.disconnect()
    
    _caldav_clients.clear()
