"""Live Symbiosis Service — Real-time HA ↔ Core integration.
Runs continuously to bridge events and trigger actions.
"""
import logging
import asyncio
from typing import Optional

_LOGGER = logging.getLogger(__name__)

class LiveSymbiosisService:
    """Continuously bridges HA events to Core Rule Engine."""
    
    def __init__(self, event_bus_sync, habitus_zone_sync, interval: float = 5.0):
        self.event_bus = event_bus_sync
        self.zone_sync = habitus_zone_sync
        self.interval = interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the live symbiosis loop."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        _LOGGER.info("Live Symbiosis Service started")
    
    async def stop(self):
        """Stop the service."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        _LOGGER.info("Live Symbiosis Service stopped")
    
    async def _run_loop(self):
        """Main loop: sync zones and process events."""
        while self._running:
            try:
                # Sync zones from HA
                await self.zone_sync.full_sync()
                
                # Process any pending events through Rule Engine
                # (Events are pushed via webhook/websocket from HA)
                
                await asyncio.sleep(self.interval)
            except Exception as e:
                _LOGGER.error(f"Live symbiosis loop error: {e}")
                await asyncio.sleep(self.interval)

async def init_live_symbiosis(services: dict) -> Optional[LiveSymbiosisService]:
    """Initialize and start live symbiosis with all dependencies."""
    try:
        from copilot_core.symbiosis.event_bus_sync import EventBusSync
        from copilot_core.symbiosis.habitus_zone_sync import HabitusZoneSync
        
        core_url = services.get("config", {}).get("core_url", "http://localhost:8909")
        ha_url = services.get("config", {}).get("ha_url", "http://homeassistant:8123")
        ha_token = services.get("config", {}).get("ha_token", "")
        
        # Get engines from services
        rule_engine = services.get("symbiosis_rules")
        context_manager = services.get("context_manager")
        
        # Create sync instances
        event_bus = EventBusSync(core_url, ha_url, ha_token, rule_engine, context_manager)
        zone_sync = HabitusZoneSync(core_url, ha_url, ha_token)
        
        # Create and start service
        service = LiveSymbiosisService(event_bus, zone_sync)
        await service.start()
        
        services["live_symbiosis"] = service
        _LOGGER.info("Live Symbiosis initialized and started")
        return service
        
    except Exception as e:
        _LOGGER.exception("Failed to init Live Symbiosis")
        return None
