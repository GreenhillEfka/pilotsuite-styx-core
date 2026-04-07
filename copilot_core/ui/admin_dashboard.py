"""P6-001: Admin Dashboard V2 — All Entities, Real-Time, Analytics."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import time

logger = logging.getLogger(__name__)


class DashboardWidgetType(Enum):
    """Dashboard widget types."""
    STAT_CARD = "stat_card"
    CHART = "chart"
    TABLE = "table"
    MAP = "map"
    LIST = "list"
    CONTROL = "control"


@dataclass
class DashboardWidget:
    """Dashboard widget definition."""
    id: str
    title: str
    widget_type: DashboardWidgetType
    data_source: str
    config: Dict[str, Any] = field(default_factory=dict)
    position: Dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0, "w": 4, "h": 3})
    refresh_interval: int = 30


@dataclass
class DashboardTab:
    """Dashboard tab."""
    id: str
    name: str
    icon: str
    widgets: List[DashboardWidget] = field(default_factory=list)
    visible: bool = True


class AdminDashboard:
    """Admin Dashboard V2 with real-time updates."""

    def __init__(self):
        self._tabs: Dict[str, DashboardTab] = {}
        self._data_sources: Dict[str, callable] = {}
        self._register_core_tabs()

    def _register_core_tabs(self):
        """Register core dashboard tabs."""
        # Overview Tab
        self._tabs["overview"] = DashboardTab(
            id="overview",
            name="Overview",
            icon="dashboard",
            widgets=[
                DashboardWidget("system_health", "System Health", DashboardWidgetType.STAT_CARD, "health"),
                DashboardWidget("active_users", "Active Users", DashboardWidgetType.STAT_CARD, "users"),
                DashboardWidget("recent_events", "Recent Events", DashboardWidgetType.LIST, "events"),
                DashboardWidget("system_chart", "System Load", DashboardWidgetType.CHART, "metrics"),
            ]
        )
        
        # RAG Tab
        self._tabs["rag"] = DashboardTab(
            id="rag",
            name="RAG System",
            icon="search",
            widgets=[
                DashboardWidget("doc_count", "Documents", DashboardWidgetType.STAT_CARD, "rag/docs"),
                DashboardWidget("query_stats", "Query Stats", DashboardWidgetType.CHART, "rag/queries"),
                DashboardWidget("recent_queries", "Recent Queries", DashboardWidgetType.TABLE, "rag/recent"),
            ]
        )
        
        # Voice Tab
        self._tabs["voice"] = DashboardTab(
            id="voice",
            name="Voice",
            icon="mic",
            widgets=[
                DashboardWidget("voice_sessions", "Active Sessions", DashboardWidgetType.STAT_CARD, "voice/sessions"),
                DashboardWidget("stt_stats", "STT Stats", DashboardWidgetType.CHART, "voice/stt"),
                DashboardWidget("tts_stats", "TTS Stats", DashboardWidgetType.CHART, "voice/tts"),
            ]
        )
        
        # ML Tab
        self._tabs["ml"] = DashboardTab(
            id="ml",
            name="Machine Learning",
            icon="psychology",
            widgets=[
                DashboardWidget("patterns", "Detected Patterns", DashboardWidgetType.TABLE, "ml/patterns"),
                DashboardWidget("habits", "Learned Habits", DashboardWidgetType.LIST, "ml/habits"),
                DashboardWidget("anomalies", "Anomalies", DashboardWidgetType.TABLE, "ml/anomalies"),
            ]
        )
        
        # Users Tab
        self._tabs["users"] = DashboardTab(
            id="users",
            name="Users",
            icon="people",
            widgets=[
                DashboardWidget("user_list", "All Users", DashboardWidgetType.TABLE, "users/list"),
                DashboardWidget("preferences", "Preferences", DashboardWidgetType.TABLE, "users/preferences"),
            ]
        )
        
        # Settings Tab
        self._tabs["settings"] = DashboardTab(
            id="settings",
            name="Settings",
            icon="settings",
            widgets=[
                DashboardWidget("system_config", "System Config", DashboardWidgetType.CONTROL, "config/system"),
                DashboardWidget("api_keys", "API Keys", DashboardWidgetType.CONTROL, "config/api"),
            ]
        )

    def register_data_source(self, name: str, fetch_fn: callable):
        """Register a data source."""
        self._data_sources[name] = fetch_fn

    def get_tab(self, tab_id: str) -> Optional[DashboardTab]:
        """Get tab by ID."""
        return self._tabs.get(tab_id)

    def list_tabs(self) -> List[DashboardTab]:
        """List all tabs."""
        return [t for t in self._tabs.values() if t.visible]

    def add_widget(self, tab_id: str, widget: DashboardWidget) -> bool:
        """Add widget to tab."""
        if tab_id not in self._tabs:
            return False
        self._tabs[tab_id].widgets.append(widget)
        return True

    def remove_widget(self, tab_id: str, widget_id: str) -> bool:
        """Remove widget from tab."""
        if tab_id not in self._tabs:
            return False
        self._tabs[tab_id].widgets = [
            w for w in self._tabs[tab_id].widgets if w.id != widget_id
        ]
        return True

    async def fetch_widget_data(self, widget: DashboardWidget) -> Any:
        """Fetch data for a widget."""
        if widget.data_source in self._data_sources:
            return await self._data_sources[widget.data_source]()
        return {"error": "Unknown data source"}

    def get_layout(self) -> Dict[str, Any]:
        """Get dashboard layout."""
        return {
            "tabs": [
                {
                    "id": tab.id,
                    "name": tab.name,
                    "icon": tab.icon,
                    "widgets": [
                        {
                            "id": w.id,
                            "title": w.title,
                            "type": w.widget_type.value,
                            "position": w.position,
                            "config": w.config,
                        }
                        for w in tab.widgets
                    ]
                }
                for tab in self.list_tabs()
            ]
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics."""
        return {
            "total_tabs": len(self._tabs),
            "total_widgets": sum(len(t.widgets) for t in self._tabs.values()),
            "data_sources": len(self._data_sources),
        }


# Global default dashboard
default_dashboard: Optional[AdminDashboard] = None


def init_admin_dashboard() -> AdminDashboard:
    """Initialize global admin dashboard."""
    global default_dashboard
    default_dashboard = AdminDashboard()
    return default_dashboard
