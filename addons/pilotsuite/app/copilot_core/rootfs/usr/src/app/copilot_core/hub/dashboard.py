"""Unified Dashboard Hub for PilotSuite (v6.0.0).

Central dashboard aggregator that collects data from all modules
(energy, battery, heat pump, EV, weather, mood, etc.) and presents
a unified overview with configurable layouts and widgets.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Widget types ──────────────────────────────────────────────────────────

WIDGET_TYPES = (
    "energy_overview",
    "battery_status",
    "heat_pump_status",
    "ev_charging",
    "weather_warnings",
    "fuel_prices",
    "tariff_chart",
    "mood_indicator",
    "comfort_index",
    "system_health",
    "quick_actions",
    "forecast_chart",
    "savings_tracker",
    "automation_insights",
)


@dataclass
class Widget:
    """Dashboard widget configuration and data."""

    widget_type: str
    title: str
    icon: str
    size: str = "medium"  # small, medium, large, full
    position: int = 0
    enabled: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    last_updated: str = ""


@dataclass
class DashboardLayout:
    """Dashboard layout configuration."""

    name: str = "default"
    columns: int = 3
    widgets: list[dict[str, Any]] = field(default_factory=list)
    theme: str = "auto"  # auto, light, dark
    language: str = "de"
    created_at: str = ""


@dataclass
class DashboardOverview:
    """Complete dashboard overview data."""

    layout: dict[str, Any] = field(default_factory=dict)
    widgets: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    alerts_count: int = 0
    active_devices: int = 0
    savings_today_eur: float = 0.0
    generated_at: str = ""
    ok: bool = True


# ── Default widget configs ────────────────────────────────────────────────

_DEFAULT_WIDGETS = [
    Widget("energy_overview", "Energie", "mdi:flash", "large", 0),
    Widget("battery_status", "Batterie", "mdi:battery-charging", "medium", 1),
    Widget("heat_pump_status", "Wärmepumpe", "mdi:heat-pump", "medium", 2),
    Widget("ev_charging", "E-Auto", "mdi:ev-station", "medium", 3),
    Widget("weather_warnings", "Wetter", "mdi:weather-cloudy-alert", "small", 4),
    Widget("tariff_chart", "Strompreis", "mdi:chart-line", "medium", 5),
    Widget("mood_indicator", "Stimmung", "mdi:emoticon", "small", 6),
    Widget("system_health", "System", "mdi:server", "small", 7),
    Widget("quick_actions", "Aktionen", "mdi:lightning-bolt", "medium", 8),
    Widget("savings_tracker", "Ersparnis", "mdi:piggy-bank", "medium", 9),
]


class DashboardHub:
    """Central dashboard aggregator.

    Collects data from all PilotSuite modules and provides a unified
    dashboard view with configurable layouts and widgets.
    """

    def __init__(self) -> None:
        self._layout = DashboardLayout(
            created_at=datetime.now(timezone.utc).isoformat()
        )
        self._widgets: list[Widget] = list(_DEFAULT_WIDGETS)
        self._data_sources: dict[str, Any] = {}
        self._savings_today: float = 0.0
        self._alerts_count: int = 0

    def set_layout(self, name: str, columns: int = 3, theme: str = "auto", language: str = "de") -> None:
        """Set dashboard layout."""
        self._layout.name = name
        self._layout.columns = max(1, min(columns, 4))
        self._layout.theme = theme
        self._layout.language = language

    def add_widget(self, widget_type: str, title: str, icon: str, size: str = "medium") -> bool:
        """Add a widget to the dashboard."""
        if widget_type not in WIDGET_TYPES:
            return False
        pos = len(self._widgets)
        self._widgets.append(Widget(widget_type, title, icon, size, pos))
        return True

    def remove_widget(self, widget_type: str) -> bool:
        """Remove a widget by type."""
        before = len(self._widgets)
        self._widgets = [w for w in self._widgets if w.widget_type != widget_type]
        return len(self._widgets) < before

    def reorder_widgets(self, order: list[str]) -> None:
        """Reorder widgets by type list."""
        by_type = {w.widget_type: w for w in self._widgets}
        reordered = []
        for i, wt in enumerate(order):
            if wt in by_type:
                w = by_type.pop(wt)
                w.position = i
                reordered.append(w)
        # Append remaining
        for w in by_type.values():
            w.position = len(reordered)
            reordered.append(w)
        self._widgets = reordered

    def update_widget_data(self, widget_type: str, data: dict[str, Any]) -> None:
        """Update a widget's data from its source module."""
        for w in self._widgets:
            if w.widget_type == widget_type:
                w.data = data
                w.last_updated = datetime.now(timezone.utc).isoformat()
                break

    def register_data_source(self, name: str, source: Any) -> None:
        """Register a data source module."""
        self._data_sources[name] = source

    def set_savings(self, savings_eur: float) -> None:
        """Update today's savings."""
        self._savings_today = savings_eur

    def set_alerts_count(self, count: int) -> None:
        """Update active alerts count."""
        self._alerts_count = count

    def get_overview(self) -> DashboardOverview:
        """Get complete dashboard overview."""
        now = datetime.now(timezone.utc).isoformat()

        widgets_data = []
        for w in self._widgets:
            if w.enabled:
                widgets_data.append({
                    "widget_type": w.widget_type,
                    "title": w.title,
                    "icon": w.icon,
                    "size": w.size,
                    "position": w.position,
                    "data": w.data,
                    "last_updated": w.last_updated,
                })

        summary = {
            "total_widgets": len(widgets_data),
            "data_sources": list(self._data_sources.keys()),
            "layout_name": self._layout.name,
            "theme": self._layout.theme,
            "language": self._layout.language,
        }

        return DashboardOverview(
            layout={
                "name": self._layout.name,
                "columns": self._layout.columns,
                "theme": self._layout.theme,
                "language": self._layout.language,
            },
            widgets=widgets_data,
            summary=summary,
            alerts_count=self._alerts_count,
            active_devices=len(self._data_sources),
            savings_today_eur=round(self._savings_today, 2),
            generated_at=now,
        )

    def get_widget(self, widget_type: str) -> dict[str, Any] | None:
        """Get a single widget's data."""
        for w in self._widgets:
            if w.widget_type == widget_type:
                return {
                    "widget_type": w.widget_type,
                    "title": w.title,
                    "icon": w.icon,
                    "size": w.size,
                    "data": w.data,
                    "last_updated": w.last_updated,
                }
        return None

    def get_widget_types(self) -> list[str]:
        """Get list of active widget types."""
        return [w.widget_type for w in self._widgets if w.enabled]
