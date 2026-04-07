"""Action Executor Sync — Runtime Symbiosis Layer.
Syncs HA Scripts/Actions to Core Action Executions.
"""
from __future__ import annotations
import logging, requests
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

@dataclass
class Action:
    action_id: str
    name: str
    target_devices: List[str] = None
    commands: List[dict] = None
    ha_script_id: Optional[str] = None
    undo_state: List[dict] = None
    last_executed: Optional[str] = None
    execution_count: int = 0
    
    def __post_init__(self):
        if self.target_devices is None:
            self.target_devices = []
        if self.commands is None:
            self.commands = []
        if self.undo_state is None:
            self.undo_state = []

class ActionExecutorSync:
    """Manages sync between HA Scripts and Core Actions."""
    
    def __init__(self, core_url: str, ha_url: str, ha_token: str):
        self.core_url = core_url
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.actions: Dict[str, Action] = {}
    
    async def discover_ha_scripts(self) -> List[Dict]:
        """Fetch all Scripts from Home Assistant."""
        headers = {"Authorization": f"Bearer {self.ha_token}"}
        resp = requests.get(f"{self.ha_url}/api/config/script/config", headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
    
    async def sync_action_to_core(self, action: Action) -> bool:
        """Push Action to Core API."""
        payload = {
            "action_id": action.action_id,
            "name": action.name,
            "target_devices": action.target_devices,
            "commands": action.commands,
            "ha_script_id": action.ha_script_id,
            "undo_state": action.undo_state,
            "last_executed": action.last_executed,
            "execution_count": action.execution_count
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(f"{self.core_url}/api/v1/actions", json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            _LOGGER.info(f"Synced Action {action.action_id} to Core")
            return True
        _LOGGER.error(f"Failed to sync action {action.action_id}: {resp.text}")
        return False
    
    async def full_sync(self) -> Dict:
        """Perform full sync of HA Scripts to Actions."""
        ha_scripts = await self.discover_ha_scripts()
        
        synced = 0
        created = 0
        
        for script in ha_scripts:
            script_id = script.get("id", "")
            action_id = f"action.script.{script_id}"
            
            action = Action(
                action_id=action_id,
                name=script.get("name", script_id),
                ha_script_id=script_id
            )
            
            if await self.sync_action_to_core(action):
                self.actions[action_id] = action
                created += 1
        
        return {"synced": synced, "created": created, "total": len(self.actions)}
