"""Google Calendar API Integration for PilotSuite.

Provides Google Calendar API client for reading and writing calendar events.
Supports OAuth2 authentication and service accounts.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google.oauth2 import service_account
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.debug("Google API libraries not available - Google Calendar disabled")


@dataclass
class GoogleCalendarConfig:
    """Configuration for Google Calendar integration."""
    credentials_path: Optional[str] = None
    token_path: Optional[str] = None
    service_account_path: Optional[str] = None
    scopes: List[str] = field(default_factory=lambda: [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ])
    calendar_ids: List[str] = field(default_factory=list)
    redirect_uri: str = "http://localhost:8080"
    sync_interval_minutes: int = 15
    max_results: int = 250


@dataclass
class GoogleCalendarEvent:
    """Google Calendar event representation."""
    event_id: str
    calendar_id: str
    summary: str
    description: Optional[str]
    start: datetime
    end: datetime
    all_day: bool
    location: Optional[str] = None
    organizer: Optional[str] = None
    attendees: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "confirmed"
    visibility: str = "default"
    recurrence: Optional[List[str]] = None
    html_link: Optional[str] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    etag: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "calendar_id": self.calendar_id,
            "summary": self.summary,
            "description": self.description,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "all_day": self.all_day,
            "location": self.location,
            "organizer": self.organizer,
            "attendees": self.attendees,
            "status": self.status,
            "visibility": self.visibility,
            "recurrence": self.recurrence,
            "html_link": self.html_link,
            "created": self.created.isoformat() if self.created else None,
            "updated": self.updated.isoformat() if self.updated else None,
            "etag": self.etag,
        }


class GoogleCalendarClient:
    """Google Calendar API client."""
    
    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ]
    
    def __init__(self, config: Optional[GoogleCalendarConfig] = None):
        if not GOOGLE_AVAILABLE:
            raise ImportError("Google API libraries not installed")
        
        self.config = config or GoogleCalendarConfig()
        self._credentials: Optional[Credentials] = None
        self._service = None
        self._calendars: Dict[str, Dict[str, Any]] = {}
    
    def authenticate_with_oauth(self, credentials_path: Optional[str] = None,
                                 token_path: Optional[str] = None) -> bool:
        """Authenticate using OAuth2 flow."""
        creds_path = credentials_path or self.config.credentials_path
        token_path = token_path or self.config.token_path
        
        if not creds_path:
            logger.error("Credentials path required for OAuth2")
            return False
        
        try:
            if token_path and Path(token_path).exists():
                self._credentials = Credentials.from_authorized_user_file(
                    token_path, self.config.scopes
                )
            
            if self._credentials and self._credentials.expired and self._credentials.refresh_token:
                self._credentials.refresh(Request())
                if token_path:
                    Path(token_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(token_path, "w") as f:
                        f.write(self._credentials.to_json())
            
            if not self._credentials or not self._credentials.valid:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, self.config.scopes)
                flow.redirect_uri = self.config.redirect_uri
                self._credentials = flow.run_local_server(port=0)
                
                if token_path:
                    Path(token_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(token_path, "w") as f:
                        f.write(self._credentials.to_json())
            
            self._build_service()
            return True
            
        except Exception as exc:
            logger.error("OAuth2 authentication failed: %s", exc)
            return False
    
    def authenticate_with_service_account(self, service_account_path: Optional[str] = None) -> bool:
        """Authenticate using service account."""
        sa_path = service_account_path or self.config.service_account_path
        
        if not sa_path:
            logger.error("Service account path required")
            return False
        
        try:
            self._credentials = service_account.Credentials.from_service_account_file(
                sa_path, scopes=self.config.scopes
            )
            self._build_service()
            return True
        except Exception as exc:
            logger.error("Service account authentication failed: %s", exc)
            return False
    
    def _build_service(self) -> None:
        """Build the Google API service client."""
        if not self._credentials:
            raise ValueError("Not authenticated")
        self._service = build("calendar", "v3", credentials=self._credentials)
    
    def list_calendars(self) -> List[Dict[str, Any]]:
        """List accessible calendars."""
        if not self._service:
            return []
        
        try:
            page_token = None
            calendars = []
            
            while True:
                response = self._service.calendarList().list(pageToken=page_token).execute()
                
                for cal in response.get("items", []):
                    calendars.append({
                        "calendar_id": cal["id"],
                        "summary": cal.get("summary", "Unknown"),
                        "description": cal.get("description"),
                        "time_zone": cal.get("timeZone"),
                        "access_role": cal.get("accessRole"),
                        "primary": cal.get("primary", False),
                    })
                
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
            
            return calendars
        except HttpError as exc:
            logger.error("Failed to list calendars: %s", exc)
            return []
    
    def get_events(self, calendar_id: str = "primary",
                   time_min: Optional[datetime] = None,
                   time_max: Optional[datetime] = None,
                   max_results: int = 250,
                   single_events: bool = True) -> List[GoogleCalendarEvent]:
        """Get events from a calendar."""
        if not self._service:
            return []
        
        try:
            params = {
                "calendarId": calendar_id,
                "singleEvents": single_events,
                "orderBy": "startTime" if single_events else None,
                "maxResults": max_results,
            }
            
            if time_min:
                params["timeMin"] = time_min.isoformat()
            if time_max:
                params["timeMax"] = time_max.isoformat()
            
            params = {k: v for k, v in params.items() if v is not None}
            
            response = self._service.events().list(**params).execute()
            
            events = []
            for item in response.get("items", []):
                event = self._parse_event(calendar_id, item)
                if event:
                    events.append(event)
            
            return events
            
        except HttpError as exc:
            logger.error("Failed to get events from %s: %s", calendar_id, exc)
            return []
    
    def _parse_event(self, calendar_id: str, data: Dict[str, Any]) -> Optional[GoogleCalendarEvent]:
        """Parse Google API event data."""
        try:
            event_id = data.get("id", "")
            summary = data.get("summary", "Untitled Event")
            description = data.get("description")
            location = data.get("location")
            status = data.get("status", "confirmed")
            visibility = data.get("visibility", "default")
            
            start_data = data.get("start", {})
            end_data = data.get("end", {})
            
            all_day = "date" in start_data
            
            if all_day:
                start = datetime.strptime(start_data["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                end = datetime.strptime(end_data.get("date", start_data["date"]), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else:
                start_str = start_data.get("dateTime", start_data.get("date"))
                end_str = end_data.get("dateTime", end_data.get("date"))
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00")) if start_str else None
                end = datetime.fromisoformat(end_str.replace("Z", "+00:00")) if end_str else None
            
            if not start:
                return None
            
            organizer = None
            org_data = data.get("organizer", {})
            if org_data:
                organizer = org_data.get("email") or org_data.get("displayName")
            
            attendees = []
            for att in data.get("attendees", []):
                attendees.append({
                    "email": att.get("email"),
                    "name": att.get("displayName"),
                    "response_status": att.get("responseStatus"),
                    "optional": att.get("optional", False),
                })
            
            created = None
            if data.get("created"):
                created = datetime.fromisoformat(data["created"].replace("Z", "+00:00"))
            
            updated = None
            if data.get("updated"):
                updated = datetime.fromisoformat(data["updated"].replace("Z", "+00:00"))
            
            return GoogleCalendarEvent(
                event_id=event_id,
                calendar_id=calendar_id,
                summary=summary,
                description=description,
                start=start,
                end=end,
                all_day=all_day,
                location=location,
                organizer=organizer,
                attendees=attendees,
                status=status,
                visibility=visibility,
                recurrence=data.get("recurrence"),
                html_link=data.get("htmlLink"),
                created=created,
                updated=updated,
                etag=data.get("etag"),
            )
        except Exception as exc:
            logger.warning("Failed to parse event: %s", exc)
            return None
    
    def get_upcoming_events(self, hours_ahead: int = 24,
                            calendar_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get upcoming events across calendars."""
        if not calendar_ids:
            calendars = self.list_calendars()
            calendar_ids = [c["calendar_id"] for c in calendars if c.get("access_role") in ("owner", "writer", "reader")]
        
        time_min = datetime.now(timezone.utc)
        time_max = time_min + timedelta(hours=hours_ahead)
        
        all_events = []
        for cal_id in calendar_ids:
            events = self.get_events(cal_id, time_min=time_min, time_max=time_max)
            all_events.extend([e.to_dict() for e in events])
        
        all_events.sort(key=lambda e: e.get("start") or "")
        return all_events


_google_client: Optional[GoogleCalendarClient] = None


def get_google_calendar_client(config: Optional[GoogleCalendarConfig] = None) -> Optional[GoogleCalendarClient]:
    """Get or create Google Calendar client."""
    global _google_client
    
    if not GOOGLE_AVAILABLE:
        logger.warning("Google Calendar API not available")
        return None
    
    if _google_client is None:
        try:
            _google_client = GoogleCalendarClient(config)
        except ImportError:
            return None
    
    return _google_client


def reset_google_calendar_client() -> None:
    """Reset the Google Calendar client instance."""
    global _google_client
    _google_client = None
