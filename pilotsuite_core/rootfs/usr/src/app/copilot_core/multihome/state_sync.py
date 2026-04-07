"""State Synchronization for Multi-Home Setup.

Handles real-time state synchronization between multiple home instances,
including entity states, climate settings, lighting scenes, and security status.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from .sync_engine import (
    SyncEngine,
    SyncOperation,
    SyncStatus,
    SyncConflict,
    ConflictResolution,
    get_sync_engine,
    HomeInstance,
)

logger = logging.getLogger(__name__)


class EntityState:
    """Represents the state of a Home Assistant entity."""
    
    def __init__(
        self,
        entity_id: str,
        state: str,
        attributes: Dict[str, Any],
        last_changed: datetime,
        last_updated: datetime,
        source_home_id: Optional[str] = None
    ):
        self.entity_id = entity_id
        self.state = state
        self.attributes = attributes
        self.last_changed = last_changed
        self.last_updated = last_updated
        self.source_home_id = source_home_id
        self._version_hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute hash for state comparison."""
        state_data = {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": self.attributes,
            "last_changed": self.last_changed.isoformat()
        }
        return hashlib.sha256(
            json.dumps(state_data, sort_keys=True).encode('utf-8')
        ).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": self.attributes,
            "last_changed": self.last_changed.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "version_hash": self._version_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], source_home_id: Optional[str] = None) -> 'EntityState':
        """Create from dictionary."""
        return cls(
            entity_id=data["entity_id"],
            state=data["state"],
            attributes=data.get("attributes", {}),
            last_changed=datetime.fromisoformat(data["last_changed"]),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            source_home_id=source_home_id
        )


class StateSync:
    """Handles state synchronization between homes."""
    
    def __init__(self, sync_engine: Optional[SyncEngine] = None):
        """Initialize state sync."""
        self.sync_engine = sync_engine or get_sync_engine()
        self._state_cache: Dict[str, Dict[str, EntityState]] = {}  # home_id -> {entity_id -> EntityState}
        self._state_timestamps: Dict[str, Dict[str, datetime]] = {}  # home_id -> {entity_id -> timestamp}
        self._synced_entity_prefixes = [
            "climate.",
            "light.",
            "cover.",
            "switch.",
            "input_boolean.",
            "scene.",
        ]
    
    def cache_entity_state(self, home_id: str, entity_state: EntityState) -> None:
        """Cache an entity state locally."""
        if home_id not in self._state_cache:
            self._state_cache[home_id] = {}
            self._state_timestamps[home_id] = {}
        
        self._state_cache[home_id][entity_state.entity_id] = entity_state
        self._state_timestamps[home_id][entity_state.entity_id] = datetime.now(timezone.utc)
    
    def get_cached_state(self, home_id: str, entity_id: str) -> Optional[EntityState]:
        """Get cached entity state."""
        return self._state_cache.get(home_id, {}).get(entity_id)
    
    def get_all_cached_states(self, home_id: str) -> Dict[str, EntityState]:
        """Get all cached states for a home."""
        return self._state_cache.get(home_id, {})
    
    def should_sync_entity(self, entity_id: str) -> bool:
        """Check if an entity should be synchronized."""
        # Only sync certain entity domains
        for prefix in self._synced_entity_prefixes:
            if entity_id.startswith(prefix):
                return True
        return False
    
    def detect_state_conflicts(
        self,
        source_home_id: str,
        target_home_id: str,
        entity_id: str
    ) -> Optional[SyncConflict]:
        """Detect state conflicts for an entity between two homes."""
        source_state = self.get_cached_state(source_home_id, entity_id)
        target_state = self.get_cached_state(target_home_id, entity_id)
        
        if not source_state or not target_state:
            return None
        
        # Check if states differ
        if source_state._version_hash == target_state._version_hash:
            return None
        
        # Create conflict record
        operation_id = f"state_sync_{entity_id}_{int(time.time())}"
        conflict = self.sync_engine.detect_conflict(
            operation=SyncOperation(
                id=operation_id,
                source_home_id=source_home_id,
                target_home_id=target_home_id,
                operation_type="state",
                data={"entity_id": entity_id}
            ),
            field_path=entity_id,
            local_value=source_state.to_dict(),
            remote_value=target_state.to_dict(),
            local_timestamp=source_state.last_updated,
            remote_timestamp=target_state.last_updated
        )
        
        logger.warning(f"State conflict detected for {entity_id}")
        return conflict
    
    def create_state_sync_operation(
        self,
        source_home_id: str,
        target_home_id: str,
        entity_ids: Optional[List[str]] = None,
        sync_mode: str = "selective"  # selective, full, domain-specific
    ) -> Optional[SyncOperation]:
        """Create a state synchronization operation."""
        source_states = self.get_all_cached_states(source_home_id)
        
        if entity_ids:
            # Sync specific entities
            states_to_sync = {
                eid: source_states[eid] for eid in entity_ids
                if eid in source_states and self.should_sync_entity(eid)
            }
        else:
            # Sync all relevant entities
            states_to_sync = {
                eid: state for eid, state in source_states.items()
                if self.should_sync_entity(eid)
            }
        
        if not states_to_sync:
            logger.info(f"No states to sync from {source_home_id}")
            return None
        
        operation_data = {
            "sync_mode": sync_mode,
            "entity_count": len(states_to_sync),
            "states": {
                eid: state.to_dict() for eid, state in states_to_sync.items()
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        operation = self.sync_engine.create_sync_operation(
            source_home_id=source_home_id,
            target_home_id=target_home_id,
            operation_type="state",
            data=operation_data
        )
        
        logger.info(f"Created state sync operation for {len(states_to_sync)} entities")
        return operation
    
    def apply_state_sync(self, operation: SyncOperation) -> bool:
        """Apply state synchronization from an operation."""
        if operation.operation_type != "state":
            logger.error(f"Invalid operation type: {operation.operation_type}")
            return False
        
        try:
            target_home_id = operation.target_home_id
            states_data = operation.data.get("states", {})
            
            if target_home_id not in self._state_cache:
                self._state_cache[target_home_id] = {}
                self._state_timestamps[target_home_id] = {}
            
            applied_count = 0
            conflicts = []
            
            for entity_id, state_dict in states_data.items():
                incoming_state = EntityState.from_dict(state_dict, operation.source_home_id)
                existing_state = self.get_cached_state(target_home_id, entity_id)
                
                # Check for conflicts
                if existing_state and existing_state._version_hash != incoming_state._version_hash:
                    # Timestamps differ - check which is newer
                    if existing_state.last_updated > incoming_state.last_updated:
                        # Local state is newer - conflict
                        conflict = self.detect_state_conflicts(
                            operation.source_home_id,
                            target_home_id,
                            entity_id
                        )
                        if conflict:
                            conflicts.append(conflict)
                            continue  # Skip this entity until conflict is resolved
                    
                # Apply state
                self.cache_entity_state(target_home_id, incoming_state)
                applied_count += 1
            
            if conflicts:
                operation.status = SyncStatus.CONFLICT
                operation.conflict_info = {
                    "conflicts": [c.to_dict() for c in conflicts],
                    "applied_count": applied_count
                }
                logger.warning(f"State sync completed with {len(conflicts)} conflicts")
            else:
                operation.status = SyncStatus.COMPLETED
                operation.completed_at = datetime.now(timezone.utc)
                logger.info(f"Applied state sync: {applied_count} entities to {target_home_id}")
            
            return len(conflicts) == 0
            
        except Exception as e:
            operation.status = SyncStatus.FAILED
            operation.error_message = str(e)
            logger.error(f"Failed to apply state sync: {e}")
            return False
    
    def sync_climate_state(
        self,
        source_home_id: str,
        target_home_id: str,
        climate_entity_id: str
    ) -> Dict[str, Any]:
        """Synchronize climate entity state (e.g., for "Ferienhaus vorheizen")."""
        source_state = self.get_cached_state(source_home_id, climate_entity_id)
        
        if not source_state:
            return {"success": False, "error": "Source climate state not found"}
        
        # Create targeted sync operation
        operation_data = {
            "sync_mode": "climate",
            "entity_id": climate_entity_id,
            "state": source_state.to_dict(),
            "target_temperature": source_state.attributes.get("temperature"),
            "hvac_mode": source_state.state,
            "preset_mode": source_state.attributes.get("preset_mode")
        }
        
        operation = self.sync_engine.create_sync_operation(
            source_home_id=source_home_id,
            target_home_id=target_home_id,
            operation_type="state",
            data=operation_data
        )
        
        logger.info(f"Created climate sync for {climate_entity_id}")
        return {
            "success": True,
            "operation_id": operation.id,
            "entity_id": climate_entity_id,
            "target_temperature": source_state.attributes.get("temperature")
        }
    
    def sync_lighting_scene(
        self,
        source_home_id: str,
        target_home_id: str,
        scene_entity_id: str
    ) -> Dict[str, Any]:
        """Synchronize lighting scene activation."""
        source_state = self.get_cached_state(source_home_id, scene_entity_id)
        
        if not source_state:
            return {"success": False, "error": "Source scene not found"}
        
        # Get all lights in the scene
        scene_attributes = source_state.attributes.get("entity_id", [])
        
        operation_data = {
            "sync_mode": "scene",
            "scene_entity_id": scene_entity_id,
            "lights": scene_attributes,
            "scene_state": source_state.to_dict()
        }
        
        operation = self.sync_engine.create_sync_operation(
            source_home_id=source_home_id,
            target_home_id=target_home_id,
            operation_type="state",
            data=operation_data
        )
        
        logger.info(f"Created scene sync for {scene_entity_id}")
        return {
            "success": True,
            "operation_id": operation.id,
            "scene_entity_id": scene_entity_id,
            "light_count": len(scene_attributes)
        }
    
    def get_state_diff_report(
        self,
        home_id_1: str,
        home_id_2: str
    ) -> Dict[str, Any]:
        """Generate a state difference report between two homes."""
        states1 = self.get_all_cached_states(home_id_1)
        states2 = self.get_all_cached_states(home_id_2)
        
        all_entity_ids = set(states1.keys()) | set(states2.keys())
        
        synced = []
        different = []
        missing_in_1 = []
        missing_in_2 = []
        
        for entity_id in all_entity_ids:
            in_1 = entity_id in states1
            in_2 = entity_id in states2
            
            if in_1 and in_2:
                if states1[entity_id]._version_hash == states2[entity_id]._version_hash:
                    synced.append(entity_id)
                else:
                    different.append(entity_id)
            elif in_1:
                missing_in_2.append(entity_id)
            else:
                missing_in_1.append(entity_id)
        
        return {
            "home_1": home_id_1,
            "home_2": home_id_2,
            "summary": {
                "total_entities": len(all_entity_ids),
                "synced": len(synced),
                "different": len(different),
                "missing_in_home_1": len(missing_in_1),
                "missing_in_home_2": len(missing_in_2)
            },
            "different_entities": different,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    
    def cleanup_stale_states(self, home_id: str, max_age_minutes: int = 60) -> int:
        """Clean up stale cached states."""
        if home_id not in self._state_timestamps:
            return 0
        
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_minutes * 60)
        original_count = len(self._state_cache.get(home_id, {}))
        
        entities_to_remove = [
            eid for eid, ts in self._state_timestamps[home_id].items()
            if ts.timestamp() < cutoff
        ]
        
        for eid in entities_to_remove:
            self._state_cache[home_id].pop(eid, None)
            self._state_timestamps[home_id].pop(eid, None)
        
        cleaned = original_count - len(self._state_cache.get(home_id, {}))
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} stale states for {home_id}")
        
        return cleaned


# Singleton instance
_state_sync: Optional[StateSync] = None


def get_state_sync(sync_engine: Optional[SyncEngine] = None) -> StateSync:
    """Get or create the state sync singleton."""
    global _state_sync
    if _state_sync is None:
        _state_sync = StateSync(sync_engine)
    return _state_sync
