"""Intent Manager Sync — Runtime Symbiosis Layer.
Syncs HA Scripts/Blueprints to Core Intents.
"""
from __future__ import annotations
import logging, requests
from typing import Dict, List, Optional
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

@dataclass
class Intent:
    intent_id: str
    name: str
    trigger_phrases: List[str] = None
    ha_script_id: Optional[str] = None
    ha_blueprint_id: Optional[str] = None
    zone_ref: Optional[str] = None
    confidence_threshold: float = 0.8
    active: bool = True
    
    def __post_init__(self):
        if self.trigger_phrases is None:
            self.trigger_phrases = []

class IntentManagerSync:
    """Manages sync between HA Scripts/Blueprints and Core Intents."""
    
    def __init__(self, core_url: str, ha_url: str, ha_token: str):
        self.core_url = core_url
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.intents: Dict[str, Intent] = {}
    
    async def discover_ha_scripts(self) -> List[Dict]:
        """Fetch all Scripts from Home Assistant."""
        headers = {"Authorization": f"Bearer {self.ha_token}"}
        resp = requests.get(f"{self.ha_url}/api/config/script/config", headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
    
    async def discover_ha_blueprints(self) -> List[Dict]:
        """Fetch all Blueprints from Home Assistant."""
        headers = {"Authorization": f"Bearer {self.ha_token}"}
        resp = requests.get(f"{self.ha_url}/api/blueprint", headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
    
    async def sync_intent_to_core(self, intent: Intent) -> bool:
        """Push Intent to Core API."""
        payload = {
            "intent_id": intent.intent_id,
            "name": intent.name,
            "trigger_phrases": intent.trigger_phrases,
            "ha_script_id": intent.ha_script_id,
            "ha_blueprint_id": intent.ha_blueprint_id,
            "zone_ref": intent.zone_ref,
            "confidence_threshold": intent.confidence_threshold,
            "active": intent.active
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(f"{self.core_url}/api/v1/intents", json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            _LOGGER.info(f"Synced Intent {intent.intent_id} to Core")
            return True
        _LOGGER.error(f"Failed to sync intent {intent.intent_id}: {resp.text}")
        return False
    
    async def full_sync(self) -> Dict:
        """Perform full sync of HA Scripts/Blueprints to Intents."""
        ha_scripts = await self.discover_ha_scripts()
        
        synced = 0
        created = 0
        
        for script in ha_scripts:
            script_id = script.get("id", "")
            intent_id = f"intent.script.{script_id}"
            
            intent = Intent(
                intent_id=intent_id,
                name=script.get("name", script_id),
                trigger_phrases=[f"script {script_id}", f"run {script.get('name', '').lower()}"],
                ha_script_id=script_id
            )
            
            if await self.sync_intent_to_core(intent):
                self.intents[intent_id] = intent
                created += 1
        
        return {"synced": synced, "created": created, "total": len(self.intents)}
