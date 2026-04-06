"""
Scene Executor for PilotSuite Core.

Handles scene execution, action sequencing, and state management.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable

from .scene_manager import Scene, SceneAction, SceneActionType, SceneEntity

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Status of scene execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ExecutionMode(str, Enum):
    """Execution mode for scenes."""
    SEQUENTIAL = "sequential"  # Execute actions one by one
    PARALLEL = "parallel"  # Execute all actions simultaneously
    GROUPED = "grouped"  # Execute actions grouped by entity type


@dataclass
class ActionResult:
    """Result of executing a single action."""
    action_id: str
    success: bool
    entity_id: str
    error_message: Optional[str] = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0


@dataclass
class SceneExecutionResult:
    """Result of executing a scene."""
    execution_id: str
    scene_id: str
    scene_name: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    actions_results: List[ActionResult] = field(default_factory=list)
    error_message: Optional[str] = None
    entities_affected: int = 0
    actions_succeeded: int = 0
    actions_failed: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "execution_id": self.execution_id,
            "scene_id": self.scene_id,
            "scene_name": self.scene_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "actions_results": [
                {
                    "action_id": r.action_id,
                    "success": r.success,
                    "entity_id": r.entity_id,
                    "error_message": r.error_message,
                    "executed_at": r.executed_at.isoformat(),
                    "duration_ms": r.duration_ms,
                }
                for r in self.actions_results
            ],
            "error_message": self.error_message,
            "entities_affected": self.entities_affected,
            "actions_succeeded": self.actions_succeeded,
            "actions_failed": self.actions_failed,
        }


@dataclass
class SceneExecutionContext:
    """
    Context for scene execution.
    """
    execution_id: str
    scene: Scene
    mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    dry_run: bool = False
    skip_disabled_actions: bool = True
    timeout_seconds: float = 60.0
    user_id: Optional[str] = None
    triggered_by: Optional[str] = None  # manual, schedule, event, etc.
    variables: Dict[str, Any] = field(default_factory=dict)
    
    # Callbacks
    on_action_start: Optional[Callable[[SceneAction], Awaitable[None]]] = None
    on_action_complete: Optional[Callable[[ActionResult], Awaitable[None]]] = None
    on_status_change: Optional[Callable[[ExecutionStatus], Awaitable[None]]] = None
    
    # State
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled: bool = False
    pause_requested: bool = False


class SceneExecutor:
    """
    Executes scenes with support for sequencing, delays, and error handling.
    """

    def __init__(
        self,
        homeassistant_client: Optional[Any] = None,
        default_timeout: float = 60.0,
    ):
        """
        Initialize the scene executor.

        Args:
            homeassistant_client: Home Assistant client for entity control.
                                  If None, actions are logged but not executed.
            default_timeout: Default timeout for scene execution in seconds.
        """
        self._ha_client = homeassistant_client
        self._default_timeout = default_timeout
        self._executions: Dict[str, SceneExecutionContext] = {}
        logger.info("SceneExecutor initialized")

    async def execute(
        self,
        scene: Scene,
        mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
        dry_run: bool = False,
        user_id: Optional[str] = None,
        triggered_by: str = "manual",
        timeout_seconds: Optional[float] = None,
        on_action_start: Optional[Callable[[SceneAction], Awaitable[None]]] = None,
        on_action_complete: Optional[Callable[[ActionResult], Awaitable[None]]] = None,
        on_status_change: Optional[Callable[[ExecutionStatus], Awaitable[None]]] = None,
    ) -> SceneExecutionResult:
        """
        Execute a scene.

        Args:
            scene: Scene to execute
            mode: Execution mode (sequential, parallel, or grouped)
            dry_run: If True, log actions but don't execute
            user_id: User ID triggering the execution
            triggered_by: What triggered this execution
            timeout_seconds: Execution timeout (uses default if None)
            on_action_start: Async callback before each action
            on_action_complete: Async callback after each action
            on_status_change: Async callback on status changes

        Returns:
            SceneExecutionResult with execution details
        """
        import uuid
        
        execution_id = str(uuid.uuid4())
        timeout = timeout_seconds or self._default_timeout

        context = SceneExecutionContext(
            execution_id=execution_id,
            scene=scene,
            mode=mode,
            dry_run=dry_run,
            user_id=user_id,
            triggered_by=triggered_by,
            timeout_seconds=timeout,
            on_action_start=on_action_start,
            on_action_complete=on_action_complete,
            on_status_change=on_status_change,
        )

        self._executions[execution_id] = context

        try:
            await self._change_status(context, ExecutionStatus.RUNNING)
            context.started_at = datetime.now(timezone.utc)

            if mode == ExecutionMode.SEQUENTIAL:
                await self._execute_sequential(context)
            elif mode == ExecutionMode.PARALLEL:
                await self._execute_parallel(context)
            elif mode == ExecutionMode.GROUPED:
                await self._execute_grouped(context)
            else:
                await self._execute_sequential(context)

            if context.cancelled:
                await self._change_status(context, ExecutionStatus.CANCELLED)
            else:
                await self._change_status(context, ExecutionStatus.COMPLETED)

            context.completed_at = datetime.now(timezone.utc)
            return self._build_result(context)

        except asyncio.TimeoutError:
            context.error_message = f"Execution timed out after {timeout}s"
            await self._change_status(context, ExecutionStatus.FAILED)
            context.completed_at = datetime.now(timezone.utc)
            logger.error(f"Scene execution timed out: {scene.name}")
            return self._build_result(context)

        except Exception as e:
            context.error_message = str(e)
            await self._change_status(context, ExecutionStatus.FAILED)
            context.completed_at = datetime.now(timezone.utc)
            logger.exception(f"Scene execution failed: {scene.name}")
            return self._build_result(context)

        finally:
            # Clean up execution context after delay
            asyncio.create_task(self._cleanup_execution(execution_id))

    async def _change_status(
        self,
        context: SceneExecutionContext,
        status: ExecutionStatus,
    ) -> None:
        """Change execution status and notify callback."""
        context.status = status
        if context.on_status_change:
            try:
                await context.on_status_change(status)
            except Exception as e:
                logger.warning(f"Status callback failed: {e}")

    async def _execute_sequential(self, context: SceneExecutionContext) -> None:
        """Execute actions one by one, respecting delays."""
        actions = self._get_enabled_actions(context)
        
        # Sort by order
        actions = sorted(actions, key=lambda a: a.order)

        for i, action in enumerate(actions):
            if context.cancelled:
                break

            if context.pause_requested:
                await self._wait_for_resume(context)
                if context.cancelled:
                    break

            # Apply delay before action (except first)
            if i > 0 and action.delay_seconds > 0:
                await asyncio.sleep(action.delay_seconds)

            result = await self._execute_action(context, action)
            context.actions_results.append(result)

            # If action failed and it's critical, stop execution
            if not result.success and self._is_critical_action(action):
                logger.warning(f"Critical action failed, stopping: {action.entity_id}")
                break

    async def _execute_parallel(self, context: SceneExecutionContext) -> None:
        """Execute all actions simultaneously."""
        actions = self._get_enabled_actions(context)
        
        async def execute_with_delay(action: SceneAction, delay: float):
            if delay > 0:
                await asyncio.sleep(delay)
            return await self._execute_action(context, action)

        tasks = [
            execute_with_delay(action, action.delay_seconds)
            for action in actions
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Parallel action failed: {result}")
            elif isinstance(result, ActionResult):
                context.actions_results.append(result)

    async def _execute_grouped(self, context: SceneExecutionContext) -> None:
        """Execute actions grouped by entity type."""
        actions = self._get_enabled_actions(context)
        
        # Group by entity type
        groups: Dict[str, List[SceneAction]] = {}
        for action in actions:
            entity_type = action.entity_id.split(".")[0] if "." in action.entity_id else "unknown"
            if entity_type not in groups:
                groups[entity_type] = []
            groups[entity_type].append(action)

        # Execute each group in parallel, groups sequentially
        for entity_type, group_actions in groups.items():
            if context.cancelled:
                break

            logger.debug(f"Executing group: {entity_type} ({len(group_actions)} actions)")
            
            tasks = [
                self._execute_action(context, action)
                for action in group_actions
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, ActionResult):
                    context.actions_results.append(result)

    async def _execute_action(
        self,
        context: SceneExecutionContext,
        action: SceneAction,
    ) -> ActionResult:
        """Execute a single action."""
        start_time = time.time()

        if context.on_action_start:
            try:
                await context.on_action_start(action)
            except Exception as e:
                logger.warning(f"Action start callback failed: {e}")

        result = ActionResult(
            action_id=action.action_id,
            success=False,
            entity_id=action.entity_id,
        )

        try:
            if context.dry_run:
                logger.info(f"[DRY RUN] Would execute: {action.action_type.value} on {action.entity_id}")
                result.success = True
            else:
                result.success = await self._perform_action(action)

        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Action failed: {action.entity_id} - {e}")

        result.duration_ms = (time.time() - start_time) * 1000
        result.executed_at = datetime.now(timezone.utc)

        if context.on_action_complete:
            try:
                await context.on_action_complete(result)
            except Exception as e:
                logger.warning(f"Action complete callback failed: {e}")

        return result

    async def _perform_action(self, action: SceneAction) -> bool:
        """
        Perform the actual action against Home Assistant.

        Args:
            action: Action to execute

        Returns:
            True if successful, False otherwise
        """
        if not self._ha_client:
            logger.debug(f"No HA client, logging action only: {action.entity_id}")
            return True

        try:
            entity_id = action.entity_id
            action_type = action.action_type
            params = action.parameters or {}

            if action_type == SceneActionType.LIGHT_ON:
                return await self._ha_client.light_turn_on(entity_id, **params)
            elif action_type == SceneActionType.LIGHT_OFF:
                return await self._ha_client.light_turn_off(entity_id)
            elif action_type == SceneActionType.LIGHT_SET:
                brightness = params.get("brightness")
                color_temp = params.get("color_temp")
                rgb_color = params.get("rgb_color")
                return await self._ha_client.light_set(
                    entity_id,
                    brightness=brightness,
                    color_temp=color_temp,
                    rgb_color=rgb_color,
                )
            elif action_type == SceneActionType.SWITCH_ON:
                return await self._ha_client.switch_turn_on(entity_id)
            elif action_type == SceneActionType.SWITCH_OFF:
                return await self._ha_client.switch_turn_off(entity_id)
            elif action_type == SceneActionType.CLIMATE_SET:
                temperature = params.get("temperature")
                hvac_mode = params.get("hvac_mode")
                return await self._ha_client.climate_set(
                    entity_id,
                    temperature=temperature,
                    hvac_mode=hvac_mode,
                )
            elif action_type == SceneActionType.COVER_OPEN:
                return await self._ha_client.cover_open(entity_id)
            elif action_type == SceneActionType.COVER_CLOSE:
                return await self._ha_client.cover_close(entity_id)
            elif action_type == SceneActionType.COVER_SET:
                position = params.get("position")
                return await self._ha_client.cover_set_position(entity_id, position)
            elif action_type == SceneActionType.MEDIA_PLAY:
                return await self._ha_client.media_play(entity_id)
            elif action_type == SceneActionType.MEDIA_PAUSE:
                return await self._ha_client.media_pause(entity_id)
            elif action_type == SceneActionType.MEDIA_VOLUME:
                volume = params.get("volume")
                return await self._ha_client.media_set_volume(entity_id, volume)
            elif action_type == SceneActionType.SCRIPT_EXECUTE:
                script_id = params.get("script_id", entity_id)
                return await self._ha_client.script_execute(script_id)
            elif action_type == SceneActionType.SERVICE_CALL:
                domain = params.get("domain", "homeassistant")
                service = params.get("service", "turn_on")
                service_data = params.get("service_data", {})
                return await self._ha_client.call_service(domain, service, service_data)
            elif action_type == SceneActionType.DELAY:
                delay = params.get("seconds", 0)
                if delay > 0:
                    await asyncio.sleep(delay)
                return True
            elif action_type == SceneActionType.CONDITION:
                # Evaluate condition, return True if passes
                return await self._evaluate_condition(action)
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return False

        except Exception as e:
            logger.error(f"Failed to perform action {action.action_type} on {entity_id}: {e}")
            return False

    async def _evaluate_condition(self, action: SceneAction) -> bool:
        """Evaluate a condition action."""
        condition_type = action.parameters.get("condition_type", "state")
        entity_id = action.parameters.get("entity_id")
        expected_state = action.parameters.get("state")
        timeout = action.parameters.get("timeout", 10.0)

        if not self._ha_client:
            return True

        if condition_type == "state":
            start = time.time()
            while time.time() - start < timeout:
                try:
                    state = await self._ha_client.get_entity_state(entity_id)
                    if state == expected_state:
                        return True
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            return False

        return True

    def _get_enabled_actions(self, context: SceneExecutionContext) -> List[SceneAction]:
        """Get enabled actions from the scene."""
        if context.skip_disabled_actions:
            return [a for a in context.scene.actions if a.enabled]
        return list(context.scene.actions)

    def _is_critical_action(self, action: SceneAction) -> bool:
        """Check if an action is critical (should stop execution on failure)."""
        return action.parameters.get("critical", False)

    async def _wait_for_resume(self, context: SceneExecutionContext) -> None:
        """Wait until pause is cleared or execution is cancelled."""
        while context.pause_requested and not context.cancelled:
            await asyncio.sleep(0.5)

    async def _cleanup_execution(self, execution_id: str, delay: float = 60.0) -> None:
        """Clean up execution context after delay."""
        await asyncio.sleep(delay)
        self._executions.pop(execution_id, None)

    def _build_result(self, context: SceneExecutionContext) -> SceneExecutionResult:
        """Build execution result from context."""
        actions_succeeded = sum(1 for r in context.actions_results if r.success)
        actions_failed = len(context.actions_results) - actions_succeeded
        entities_affected = len(set(r.entity_id for r in context.actions_results))

        return SceneExecutionResult(
            execution_id=context.execution_id,
            scene_id=context.scene.scene_id,
            scene_name=context.scene.name,
            status=context.status,
            started_at=context.started_at or datetime.now(timezone.utc),
            completed_at=context.completed_at,
            actions_results=context.actions_results,
            error_message=context.error_message,
            entities_affected=entities_affected,
            actions_succeeded=actions_succeeded,
            actions_failed=actions_failed,
        )

    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running execution."""
        context = self._executions.get(execution_id)
        if not context:
            return False
        
        context.cancelled = True
        logger.info(f"Cancelled execution: {execution_id}")
        return True

    def pause_execution(self, execution_id: str) -> bool:
        """Pause a running execution."""
        context = self._executions.get(execution_id)
        if not context or context.status != ExecutionStatus.RUNNING:
            return False
        
        context.pause_requested = True
        logger.info(f"Paused execution: {execution_id}")
        return True

    def resume_execution(self, execution_id: str) -> bool:
        """Resume a paused execution."""
        context = self._executions.get(execution_id)
        if not context:
            return False
        
        context.pause_requested = False
        logger.info(f"Resumed execution: {execution_id}")
        return True

    def get_execution(self, execution_id: str) -> Optional[SceneExecutionContext]:
        """Get execution context by ID."""
        return self._executions.get(execution_id)

    def get_active_executions(self) -> List[SceneExecutionContext]:
        """Get all active (running/paused) executions."""
        return [
            ctx for ctx in self._executions.values()
            if ctx.status in (ExecutionStatus.RUNNING, ExecutionStatus.PAUSED)
        ]

    async def execute_entities(
        self,
        entities: List[SceneEntity],
        dry_run: bool = False,
    ) -> List[ActionResult]:
        """
        Execute a list of entity states (restore scene entities).

        Args:
            entities: List of entities with target states
            dry_run: If True, log only

        Returns:
            List of action results
        """
        results = []

        for entity in entities:
            action = self._entity_to_action(entity)
            if action:
                result = await self._execute_action(
                    SceneExecutionContext(
                        execution_id="adhoc",
                        scene=Scene(scene_id="adhoc", name="Ad-hoc"),
                        dry_run=dry_run,
                    ),
                    action,
                )
                results.append(result)

        return results

    def _entity_to_action(self, entity: SceneEntity) -> Optional[SceneAction]:
        """Convert a SceneEntity to a SceneAction."""
        entity_type = entity.entity_type
        entity_id = entity.entity_id
        state = entity.state
        attrs = entity.attributes

        action_type_map = {
            "light": SceneActionType.LIGHT_SET if state == "on" else SceneActionType.LIGHT_OFF,
            "switch": SceneActionType.SWITCH_ON if state == "on" else SceneActionType.SWITCH_OFF,
            "climate": SceneActionType.CLIMATE_SET,
            "cover": SceneActionType.COVER_SET if state == "on" else SceneActionType.COVER_CLOSE,
            "media_player": SceneActionType.MEDIA_PLAY if state == "playing" else SceneActionType.MEDIA_PAUSE,
        }

        action_type = action_type_map.get(entity_type)
        if not action_type:
            return None

        params = {}
        if entity_type == "light":
            if "brightness" in attrs:
                params["brightness"] = attrs["brightness"]
            if "color_temp" in attrs:
                params["color_temp"] = attrs["color_temp"]
            if "rgb_color" in attrs:
                params["rgb_color"] = attrs["rgb_color"]
        elif entity_type == "climate":
            if "temperature" in attrs:
                params["temperature"] = attrs["temperature"]
            if "hvac_mode" in attrs:
                params["hvac_mode"] = attrs["hvac_mode"]
        elif entity_type == "cover":
            if "position" in attrs:
                params["position"] = attrs["position"]
        elif entity_type == "media_player":
            if "volume_level" in attrs:
                params["volume"] = attrs["volume_level"]

        return SceneAction(
            action_id=f"entity_{entity_id}",
            action_type=action_type,
            entity_id=entity_id,
            parameters=params,
        )
