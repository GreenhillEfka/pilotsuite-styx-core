"""Multi-Zone Coordination Engine — Slice 15 follow-up hardening (v15.3.26).

Coordinates actions across multiple zones (scenes, routines, events).

Hardening additions:
- proposal/action handoff metadata is preserved end-to-end,
- scheduler-driven runtime execution can trigger scenes and routines,
- execution contracts expose real zone/module/service targets.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


SERVICE_TARGET_KEYS = ("entity_id", "device_id", "area_id")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _copy_optional_mapping(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def _copy_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _action_type(domain: str, service: str) -> str:
    if domain and service:
        return f"{domain}.{service}"
    return domain or service or "unknown"


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
    target: Dict[str, Any] = field(default_factory=dict)
    proposal_intent: Optional[Dict[str, Any]] = None
    action_intent: Optional[Dict[str, Any]] = None
    source: str = "multizone.manual"
    queued_at: Optional[str] = None
    queue_source: Optional[str] = None
    subject_type: Optional[str] = None
    subject_id: Optional[str] = None
    scene_id: Optional[str] = None
    routine_id: Optional[str] = None
    scheduled_job_id: Optional[str] = None

    def normalized_target(self) -> Dict[str, Any]:
        target = dict(self.target)
        if self.zone_id and not target.get("zone_id"):
            target["zone_id"] = self.zone_id
        if self.module_id and not target.get("module_id"):
            target["module_id"] = self.module_id
        if self.entity_id and not target.get("entity_id"):
            target["entity_id"] = self.entity_id
        return target

    def conflict_key(self) -> str:
        target = self.normalized_target()
        for key in SERVICE_TARGET_KEYS:
            value = target.get(key)
            if isinstance(value, str) and value:
                return f"{key}:{value}"
        return f"zone:{self.zone_id}|module:{self.module_id}|service:{self.domain}.{self.service}"

    def to_dict(self) -> Dict[str, Any]:
        target = self.normalized_target()
        module_target = {"module_id": self.module_id}
        for key in SERVICE_TARGET_KEYS:
            value = target.get(key)
            if value:
                module_target[key] = value

        return {
            "contract": "ZoneActionV1",
            "execution_contract": "MultiZoneActionExecutionV1",
            "action_id": self.action_id,
            "action_type": _action_type(self.domain, self.service),
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "entity_id": self.entity_id,
            "domain": self.domain,
            "service": self.service,
            "target": target,
            "targets": {
                "zone": {"zone_id": self.zone_id},
                "module": module_target,
                "service": {
                    "domain": self.domain,
                    "service": self.service,
                    "target": target,
                    "payload": dict(self.data),
                },
            },
            "data": dict(self.data),
            "priority": self.priority,
            "scheduled_at": self.scheduled_at,
            "expires_at": self.expires_at,
            "dependencies": list(self.dependencies),
            "proposal_intent": _copy_optional_mapping(self.proposal_intent),
            "action_intent": _copy_optional_mapping(self.action_intent),
            "source": self.source,
            "queued_at": self.queued_at,
            "queue_source": self.queue_source,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "scene_id": self.scene_id,
            "routine_id": self.routine_id,
            "scheduled_job_id": self.scheduled_job_id,
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
    proposal_handoff: Optional[Dict[str, Any]] = None
    action_handoff: Optional[Dict[str, Any]] = None
    scheduler_job_id: Optional[str] = None
    scheduler_binding: Dict[str, Any] = field(default_factory=dict)
    last_execution_source: Optional[str] = None
    last_execution_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": "MultiZoneSceneV1",
            "execution_contract": "MultiZoneSceneRuntimeV1",
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
            "proposal_handoff": _copy_optional_mapping(self.proposal_handoff),
            "action_handoff": _copy_optional_mapping(self.action_handoff),
            "scheduler_job_id": self.scheduler_job_id,
            "scheduler_binding": dict(self.scheduler_binding),
            "last_execution_source": self.last_execution_source,
            "last_execution_at": self.last_execution_at,
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
    proposal_handoff: Optional[Dict[str, Any]] = None
    action_handoff: Optional[Dict[str, Any]] = None
    scheduler_job_id: Optional[str] = None
    scheduler_binding: Dict[str, Any] = field(default_factory=dict)
    last_execution_source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": "MultiZoneRoutineV1",
            "execution_contract": "MultiZoneRoutineRuntimeV1",
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
            "proposal_handoff": _copy_optional_mapping(self.proposal_handoff),
            "action_handoff": _copy_optional_mapping(self.action_handoff),
            "scheduler_job_id": self.scheduler_job_id,
            "scheduler_binding": dict(self.scheduler_binding),
            "last_execution_source": self.last_execution_source,
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

    def __init__(self, scheduler_engine: Any | None = None):
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
        self._scheduler_engine = None
        self.attach_scheduler(scheduler_engine)

    def attach_scheduler(self, scheduler_engine: Any | None) -> None:
        """Attach an optional scheduler engine and register runtime hooks."""
        self._scheduler_engine = scheduler_engine
        if scheduler_engine is None:
            return

        register_action = getattr(scheduler_engine, "register_action", None)
        if callable(register_action):
            register_action("multizone.trigger_routine", self._scheduler_trigger_routine)
            register_action("multizone.activate_scene", self._scheduler_activate_scene)

    def _scheduler_trigger_routine(self, routine_id: str, runtime_source: str = "scheduler", **kwargs) -> Dict[str, Any]:
        ok = self.trigger_routine(routine_id, runtime_source=runtime_source, runtime_context=kwargs)
        return {"ok": ok, "routine_id": routine_id, "runtime_source": runtime_source}

    def _scheduler_activate_scene(self, scene_id: str, runtime_source: str = "scheduler", activated_by: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        ok = self.activate_scene(
            scene_id,
            activated_by=activated_by or runtime_source,
            runtime_source=runtime_source,
            runtime_context=kwargs,
        )
        return {"ok": ok, "scene_id": scene_id, "runtime_source": runtime_source}

    def _next_action_id(self) -> str:
        self._action_counter += 1
        return f"action_{self._action_counter}"

    def _normalize_domain_service(
        self,
        payload: dict[str, Any],
        proposal_intent: dict[str, Any] | None,
        action_intent: dict[str, Any] | None,
    ) -> tuple[str, str]:
        domain = str(payload.pop("domain", "") or "").strip()
        service = str(payload.pop("service", "") or "").strip()
        action_type = str(
            payload.get("action_type")
            or (action_intent or {}).get("action_type")
            or (proposal_intent or {}).get("action_type")
            or ""
        ).strip()
        if (not domain or not service) and "." in action_type:
            candidate_domain, candidate_service = action_type.split(".", 1)
            domain = domain or candidate_domain
            service = service or candidate_service
        return domain, service

    def _resolve_schedule_binding(self, config: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(config, dict):
            return {}

        schedule_type = str(config.get("schedule_type") or "").strip().lower()
        schedule_expression = str(config.get("schedule_expression") or "").strip()
        if schedule_type and schedule_expression:
            return {
                "schedule_type": schedule_type,
                "schedule_expression": schedule_expression,
            }

        for key in ("at", "datetime"):
            value = config.get(key)
            if isinstance(value, str) and value.strip():
                return {
                    "schedule_type": "once",
                    "schedule_expression": value.strip(),
                }

        interval_seconds = config.get("interval_seconds")
        if interval_seconds is not None:
            return {
                "schedule_type": "interval",
                "schedule_expression": str(_coerce_int(interval_seconds, 60)),
            }

        hour = config.get("hour")
        minute = config.get("minute", 0)
        weekday = str(
            config.get("weekday")
            or config.get("day_of_week")
            or ""
        ).strip().lower()
        if hour is not None:
            expression = f"{_coerce_int(hour, 0):02d}:{_coerce_int(minute, 0):02d}"
            if weekday:
                return {
                    "schedule_type": "weekly",
                    "schedule_expression": f"{weekday} {expression}",
                }
            return {
                "schedule_type": "daily",
                "schedule_expression": expression,
            }

        return {}

    def _bind_scheduler_job(
        self,
        *,
        name: str,
        description: str,
        binding_config: dict[str, Any],
        action_name: str,
        parameters: dict[str, Any],
        tags: list[str],
    ) -> tuple[str | None, dict[str, Any]]:
        scheduler = self._scheduler_engine
        if scheduler is None:
            return None, {}

        create_job = getattr(scheduler, "create_job", None)
        if not callable(create_job):
            return None, {}

        binding = self._resolve_schedule_binding(binding_config)
        if not binding:
            return None, {}

        timezone_name = str(binding_config.get("timezone") or "UTC")
        job_id = create_job(
            name=name,
            description=description,
            schedule_type=binding["schedule_type"],
            schedule_expression=binding["schedule_expression"],
            action_name=action_name,
            parameters=dict(parameters),
            timezone=timezone_name,
            tags=list(tags),
        )
        binding["timezone"] = timezone_name
        return job_id, binding

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
                    proposal_intent = _copy_optional_mapping(payload.pop("proposal_intent", None))
                    action_intent = _copy_optional_mapping(payload.pop("action_intent", None))

                    target = _copy_mapping(payload.pop("target", None))
                    if not target and proposal_intent:
                        target = _copy_mapping(proposal_intent.get("target"))
                    if not target and action_intent:
                        target = _copy_mapping(action_intent.get("target"))

                    domain, service = self._normalize_domain_service(payload, proposal_intent, action_intent)
                    zone_id_value = str(
                        payload.pop("zone_id", "")
                        or target.get("zone_id")
                        or (action_intent or {}).get("zone_id")
                        or (proposal_intent or {}).get("zone_id")
                        or zone_id
                    )
                    module_id = str(
                        payload.pop("module_id", "")
                        or target.get("module_id")
                        or (action_intent or {}).get("module_id")
                        or (proposal_intent or {}).get("module_id")
                        or domain
                        or "unknown"
                    )
                    entity_id = str(
                        payload.pop("entity_id", "")
                        or target.get("entity_id")
                        or _copy_mapping((action_intent or {}).get("target")).get("entity_id")
                        or _copy_mapping((proposal_intent or {}).get("target")).get("entity_id")
                        or ""
                    )
                    target.setdefault("zone_id", zone_id_value)
                    target.setdefault("module_id", module_id)
                    if entity_id:
                        target.setdefault("entity_id", entity_id)

                    data = payload.pop("data", None)
                    if not isinstance(data, dict):
                        data = payload.pop("payload", None)
                    if not isinstance(data, dict):
                        data = payload.pop("service_data", None)
                    if not isinstance(data, dict):
                        data = _copy_mapping((action_intent or {}).get("payload"))
                    if not data:
                        data = _copy_mapping((proposal_intent or {}).get("payload"))

                    source = str(
                        payload.pop("source", "")
                        or (action_intent or {}).get("source")
                        or (proposal_intent or {}).get("source")
                        or "multizone.manual"
                    )

                    action = ZoneAction(
                        action_id=str(payload.pop("action_id", "") or self._next_action_id()),
                        zone_id=zone_id_value,
                        module_id=module_id,
                        entity_id=entity_id,
                        domain=domain,
                        service=service,
                        data=data or {},
                        priority=_coerce_int(payload.pop("priority", 5), 5),
                        scheduled_at=payload.pop("scheduled_at", None),
                        expires_at=payload.pop("expires_at", None),
                        dependencies=_copy_str_list(payload.pop("dependencies", [])),
                        target=target,
                        proposal_intent=proposal_intent,
                        action_intent=action_intent,
                        source=source,
                        scheduled_job_id=payload.pop("scheduled_job_id", None),
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
        *,
        proposal_handoff: dict[str, Any] | None = None,
        action_handoff: dict[str, Any] | None = None,
        schedule_config: dict[str, Any] | None = None,
    ) -> str:
        """Create a multi-zone scene."""
        self._scene_counter += 1
        scene_id = f"scene_{self._scene_counter}"
        scene = MultiZoneScene(
            scene_id=scene_id,
            name=name,
            description=description,
            zone_actions=self._materialize_zone_actions(zone_actions),
            proposal_handoff=_copy_optional_mapping(proposal_handoff),
            action_handoff=_copy_optional_mapping(action_handoff),
        )

        if schedule_config:
            job_id, binding = self._bind_scheduler_job(
                name=f"Scene: {name}",
                description=description or f"Activate multi-zone scene {scene_id}",
                binding_config=dict(schedule_config),
                action_name="multizone.activate_scene",
                parameters={"scene_id": scene_id, "runtime_source": "scheduler", "activated_by": "scheduler"},
                tags=["multizone", "scene", scene_id],
            )
            scene.scheduler_job_id = job_id
            scene.scheduler_binding = binding

        self._scenes[scene_id] = scene
        return scene_id

    def create_routine(
        self,
        name: str,
        description: str,
        trigger_type: str,
        trigger_config: Dict[str, Any],
        zone_actions: Dict[str, List[Dict[str, Any] | ZoneAction]],
        *,
        proposal_handoff: dict[str, Any] | None = None,
        action_handoff: dict[str, Any] | None = None,
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
            proposal_handoff=_copy_optional_mapping(proposal_handoff),
            action_handoff=_copy_optional_mapping(action_handoff),
        )

        if str(trigger_type).strip().lower() == "time":
            job_id, binding = self._bind_scheduler_job(
                name=f"Routine: {name}",
                description=description or f"Trigger multi-zone routine {routine_id}",
                binding_config=dict(trigger_config),
                action_name="multizone.trigger_routine",
                parameters={"routine_id": routine_id, "runtime_source": "scheduler"},
                tags=["multizone", "routine", routine_id],
            )
            routine.scheduler_job_id = job_id
            routine.scheduler_binding = binding

        self._routines[routine_id] = routine
        return routine_id

    def _detect_action_conflicts(self, actions: List[ZoneAction]) -> List[Conflict]:
        conflicts: List[Conflict] = []
        actions_by_target: Dict[str, List[ZoneAction]] = {}
        for action in actions:
            actions_by_target.setdefault(action.conflict_key(), []).append(action)

        for target_key, target_actions in actions_by_target.items():
            if len(target_actions) < 2:
                continue

            services = {action.service for action in target_actions}
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
                        action_ids=[action.action_id for action in target_actions],
                        description=f"Conflicting actions for {target_key}: {sorted(services)}",
                        resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
                    )
                )
                continue

            scheduled = {action.scheduled_at for action in target_actions if action.scheduled_at}
            if len(scheduled) == 1 and len(services) > 1:
                self._conflict_counter += 1
                conflicts.append(
                    Conflict(
                        conflict_id=f"conflict_{self._conflict_counter}",
                        conflict_type=ConflictType.TIMING_CONFLICT,
                        action_ids=[action.action_id for action in target_actions],
                        description=f"Timing conflict for {target_key} at {next(iter(scheduled))}",
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

    def _prepare_actions_for_runtime(
        self,
        actions: list[ZoneAction],
        *,
        runtime_source: str,
        subject_type: str,
        subject_id: str,
        scheduled_job_id: str | None = None,
    ) -> list[ZoneAction]:
        queued_at = _utcnow()
        for action in actions:
            action.target = action.normalized_target()
            if action.action_intent and isinstance(action.action_intent.get("source"), str):
                action.source = str(action.action_intent.get("source") or action.source)
            elif action.proposal_intent and isinstance(action.proposal_intent.get("source"), str):
                action.source = str(action.proposal_intent.get("source") or action.source)
            action.queued_at = queued_at
            action.queue_source = runtime_source
            action.subject_type = subject_type
            action.subject_id = subject_id
            if subject_type == "scene":
                action.scene_id = subject_id
            if subject_type == "routine":
                action.routine_id = subject_id
            if scheduled_job_id:
                action.scheduled_job_id = scheduled_job_id
        return actions

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

    def activate_scene(
        self,
        scene_id: str,
        activated_by: Optional[str] = None,
        *,
        runtime_source: str = "manual",
        runtime_context: dict[str, Any] | None = None,
    ) -> bool:
        """Activate a multi-zone scene."""
        scene = self._scenes.get(scene_id)
        if scene is None:
            return False

        actions = self._prepare_actions_for_runtime(
            self._flatten_actions(scene.zone_actions),
            runtime_source=runtime_source,
            subject_type="scene",
            subject_id=scene_id,
            scheduled_job_id=scene.scheduler_job_id,
        )
        if not self._queue_with_conflict_resolution(actions):
            logger.warning("Scene activation aborted due to unresolved conflicts")
            return False

        scene.is_active = True
        scene.activated_at = _utcnow()
        scene.activated_by = activated_by or runtime_source
        scene.last_execution_source = runtime_source
        scene.last_execution_at = scene.activated_at
        if runtime_context and not scene.action_handoff:
            scene.action_handoff = {"runtime_context": dict(runtime_context)}
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

    def trigger_routine(
        self,
        routine_id: str,
        *,
        runtime_source: str = "manual",
        runtime_context: dict[str, Any] | None = None,
    ) -> bool:
        """Trigger a routine manually or via scheduler."""
        routine = self._routines.get(routine_id)
        if routine is None:
            return False
        if not routine.enabled:
            logger.info("Routine %s is disabled", routine_id)
            return False

        actions = self._prepare_actions_for_runtime(
            self._flatten_actions(routine.zone_actions),
            runtime_source=runtime_source,
            subject_type="routine",
            subject_id=routine_id,
            scheduled_job_id=routine.scheduler_job_id,
        )
        if not self._queue_with_conflict_resolution(actions):
            logger.warning("Routine trigger aborted due to unresolved conflicts")
            return False

        routine.last_triggered = _utcnow()
        routine.last_execution_source = runtime_source
        routine.trigger_count += 1
        if runtime_context and not routine.action_handoff:
            routine.action_handoff = {"runtime_context": dict(runtime_context)}
        return True

    def enable_routine(self, routine_id: str) -> bool:
        """Enable a routine."""
        routine = self._routines.get(routine_id)
        if routine is None:
            return False
        routine.enabled = True
        enable_job = getattr(self._scheduler_engine, "enable_job", None)
        if routine.scheduler_job_id and callable(enable_job):
            enable_job(routine.scheduler_job_id)
        return True

    def disable_routine(self, routine_id: str) -> bool:
        """Disable a routine."""
        routine = self._routines.get(routine_id)
        if routine is None:
            return False
        routine.enabled = False
        disable_job = getattr(self._scheduler_engine, "disable_job", None)
        if routine.scheduler_job_id and callable(disable_job):
            disable_job(routine.scheduler_job_id)
        return True

    def get_pending_actions(
        self,
        zone_id: Optional[str] = None,
        module_id: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get pending actions, optionally filtered by runtime target."""
        actions = list(self._pending_actions.values())
        if zone_id:
            actions = [action for action in actions if action.zone_id == zone_id]
        if module_id:
            actions = [action for action in actions if action.module_id == module_id]
        if entity_id:
            actions = [action for action in actions if action.normalized_target().get("entity_id") == entity_id]
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
            "scenes_scheduler_bound": sum(1 for scene in self._scenes.values() if scene.scheduler_job_id),
            "routines_total": len(self._routines),
            "routines_enabled": sum(1 for routine in self._routines.values() if routine.enabled),
            "routines_scheduler_bound": sum(1 for routine in self._routines.values() if routine.scheduler_job_id),
            "pending_actions": len(self._pending_actions),
            "pending_actions_with_handoffs": sum(
                1
                for action in self._pending_actions.values()
                if action.proposal_intent or action.action_intent
            ),
            "conflicts_total": len(self._conflicts),
            "conflicts_unresolved": sum(1 for conflict in self._conflicts.values() if not conflict.resolved),
        }


def create_multi_zone_coordination_engine(
    scheduler_engine: Any | None = None,
) -> MultiZoneCoordinationEngine:
    """Factory function to create multi-zone coordination engine."""
    return MultiZoneCoordinationEngine(scheduler_engine=scheduler_engine)
