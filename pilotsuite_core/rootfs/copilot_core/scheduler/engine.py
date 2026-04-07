"""Scheduler Engine — Stub for tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import uuid
import secrets


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Alias for backwards compatibility
JobStatus = TaskStatus


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ScheduleType(str, Enum):
    """Schedule types."""
    ONCE = "once"
    CRON = "cron"
    INTERVAL = "interval"
    RECURRING = "recurring"


@dataclass
class ScheduledJob:
    """A scheduled job."""
    id: str
    name: str
    description: str = ""
    schedule_type: ScheduleType = ScheduleType.ONCE
    schedule_expression: str = ""
    action_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    last_result: Any = None
    error_message: Optional[str] = None
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "schedule_type": self.schedule_type.value,
            "schedule_expression": self.schedule_expression,
            "action_name": self.action_name,
            "parameters": self.parameters,
            "status": self.status.value,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "enabled": self.enabled,
        }


@dataclass
class ScheduledTask:
    """A scheduled task."""
    id: str
    name: str
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    handler: Optional[Callable] = None
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    last_result: Any = None
    error_message: Optional[str] = None
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "cron_expression": self.cron_expression,
            "interval_seconds": self.interval_seconds,
            "priority": self.priority.value,
            "status": self.status.value,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "enabled": self.enabled,
            "error_message": self.error_message,
        }


class SchedulerEngine:
    """Task scheduling engine."""
    
    def __init__(self):
        self._jobs: Dict[str, ScheduledJob] = {}
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
    
    def create_job(
        self,
        name: str,
        description: str = "",
        schedule_type: str = "once",
        schedule_expression: str = "",
        action_name: str = "",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new scheduled job."""
        job_id = f"job_{secrets.token_hex(4)}"
        try:
            st = ScheduleType(schedule_type)
        except ValueError:
            st = ScheduleType.ONCE
        
        job = ScheduledJob(
            id=job_id,
            name=name,
            description=description,
            schedule_type=st,
            schedule_expression=schedule_expression,
            action_name=action_name,
            parameters=parameters or {},
        )
        self._jobs[job_id] = job
        return job_id
    
    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.status = TaskStatus.CANCELLED
        job.enabled = False
        return True
    
    def enable_job(self, job_id: str) -> bool:
        """Enable a job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.enabled = True
        return True
    
    def disable_job(self, job_id: str) -> bool:
        """Disable a job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.enabled = False
        return True
    
    def get_all_jobs(self) -> List[ScheduledJob]:
        """Get all scheduled jobs."""
        return list(self._jobs.values())
    
    def get_pending_jobs(self) -> List[ScheduledJob]:
        """Get pending jobs."""
        return [j for j in self._jobs.values() if j.status == TaskStatus.PENDING and j.enabled]
    
    def schedule(
        self,
        name: str,
        cron_expression: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        handler: Optional[Callable] = None,
        args: tuple = (),
        kwargs: Optional[dict] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> str:
        """Schedule a new task."""
        task_id = str(uuid.uuid4())
        task = ScheduledTask(
            id=task_id,
            name=name,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
            handler=handler,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
        )
        self._tasks[task_id] = task
        return task_id
    
    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get task by ID."""
        return self._tasks.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.status = TaskStatus.CANCELLED
        task.enabled = False
        return True
    
    def enable_task(self, task_id: str) -> bool:
        """Enable a task."""
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.enabled = True
        return True
    
    def disable_task(self, task_id: str) -> bool:
        """Disable a task."""
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.enabled = False
        return True
    
    def get_all_tasks(self) -> List[ScheduledTask]:
        """Get all scheduled tasks."""
        return list(self._tasks.values())
    
    def get_pending_tasks(self) -> List[ScheduledTask]:
        """Get pending tasks."""
        return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING and t.enabled]
    
    def start(self) -> None:
        """Start the scheduler."""
        self._running = True
    
    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running


def create_scheduler_engine() -> SchedulerEngine:
    """Factory function."""
    return SchedulerEngine()
