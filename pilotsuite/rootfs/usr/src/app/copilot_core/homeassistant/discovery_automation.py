"""HA Discovery Automation (Slice 143).

Automatische Erkennung und Zuordnung von Home Assistant Entitäten:
- Discovery von neuen Geräten
- Auto-Assignment zu Zonen basierend auf Tags/Räumen
- Modul-Registrierung (Presence, Light, Climate, etc.)
- Registry Sync
"""

from __future__ import annotations

import logging
import asyncio
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from copilot_core.hub.habitus_zones import HabitusZoneEngine
from copilot_core.module_registry import ModuleRegistry

_LOGGER = logging.getLogger(__name__)


@dataclass
class DiscoveredEntity:
    entity_id: str
    domain: str
    room: Optional[str]
    device_class: Optional[str]
    friendly_name: Optional[str]
    suggested_zone: Optional[str] = None
    suggested_modules: List[str] = None
    
    def __post_init__(self):
        if self.suggested_modules is None:
            self.suggested_modules = []


class HADiscoveryAutomation:
    """Automates HA entity discovery and zone/module assignment."""
    
    # Domain to module mapping
    DOMAIN_MODULES = {
        "binary_sensor": ["presence"],
        "sensor": ["presence", "climate"],
        "light": ["light"],
        "climate": ["climate"],
        "media_player": ["media"],
        "switch": ["automation"],
        "cover": ["automation"],
        "camera": ["security"],
        "lock": ["security"],
    }
    
    # Room hints for zone assignment
    ROOM_ZONE_HINTS = {
        "living": "living_room",
        "wohn": "living_room",
        "kitchen": "kitchen",
        "küche": "kitchen",
        "bedroom": "bedroom",
        "schlaf": "bedroom",
        "bathroom": "bathroom",
        "bad": "bathroom",
        "office": "office",
        "büro": "office",
        "hallway": "hallway",
        "flur": "hallway",
        "garden": "garden",
        "garten": "garden",
    }
    
    def __init__(self):
        self._engine = HabitusZoneEngine()
        self._registry = ModuleRegistry()
    
    async def discover_entities(self, ha_states: List[Dict[str, Any]]) -> List[DiscoveredEntity]:
        """Process HA states and discover assignable entities."""
        discovered = []
        
        for state in ha_states:
            entity_id = state.get("entity_id", "")
            if not entity_id or "." not in entity_id:
                continue
                
            domain = entity_id.split(".")[0]
            attributes = state.get("attributes", {})
            
            # Skip non-relevant domains
            if domain not in self.DOMAIN_MODULES:
                continue
            
            # Extract room hint
            room = self._extract_room(entity_id, attributes)
            
            # Suggest zone
            suggested_zone = self._suggest_zone(room, entity_id)
            
            # Suggest modules
            suggested_modules = self.DOMAIN_MODULES.get(domain, [])
            
            discovered.append(DiscoveredEntity(
                entity_id=entity_id,
                domain=domain,
                room=room,
                device_class=attributes.get("device_class"),
                friendly_name=attributes.get("friendly_name"),
                suggested_zone=suggested_zone,
                suggested_modules=suggested_modules,
            ))
        
        _LOGGER.info("Discovered %d assignable entities", len(discovered))
        return discovered
    
    def _extract_room(self, entity_id: str, attributes: Dict[str, Any]) -> Optional[str]:
        """Extract room hint from entity."""
        # Check area_id first
        room = attributes.get("area_id")
        if room:
            return room
        
        # Check friendly_name
        friendly = attributes.get("friendly_name", "")
        for hint, zone in self.ROOM_ZONE_HINTS.items():
            if hint.lower() in friendly.lower() or hint.lower() in entity_id.lower():
                return zone
        
        return None
    
    def _suggest_zone(self, room: Optional[str], entity_id: str) -> Optional[str]:
        """Suggest zone based on room hint."""
        if room and room in self._engine._zones:
            return room
        
        # Fallback: check if any zone name matches
        for zone_id in self._engine._zones:
            if zone_id.replace("_", " ") in entity_id.lower():
                return zone_id
        
        return None
    
    async def auto_assign(self, discovered: List[DiscoveredEntity], dry_run: bool = False) -> Dict[str, Any]:
        """Auto-assign discovered entities to zones and modules."""
        results = {
            "assigned_to_zones": 0,
            "registered_to_modules": 0,
            "skipped": 0,
            "errors": [],
            "assignments": [],
        }
        
        for entity in discovered:
            try:
                # Assign to zone
                if entity.suggested_zone and entity.suggested_zone in self._engine._zones:
                    if not dry_run:
                        zone = self._engine._zones[entity.suggested_zone]
                        zone.entities.add(entity.entity_id)
                    results["assigned_to_zones"] += 1
                    results["assignments"].append({
                        "entity_id": entity.entity_id,
                        "zone": entity.suggested_zone,
                        "action": "assigned",
                    })
                
                # Register to modules
                for module_id in entity.suggested_modules:
                    if not dry_run:
                        # Enable module in zone
                        if entity.suggested_zone:
                            zone = self._engine._zones.get(entity.suggested_zone)
                            if zone:
                                zone.enabled_modules.add(module_id)
                                _LOGGER.debug("Enabled %s in %s", module_id, entity.suggested_zone)
                    results["registered_to_modules"] += 1
                    
            except Exception as exc:
                _LOGGER.error("Failed to assign %s: %s", entity.entity_id, exc)
                results["errors"].append({"entity": entity.entity_id, "error": str(exc)})
        
        return results
    
    async def run_discovery_cycle(self, ha_states: List[Dict[str, Any]], dry_run: bool = False) -> Dict[str, Any]:
        """Full discovery cycle: discover + assign."""
        discovered = await self.discover_entities(ha_states)
        results = await self.auto_assign(discovered, dry_run)
        
        _LOGGER.info(
            "Discovery cycle complete: %d entities, %d assigned to zones, %d module registrations",
            len(discovered),
            results["assigned_to_zones"],
            results["registered_to_modules"],
        )
        
        return {
            "discovered_count": len(discovered),
            "results": results,
            "dry_run": dry_run,
        }
