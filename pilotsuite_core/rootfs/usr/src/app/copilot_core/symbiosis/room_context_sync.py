"""Room Context Sync — Runtime Symbiosis Layer.
Syncs HA Scenes/Automations to Core Room Contexts.
"""
from __future__ import annotations
import logging, requests
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

@dataclass
class RoomContext:
    context_id: str
    name: str
    zone_ref: str
    trigger_time: Optional[str] = None
    trigger_presence: Optional[str] = None
    ha_scene_id: Optional[str] = None
    ha_automation_ids: List[str] = None
    active: bool = False
    learned: bool = False
    
    def __post_init__(self):
        if self.ha_automation_ids is None:
            self.ha_automation_ids = []

class RoomContextSync:
    """Manages sync between HA Scenes/Automations and Core Room Contexts."""
    
    def __init__(self, core_url: str, ha_url: str, ha_token: str):
        self.core_url = core_url
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.contexts: Dict[str, RoomContext] = {}
    
    async def discover_ha_scenes(self) -> List[Dict]:
        """Fetch all Scenes from Home Assistant."""
        headers = {"Authorization": f"Bearer {self.ha_token}"}
        resp = requests.get(f"{self.ha_url}/api/scenes", headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
    
    async def discover_ha_automations(self) -> List[Dict]:
        """Fetch all Automations from Home Assistant."""
        headers = {"Authorization": f"Bearer {self.ha_token}"}
        resp = requests.get(f"{self.ha_url}/api/config/automation", headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
    
    async def sync_context_to_core(self, ctx: RoomContext) -> bool:
        """Push Room Context to Core API."""
        payload = {
            "context_id": ctx.context_id,
            "name": ctx.name,
            "zone_ref": ctx.zone_ref,
            "trigger_time": ctx.trigger_time,
            "trigger_presence": ctx.trigger_presence,
            "ha_scene_id": ctx.ha_scene_id,
            "ha_automation_ids": ctx.ha_automation_ids,
            "active": ctx.active,
            "learned": ctx.learned
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(f"{self.core_url}/api/v1/contexts/rooms", json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            _LOGGER.info(f"Synced Room Context {ctx.context_id} to Core")
            return True
        _LOGGER.error(f"Failed to sync context {ctx.context_id}: {resp.text}")
        return False
    
    async def full_sync(self) -> Dict:
        """Perform full sync of HA Scenes/Automations to Room Contexts."""
        ha_scenes = await self.discover_ha_scenes()
        ha_automations = await self.discover_ha_automations()
        
        synced = 0
        created = 0
        
        # Create contexts from HA scenes with room prefix
        for scene in ha_scenes:
            scene_id = scene.get("entity_id", "")
            if scene_id.startswith("scene."):
                # Extract room name from scene (e.g., scene.living_room_evening)
                parts = scene_id.replace("scene.", "").split("_")
                if len(parts) >= 2:
                    room = parts[0]
                    context_name = parts[-1]
                    context_id = f"context.{room}.{context_name}"
                    
                    ctx = RoomContext(
                        context_id=context_id,
                        name=f"{room} - {context_name}",
                        zone_ref=f"zone.{room}",
                        ha_scene_id=scene_id
                    )
                    
                    if await self.sync_context_to_core(ctx):
                        self.contexts[context_id] = ctx
                        created += 1
        
        return {"synced": synced, "created": created, "total": len(self.contexts)}
