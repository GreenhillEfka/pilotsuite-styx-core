"""PilotSuite Lovelace Cards — Additional Custom Cards."""
from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# =============================================================================
# CARD 1: NOTIFICATION CENTER CARD
# =============================================================================

@dataclass
class NotificationCardConfig:
    """Configuration for notification center card."""
    title: str = "Notifications"
    show_unread_only: bool = False
    max_notifications: int = 10
    sort_by: str = "timestamp"  # timestamp, priority
    filter_channels: List[str] = None


class NotificationCard:
    """
    Lovelace Card: Notification Center
    
    Features:
    - Display notifications from all channels
    - Filter by read/unread
    - Sort by timestamp or priority
    - Dismiss notifications
    - Quick actions
    
    YAML Config:
    ```yaml
    type: custom:pilotsuite-notifications
    title: Notifications
    show_unread_only: true
    max_notifications: 10
    ```
    """

    def __init__(self, config: NotificationCardConfig):
        self.config = config
        self._notifications = []

    def render(self) -> Dict[str, Any]:
        """Render card HTML."""
        notifications = self._get_notifications()
        
        return {
            "type": "custom:pilotsuite-notifications",
            "title": self.config.title,
            "notifications": notifications,
            "unread_count": self._get_unread_count(),
            "actions": [
                {"label": "Dismiss All", "action": "dismiss_all"},
                {"label": "Mark Read", "action": "mark_read"},
            ]
        }

    def _get_notifications(self) -> List[Dict[str, Any]]:
        """Get filtered notifications."""
        # In real implementation, fetch from API
        notifications = self._notifications
        
        if self.config.show_unread_only:
            notifications = [n for n in notifications if not n.get("read", False)]
        
        # Sort
        if self.config.sort_by == "timestamp":
            notifications.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        elif self.config.sort_by == "priority":
            notifications.sort(key=lambda x: x.get("priority", 0), reverse=True)
        
        return notifications[:self.config.max_notifications]

    def _get_unread_count(self) -> int:
        """Get count of unread notifications."""
        return sum(1 for n in self._notifications if not n.get("read", False))


# =============================================================================
# CARD 2: CALENDAR INTEGRATION CARD
# =============================================================================

@dataclass
class CalendarCardConfig:
    """Configuration for calendar card."""
    title: str = "Calendar"
    calendars: List[str] = None  # Calendar entity IDs
    days_to_show: int = 7
    show_past_events: bool = False
    max_events: int = 20


class CalendarCard:
    """
    Lovelace Card: Calendar Integration
    
    Features:
    - Multiple calendar sources
    - Upcoming events display
    - Filter by calendar
    - Event details on click
    
    YAML Config:
    ```yaml
    type: custom:pilotsuite-calendar
    title: Upcoming Events
    calendars:
      - calendar.family
      - calendar.work
    days_to_show: 7
    max_events: 10
    ```
    """

    def __init__(self, config: CalendarCardConfig):
        self.config = config
        self._events = []

    def render(self) -> Dict[str, Any]:
        """Render card HTML."""
        events = self._get_upcoming_events()
        
        return {
            "type": "custom:pilotsuite-calendar",
            "title": self.config.title,
            "events": events,
            "days_range": self.config.days_to_show,
            "actions": [
                {"label": "Today", "action": "show_today"},
                {"label": "Week", "action": "show_week"},
            ]
        }

    def _get_upcoming_events(self) -> List[Dict[str, Any]]:
        """Get upcoming events from calendars."""
        now = datetime.now()
        end_date = now + timedelta(days=self.config.days_to_show)
        
        # Filter events
        events = [
            e for e in self._events
            if now <= e.get("start", now) <= end_date
        ]
        
        # Filter by calendar
        if self.config.calendars:
            events = [
                e for e in events
                if e.get("calendar") in self.config.calendars
            ]
        
        # Sort by start time
        events.sort(key=lambda x: x.get("start", now))
        
        return events[:self.config.max_events]


# =============================================================================
# CARD 3: WEATHER AUTOMATION CARD
# =============================================================================

@dataclass
class WeatherCardConfig:
    """Configuration for weather automation card."""
    title: str = "Weather Automations"
    weather_entity: str = "weather.home"
    show_forecast: bool = True
    forecast_days: int = 5
    show_automations: bool = True


class WeatherAutomationCard:
    """
    Lovelace Card: Weather-based Automations
    
    Features:
    - Current weather display
    - Forecast visualization
    - Weather-triggered automations
    - Manual trigger buttons
    
    YAML Config:
    ```yaml
    type: custom:pilotsuite-weather-automation
    title: Weather & Automations
    weather_entity: weather.home
    show_forecast: true
    forecast_days: 3
    show_automations: true
    ```
    """

    def __init__(self, config: WeatherCardConfig):
        self.config = config
        self._weather_state = {}
        self._automations = []

    def render(self) -> Dict[str, Any]:
        """Render card HTML."""
        return {
            "type": "custom:pilotsuite-weather-automation",
            "title": self.config.title,
            "current_weather": self._get_current_weather(),
            "forecast": self._get_forecast() if self.config.show_forecast else [],
            "automations": self._get_active_automations() if self.config.show_automations else [],
            "actions": [
                {"label": "Refresh", "action": "refresh_weather"},
                {"label": "Run All", "action": "trigger_all"},
            ]
        }

    def _get_current_weather(self) -> Dict[str, Any]:
        """Get current weather state."""
        return {
            "temperature": self._weather_state.get("temperature", 0),
            "condition": self._weather_state.get("condition", "unknown"),
            "humidity": self._weather_state.get("humidity", 0),
            "wind_speed": self._weather_state.get("wind_speed", 0),
        }

    def _get_forecast(self) -> List[Dict[str, Any]]:
        """Get weather forecast."""
        return self._weather_state.get("forecast", [])[:self.config.forecast_days]

    def _get_active_automations(self) -> List[Dict[str, Any]]:
        """Get weather-triggered automations."""
        return [
            a for a in self._automations
            if a.get("enabled", True)
        ]


# =============================================================================
# CARD 4: ANALYTICS DASHBOARD CARD
# =============================================================================

@dataclass
class AnalyticsCardConfig:
    """Configuration for analytics card."""
    title: str = "Analytics"
    metrics: List[str] = None
    time_range: str = "7d"  # 1d, 7d, 30d, 90d
    chart_type: str = "line"  # line, bar, pie
    refresh_interval: int = 300  # seconds


class AnalyticsDashboardCard:
    """
    Lovelace Card: Advanced Analytics Dashboard
    
    Features:
    - Multiple metric visualization
    - Time range selection
    - Interactive charts
    - Export capabilities
    
    YAML Config:
    ```yaml
    type: custom:pilotsuite-analytics
    title: System Analytics
    metrics:
      - presence_confidence
      - energy_savings
      - automation_count
    time_range: 7d
    chart_type: line
    ```
    """

    def __init__(self, config: AnalyticsCardConfig):
        self.config = config
        self._metrics_data = {}

    def render(self) -> Dict[str, Any]:
        """Render card HTML."""
        return {
            "type": "custom:pilotsuite-analytics",
            "title": self.config.title,
            "metrics": self._get_metrics(),
            "time_range": self.config.time_range,
            "chart_type": self.config.chart_type,
            "actions": [
                {"label": "1D", "action": "set_range", "params": {"range": "1d"}},
                {"label": "7D", "action": "set_range", "params": {"range": "7d"}},
                {"label": "30D", "action": "set_range", "params": {"range": "30d"}},
                {"label": "Export", "action": "export_data"},
            ]
        }

    def _get_metrics(self) -> List[Dict[str, Any]]:
        """Get metrics data."""
        metrics = []
        
        for metric_name in (self.config.metrics or []):
            if metric_name in self._metrics_data:
                metrics.append({
                    "name": metric_name,
                    "data": self._metrics_data[metric_name],
                })
        
        return metrics


# =============================================================================
# CARD 5: SYSTEM HEALTH CARD
# =============================================================================

@dataclass
class SystemHealthCardConfig:
    """Configuration for system health card."""
    title: str = "System Health"
    show_resources: bool = True
    show_services: bool = True
    show_errors: bool = True
    refresh_interval: int = 60  # seconds


class SystemHealthCard:
    """
    Lovelace Card: System Health Monitor
    
    Features:
    - Resource usage (CPU, Memory, Disk)
    - Service status
    - Error/warning display
    - Quick actions (restart, refresh)
    
    YAML Config:
    ```yaml
    type: custom:pilotsuite-system-health
    title: System Health
    show_resources: true
    show_services: true
    show_errors: true
    ```
    """

    def __init__(self, config: SystemHealthCardConfig):
        self.config = config
        self._system_state = {}

    def render(self) -> Dict[str, Any]:
        """Render card HTML."""
        return {
            "type": "custom:pilotsuite-system-health",
            "title": self.config.title,
            "resources": self._get_resources() if self.config.show_resources else {},
            "services": self._get_services() if self.config.show_services else [],
            "errors": self._get_errors() if self.config.show_errors else [],
            "overall_status": self._get_overall_status(),
            "actions": [
                {"label": "Refresh", "action": "refresh"},
                {"label": "Restart", "action": "restart"},
                {"label": "Logs", "action": "view_logs"},
            ]
        }

    def _get_resources(self) -> Dict[str, Any]:
        """Get resource usage."""
        return {
            "cpu_percent": self._system_state.get("cpu_percent", 0),
            "memory_percent": self._system_state.get("memory_percent", 0),
            "disk_percent": self._system_state.get("disk_percent", 0),
        }

    def _get_services(self) -> List[Dict[str, Any]]:
        """Get service status."""
        return self._system_state.get("services", [])

    def _get_errors(self) -> List[Dict[str, Any]]:
        """Get recent errors."""
        return self._system_state.get("errors", [])

    def _get_overall_status(self) -> str:
        """Get overall system status."""
        errors = self._get_errors()
        if len(errors) > 0:
            return "warning"
        return "healthy"


# =============================================================================
# CARD REGISTRY
# =============================================================================

CARD_REGISTRY = {
    "pilotsuite-notifications": NotificationCard,
    "pilotsuite-calendar": CalendarCard,
    "pilotsuite-weather-automation": WeatherAutomationCard,
    "pilotsuite-analytics": AnalyticsDashboardCard,
    "pilotsuite-system-health": SystemHealthCard,
}


def create_card(card_type: str, config: Dict[str, Any]):
    """Create a card instance from type and config."""
    if card_type not in CARD_REGISTRY:
        raise ValueError(f"Unknown card type: {card_type}")
    
    card_class = CARD_REGISTRY[card_type]
    config_class = {
        "pilotsuite-notifications": NotificationCardConfig,
        "pilotsuite-calendar": CalendarCardConfig,
        "pilotsuite-weather-automation": WeatherCardConfig,
        "pilotsuite-analytics": AnalyticsCardConfig,
        "pilotsuite-system-health": SystemHealthCardConfig,
    }[card_type]
    
    return card_class(config_class(**config))
