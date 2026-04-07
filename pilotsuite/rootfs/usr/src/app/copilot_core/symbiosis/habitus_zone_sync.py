"""Habitus Zone Sync — Runtime Symbiosis Layer.
Bidirectional sync between HA Areas and Core Habitus Zones.
"""
from __future__ import annotations
import logging, asyncio, requests
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

@dataclass
class HabitusZone:
    zone_id: str
    name: str
    ha_area_id: Optional[str] = None
    linked_entities: List[str] = None
    habitus_rules: List[str] = None
    active_context: str = "ready"
    last_sync: Optional[str] = None
    
    def __post_init__(self):
        if self.linked_entities is None:
            self.linked_entities = []
        if self.habitus_rules is None:
            self.habitus_rules = []

class HabitusZoneSync:
    """Manages bidirectional sync between HA Areas and Core Habitus Zones."""
    
    def __init__(self, core_url: str, ha_url: str, ha_token: str):
        self.core_url = core_url
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.zones: Dict[str, HabitusZone] = {}
        self._sync_interval = 30  # seconds
        
    async def discover_ha_areas(self) -> List[Dict]:
        """Fetch all Areas from Home Assistant."""
        headers = {"Authorization": f"Bearer {self.ha_token}"}
        resp = requests.get(f"{self.ha_url}/api/config/area_registry", headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
    
    async def sync_zone_to_core(self, zone: HabitusZone) -> bool:
        """Push Habitus Zone state to Core API."""
        payload = {
            "zone_id": zone.zone_id,
            "name": zone.name,
            "ha_area_id": zone.ha_area_id,
            "linked_entities": zone.linked_entities,
            "habitus_rules": zone.habitus_rules,
            "active_context": zone.active_context
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(f"{self.core_url}/api/v1/habitus/zones", json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            zone.last_sync = datetime.utcnow().isoformat()
            _LOGGER.info(f"Synced zone {zone.zone_id} to Core")
            return True
        _LOGGER.error(f"Failed to sync zone {zone.zone_id}: {resp.text}")
        return False
    
    async def pull_core_zones(self) -> List[HabitusZone]:
        """Fetch existing Habitus Zones from Core."""
        resp = requests.get(f"{self.core_url}/api/v1/habitus/zones", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            zones = []
            for z in data.get("zones", []):
                zones.append(HabitusZone(
                    zone_id=z.get("zone_id"),
                    name=z.get("name"),
                    ha_area_id=z.get("ha_area_id"),
                    linked_entities=z.get("linked_entities", []),
                    habitus_rules=z.get("habitus_rules", []),
                    active_context=z.get("active_context", "ready"),
                    last_sync=z.get("last_sync")
                ))
            return zones
        return []
    
    async def full_sync(self) -> Dict:
        """Perform full bidirectional sync."""
        ha_areas = await self.discover_ha_areas()
        core_zones = await self.pull_core_zones()
        
        synced = 0
        created = 0
        
        # Sync HA Areas → Core (if not exists)
        for area in ha_areas:
            zone_id = f"zone.{area['name'].lower().replace(' ', '_')}"
            if not any(z.zone_id == zone_id for z in core_zones):
                new_zone = HabitusZone(
                    zone_id=zone_id,
                    name=area["name"],
                    ha_area_id=area["area_id"]
                )
                if await self.sync_zone_to_core(new_zone):
                    self.zones[zone_id] = new_zone
                    created += 1
        
        # Sync Core Zones → Local Cache
        for zone in core_zones:
            self.zones[zone.zone_id] = zone
            synced += 1
        
        return {"synced": synced, "created": created, "total": len(self.zones)}
    
    def get_zone(self, zone_id: str) -> Optional[HabitusZone]:
        return self.zones.get(zone_id)
    
    def list_zones(self) -> List[HabitusZone]:
        return list(self.zones.values())
