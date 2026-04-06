"""State Bridge Sync — Runtime Symbiosis Layer.
Syncs HA Entity States to Core State Bridges with history.
"""
from __future__ import annotations
import logging, requests
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

@dataclass
class StateBridge:
    state_id: str
    ha_entity_id: str
    name: str
    current_state: Optional[dict] = None
    history: List[dict] = field(default_factory=list)
    subscribers: List[str] = field(default_factory=list)
    last_sync: Optional[str] = None
    
    def __post_init__(self):
        pass

class StateBridgeSync:
    """Manages sync between HA Entity States and Core State Bridges."""
    
    def __init__(self, core_url: str, ha_url: str, ha_token: str):
        self.core_url = core_url
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.bridges: Dict[str, StateBridge] = {}
        self._max_history = 50
    
    async def discover_ha_states(self) -> List[Dict]:
        """Fetch all Entity States from Home Assistant."""
        headers = {"Authorization": f"Bearer {self.ha_token}"}
        resp = requests.get(f"{self.ha_url}/api/states", headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
    
    async def sync_state_to_core(self, bridge: StateBridge) -> bool:
        """Push State Bridge to Core API."""
        payload = {
            "state_id": bridge.state_id,
            "ha_entity_id": bridge.ha_entity_id,
            "name": bridge.name,
            "current_state": bridge.current_state,
            "history": bridge.history[-self._max_history:],
            "subscribers": bridge.subscribers,
            "last_sync": bridge.last_sync
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(f"{self.core_url}/api/v1/states", json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            _LOGGER.info(f"Synced State Bridge {bridge.state_id} to Core")
            return True
        _LOGGER.error(f"Failed to sync state {bridge.state_id}: {resp.text}")
        return False
    
    async def full_sync(self) -> Dict:
        """Perform full sync of HA States to State Bridges."""
        ha_states = await self.discover_ha_states()
        
        synced = 0
        created = 0
        
        for state in ha_states:
            entity_id = state.get("entity_id", "").replace(".", "_")
            state_id = f"state.{entity_id}"
            
            bridge = StateBridge(
                state_id=state_id,
                ha_entity_id=state.get("entity_id"),
                name=state.get("attributes", {}).get("friendly_name", state.get("entity_id")),
                current_state={
                    "state": state.get("state"),
                    "attributes": state.get("attributes", {}),
                    "last_changed": state.get("last_changed"),
                    "last_updated": state.get("last_updated")
                },
                last_sync=datetime.utcnow().isoformat()
            )
            
            if await self.sync_state_to_core(bridge):
                self.bridges[state_id] = bridge
                created += 1
        
        return {"synced": synced, "created": created, "total": len(self.bridges)}
