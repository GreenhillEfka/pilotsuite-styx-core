"""Home Assistant Calendar Sensors for PilotSuite.

Provides calendar sensors for Home Assistant integration:
- Calendar event count sensors
- Next event sensors
- Calendar presence prediction sensors
- Multi-calendar support

Sensors:
- sensor.pilot_calendar_event_count — Number of events today
- sensor.pilot_calendar_next_event — Next upcoming event
- sensor.pilot_calendar_next_event_time — Time of next event
- sensor.pilot_calendar_presence_probability — Presence prediction from calendar
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CalendarSensorState:
    """Calendar sensor state."""
    entity_id: str
    name: str
    state: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    unit_of_measurement: Optional[str] = None
    icon: Optional[str] = None
    device_class: Optional[str] = None
    state_class: Optional[str] = None
    
    def to_hass_state(self) -> Dict[str, Any]:
        """Convert to Home Assistant state dict."""
        state = {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": self.attributes,
        }
        
        if self.unit_of_measurement:
            state["attributes"]["unit_of_measurement"] = self.unit_of_measurement
        if self.icon:
            state["attributes"]["icon"] = self.icon
        if self.device_class:
            state["attributes"]["device_class"] = self.device_class
        if self.state_class:
            state["attributes"]["state_class"] = self.state_class
        
        return state


class CalendarSensorManager:
    """Home Assistant calendar sensor manager."""
    
    def __init__(self, calendar_manager=None):
        self._calendar_manager = calendar_manager
        self._sensors: Dict[str, CalendarSensorState] = {}
        self._last_update: Optional[datetime] = None
        self._update_interval_seconds = 60  # Update every minute
    
    def set_calendar_manager(self, manager) -> None:
        """Set the calendar manager."""
        self._calendar_manager = manager
    
    def update_sensors(self) -> List[CalendarSensorState]:
        """Update all calendar sensors.
        
        Returns:
            List of updated sensor states
        """
        now = datetime.now(timezone.utc)
        
        # Check if update is needed
        if self._last_update:
            elapsed = (now - self._last_update).total_seconds()
            if elapsed < self._update_interval_seconds:
                return list(self._sensors.values())
        
        self._last_update = now
        
        sensors = []
        
        # Update event count sensor
        sensors.append(self._update_event_count_sensor())
        
        # Update next event sensor
        sensors.append(self._update_next_event_sensor())
        
        # Update presence prediction sensor
        sensors.append(self._update_presence_sensor())
        
        return sensors
    
    def _update_event_count_sensor(self) -> CalendarSensorState:
        """Update event count sensor."""
        entity_id = "sensor.pilot_calendar_event_count"
        
        if not self._calendar_manager:
            return CalendarSensorState(
                entity_id=entity_id,
                name="Pilot Calendar Event Count",
                state="unavailable",
                attributes={
                    "friendly_name": "Pilot Calendar Event Count",
                    "error": "Calendar manager not available",
                },
                icon="mdi:calendar",
            )
        
        # Get today's events
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        events = self._calendar_manager.get_events(start=start, end=end, limit=100)
        count = len(events)
        
        # Build attributes
        attributes = {
            "friendly_name": "Pilot Calendar Event Count",
            "icon": "mdi:calendar",
            "device_class": "duration",
            "state_class": "measurement",
            "events_today": count,
            "last_updated": now.isoformat(),
        }
        
        # Add event summaries
        if events:
            attributes["events"] = [
                {
                    "summary": e.get("summary", ""),
                    "start": e.get("start", ""),
                    "end": e.get("end", ""),
                }
                for e in events[:5]  # Limit to 5 events
            ]
        
        return CalendarSensorState(
            entity_id=entity_id,
            name="Pilot Calendar Event Count",
            state=str(count),
            attributes=attributes,
            unit_of_measurement="events",
            icon="mdi:calendar",
            device_class=None,
            state_class="measurement",
        )
    
    def _update_next_event_sensor(self) -> CalendarSensorState:
        """Update next event sensor."""
        entity_id = "sensor.pilot_calendar_next_event"
        
        if not self._calendar_manager:
            return CalendarSensorState(
                entity_id=entity_id,
                name="Pilot Calendar Next Event",
                state="unavailable",
                attributes={
                    "friendly_name": "Pilot Calendar Next Event",
                    "error": "Calendar manager not available",
                },
                icon="mdi:calendar-clock",
            )
        
        # Get upcoming events
        now = datetime.now(timezone.utc)
        events = self._calendar_manager.get_upcoming_events(hours_ahead=168, limit=10)
        
        if not events:
            return CalendarSensorState(
                entity_id=entity_id,
                name="Pilot Calendar Next Event",
                state="No events",
                attributes={
                    "friendly_name": "Pilot Calendar Next Event",
                    "icon": "mdi:calendar-clock",
                    "last_updated": now.isoformat(),
                },
                icon="mdi:calendar-clock",
            )
        
        # Get next event
        next_event = events[0]
        summary = next_event.get("summary", "Untitled")
        start_str = next_event.get("start", "")
        
        # Parse start time
        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            time_until = start - now
            
            if time_until.total_seconds() < 0:
                state = "Starting soon"
            elif time_until.total_seconds() < 60:
                state = "Starting now"
            elif time_until.total_seconds() < 3600:
                minutes = int(time_until.total_seconds() / 60)
                state = f"In {minutes} min"
            elif time_until.total_seconds() < 86400:
                hours = int(time_until.total_seconds() / 3600)
                state = f"In {hours} h"
            else:
                days = int(time_until.total_seconds() / 86400)
                state = f"In {days} d"
        except Exception:
            state = summary
        
        # Build attributes
        attributes = {
            "friendly_name": "Pilot Calendar Next Event",
            "icon": "mdi:calendar-clock",
            "event_summary": summary,
            "event_start": start_str,
            "event_end": next_event.get("end", ""),
            "event_location": next_event.get("location", ""),
            "event_source": next_event.get("source_type", ""),
            "last_updated": now.isoformat(),
        }
        
        # Add time until
        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            time_until = start - now
            attributes["time_until_seconds"] = int(time_until.total_seconds())
        except Exception:
            pass
        
        return CalendarSensorState(
            entity_id=entity_id,
            name="Pilot Calendar Next Event",
            state=state,
            attributes=attributes,
            icon="mdi:calendar-clock",
        )
    
    def _update_next_event_time_sensor(self) -> CalendarSensorState:
        """Update next event time sensor."""
        entity_id = "sensor.pilot_calendar_next_event_time"
        
        if not self._calendar_manager:
            return CalendarSensorState(
                entity_id=entity_id,
                name="Pilot Calendar Next Event Time",
                state="unavailable",
                attributes={
                    "friendly_name": "Pilot Calendar Next Event Time",
                    "error": "Calendar manager not available",
                },
                icon="mdi:clock-outline",
            )
        
        # Get upcoming events
        now = datetime.now(timezone.utc)
        events = self._calendar_manager.get_upcoming_events(hours_ahead=168, limit=1)
        
        if not events:
            return CalendarSensorState(
                entity_id=entity_id,
                name="Pilot Calendar Next Event Time",
                state="unavailable",
                attributes={
                    "friendly_name": "Pilot Calendar Next Event Time",
                    "icon": "mdi:clock-outline",
                    "last_updated": now.isoformat(),
                },
                icon="mdi:clock-outline",
            )
        
        next_event = events[0]
        start_str = next_event.get("start", "")
        
        # Format time
        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            state = start.strftime("%H:%M")
            
            # Add date if not today
            today = now.date()
            if start.date() != today:
                state = start.strftime("%a %H:%M")
        except Exception:
            state = start_str
        
        return CalendarSensorState(
            entity_id=entity_id,
            name="Pilot Calendar Next Event Time",
            state=state,
            attributes={
                "friendly_name": "Pilot Calendar Next Event Time",
                "icon": "mdi:clock-outline",
                "datetime": start_str,
                "last_updated": now.isoformat(),
            },
            icon="mdi:clock-outline",
            device_class="timestamp",
        )
    
    def _update_presence_sensor(self) -> CalendarSensorState:
        """Update presence prediction sensor."""
        entity_id = "sensor.pilot_calendar_presence_probability"
        
        if not self._calendar_manager:
            return CalendarSensorState(
                entity_id=entity_id,
                name="Pilot Calendar Presence Probability",
                state="unavailable",
                attributes={
                    "friendly_name": "Pilot Calendar Presence Probability",
                    "error": "Calendar manager not available",
                },
                icon="mdi:home-account",
            )
        
        # Get presence prediction
        prediction = self._calendar_manager.get_presence_prediction(hours_ahead=4)
        
        probability = prediction.get("presence_probability", 0.5)
        away_count = prediction.get("away_event_count", 0)
        
        # Determine state
        if probability >= 0.7:
            state = "home"
        elif probability >= 0.4:
            state = "away_soon"
        else:
            state = "away"
        
        # Build attributes
        attributes = {
            "friendly_name": "Pilot Calendar Presence Probability",
            "icon": "mdi:home-account",
            "probability": round(probability, 3),
            "away_events": away_count,
            "prediction_until": prediction.get("prediction_until", ""),
            "last_updated": prediction.get("generated_at", datetime.now(timezone.utc).isoformat()),
        }
        
        # Add away event summaries
        away_events = prediction.get("away_events", [])
        if away_events:
            attributes["away_event_summaries"] = [
                {"summary": e.get("summary", ""), "start": e.get("start", "")}
                for e in away_events[:3]
            ]
        
        return CalendarSensorState(
            entity_id=entity_id,
            name="Pilot Calendar Presence Probability",
            state=state,
            attributes=attributes,
            icon="mdi:home-account",
        )
    
    def get_all_sensors(self) -> List[Dict[str, Any]]:
        """Get all sensor states as Home Assistant compatible dicts.
        
        Returns:
            List of sensor state dictionaries
        """
        self.update_sensors()
        
        return [s.to_hass_state() for s in self._sensors.values()]
    
    def get_sensor(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific sensor state.
        
        Args:
            entity_id: Sensor entity ID
            
        Returns:
            Sensor state dict or None
        """
        if entity_id in self._sensors:
            return self._sensors[entity_id].to_hass_state()
        return None


# Global instance
_sensor_manager: Optional[CalendarSensorManager] = None


def get_calendar_sensor_manager(calendar_manager=None) -> CalendarSensorManager:
    """Get or create calendar sensor manager.
    
    Args:
        calendar_manager: Calendar manager instance
        
    Returns:
        Calendar sensor manager
    """
    global _sensor_manager
    
    if _sensor_manager is None:
        _sensor_manager = CalendarSensorManager(calendar_manager)
    elif calendar_manager:
        _sensor_manager.set_calendar_manager(calendar_manager)
    
    return _sensor_manager


def reset_calendar_sensor_manager() -> None:
    """Reset the calendar sensor manager instance."""
    global _sensor_manager
    _sensor_manager = None


def update_calendar_sensors(calendar_manager=None) -> List[Dict[str, Any]]:
    """Update and return all calendar sensors.
    
    Args:
        calendar_manager: Calendar manager instance
        
    Returns:
        List of sensor state dictionaries
    """
    manager = get_calendar_sensor_manager(calendar_manager)
    manager.update_sensors()
    return manager.get_all_sensors()
