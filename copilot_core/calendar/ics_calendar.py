"""ICS Calendar Reader for PilotSuite.

Provides ICS/iCal file parsing and calendar event extraction.
Supports local files and remote URLs.
"""

from __future__ import annotations

import logging
import re
import requests
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class ICSEvent:
    """Parsed ICS calendar event."""
    uid: str
    summary: str
    description: Optional[str]
    start: datetime
    end: datetime
    all_day: bool
    location: Optional[str] = None
    organizer: Optional[str] = None
    attendees: List[str] = field(default_factory=list)
    recurrence_id: Optional[str] = None
    rrule: Optional[str] = None
    created: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    sequence: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "uid": self.uid,
            "summary": self.summary,
            "description": self.description,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "all_day": self.all_day,
            "location": self.location,
            "organizer": self.organizer,
            "attendees": self.attendees,
            "recurrence_id": self.recurrence_id,
            "rrule": self.rrule,
            "created": self.created.isoformat() if self.created else None,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "sequence": self.sequence,
        }


class ICSCalendarReader:
    """ICS calendar file reader and parser."""
    
    def __init__(self):
        self._calendars: Dict[str, Dict[str, Any]] = {}
        self._events: Dict[str, List[ICSEvent]] = {}
    
    def load_file(self, calendar_id: str, file_path: str, name: Optional[str] = None) -> int:
        """Load events from an ICS file."""
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error("ICS file not found: %s", file_path)
                return 0
            
            content = path.read_text(encoding="utf-8")
            return self._parse_content(calendar_id, content, name or path.stem)
        except Exception as exc:
            logger.error("Failed to load ICS file %s: %s", file_path, exc)
            return 0
    
    def load_url(self, calendar_id: str, url: str, name: Optional[str] = None,
                 timeout: int = 30) -> int:
        """Load events from a remote ICS URL."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.error("Invalid URL: %s", url)
                return 0
            
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            
            content = response.text
            return self._parse_content(calendar_id, content, name or parsed.path.split("/")[-1].replace(".ics", ""))
        except Exception as exc:
            logger.error("Failed to load ICS URL %s: %s", url, exc)
            return 0
    
    def _parse_content(self, calendar_id: str, content: str, name: str) -> int:
        """Parse ICS content and extract events."""
        events = []
        
        if not content.strip().startswith("BEGIN:VCALENDAR"):
            logger.warning("Invalid ICS content for calendar %s", calendar_id)
            return 0
        
        cal_name = self._extract_property(content, "X-WR-CALNAME") or name
        cal_desc = self._extract_property(content, "X-WR-CALDESC")
        
        self._calendars[calendar_id] = {
            "calendar_id": calendar_id,
            "name": cal_name,
            "description": cal_desc,
            "source": "ics",
            "enabled": True,
        }
        
        event_blocks = self._extract_blocks(content, "VEVENT")
        
        for block in event_blocks:
            event = self._parse_event(block)
            if event:
                events.append(event)
        
        events.sort(key=lambda e: e.start or datetime.min.replace(tzinfo=timezone.utc))
        
        self._events[calendar_id] = events
        logger.info("Loaded %d events from ICS calendar %s", len(events), calendar_id)
        
        return len(events)
    
    def _extract_property(self, content: str, prop_name: str) -> Optional[str]:
        """Extract a property value from ICS content."""
        pattern = rf"{prop_name}:(.+?)(?:\r?\n|$)"
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_blocks(self, content: str, block_type: str) -> List[str]:
        """Extract all blocks of a specific type from ICS content."""
        blocks = []
        lines = content.split("\n")
        
        in_block = False
        block_lines = []
        
        for line in lines:
            line = line.strip()
            
            if line == f"BEGIN:{block_type}":
                in_block = True
                block_lines = []
            elif line == f"END:{block_type}":
                if in_block:
                    blocks.append("\n".join(block_lines))
                in_block = False
            elif in_block:
                block_lines.append(line)
        
        return blocks
    
    def _parse_event(self, block: str) -> Optional[ICSEvent]:
        """Parse a VEVENT block into an ICSEvent."""
        try:
            uid = self._extract_property(block, "UID")
            if not uid:
                logger.warning("Event missing UID")
                return None
            
            summary = self._extract_property(block, "SUMMARY") or "Untitled Event"
            description = self._extract_property(block, "DESCRIPTION")
            location = self._extract_property(block, "LOCATION")
            
            start_dt, start_all_day = self._parse_datetime_field(block, "DTSTART")
            end_dt, end_all_day = self._parse_datetime_field(block, "DTEND")
            
            if not start_dt:
                logger.warning("Event %s missing start date", uid)
                return None
            
            all_day = start_all_day or end_all_day
            
            organizer = self._extract_property(block, "ORGANIZER")
            if organizer and organizer.startswith("mailto:"):
                organizer = organizer[7:]
            
            attendees = []
            for match in re.finditer(r"ATTENDEE[^:]*:(mailto:)?([^;\r\n]+)", block, re.IGNORECASE):
                attendee = match.group(2).strip()
                if attendee:
                    attendees.append(attendee)
            
            recurrence_id = self._extract_property(block, "RECURRENCE-ID")
            rrule = self._extract_property(block, "RRULE")
            
            created = None
            created_str = self._extract_property(block, "CREATED")
            if created_str:
                created = self._parse_datetime_value(created_str)
            
            last_modified = None
            modified_str = self._extract_property(block, "LAST-MODIFIED")
            if modified_str:
                last_modified = self._parse_datetime_value(modified_str)
            
            sequence = 0
            seq_str = self._extract_property(block, "SEQUENCE")
            if seq_str:
                try:
                    sequence = int(seq_str)
                except ValueError:
                    pass
            
            return ICSEvent(
                uid=uid,
                summary=summary,
                description=description,
                start=start_dt,
                end=end_dt or start_dt + timedelta(hours=1),
                all_day=all_day,
                location=location,
                organizer=organizer,
                attendees=attendees,
                recurrence_id=recurrence_id,
                rrule=rrule,
                created=created,
                last_modified=last_modified,
                sequence=sequence,
            )
        except Exception as exc:
            logger.warning("Failed to parse event block: %s", exc)
            return None
    
    def _parse_datetime_field(self, block: str, field_name: str) -> Tuple[Optional[datetime], bool]:
        """Parse a datetime field from an event block."""
        value = self._extract_property(block, field_name)
        if not value:
            return None, False
        
        is_all_day = "VALUE=DATE" in value.upper()
        
        match = re.search(r":([0-9TZ]+)", value)
        if not match:
            return None, False
        
        dt_value = match.group(1)
        return self._parse_datetime_value(dt_value), is_all_day
    
    def _parse_datetime_value(self, value: str) -> Optional[datetime]:
        """Parse a datetime string into a datetime object."""
        if not value:
            return None
        
        value = value.split(":")[-1].strip()
        
        try:
            if "T" in value:
                if value.endswith("Z"):
                    value = value[:-1] + "+00:00"
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            
            if len(value) == 8:
                return datetime(
                    year=int(value[0:4]),
                    month=int(value[4:6]),
                    day=int(value[6:8]),
                    tzinfo=timezone.utc
                )
            
            if len(value) == 15:
                return datetime(
                    year=int(value[0:4]),
                    month=int(value[4:6]),
                    day=int(value[6:8]),
                    hour=int(value[9:11]),
                    minute=int(value[11:13]),
                    second=int(value[13:15]),
                    tzinfo=timezone.utc
                )
        except (ValueError, IndexError) as exc:
            logger.debug("Failed to parse datetime %s: %s", value, exc)
        
        return None
    
    def get_calendar(self, calendar_id: str) -> Optional[Dict[str, Any]]:
        """Get calendar metadata."""
        return self._calendars.get(calendar_id)
    
    def get_events(self, calendar_id: Optional[str] = None,
                   start: Optional[datetime] = None,
                   end: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get events, optionally filtered by date range."""
        events = []
        
        calendars = [calendar_id] if calendar_id else list(self._calendars.keys())
        
        for cal_id in calendars:
            if cal_id not in self._events:
                continue
            
            for event in self._events[cal_id]:
                if start and event.end and event.end < start:
                    continue
                if end and event.start and event.start > end:
                    continue
                
                events.append(event.to_dict())
        
        events.sort(key=lambda e: e.get("start") or "")
        
        return events
    
    def list_calendars(self) -> List[Dict[str, Any]]:
        """List all registered calendars."""
        return list(self._calendars.values())
    
    def remove_calendar(self, calendar_id: str) -> bool:
        """Remove a calendar and its events."""
        if calendar_id in self._calendars:
            del self._calendars[calendar_id]
        if calendar_id in self._events:
            del self._events[calendar_id]
        return True
    
    def refresh(self, calendar_id: str) -> int:
        """Refresh events from a calendar (re-load from source)."""
        cal_info = self._calendars.get(calendar_id)
        if not cal_info:
            return 0
        
        return len(self._events.get(calendar_id, []))


def get_ics_reader() -> ICSCalendarReader:
    """Get or create ICS calendar reader instance."""
    if not hasattr(get_ics_reader, "_instance"):
        get_ics_reader._instance = ICSCalendarReader()
    return get_ics_reader._instance


def reset_ics_reader() -> None:
    """Reset the ICS reader instance."""
    if hasattr(get_ics_reader, "_instance"):
        del get_ics_reader._instance
