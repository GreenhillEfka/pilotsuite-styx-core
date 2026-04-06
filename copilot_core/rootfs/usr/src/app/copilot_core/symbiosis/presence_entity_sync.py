"""Presence Entity Sync — Runtime Symbiosis Layer.
Syncs HA Binary Sensors (Presence/Motion) to Core Presence Entities.
"""
from __future__ import annotations
import logging, requests
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

@dataclass
class PresenceEntity:
    entity_id: str
    ha_entity_id: str
    name: str
    presence_type: str  # motion, occupancy, user_presence
    zone_ref: Optional[str] = None
    current_state: bool = False
    last_changed: Optional[str] = None
    
    def __post_init__(self):
        pass

class PresenceEntitySync:
    """Manages sync between HA Binary Sensors and Core Presence Entities."""
    
    def __init__(self, core_url: str, ha_url: str, ha_token: str):
        self.core_url = core_url
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.entities: Dict[str, PresenceEntity] = {}
    
    async def discover_ha_presence_sensors(self) -> List[Dict]:
        """Fetch presence-related binary sensors from HA."""
        headers = {"Authorization": f"Bearer {self.ha_token}"}
        resp = requests.get(f"{self.ha_url}/api/states", headers=headers, timeout=10)
        if resp.status_code == 200:
            states = resp.json()
            # Filter for binary sensors related to presence/motion/occupancy
            return [
                s for s in states 
                if s.get("entity_id", "").startswith("binary_sensor.") and
                   any(kw in s.get("entity_id", "") for kw in ["motion", "occupancy", "presence", "person"])
            ]
        return []
    
    def _determine_presence_type(self, entity_id: str) -> str:
        """Determine presence type from entity_id."""
        if "motion" in entity_id:
            return "motion"
        elif "occupancy" in entity_id:
            return "occupancy"
        elif "person" in entity_id:
            return "user_presence"
        return "presence"
    
    async def sync_entity_to_core(self, entity: PresenceEntity) -> bool:
        """Push Presence Entity to Core API."""
        payload = {
            "entity_id": entity.entity_id,
            "ha_entity_id": entity.ha_entity_id,
            "name": entity.name,
            "presence_type": entity.presence_type,
            "zone_ref": entity.zone_ref,
            "current_state": entity.current_state,
            "last_changed": entity.last_changed
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(f"{self.core_url}/api/v1/entities/presence", json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            _LOGGER.info(f"Synced Presence Entity {entity.entity_id} to Core")
            return True
        _LOGGER.error(f"Failed to sync presence {entity.entity_id}: {resp.text}")
        return False
    
    async def full_sync(self) -> Dict:
        """Perform full sync of HA presence sensors to Core."""
        ha_sensors = await self.discover_ha_presence_sensors()
        
        synced = 0
        created = 0
        
        for sensor in ha_sensors:
            entity_id = sensor.get("entity_id", "").replace(".", "_")
            presence_entity = PresenceEntity(
                entity_id=f"presence.{entity_id}",
                ha_entity_id=sensor.get("entity_id"),
                name=sensor.get("attributes", {}).get("friendly_name", entity_id),
                presence_type=self._determine_presence_type(sensor.get("entity_id", "")),
                current_state=sensor.get("state") == "on",
                last_changed=sensor.get("last_changed")
            )
            
            if await self.sync_entity_to_core(presence_entity):
                self.entities[presence_entity.entity_id] = presence_entity
                created += 1
        
        return {"synced": synced, "created": created, "total": len(self.entities)}
