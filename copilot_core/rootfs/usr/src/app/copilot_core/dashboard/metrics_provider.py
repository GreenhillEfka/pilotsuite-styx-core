"""Dashboard Live Metrics Provider (Slice 151).

Background service to periodically update and push metrics for Dashboard widgets.
Integrates with KPIService, SystemHealthMonitor, and ModuleRegistry.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

class MetricsProvider:
    """Service to provide live metrics for Dashboard visualization."""
    
    def __init__(self, update_interval: float = 2.0):
        self.update_interval = update_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_metrics: Dict[str, Any] = {}
        
    async def start(self):
        """Start the background metrics collection task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_collection_loop())
        _LOGGER.info("Dashboard Metrics Provider started (interval: %.1fs)", self.update_interval)
        
    async def stop(self):
        """Stop the background metrics collection task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        _LOGGER.info("Dashboard Metrics Provider stopped")

    async def _run_collection_loop(self):
        """Main loop for periodic metrics collection."""
        from copilot_core.dashboard.kpi_service import get_kpi_service
        from copilot_core.system_health.service import SystemHealthMonitor
        from copilot_core.module_registry import ModuleRegistry
        
        kpi_service = get_kpi_service()
        health_monitor = SystemHealthMonitor()
        registry = ModuleRegistry()
        
        while self._running:
            try:
                # 1. Collect KPIs
                kpi_data = kpi_service.get_all_metrics()
                
                # 2. Collect System Health
                health_data = health_monitor.get_summary()
                
                # 3. Collect Module Stats
                module_stats = {
                    "total": len(registry.get_all_states()),
                    "active": sum(1 for s in registry.get_all_states().values() if s != "off"),
                }
                
                # 4. Consolidate into Live Metrics Snapshot
                self._last_metrics = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "kpis": kpi_data,
                    "health": health_data,
                    "modules": module_stats,
                }
                
                # TODO: Trigger SSE push to connected clients
                
            except Exception as exc:
                _LOGGER.error("Error in metrics collection: %s", exc)
                
            await asyncio.sleep(self.update_interval)

    def get_latest_snapshot(self) -> Dict[str, Any]:
        """Get the most recent metrics snapshot."""
        return self._last_metrics

# Global instance for app-wide access
_metrics_provider: Optional[MetricsProvider] = None

def get_metrics_provider() -> MetricsProvider:
    """Get singleton MetricsProvider."""
    global _metrics_provider
    if _metrics_provider is None:
        _metrics_provider = MetricsProvider()
    return _metrics_provider
