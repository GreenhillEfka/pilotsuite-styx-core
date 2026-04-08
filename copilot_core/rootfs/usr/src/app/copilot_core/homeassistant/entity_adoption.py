"""Entity Adoption System.

Auto-Vererbung von Entities (Raum → Zone) mit:
- Automatische Vererbung: Alle Entities eines Raums → Zone
- Aggregation: Zone-Temperatur = Durchschnitt aller Raum-Temperaturen
- Priority-System: Spezifische Entities haben Vorrang
- Override-Möglichkeit: Manuelle Zuordnung möglich
- Real-time Updates bei Adoption-Änderung
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class AdoptionPriority(Enum):
    """Priority levels for entity adoption."""
    
    OVERRIDE = 100  # Manuelle Zuordnung (höchste Priorität)
    SPECIFIC = 50   # Spezifische Entity-Zuordnung
    INHERITED = 10  # Automatisch vererbt vom Raum


@dataclass
class AdoptionAssignment:
    """Eine Entity-Zuordnung."""
    
    id: str
    entity_id: str
    zone_id: str
    source_room_id: Optional[str]
    priority: AdoptionPriority
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "zone_id": self.zone_id,
            "source_room_id": self.source_room_id,
            "priority": self.priority.value,
            "priority_name": self.priority.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ZoneAdoptionState:
    """Adoption state for a zone."""
    
    zone_id: str
    zone_name: str
    inherited_entities: List[str] = field(default_factory=list)
    overridden_entities: List[str] = field(default_factory=list)
    aggregated_sensors: Dict[str, Any] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "inherited_entities": self.inherited_entities,
            "overridden_entities": self.overridden_entities,
            "aggregated_sensors": self.aggregated_sensors,
            "last_updated": self.last_updated.isoformat(),
            "entity_count": len(self.inherited_entities) + len(self.overridden_entities),
        }


class EntityAdoptionService:
    """Service für Entity-Adoption (Raum → Zone Vererbung)."""
    
    def __init__(self):
        self._assignments: Dict[str, AdoptionAssignment] = {}  # id -> assignment
        self._zone_states: Dict[str, ZoneAdoptionState] = {}  # zone_id -> state
        self._room_zone_map: Dict[str, str] = {}  # room_id -> zone_id
        self._entity_room_map: Dict[str, str] = {}  # entity_id -> room_id
        self._lock = asyncio.Lock()
        self._listeners: List[callable] = []
    
    def add_listener(self, callback: callable) -> None:
        """Add listener for adoption changes."""
        self._listeners.append(callback)
    
    def remove_listener(self, callback: callable) -> None:
        """Remove listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    async def _notify_listeners(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notify all listeners of adoption changes."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event_type, data)
                else:
                    listener(event_type, data)
            except Exception as e:
                logger.error(f"Adoption listener error: {e}")
    
    def set_room_zone_mapping(self, room_id: str, zone_id: str) -> None:
        """Map a room to a zone for inheritance."""
        self._room_zone_map[room_id] = zone_id
        logger.debug(f"Mapped room {room_id} to zone {zone_id}")
    
    def set_entity_room_mapping(self, entity_id: str, room_id: str) -> None:
        """Map an entity to a room."""
        self._entity_room_map[entity_id] = room_id
        logger.debug(f"Mapped entity {entity_id} to room {room_id}")
    
    async def assign_entity(
        self,
        entity_id: str,
        zone_id: str,
        source_room_id: Optional[str] = None,
        priority: AdoptionPriority = AdoptionPriority.OVERRIDE,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AdoptionAssignment:
        """Manuelle Zuordnung einer Entity zu einer Zone."""
        async with self._lock:
            assignment_id = f"{entity_id}:{zone_id}"
            
            now = datetime.now(timezone.utc)
            
            if assignment_id in self._assignments:
                # Update existing
                assignment = self._assignments[assignment_id]
                assignment.zone_id = zone_id
                assignment.source_room_id = source_room_id
                assignment.priority = priority
                assignment.updated_at = now
                assignment.metadata = metadata or {}
            else:
                # Create new
                assignment = AdoptionAssignment(
                    id=assignment_id,
                    entity_id=entity_id,
                    zone_id=zone_id,
                    source_room_id=source_room_id,
                    priority=priority,
                    metadata=metadata or {},
                )
            
            self._assignments[assignment_id] = assignment
            
            # Update zone state
            await self._update_zone_state(zone_id)
            
            # Notify listeners
            await self._notify_listeners("entity_assigned", assignment.to_dict())
            
            logger.info(f"Assigned entity {entity_id} to zone {zone_id} with priority {priority.name}")
            return assignment
    
    async def remove_assignment(self, assignment_id: str) -> bool:
        """Remove an entity assignment."""
        async with self._lock:
            if assignment_id not in self._assignments:
                return False
            
            assignment = self._assignments[assignment_id]
            zone_id = assignment.zone_id
            
            del self._assignments[assignment_id]
            
            # Update zone state
            await self._update_zone_state(zone_id)
            
            # Notify listeners
            await self._notify_listeners("assignment_removed", {"assignment_id": assignment_id})
            
            logger.info(f"Removed assignment {assignment_id}")
            return True
    
    async def _update_zone_state(self, zone_id: str) -> None:
        """Update the adoption state for a zone."""
        inherited = []
        overridden = []
        
        # Get all assignments for this zone
        zone_assignments = [
            a for a in self._assignments.values()
            if a.zone_id == zone_id
        ]
        
        # Separate by priority
        for assignment in zone_assignments:
            if assignment.priority == AdoptionPriority.OVERRIDE:
                overridden.append(assignment.entity_id)
            else:
                inherited.append(assignment.entity_id)
        
        # Add auto-inherited entities from rooms
        for room_id, mapped_zone in self._room_zone_map.items():
            if mapped_zone == zone_id:
                # Get all entities in this room
                room_entities = [
                    eid for eid, rid in self._entity_room_map.items()
                    if rid == room_id
                ]
                
                for entity_id in room_entities:
                    # Only add if not overridden
                    if entity_id not in overridden:
                        if entity_id not in inherited:
                            inherited.append(entity_id)
        
        # Calculate aggregated sensors
        aggregated = await self._calculate_aggregations(zone_id, inherited)
        
        self._zone_states[zone_id] = ZoneAdoptionState(
            zone_id=zone_id,
            zone_name=zone_id,  # Would be fetched from HA in production
            inherited_entities=inherited,
            overridden_entities=overridden,
            aggregated_sensors=aggregated,
            last_updated=datetime.now(timezone.utc),
        )
    
    async def _calculate_aggregations(
        self,
        zone_id: str,
        entity_ids: List[str]
    ) -> Dict[str, Any]:
        """Calculate aggregated sensor values for a zone."""
        aggregated = {
            "temperature": None,
            "humidity": None,
            "co2": None,
        }
        
        # In production, this would fetch actual sensor values from HA
        # For now, we just track which entities would be aggregated
        
        temp_entities = [eid for eid in entity_ids if "temperature" in eid.lower()]
        humidity_entities = [eid for eid in entity_ids if "humidity" in eid.lower()]
        co2_entities = [eid for eid in entity_ids if "co2" in eid.lower()]
        
        aggregated["temperature_entities"] = temp_entities
        aggregated["humidity_entities"] = humidity_entities
        aggregated["co2_entities"] = co2_entities
        
        # If we had actual values, we'd calculate averages here:
        # if temp_values:
        #     aggregated["temperature"] = sum(temp_values) / len(temp_values)
        
        return aggregated
    
    def get_zone_state(self, zone_id: str) -> Optional[ZoneAdoptionState]:
        """Get adoption state for a zone."""
        return self._zone_states.get(zone_id)
    
    def get_all_zone_states(self) -> Dict[str, ZoneAdoptionState]:
        """Get all zone adoption states."""
        return self._zone_states.copy()
    
    def get_assignments_for_zone(self, zone_id: str) -> List[AdoptionAssignment]:
        """Get all assignments for a zone."""
        return [
            a for a in self._assignments.values()
            if a.zone_id == zone_id
        ]
    
    def get_assignment(self, assignment_id: str) -> Optional[AdoptionAssignment]:
        """Get specific assignment by ID."""
        return self._assignments.get(assignment_id)
    
    def get_all_assignments(self) -> List[AdoptionAssignment]:
        """Get all assignments."""
        return list(self._assignments.values())
    
    async def get_zone_entities(self, zone_id: str) -> Dict[str, Any]:
        """Get all entities for a zone (inherited + overridden)."""
        state = self.get_zone_state(zone_id)
        
        if not state:
            # Auto-update if not exists
            await self._update_zone_state(zone_id)
            state = self.get_zone_state(zone_id)
        
        if not state:
            return {
                "zone_id": zone_id,
                "entities": [],
                "inherited_count": 0,
                "overridden_count": 0,
                "aggregated": {},
            }
        
        all_entities = state.inherited_entities + state.overridden_entities
        
        return {
            "zone_id": zone_id,
            "zone_name": state.zone_name,
            "entities": all_entities,
            "inherited_count": len(state.inherited_entities),
            "overridden_count": len(state.overridden_entities),
            "total_count": len(all_entities),
            "aggregated": state.aggregated_sensors,
            "last_updated": state.last_updated.isoformat(),
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get adoption statistics."""
        total_assignments = len(self._assignments)
        total_zones = len(self._zone_states)
        
        override_count = sum(
            1 for a in self._assignments.values()
            if a.priority == AdoptionPriority.OVERRIDE
        )
        
        inherited_count = total_assignments - override_count
        
        return {
            "total_assignments": total_assignments,
            "total_zones": total_zones,
            "total_rooms_mapped": len(self._room_zone_map),
            "override_assignments": override_count,
            "inherited_assignments": inherited_count,
            "total_entities_tracked": len(self._entity_room_map),
            "zone_details": {
                zone_id: {
                    "inherited": len(state.inherited_entities),
                    "overridden": len(state.overridden_entities),
                }
                for zone_id, state in self._zone_states.items()
            },
        }
    
    async def refresh_zone(self, zone_id: str) -> ZoneAdoptionState:
        """Force refresh of a zone's adoption state."""
        async with self._lock:
            await self._update_zone_state(zone_id)
            state = self._zone_states.get(zone_id)
            
            if state:
                await self._notify_listeners("zone_refreshed", state.to_dict())
            
            return state
    
    async def refresh_all_zones(self) -> Dict[str, ZoneAdoptionState]:
        """Force refresh of all zone adoption states."""
        async with self._lock:
            zone_ids = list(self._zone_states.keys())
            
            for zone_id in zone_ids:
                await self._update_zone_state(zone_id)
            
            # Also update zones from room mappings
            for room_id, zone_id in self._room_zone_map.items():
                if zone_id not in self._zone_states:
                    await self._update_zone_state(zone_id)
            
            await self._notify_listeners("all_zones_refreshed", {
                "zone_count": len(self._zone_states),
            })
            
            return self._zone_states.copy()
    
    def clear(self) -> None:
        """Clear all adoption data."""
        self._assignments.clear()
        self._zone_states.clear()
        self._room_zone_map.clear()
        self._entity_room_map.clear()
        logger.info("Cleared all adoption data")


# Global service instance
_adoption_service: Optional[EntityAdoptionService] = None


def get_adoption_service() -> EntityAdoptionService:
    """Get or create global adoption service instance."""
    global _adoption_service
    if _adoption_service is None:
        _adoption_service = EntityAdoptionService()
    return _adoption_service
