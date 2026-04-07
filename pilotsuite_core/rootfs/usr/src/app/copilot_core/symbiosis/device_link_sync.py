"""Device Link Sync — Runtime Symbiosis Layer.
Syncs HA Entities to Core Device Links with capabilities.
"""
from __future__ import annotations
import logging, requests
from typing import Dict, List, Optional
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

@dataclass
class DeviceLink:
    link_id: str
    ha_entity_id: str
    name: str
    domain: str
    capabilities: List[str] = None
    zone_ref: Optional[str] = None
    last_state: Optional[dict] = None
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []

class DeviceLinkSync:
    """Manages sync between HA Entities and Core Device Links."""
    
    def __init__(self, core_url: str, ha_url: str, ha_token: str):
        self.core_url = core_url
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.links: Dict[str, DeviceLink] = {}
    
    async def discover_ha_entities(self) -> List[Dict]:
        """Fetch all Entities from Home Assistant."""
        headers = {"Authorization": f"Bearer {self.ha_token}"}
        resp = requests.get(f"{self.ha_url}/api/states", headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
    
    def _extract_capabilities(self, entity: Dict) -> List[str]:
        """Extract capabilities from HA entity attributes."""
        caps = []
        attrs = entity.get("attributes", {})
        domain = entity.get("entity_id", "").split(".")[0]
        
        if domain == "light":
            caps.append("on_off")
            if "brightness" in attrs:
                caps.append("brightness")
            if "color_temp" in attrs or "rgb_color" in attrs:
                caps.append("color")
            if "effect" in attrs:
                caps.append("effect")
        elif domain == "media_player":
            caps.append("on_off")
            caps.append("volume")
            caps.append("play_pause")
            if "source_list" in attrs:
                caps.append("source_select")
        elif domain == "climate":
            caps.append("temperature")
            caps.append("hvac_mode")
            if "fan_mode" in attrs:
                caps.append("fan_mode")
        elif domain == "cover":
            caps.append("open_close")
            if "current_position" in attrs:
                caps.append("position")
        
        return caps
    
    async def sync_entity_to_core(self, link: DeviceLink) -> bool:
        """Push Device Link to Core API."""
        payload = {
            "link_id": link.link_id,
            "ha_entity_id": link.ha_entity_id,
            "name": link.name,
            "domain": link.domain,
            "capabilities": link.capabilities,
            "zone_ref": link.zone_ref,
            "last_state": link.last_state
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(f"{self.core_url}/api/v1/devices/links", json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            _LOGGER.info(f"Synced Device Link {link.link_id} to Core")
            return True
        _LOGGER.error(f"Failed to sync device {link.link_id}: {resp.text}")
        return False
    
    async def full_sync(self) -> Dict:
        """Perform full sync of HA Entities to Device Links."""
        ha_entities = await self.discover_ha_entities()
        
        synced = 0
        created = 0
        
        for entity in ha_entities:
            entity_id = entity.get("entity_id", "")
            domain = entity_id.split(".")[0]
            
            # Skip unsupported domains
            if domain not in ("light", "media_player", "climate", "cover", "switch", "input_boolean"):
                continue
            
            link_id = f"device.{entity_id.replace('.', '_')}"
            
            link = DeviceLink(
                link_id=link_id,
                ha_entity_id=entity_id,
                name=entity.get("attributes", {}).get("friendly_name", entity_id),
                domain=domain,
                capabilities=self._extract_capabilities(entity),
                last_state={
                    "state": entity.get("state"),
                    "attributes": entity.get("attributes", {})
                }
            )
            
            if await self.sync_entity_to_core(link):
                self.links[link_id] = link
                created += 1
        
        return {"synced": synced, "created": created, "total": len(self.links)}
