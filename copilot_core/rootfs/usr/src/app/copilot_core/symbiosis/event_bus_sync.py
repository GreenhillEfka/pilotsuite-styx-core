"""Event Bus Sync — Runtime Symbiosis Layer.
Bridges HA Bus Events to Core Event Bus.
"""
from __future__ import annotations
import logging, requests, json
from typing import Dict, List, Optional
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
    """Bridges events between HA and Core."""
    
    def __init__(self, core_url: str, ha_url: str, ha_token: str):
        self.core_url = core_url
        self.ha_url = ha_url
        self.ha_token = ha_token
    
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
