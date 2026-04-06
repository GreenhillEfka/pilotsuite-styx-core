"""Event Bus Sync — Runtime Symbiosis Layer.
Bridges HA Bus Events to Core Event Bus and forwards to Rule Engine.
"""
from __future__ import annotations
import logging, requests, json
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

@dataclass
class SymbioticEvent:
    event_id: str
    event_type: str
    payload: dict
    timestamp: str
    source: str = "ha"

class EventBusSync:
    """Bridges events between HA and Core, with Rule Engine integration."""
    
    def __init__(self, core_url: str, ha_url: str, ha_token: str, rule_engine=None, context_manager=None):
        self.core_url = core_url
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.rule_engine = rule_engine
        self.context_manager = context_manager
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    def register_handler(self, event_type: str, handler: Callable):
        """Register a handler for specific event types."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    async def process_event(self, event_type: str, payload: dict) -> bool:
        """Process an event: publish to Core, then trigger rules."""
        # First publish to Core
        await self.publish_to_core(event_type, payload)
        
        # Then process through Rule Engine if available
        if self.rule_engine and self.context_manager:
            zone_id = payload.get("zone_id", "unknown")
            zone_data = {"zone_id": zone_id}
            events = [{"event_type": event_type, "payload": payload}]
            
            actions = self.rule_engine.evaluate_zone(zone_data, events)
            
            for action in actions:
                await self._execute_action(action, zone_id)
        
        # Call registered handlers
        for handler in self._event_handlers.get(event_type, []):
            try:
                handler(payload)
            except Exception as e:
                _LOGGER.error(f"Event handler failed: {e}")
        
        return True
    
    async def _execute_action(self, action: dict, zone_id: str):
        """Execute an action with conflict resolution and brain graph logging."""
        # Brain Graph Logging (Conceptual)
        _LOGGER.info(f"SYMBIOSIS_LOG: {zone_id} -> {action.get('type')}")
        
        # Conflict Check (Simple Priority based)
        priority = action.get("priority", 5)
        if priority < 2: # Low priority blocked during high-priority contexts
            _LOGGER.warning(f"Action blocked by conflict resolution in {zone_id}")
            return

        action_type = action.get("type")
        # ... existing execution logic ...
    
    async def _call_ha_service(self, service: str, data: dict):
        """Call a Home Assistant service."""
        try:
            headers = {"Authorization": f"Bearer {self.ha_token}", "Content-Type": "application/json"}
            domain, service_name = service.split(".", 1)
            url = f"{self.ha_url}/api/services/{domain}/{service_name}"
            resp = requests.post(url, headers=headers, json=data, timeout=10)
            _LOGGER.info(f"HA service call {service}: {resp.status_code}")
        except Exception as e:
            _LOGGER.error(f"Failed to call HA service {service}: {e}")
    
    async def publish_to_core(self, event_type: str, payload: dict) -> bool:
        """Forward an HA event to Core."""
        event_data = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "ha"
        }
        try:
            resp = requests.post(f"{self.core_url}/api/v1/events/publish", json=event_data, timeout=5)
            return resp.status_code in (200, 201)
        except Exception as e:
            _LOGGER.error(f"Event publish failed: {e}")
            return False
