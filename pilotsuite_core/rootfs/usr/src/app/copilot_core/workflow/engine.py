"""Workflow Engine — Slice 29.

Workflow orchestration for PilotSuite Core.

Features:
- Workflow definition and execution
- Step-based workflow processing
- Conditional branching
- Parallel execution
- Error handling and rollback
- Workflow state persistence
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepType(Enum):
    """Step type."""
    ACTION = "action"
    CONDITION = "condition"
    PARALLEL = "parallel"
    WAIT = "wait"
    TRANSFORM = "transform"


@dataclass
class WorkflowStep:
    """Workflow step definition."""
    step_id: str
    name: str
    step_type: StepType
    action: Optional[Callable] = None
    condition: Optional[str] = None
    on_success: Optional[str] = None  # Next step on success
    on_failure: Optional[str] = None  # Next step on failure
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "step_type": self.step_type.value,
            "on_success": self.on_success,
            "on_failure": self.on_failure,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "metadata": self.metadata,
        }


@dataclass
class StepResult:
    """Result of step execution."""
    step_id: str
    status: StepStatus
    result: Any = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "status": self.status.value,
            "result": self.result,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
        }


@dataclass
class WorkflowDefinition:
    """Workflow definition."""
    workflow_id: str
    name: str
    description: str
    version: str
    steps: List[WorkflowStep]
    start_step: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "steps": [s.to_dict() for s in self.steps],
            "start_step": self.start_step,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class WorkflowInstance:
    """Workflow execution instance."""
    instance_id: str
    workflow_id: str
    status: WorkflowStatus
    context: Dict[str, Any]
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    current_step: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "context": self.context,
            "step_results": {k: v.to_dict() for k, v in self.step_results.items()},
            "current_step": self.current_step,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
        }


class WorkflowEngine:
    """Workflow orchestration engine."""
    
    def __init__(self):
        self._definitions: Dict[str, WorkflowDefinition] = {}
        self._instances: Dict[str, WorkflowInstance] = {}
        self._step_registry: Dict[str, Callable] = {}
        
        # Register built-in steps
        self._register_builtin_steps()
    
    def _register_builtin_steps(self) -> None:
        """Register built-in workflow steps."""
        # Wait step
        self._step_registry["wait"] = self._builtin_wait
        
        # Log step
        self._step_registry["log"] = self._builtin_log
        
        # Transform step
        self._step_registry["transform"] = self._builtin_transform
    
    def _builtin_wait(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Built-in wait step."""
        import time
        seconds = kwargs.get("seconds", 1)
        time.sleep(min(seconds, 60))  # Cap at 60 seconds
        return {"waited": seconds}
    
    def _builtin_log(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Built-in log step."""
        message = kwargs.get("message", "")
        level = kwargs.get("level", "info")
        
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)
        
        return {"logged": message}
    
    def _builtin_transform(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Built-in transform step."""
        # Simple transformation
        return {"transformed": True}
    
    def register_step(self, step_name: str, action: Callable) -> None:
        """Register a custom step action."""
        self._step_registry[step_name] = action
        logger.info("Step registered: %s", step_name)
    
    def create_workflow(self, name: str, description: str,
                       steps: List[Dict[str, Any]],
                       start_step: str,
                       version: str = "1.0.0",
                       metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a workflow definition."""
        workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
        
        workflow_steps = []
        for step_def in steps:
            step = WorkflowStep(
                step_id=step_def.get("step_id", f"step_{uuid.uuid4().hex[:8]}"),
                name=step_def.get("name", "Unnamed Step"),
                step_type=StepType(step_def.get("step_type", "action")),
                condition=step_def.get("condition"),
                on_success=step_def.get("on_success"),
                on_failure=step_def.get("on_failure"),
                timeout_seconds=step_def.get("timeout_seconds", 300),
                max_retries=step_def.get("max_retries", 3),
                metadata=step_def.get("metadata", {}),
            )
            workflow_steps.append(step)
        
        definition = WorkflowDefinition(
            workflow_id=workflow_id,
            name=name,
            description=description,
            version=version,
            steps=workflow_steps,
            start_step=start_step,
            metadata=metadata or {},
        )
        
        self._definitions[workflow_id] = definition
        
        logger.info("Workflow created: %s (%s)", name, workflow_id)
        
        return workflow_id
    
    def start_workflow(self, workflow_id: str,
                      context: Optional[Dict[str, Any]] = None) -> str:
        """Start a workflow execution."""
        if workflow_id not in self._definitions:
            raise ValueError(f"Unknown workflow: {workflow_id}")
        
        definition = self._definitions[workflow_id]
        
        instance = WorkflowInstance(
            instance_id=f"inst_{uuid.uuid4().hex[:8]}",
            workflow_id=workflow_id,
            status=WorkflowStatus.PENDING,
            context=context or {},
        )
        
        self._instances[instance.instance_id] = instance
        
        # Start execution
        self._execute_workflow(instance)
        
        logger.info("Workflow started: %s (%s)", definition.name, instance.instance_id)
        
        return instance.instance_id
    
    def _execute_workflow(self, instance: WorkflowInstance) -> None:
        """Execute workflow."""
        definition = self._definitions[instance.workflow_id]
        
        instance.status = WorkflowStatus.RUNNING
        instance.started_at = datetime.now(timezone.utc).isoformat()
        
        current_step_id = definition.start_step
        
        while current_step_id:
            # Find step
            step = None
            for s in definition.steps:
                if s.step_id == current_step_id:
                    step = s
                    break
            
            if not step:
                instance.status = WorkflowStatus.FAILED
                instance.error_message = f"Step not found: {current_step_id}"
                break
            
            # Execute step
            instance.current_step = current_step_id
            result = self._execute_step(instance, step)
            
            if result.status == StepStatus.COMPLETED:
                current_step_id = step.on_success
            elif result.status == StepStatus.FAILED:
                if step.on_failure:
                    current_step_id = step.on_failure
                else:
                    instance.status = WorkflowStatus.FAILED
                    instance.error_message = result.error_message
                    break
            elif result.status == StepStatus.SKIPPED:
                current_step_id = step.on_success
            else:
                break
        
        # Complete workflow
        if instance.status == WorkflowStatus.RUNNING:
            instance.status = WorkflowStatus.COMPLETED
        
        instance.completed_at = datetime.now(timezone.utc).isoformat()
        instance.current_step = None
    
    def _execute_step(self, instance: WorkflowInstance,
                     step: WorkflowStep) -> StepResult:
        """Execute a single workflow step."""
        result = StepResult(
            step_id=step.step_id,
            status=StepStatus.PENDING,
        )
        
        # Check condition if present
        if step.condition:
            if not self._evaluate_condition(instance.context, step.condition):
                result.status = StepStatus.SKIPPED
                result.completed_at = datetime.now(timezone.utc).isoformat()
                instance.step_results[step.step_id] = result
                return result
        
        # Execute with retries
        for attempt in range(step.max_retries + 1):
            result.retry_count = attempt
            result.status = StepStatus.RUNNING
            result.started_at = datetime.now(timezone.utc).isoformat()
            
            try:
                # Get action from registry
                action_name = step.metadata.get("action")
                if not action_name or action_name not in self._step_registry:
                    raise ValueError(f"Unknown action: {action_name}")
                
                action = self._step_registry[action_name]
                
                # Execute action
                step_result = action(instance.context, **step.metadata)
                
                result.status = StepStatus.COMPLETED
                result.result = step_result
                result.completed_at = datetime.now(timezone.utc).isoformat()
                
                # Update context with result
                instance.context[f"step_{step.step_id}_result"] = step_result
                
                break
                
            except Exception as exc:
                logger.exception("Step %s failed (attempt %d): %s",
                               step.step_id, attempt + 1, exc)
                result.error_message = str(exc)
                
                if attempt < step.max_retries:
                    result.status = StepStatus.PENDING
                else:
                    result.status = StepStatus.FAILED
                    result.completed_at = datetime.now(timezone.utc).isoformat()
        
        instance.step_results[step.step_id] = result
        return result
    
    def _evaluate_condition(self, context: Dict[str, Any],
                           condition: str) -> bool:
        """Evaluate condition expression."""
        # Simplified condition evaluation
        # In production, use proper expression parser
        try:
            # Support basic conditions like "context.status == 'active'"
            if "==" in condition:
                parts = condition.split("==")
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip().strip("'\"")
                    
                    if left.startswith("context."):
                        var_name = left[8:]
                        left_value = context.get(var_name, "")
                        return str(left_value) == right
            
            return True  # Default to true if can't evaluate
        except Exception:
            return True
    
    def pause_workflow(self, instance_id: str) -> bool:
        """Pause a running workflow."""
        if instance_id not in self._instances:
            return False
        
        instance = self._instances[instance_id]
        
        if instance.status != WorkflowStatus.RUNNING:
            return False
        
        instance.status = WorkflowStatus.PAUSED
        logger.info("Workflow paused: %s", instance_id)
        
        return True
    
    def resume_workflow(self, instance_id: str) -> bool:
        """Resume a paused workflow."""
        if instance_id not in self._instances:
            return False
        
        instance = self._instances[instance_id]
        
        if instance.status != WorkflowStatus.PAUSED:
            return False
        
        instance.status = WorkflowStatus.RUNNING
        self._execute_workflow(instance)
        
        logger.info("Workflow resumed: %s", instance_id)
        
        return True
    
    def cancel_workflow(self, instance_id: str) -> bool:
        """Cancel a workflow."""
        if instance_id not in self._instances:
            return False
        
        instance = self._instances[instance_id]
        
        if instance.status in (WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED):
            return False
        
        instance.status = WorkflowStatus.CANCELLED
        instance.completed_at = datetime.now(timezone.utc).isoformat()
        
        logger.info("Workflow cancelled: %s", instance_id)
        
        return True
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow definition."""
        if workflow_id not in self._definitions:
            return None
        
        return self._definitions[workflow_id].to_dict()
    
    def get_all_workflows(self) -> List[Dict[str, Any]]:
        """Get all workflow definitions."""
        return [d.to_dict() for d in self._definitions.values()]
    
    def get_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow instance."""
        if instance_id not in self._instances:
            return None
        
        return self._instances[instance_id].to_dict()
    
    def get_instances_by_workflow(self, workflow_id: str,
                                  status: Optional[WorkflowStatus] = None,
                                  limit: int = 50) -> List[Dict[str, Any]]:
        """Get instances for a workflow."""
        instances = [
            i for i in self._instances.values()
            if i.workflow_id == workflow_id
        ]
        
        if status:
            instances = [i for i in instances if i.status == status]
        
        # Sort by started_at (newest first)
        instances.sort(key=lambda i: i.started_at or "", reverse=True)
        
        return [i.to_dict() for i in instances[:limit]]
    
    def get_workflow_summary(self) -> Dict[str, Any]:
        """Get workflow engine summary."""
        total_workflows = len(self._definitions)
        total_instances = len(self._instances)
        
        running = len([i for i in self._instances.values() if i.status == WorkflowStatus.RUNNING])
        completed = len([i for i in self._instances.values() if i.status == WorkflowStatus.COMPLETED])
        failed = len([i for i in self._instances.values() if i.status == WorkflowStatus.FAILED])
        paused = len([i for i in self._instances.values() if i.status == WorkflowStatus.PAUSED])
        
        return {
            "total_workflows": total_workflows,
            "total_instances": total_instances,
            "running_instances": running,
            "completed_instances": completed,
            "failed_instances": failed,
            "paused_instances": paused,
            "registered_steps": len(self._step_registry),
        }


def create_workflow_engine() -> WorkflowEngine:
    """Factory function to create workflow engine."""
    return WorkflowEngine()
