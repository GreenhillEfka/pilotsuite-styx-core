"""Smart Scheduler — Cron, Task Queue, Priority Scheduling, Dependencies."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class ScheduledTask:
    """Scheduled task definition."""
    id: str
    name: str
    cron_expression: str
    handler: str
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    enabled: bool = True
    max_retries: int = 3
    timeout_seconds: int = 300
    dependencies: List[str] = field(default_factory=list)
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0
    fail_count: int = 0


@dataclass
class TaskExecution:
    """Task execution record."""
    task_id: str
    started_at: float
    completed_at: Optional[float] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0


class SmartScheduler:
    """Smart task scheduler with dependencies and priority queue."""

    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._executions: Dict[str, TaskExecution] = {}
        self._task_queue: List[ScheduledTask] = []
        self._handlers: Dict[str, Callable] = {}
        self._running_tasks: Set[str] = set()

    def register_handler(self, name: str, handler: Callable):
        """Register a task handler."""
        self._handlers[name] = handler
        logger.info(f"Task handler registered: {name}")

    def schedule_task(self, task: ScheduledTask) -> str:
        """Schedule a new task."""
        self._tasks[task.id] = task
        self._calculate_next_run(task)
        logger.info(f"Task scheduled: {task.name} ({task.cron_expression})")
        return task.id

    def _calculate_next_run(self, task: ScheduledTask):
        """Calculate next run time based on cron expression."""
        # Simplified cron parsing
        # In production, would use proper cron library
        if task.cron_expression == "@hourly":
            task.next_run = time.time() + 3600
        elif task.cron_expression == "@daily":
            task.next_run = time.time() + 86400
        elif task.cron_expression == "@minutely":
            task.next_run = time.time() + 60
        else:
            # Default: run in 1 hour
            task.next_run = time.time() + 3600

    def enqueue_task(self, task_id: str, priority: Optional[TaskPriority] = None) -> bool:
        """Enqueue a task for immediate execution."""
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        if priority:
            task.priority = priority
        
        self._task_queue.append(task)
        self._task_queue.sort(key=lambda t: t.priority.value)
        
        logger.info(f"Task enqueued: {task_id}")
        return True

    def run_due_tasks(self) -> List[TaskExecution]:
        """Run all tasks that are due."""
        executions = []
        now = time.time()
        
        for task in self._tasks.values():
            if not task.enabled:
                continue
            if task.next_run and task.next_run <= now:
                if self._can_run_task(task):
                    execution = self._execute_task(task)
                    executions.append(execution)
        
        return executions

    def _can_run_task(self, task: ScheduledTask) -> bool:
        """Check if task can run (dependencies met)."""
        for dep_id in task.dependencies:
            if dep_id not in self._executions:
                return False
            if self._executions[dep_id].status != TaskStatus.COMPLETED:
                return False
        return True

    def _execute_task(self, task: ScheduledTask) -> TaskExecution:
        """Execute a task."""
        execution = TaskExecution(
            task_id=task.id,
            started_at=time.time(),
            status=TaskStatus.RUNNING,
        )
        
        self._running_tasks.add(task.id)
        self._executions[execution.task_id] = execution
        
        try:
            handler = self._handlers.get(task.handler)
            if not handler:
                raise ValueError(f"Handler not found: {task.handler}")
            
            # Execute handler
            result = handler(*task.args, **task.kwargs)
            
            execution.status = TaskStatus.COMPLETED
            execution.result = result
            execution.completed_at = time.time()
            
            task.last_run = time.time()
            task.run_count += 1
            self._calculate_next_run(task)
            
            logger.info(f"Task completed: {task.id} in {execution.completed_at - execution.started_at:.2f}s")
            
        except Exception as e:
            execution.status = TaskStatus.FAILED
            execution.error = str(e)
            execution.completed_at = time.time()
            task.fail_count += 1
            
            # Retry logic
            if task.fail_count <= task.max_retries:
                execution.status = TaskStatus.RETRYING
                logger.warning(f"Task failed, will retry: {task.id} - {e}")
            else:
                logger.error(f"Task failed permanently: {task.id} - {e}")
        
        finally:
            self._running_tasks.discard(task.id)
        
        return execution

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        task.enabled = False
        
        # Cancel any pending execution
        self._task_queue = [t for t in self._task_queue if t.id != task_id]
        
        logger.info(f"Task cancelled: {task_id}")
        return True

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status."""
        if task_id not in self._tasks:
            return None
        
        task = self._tasks[task_id]
        last_execution = self._executions.get(task_id)
        
        return {
            "id": task.id,
            "name": task.name,
            "enabled": task.enabled,
            "cron": task.cron_expression,
            "priority": task.priority.name,
            "last_run": task.last_run,
            "next_run": task.next_run,
            "run_count": task.run_count,
            "fail_count": task.fail_count,
            "last_status": last_execution.status.value if last_execution else None,
        }

    def list_tasks(self) -> List[Dict]:
        """List all scheduled tasks."""
        return [self.get_task_status(t.id) for t in self._tasks.values()]

    def get_running_tasks(self) -> List[str]:
        """Get list of currently running tasks."""
        return list(self._running_tasks)

    def get_execution_history(self, task_id: Optional[str] = None, limit: int = 50) -> List[TaskExecution]:
        """Get task execution history."""
        executions = list(self._executions.values())
        if task_id:
            executions = [e for e in executions if e.task_id == task_id]
        return sorted(executions, key=lambda e: e.started_at, reverse=True)[:limit]

    def get_queue_status(self) -> Dict[str, Any]:
        """Get scheduler queue status."""
        return {
            "total_tasks": len(self._tasks),
            "enabled_tasks": len([t for t in self._tasks.values() if t.enabled]),
            "running_tasks": len(self._running_tasks),
            "queued_tasks": len(self._task_queue),
            "total_executions": len(self._executions),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        return {
            "total_tasks": len(self._tasks),
            "total_executions": len(self._executions),
            "successful": len([e for e in self._executions.values() if e.status == TaskStatus.COMPLETED]),
            "failed": len([e for e in self._executions.values() if e.status == TaskStatus.FAILED]),
            "running": len(self._running_tasks),
        }


# Global default scheduler
default_scheduler: Optional[SmartScheduler] = None


def init_scheduler() -> SmartScheduler:
    """Initialize global scheduler."""
    global default_scheduler
    default_scheduler = SmartScheduler()
    return default_scheduler
