"""Dashboard Data Provider - Real-time Core Metrics (Slice 144).

Replaces placeholder data with live metrics from ModuleRegistry, BrainGraph, etc.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


@dataclass
class DashboardMetrics:
    """Real-time dashboard metrics from Core."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Module stats
    modules_active: int = 0
    modules_learning: int = 0
    modules_off: int = 0
    
    # Zone stats
    zones_total: int = 0
    zones_occupied: int = 0
    zones_empty: int = 0
    
    # Brain stats
    brain_nodes: int = 0
    brain_edges: int = 0
    
    # Event stats
    events_last_hour: int = 0
    events_last_24h: int = 0
    
    # System health
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0


class DashboardDataProvider:
    """Provider for real-time dashboard data with caching."""
    
    def __init__(self, cache_ttl: float = 10.0):
        self._cache_ttl = cache_ttl
        self._last_update: Optional[float] = None
        self._cached_metrics: Optional[DashboardMetrics] = None
        self._lock = threading.Lock()
        
        _LOGGER.info("DashboardDataProvider initialized (cache_ttl=%ss)", cache_ttl)
    
    def get_metrics(self) -> DashboardMetrics:
        """Get current dashboard metrics (cached or fresh)."""
        with self._lock:
            now = time.monotonic()
            
            # Return cached if still valid
            if self._cached_metrics and self._last_update:
                if now - self._last_update < self._cache_ttl:
                    return self._cached_metrics
            
            # Fetch fresh data
            metrics = self._fetch_live_metrics()
            self._cached_metrics = metrics
            self._last_update = now
            
            return metrics
    
    def _fetch_live_metrics(self) -> DashboardMetrics:
        """Fetch live metrics from all Core services."""
        metrics = DashboardMetrics()
        
        # Module stats from Registry
        try:
            from copilot_core.module_registry import ModuleRegistry
            registry = ModuleRegistry.get_instance()
            states = registry.get_all_states()
            
            metrics.modules_active = sum(1 for s in states.values() if s == "active")
            metrics.modules_learning = sum(1 for s in states.values() if s == "learning")
            metrics.modules_off = sum(1 for s in states.values() if s == "off")
        except Exception as exc:
            _LOGGER.debug("Could not fetch module stats: %s", exc)
        
        # Zone stats from HabitusZoneEngine
        try:
            from copilot_core.hub.habitus_zones import HabitusZoneEngine
            engine = HabitusZoneEngine()
            overview = engine.get_overview()
            
            zones_data = overview.get("zones", {})
            metrics.zones_total = len(zones_data)
            
            # Count occupied zones (simplified - would need presence data)
            metrics.zones_occupied = len([z for z in zones_data.values() if z.get("presence") == "present"])
            metrics.zones_empty = metrics.zones_total - metrics.zones_occupied
        except Exception as exc:
            _LOGGER.debug("Could not fetch zone stats: %s", exc)
        
        # Brain stats from BrainGraphService
        try:
            from copilot_core.brain_graph.service import BrainGraphService
            service = BrainGraphService()
            stats = service.get_graph_stats()
            
            metrics.brain_nodes = stats.get("node_count", 0)
            metrics.brain_edges = stats.get("edge_count", 0)
        except Exception as exc:
            _LOGGER.debug("Could not fetch brain stats: %s", exc)
        
        # System health
        try:
            from copilot_core.system_health.service import SystemHealthMonitor
            monitor = SystemHealthMonitor()
            health = monitor.get_full_health()
            
            metrics.cpu_usage = health.get("cpu_usage", 0.0)
            metrics.memory_usage = health.get("memory_usage", 0.0)
            metrics.disk_usage = health.get("disk_usage", 0.0)
        except Exception as exc:
            _LOGGER.debug("Could not fetch system health: %s", exc)
        
        return metrics
    
    def invalidate_cache(self) -> None:
        """Force cache invalidation."""
        with self._lock:
            self._cached_metrics = None
            self._last_update = None


# Global instance
_dashboard_provider: Optional[DashboardDataProvider] = None
_dashboard_lock = threading.Lock()


def get_dashboard_provider() -> DashboardDataProvider:
    """Get singleton DashboardDataProvider instance."""
    global _dashboard_provider
    with _dashboard_lock:
        if _dashboard_provider is None:
            _dashboard_provider = DashboardDataProvider()
        return _dashboard_provider
