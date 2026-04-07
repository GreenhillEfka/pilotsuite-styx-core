"""P4-004: Action Executor — HA Service Calls, Multi-Step Workflows."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ActionStatus(Enum):
    """Action execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Action:
    """Single action to execute."""
    id: str
    name: str
    domain: str  # light, switch, climate, etc.
    service: str  # turn_on, turn_off, set_temperature, etc.
    entity_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    status: ActionStatus = ActionStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class Workflow:
    """Multi-step workflow."""
    id: str
    name: str
    actions: List[Action]
    status: ActionStatus = ActionStatus.PENDING
    current_step: int = 0
    created_at: float = field(default_factory=time.time)


class ActionExecutor:
    """Executes actions and workflows."""

    def __init__(self, ha_service_callback: Optional[Callable] = None):
        self.ha_service_callback = ha_service_callback
        self._actions: Dict[str, Action] = {}
        self._workflows: Dict[str, Workflow] = {}
        self._execution_log: List[Dict[str, Any]] = []

    def create_action(
        self,
        name: str,
        domain: str,
        service: str,
        entity_id: str,
        data: Optional[Dict] = None,
    ) -> Action:
        """Create a new action."""
        import hashlib
        action_id = hashlib.sha256(f"{name}{time.time()}".encode()).hexdigest()[:16]
        
        action = Action(
            id=action_id,
            name=name,
            domain=domain,
            service=service,
            entity_id=entity_id,
            data=data or {}
        )
        
        self._actions[action_id] = action
        return action

    async def execute_action(self, action_id: str) -> bool:
        """Execute a single action."""
        if action_id not in self._actions:
            return False
        
        action = self._actions[action_id]
        action.status = ActionStatus.RUNNING
        action.started_at = time.time()
        
        try:
            if self.ha_service_callback:
                result = await self.ha_service_callback(
                    action.domain,
                    action.service,
                    action.entity_id,
                    action.data
                )
                action.result = result
                action.status = ActionStatus.COMPLETED
            else:
                # Simulated execution
                action.result = {"success": True}
                action.status = ActionStatus.COMPLETED
            
            action.completed_at = time.time()
            
            self._execution_log.append({
                "action_id": action_id,
                "status": "completed",
                "duration_ms": (action.completed_at - action.started_at) * 1000
            })
            
            logger.info(f"Action completed: {action.name}")
            return True
            
        except Exception as e:
            action.error = str(e)
            action.status = ActionStatus.FAILED
            action.completed_at = time.time()
            
            self._execution_log.append({
                "action_id": action_id,
                "status": "failed",
                "error": str(e)
            })
            
            logger.error(f"Action failed: {action.name} - {e}")
            return False

    def create_workflow(self, name: str, actions: List[Action]) -> Workflow:
        """Create a multi-step workflow."""
        import hashlib
        workflow_id = hashlib.sha256(f"{name}{time.time()}".encode()).hexdigest()[:16]
        
        workflow = Workflow(
            id=workflow_id,
            name=name,
            actions=actions
        )
        
        self._workflows[workflow_id] = workflow
        return workflow

    async def execute_workflow(self, workflow_id: str) -> bool:
        """Execute a workflow step by step."""
        if workflow_id not in self._workflows:
            return False
        
        workflow = self._workflows[workflow_id]
        workflow.status = ActionStatus.RUNNING
        
        for i, action in enumerate(workflow.actions):
            workflow.current_step = i
            
            success = await self.execute_action(action.id)
            
            if not success:
                workflow.status = ActionStatus.FAILED
                logger.warning(f"Workflow stopped at step {i}: {action.name}")
                return False
        
        workflow.status = ActionStatus.COMPLETED
        workflow.current_step = len(workflow.actions)
        logger.info(f"Workflow completed: {workflow.name}")
        return True

    def get_action(self, action_id: str) -> Optional[Action]:
        """Get action by ID."""
        return self._actions.get(action_id)

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get workflow by ID."""
        return self._workflows.get(workflow_id)

    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history."""
        return self._execution_log[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        completed = len([a for a in self._actions.values() if a.status == ActionStatus.COMPLETED])
        failed = len([a for a in self._actions.values() if a.status == ActionStatus.FAILED])
        
        return {
            "total_actions": len(self._actions),
            "total_workflows": len(self._workflows),
            "completed_actions": completed,
            "failed_actions": failed,
            "success_rate": completed / max(1, completed + failed),
        }


# Global default executor
default_executor: Optional[ActionExecutor] = None


def init_action_executor(ha_callback: Optional[Callable] = None) -> ActionExecutor:
    """Initialize global action executor."""
    global default_executor
    default_executor = ActionExecutor(ha_callback)
    return default_executor
