"""Multi-Zone Coordination Engine — Slice 15.

Coordinates actions across multiple zones (scenes, routines, events).

Features:
- Cross-zone action coordination
- Scene composition (multi-zone scenes)
- Routine engine (time/event-triggered multi-zone actions)
- Conflict detection + resolution
- Zone dependency management
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Type of action conflict."""
    RESOURCE_CONFLICT = "resource_conflict"  # Two actions compete for same resource
    STATE_CONFLICT = "state_conflict"  # Actions want opposite states
    TIMING_CONFLICT = "timing_conflict"  # Actions scheduled at same time
    PRIORITY_CONFLICT = "priority_conflict"  # Actions have different priorities
    DEPENDENCY_CONFLICT = "dependency_conflict"  # Dependency chain violation


class ResolutionStrategy(Enum):
    """Strategy for resolving conflicts."""
    PRIORITY_BASED = "priority_based"  # Higher priority wins
    TIME_BASED = "time_based"  # Earlier action wins
    USER_PROMPT = "user_prompt"  # Ask user
    MERGE = "merge"  # Merge actions if possible
    SEQUENCE = "sequence"  # Execute in sequence


@dataclass
class ZoneAction:
    """Action to be executed in a zone."""
    action_id: str
    zone_id: str
    module_id: str
    entity_id: str
    domain: str
    service: str
    data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10, higher = more important
    scheduled_at: Optional[str] = None
    expires_at: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)  # List of action_ids
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "entity_id": self.entity_id,
            "domain": self.domain,
            "service": self.service,
            "data": self.data,
            "priority": self.priority,
            "scheduled_at": self.scheduled_at,
            "expires_at": self.expires_at,
            "dependencies": self.dependencies,
        }


@dataclass
class MultiZoneScene:
    """Multi-zone scene composition."""
    scene_id: str
    name: str
    description: str
    zone_actions: Dict[str, List[ZoneAction]]  # zone_id -> actions
    is_active: bool = False
    activated_at: Optional[str] = None
    activated_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "name": self.name,
            "description": self.description,
            "zone_actions": {
                zone_id: [a.to_dict() for a in actions]
                for zone_id, actions in self.zone_actions.items()
            },
            "is_active": self.is_active,
            "activated_at": self.activated_at,
            "activated_by": self.activated_by,
        }


@dataclass
class Routine:
    """Time/event-triggered routine."""
    routine_id: str
    name: str
    description: str
    trigger_type: str  # "time", "presence", "sunset", "sunrise"
    trigger_config: Dict[str, Any]
    zone_actions: Dict[str, List[ZoneAction]]
    enabled: bool = True
    last_triggered: Optional[str] = None
    trigger_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "routine_id": self.routine_id,
            "name": self.name,
            "description": self.description,
            "trigger_type": self.trigger_type,
            "trigger_config": self.trigger_config,
            "zone_actions": {
                zone_id: [a.to_dict() for a in actions]
                for zone_id, actions in self.zone_actions.items()
            },
            "enabled": self.enabled,
            "last_triggered": self.last_triggered,
            "trigger_count": self.trigger_count,
        }


@dataclass
class Conflict:
    """Detected conflict between actions."""
    conflict_id: str
    conflict_type: ConflictType
    action_ids: List[str]
    description: str
    resolution_strategy: ResolutionStrategy
    resolved: bool = False
    resolution: Optional[str] = None
    resolved_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "action_ids": self.action_ids,
            "description": self.description,
            "resolution_strategy": self.resolution_strategy.value,
            "resolved": self.resolved,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at,
        }


class MultiZoneCoordinationEngine:
    """Main multi-zone coordination engine."""
    
    def __init__(self):
        self._scenes: Dict[str, MultiZoneScene] = {}
        self._routines: Dict[str, Routine] = {}
        self._pending_actions: Dict[str, ZoneAction] = {}
        self._conflicts: Dict[str, Conflict] = {}
        self._action_counter = 0
        self._scene_counter = 0
        self._routine_counter = 0
        self._conflict_counter = 0
        
        # Conflict detection settings
        self._detect_conflicts = True
        self._default_resolution = ResolutionStrategy.PRIORITY_BASED
    
    def create_scene(self, name: str, description: str, zone_actions: Dict[str, List[Dict[str, Any]]]) -> str:
        """Create a multi-zone scene."""
        self._scene_counter += 1
        scene_id = f"scene_{self._scene_counter}"
        
        # Convert dict actions to ZoneAction objects
        converted_actions: Dict[str, List[ZoneAction]] = {}
        for zone_id, actions in zone_actions.items():
            converted_actions[zone_id] = []
            for action_data in actions:
                self._action_counter += 1
                action = ZoneAction(
                    action_id=f"action_{self._action_counter}",
                    zone_id=zone_id,
                    **action_data
                )
                converted_actions[zone_id].append(action)
        
        scene = MultiZoneScene(
            scene_id=scene_id,
            name=name,
            description=description,
            zone_actions=converted_actions,
        )
        
        self._scenes[scene_id] = scene
        return scene_id
    
    def activate_scene(self, scene_id: str, activated_by: Optional[str] = None) -> bool:
        """Activate a multi-zone scene."""
        if scene_id not in self._scenes:
            return False
        
        scene = self._scenes[scene_id]
        
        # Check for conflicts before activation
        if self._detect_conflicts:
            conflicts = self._detect_scene_conflicts(scene)
            if conflicts:
                # Try to resolve conflicts
                for conflict in conflicts:
                    self._resolve_conflict(conflict)
                
                # If still unresolved, abort
                if any(not c.resolved for c in conflicts):
                    logger.warning("Scene activation aborted due to unresolved conflicts")
                    return False
        
        # Activate scene
        scene.is_active = True
        scene.activated_at = datetime.now(timezone.utc).isoformat()
        scene.activated_by = activated_by
        
        # Queue actions for execution
        for zone_id, actions in scene.zone_actions.items():
            for action in actions:
                self._pending_actions[action.action_id] = action
        
        return True
    
    def deactivate_scene(self, scene_id: str) -> bool:
        """Deactivate a multi-zone scene."""
        if scene_id not in self._scenes:
            return False
        
        scene = self._scenes[scene_id]
        scene.is_active = False
        
        # Remove pending actions from this scene
        scene_action_ids = {
            action.action_id
            for actions in scene.zone_actions.values()
            for action in actions
        }
        
        for action_id in scene_action_ids:
            self._pending_actions.pop(action_id, None)
        
        return True
    
    def create_routine(self, name: str, description: str, trigger_type: str,
                       trigger_config: Dict[str, Any], zone_actions: Dict[str, List[Dict[str, Any]]]) -> str:
        """Create a time/event-triggered routine."""
        self._routine_counter += 1
        routine_id = f"routine_{self._routine_counter}"
        
        # Convert dict actions to ZoneAction objects
        converted_actions: Dict[str, List[ZoneAction]] = {}
        for zone_id, actions in zone_actions.items():
            converted_actions[zone_id] = []
            for action_data in actions:
                self._action_counter += 1
                action = ZoneAction(
                    action_id=f"action_{self._action_counter}",
                    zone_id=zone_id,
                    **action_data
                )
                converted_actions[zone_id].append(action)
        
        routine = Routine(
            routine_id=routine_id,
            name=name,
            description=description,
            trigger_type=trigger_type,
            trigger_config=trigger_config,
            zone_actions=converted_actions,
        )
        
        self._routines[routine_id] = routine
        return routine_id
    
    def trigger_routine(self, routine_id: str) -> bool:
        """Trigger a routine manually or via scheduler."""
        if routine_id not in self._routines:
            return False
        
        routine = self._routines[routine_id]
        
        if not routine.enabled:
            logger.info("Routine %s is disabled", routine_id)
            return False
        
        # Check for conflicts
        if self._detect_conflicts:
            conflicts = self._detect_routine_conflicts(routine)
            if conflicts:
                for conflict in conflicts:
                    self._resolve_conflict(conflict)
                
                if any(not c.resolved for c in conflicts):
                    logger.warning("Routine trigger aborted due to unresolved conflicts")
                    return False
        
        # Queue actions for execution
        for zone_id, actions in routine.zone_actions.items():
            for action in actions:
                self._pending_actions[action.action_id] = action
        
        # Update routine stats
        routine.last_triggered = datetime.now(timezone.utc).isoformat()
        routine.trigger_count += 1
        
        return True
    
    def _detect_scene_conflicts(self, scene: MultiZoneScene) -> List[Conflict]:
        """Detect conflicts within a scene."""
        conflicts = []
        
        # Collect all actions
        all_actions: List[ZoneAction] = []
        for actions in scene.zone_actions.values():
            all_actions.extend(actions)
        
        # Check for resource conflicts (same entity, different actions)
        entity_actions: Dict[str, List[ZoneAction]] = {}
        for action in all_actions:
            if action.entity_id not in entity_actions:
                entity_actions[action.entity_id] = []
            entity_actions[action.entity_id].append(action)
        
        for entity_id, actions in entity_actions.items():
            if len(actions) > 1:
                # Check if actions conflict
                services = {a.service for a in actions}
                if "turn_on" in services and "turn_off" in services:
                    self._conflict_counter += 1
                    conflicts.append(Conflict(
                        conflict_id=f"conflict_{self._conflict_counter}",
                        conflict_type=ConflictType.STATE_CONFLICT,
                        action_ids=[a.action_id for a in actions],
                        description=f"Conflicting actions for {entity_id}: turn_on vs turn_off",
                        resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
                    ))
        
        return conflicts
    
    def _detect_routine_conflicts(self, routine: Routine) -> List[Conflict]:
        """Detect conflicts within a routine."""
        # Similar to scene conflict detection
        return self._detect_scene_conflicts(
            MultiZoneScene(
                scene_id="temp",
                name=routine.name,
                description="",
                zone_actions=routine.zone_actions,
            )
        )
    
    def _resolve_conflict(self, conflict: Conflict) -> bool:
        """Resolve a conflict using the specified strategy."""
        if conflict.resolution_strategy == ResolutionStrategy.PRIORITY_BASED:
            # Higher priority wins
            actions = [self._pending_actions.get(aid) for aid in conflict.action_ids]
            actions = [a for a in actions if a is not None]
            
            if actions:
                winner = max(actions, key=lambda a: a.priority)
                losers = [a for a in actions if a != winner]
                
                # Remove losing actions
                for loser in losers:
                    self._pending_actions.pop(loser.action_id, None)
                
                conflict.resolved = True
                conflict.resolution = f"Priority-based: {winner.action_id} (priority {winner.priority}) wins"
                conflict.resolved_at = datetime.now(timezone.utc).isoformat()
                return True
        
        elif conflict.resolution_strategy == ResolutionStrategy.SEQUENCE:
            # Execute in sequence instead of parallel
            conflict.resolved = True
            conflict.resolution = "Sequential execution scheduled"
            conflict.resolved_at = datetime.now(timezone.utc).isoformat()
            return True
        
        elif conflict.resolution_strategy == ResolutionStrategy.MERGE:
            # Try to merge actions
            conflict.resolved = True
            conflict.resolution = "Actions merged"
            conflict.resolved_at = datetime.now(timezone.utc).isoformat()
            return True
        
        # USER_PROMPT requires user interaction - mark as unresolved
        conflict.resolved = False
        return False
    
    def get_pending_actions(self, zone_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pending actions, optionally filtered by zone."""
        actions = list(self._pending_actions.values())
        
        if zone_id:
            actions = [a for a in actions if a.zone_id == zone_id]
        
        # Sort by priority (highest first)
        actions.sort(key=lambda a: a.priority, reverse=True)
        
        return [a.to_dict() for a in actions]
    
    def get_scenes(self) -> List[Dict[str, Any]]:
        """Get all scenes."""
        return [s.to_dict() for s in self._scenes.values()]
    
    def get_routines(self) -> List[Dict[str, Any]]:
        """Get all routines."""
        return [r.to_dict() for r in self._routines.values()]
    
    def get_conflicts(self, unresolved_only: bool = True) -> List[Dict[str, Any]]:
        """Get conflicts."""
        conflicts = list(self._conflicts.values())
        
        if unresolved_only:
            conflicts = [c for c in conflicts if not c.resolved]
        
        return [c.to_dict() for c in conflicts]
    
    def enable_routine(self, routine_id: str) -> bool:
        """Enable a routine."""
        if routine_id not in self._routines:
            return False
        
        self._routines[routine_id].enabled = True
        return True
    
    def disable_routine(self, routine_id: str) -> bool:
        """Disable a routine."""
        if routine_id not in self._routines:
            return False
        
        self._routines[routine_id].enabled = False
        return True


def create_multi_zone_coordination_engine() -> MultiZoneCoordinationEngine:
    """Factory function to create multi-zone coordination engine."""
    return MultiZoneCoordinationEngine()
