"""Multi-Zone Coordination Engine — Slice 15.

Coordinates actions across multiple zones (scenes, routines, events).

Features:
- Cross-zone action coordination
- Scene composition (multi-zone scenes)
- Routine engine (time/event-triggered multi-zone actions)
- Conflict detection + resolution
- Pending-action read model + basic runtime stats
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConflictType(Enum):
    """Type of action conflict."""

    RESOURCE_CONFLICT = "resource_conflict"
    STATE_CONFLICT = "state_conflict"
    TIMING_CONFLICT = "timing_conflict"
    PRIORITY_CONFLICT = "priority_conflict"
    DEPENDENCY_CONFLICT = "dependency_conflict"


class ResolutionStrategy(Enum):
    """Strategy for resolving conflicts."""

    PRIORITY_BASED = "priority_based"
    TIME_BASED = "time_based"
    USER_PROMPT = "user_prompt"
    MERGE = "merge"
    SEQUENCE = "sequence"


_CONFLICTING_SERVICES: Dict[str, set[str]] = {
    "turn_on": {"turn_off"},
    "turn_off": {"turn_on"},
    "open": {"close"},
    "close": {"open"},
    "lock": {"unlock"},
    "unlock": {"lock"},
    "increase": {"decrease"},
    "decrease": {"increase"},
}


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
    priority: int = 5
    scheduled_at: Optional[str] = None
    expires_at: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": "ZoneActionV1",
            "action_id": self.action_id,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "entity_id": self.entity_id,
            "domain": self.domain,
            "service": self.service,
            "data": dict(self.data),
            "priority": self.priority,
            "scheduled_at": self.scheduled_at,
            "expires_at": self.expires_at,
            "dependencies": list(self.dependencies),
        }


@dataclass
class MultiZoneScene:
    """Multi-zone scene composition."""

    scene_id: str
    name: str
    description: str
    zone_actions: Dict[str, List[ZoneAction]]
    is_active: bool = False
    activated_at: Optional[str] = None
    activated_by: Optional[str] = None
    created_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": "MultiZoneSceneV1",
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
            "created_at": self.created_at,
        }


@dataclass
class Routine:
    """Time/event-triggered routine."""

    routine_id: str
    name: str
    description: str
    trigger_type: str
    trigger_config: Dict[str, Any]
    zone_actions: Dict[str, List[ZoneAction]]
    enabled: bool = True
    last_triggered: Optional[str] = None
    trigger_count: int = 0
    created_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": "MultiZoneRoutineV1",
            "routine_id": self.routine_id,
            "name": self.name,
            "description": self.description,
            "trigger_type": self.trigger_type,
            "trigger_config": dict(self.trigger_config),
            "zone_actions": {
                zone_id: [a.to_dict() for a in actions]
                for zone_id, actions in self.zone_actions.items()
            },
            "enabled": self.enabled,
            "last_triggered": self.last_triggered,
            "trigger_count": self.trigger_count,
            "created_at": self.created_at,
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
            "contract": "MultiZoneConflictV1",
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "action_ids": list(self.action_ids),
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
        self._detect_conflicts = True
        self._default_resolution = ResolutionStrategy.PRIORITY_BASED

    def _next_action_id(self) -> str:
        self._action_counter += 1
        return f"action_{self._action_counter}"

    def _materialize_zone_actions(
        self,
        zone_actions: Dict[str, List[Dict[str, Any] | ZoneAction]],
    ) -> Dict[str, List[ZoneAction]]:
        converted: Dict[str, List[ZoneAction]] = {}
        for zone_id, actions in zone_actions.items():
            converted[zone_id] = []
            for action_data in actions:
                if isinstance(action_data, ZoneAction):
                    action = action_data
                else:
                    payload = dict(action_data)
                    action = ZoneAction(
                        action_id=str(payload.pop("action_id", "") or self._next_action_id()),
                        zone_id=str(payload.pop("zone_id", zone_id)),
                        module_id=str(payload.pop("module_id")),
                        entity_id=str(payload.pop("entity_id")),
                        domain=str(payload.pop("domain")),
                        service=str(payload.pop("service")),
                        data=payload.pop("data", {}) or {},
                        priority=int(payload.pop("priority", 5) or 5),
                        scheduled_at=payload.pop("scheduled_at", None),
                        expires_at=payload.pop("expires_at", None),
                        dependencies=list(payload.pop("dependencies", []) or []),
                    )
                converted[zone_id].append(action)
        return converted

    def _flatten_actions(self, zone_actions: Dict[str, List[ZoneAction]]) -> List[ZoneAction]:
        return [action for actions in zone_actions.values() for action in actions]

    def _register_conflicts(self, conflicts: List[Conflict]) -> None:
        for conflict in conflicts:
            self._conflicts[conflict.conflict_id] = conflict

    def _sorted_actions_for_conflict(self, actions: List[ZoneAction]) -> List[ZoneAction]:
        return sorted(
            actions,
            key=lambda action: (
                action.priority,
                action.scheduled_at or "",
                action.action_id,
            ),
            reverse=True,
        )

    def create_scene(
        self,
        name: str,
        description: str,
        zone_actions: Dict[str, List[Dict[str, Any] | ZoneAction]],
    ) -> str:
        """Create a multi-zone scene."""
        self._scene_counter += 1
        scene_id = f"scene_{self._scene_counter}"
        scene = MultiZoneScene(
            scene_id=scene_id,
            name=name,
            description=description,
            zone_actions=self._materialize_zone_actions(zone_actions),
        )
        self._scenes[scene_id] = scene
        return scene_id

    def create_routine(
        self,
        name: str,
        description: str,
        trigger_type: str,
        trigger_config: Dict[str, Any],
        zone_actions: Dict[str, List[Dict[str, Any] | ZoneAction]],
    ) -> str:
        """Create a time/event-triggered routine."""
        self._routine_counter += 1
        routine_id = f"routine_{self._routine_counter}"
        routine = Routine(
            routine_id=routine_id,
            name=name,
            description=description,
            trigger_type=trigger_type,
            trigger_config=dict(trigger_config),
            zone_actions=self._materialize_zone_actions(zone_actions),
        )
        self._routines[routine_id] = routine
        return routine_id

    def _detect_action_conflicts(self, actions: List[ZoneAction]) -> List[Conflict]:
        conflicts: List[Conflict] = []
        actions_by_entity: Dict[str, List[ZoneAction]] = {}
        for action in actions:
            actions_by_entity.setdefault(action.entity_id, []).append(action)

        for entity_id, entity_actions in actions_by_entity.items():
            if len(entity_actions) < 2:
                continue

            services = {action.service for action in entity_actions}
            state_conflict = any(
                other in services
                for service in services
                for other in _CONFLICTING_SERVICES.get(service, set())
            )
            if state_conflict:
                self._conflict_counter += 1
                conflicts.append(
                    Conflict(
                        conflict_id=f"conflict_{self._conflict_counter}",
                        conflict_type=ConflictType.STATE_CONFLICT,
                        action_ids=[action.action_id for action in entity_actions],
                        description=f"Conflicting actions for {entity_id}: {sorted(services)}",
                        resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
                    )
                )
                continue

            scheduled = {action.scheduled_at for action in entity_actions if action.scheduled_at}
            if len(scheduled) == 1 and len(services) > 1:
                self._conflict_counter += 1
                conflicts.append(
                    Conflict(
                        conflict_id=f"conflict_{self._conflict_counter}",
                        conflict_type=ConflictType.TIMING_CONFLICT,
                        action_ids=[action.action_id for action in entity_actions],
                        description=f"Timing conflict for {entity_id} at {next(iter(scheduled))}",
                        resolution_strategy=ResolutionStrategy.SEQUENCE,
                    )
                )

        return conflicts

    def _detect_scene_conflicts(self, scene: MultiZoneScene) -> List[Conflict]:
        """Detect conflicts within a scene."""
        return self._detect_action_conflicts(self._flatten_actions(scene.zone_actions))

    def _detect_routine_conflicts(self, routine: Routine) -> List[Conflict]:
        """Detect conflicts within a routine."""
        return self._detect_action_conflicts(self._flatten_actions(routine.zone_actions))

    def _resolve_conflict(
        self,
        conflict: Conflict,
        action_pool: Optional[Dict[str, ZoneAction]] = None,
    ) -> bool:
        """Resolve a conflict using the specified strategy."""
        pool = action_pool if action_pool is not None else self._pending_actions
        actions = [pool.get(action_id) for action_id in conflict.action_ids]
        actions = [action for action in actions if action is not None]
        if not actions:
            return False

        if conflict.resolution_strategy == ResolutionStrategy.PRIORITY_BASED:
            ranked = self._sorted_actions_for_conflict(actions)
            winner = ranked[0]
            for loser in ranked[1:]:
                pool.pop(loser.action_id, None)
            conflict.resolved = True
            conflict.resolution = f"Priority-based: {winner.action_id} (priority {winner.priority}) wins"
            conflict.resolved_at = _utcnow()
            return True

        if conflict.resolution_strategy == ResolutionStrategy.TIME_BASED:
            ranked = sorted(actions, key=lambda action: (action.scheduled_at or "", -action.priority, action.action_id))
            winner = ranked[0]
            for loser in ranked[1:]:
                pool.pop(loser.action_id, None)
            conflict.resolved = True
            conflict.resolution = f"Time-based: {winner.action_id} executes first"
            conflict.resolved_at = _utcnow()
            return True

        if conflict.resolution_strategy == ResolutionStrategy.SEQUENCE:
            conflict.resolved = True
            conflict.resolution = "Sequential execution scheduled"
            conflict.resolved_at = _utcnow()
            return True

        if conflict.resolution_strategy == ResolutionStrategy.MERGE:
            conflict.resolved = True
            conflict.resolution = "Actions merged"
            conflict.resolved_at = _utcnow()
            return True

        conflict.resolved = False
        return False

    def _queue_with_conflict_resolution(self, actions: List[ZoneAction]) -> bool:
        action_pool = dict(self._pending_actions)
        for action in actions:
            action_pool[action.action_id] = action

        conflicts = self._detect_action_conflicts(list(action_pool.values())) if self._detect_conflicts else []
        self._register_conflicts(conflicts)
        unresolved = []
        for conflict in conflicts:
            if not self._resolve_conflict(conflict, action_pool=action_pool):
                unresolved.append(conflict)

        if unresolved:
            return False

        self._pending_actions = action_pool
        return True

    def activate_scene(self, scene_id: str, activated_by: Optional[str] = None) -> bool:
        """Activate a multi-zone scene."""
        scene = self._scenes.get(scene_id)
        if scene is None:
            return False

        if not self._queue_with_conflict_resolution(self._flatten_actions(scene.zone_actions)):
            logger.warning("Scene activation aborted due to unresolved conflicts")
            return False

        scene.is_active = True
        scene.activated_at = _utcnow()
        scene.activated_by = activated_by
        return True

    def deactivate_scene(self, scene_id: str) -> bool:
        """Deactivate a multi-zone scene."""
        scene = self._scenes.get(scene_id)
        if scene is None:
            return False

        scene.is_active = False
        scene_action_ids = {
            action.action_id
            for actions in scene.zone_actions.values()
            for action in actions
        }
        for action_id in scene_action_ids:
            self._pending_actions.pop(action_id, None)
        return True

    def trigger_routine(self, routine_id: str) -> bool:
        """Trigger a routine manually or via scheduler."""
        routine = self._routines.get(routine_id)
        if routine is None:
            return False
        if not routine.enabled:
            logger.info("Routine %s is disabled", routine_id)
            return False

        if not self._queue_with_conflict_resolution(self._flatten_actions(routine.zone_actions)):
            logger.warning("Routine trigger aborted due to unresolved conflicts")
            return False

        routine.last_triggered = _utcnow()
        routine.trigger_count += 1
        return True

    def enable_routine(self, routine_id: str) -> bool:
        """Enable a routine."""
        routine = self._routines.get(routine_id)
        if routine is None:
            return False
        routine.enabled = True
        return True

    def disable_routine(self, routine_id: str) -> bool:
        """Disable a routine."""
        routine = self._routines.get(routine_id)
        if routine is None:
            return False
        routine.enabled = False
        return True

    def get_pending_actions(self, zone_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pending actions, optionally filtered by zone."""
        actions = list(self._pending_actions.values())
        if zone_id:
            actions = [action for action in actions if action.zone_id == zone_id]
        actions = self._sorted_actions_for_conflict(actions)
        return [action.to_dict() for action in actions]

    def get_scenes(self) -> List[Dict[str, Any]]:
        """Get all scenes."""
        return [scene.to_dict() for scene in self._scenes.values()]

    def get_routines(self) -> List[Dict[str, Any]]:
        """Get all routines."""
        return [routine.to_dict() for routine in self._routines.values()]

    def get_conflicts(self, unresolved_only: bool = True) -> List[Dict[str, Any]]:
        """Get conflicts."""
        conflicts = list(self._conflicts.values())
        if unresolved_only:
            conflicts = [conflict for conflict in conflicts if not conflict.resolved]
        conflicts.sort(key=lambda conflict: conflict.conflict_id)
        return [conflict.to_dict() for conflict in conflicts]

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregate coordination stats."""
        return {
            "scenes_total": len(self._scenes),
            "scenes_active": sum(1 for scene in self._scenes.values() if scene.is_active),
            "routines_total": len(self._routines),
            "routines_enabled": sum(1 for routine in self._routines.values() if routine.enabled),
            "pending_actions": len(self._pending_actions),
            "conflicts_total": len(self._conflicts),
            "conflicts_unresolved": sum(1 for conflict in self._conflicts.values() if not conflict.resolved),
        }


def create_multi_zone_coordination_engine() -> MultiZoneCoordinationEngine:
    """Factory function to create multi-zone coordination engine."""
    return MultiZoneCoordinationEngine()
