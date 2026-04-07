"""Scheduler Engine — Slice 31.

Time-based scheduling for PilotSuite Core.

Features:
- Cron-like scheduling
- One-time and recurring jobs
- Timezone support
- Job dependencies and chaining
- Pause/resume scheduling
- Schedule analytics
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable, Set
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ScheduleType(Enum):
    """Schedule type."""
    ONCE = "once"  # One-time execution
    CRON = "cron"  # Cron expression
    INTERVAL = "interval"  # Fixed interval
    DAILY = "daily"  # Daily at specific time
    WEEKLY = "weekly"  # Weekly on specific day
    MONTHLY = "monthly"  # Monthly on specific day


@dataclass
class ScheduledJob:
    """Scheduled job definition."""
    job_id: str
    name: str
    description: str
    schedule_type: ScheduleType
    schedule_expression: str  # Cron expression, interval seconds, or time string
    action: Optional[Callable] = None
    action_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    timezone: str = "UTC"
    enabled: bool = True
    priority: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    dependencies: List[str] = field(default_factory=list)  # Job IDs that must complete first
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0
    fail_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "description": self.description,
            "schedule_type": self.schedule_type.value,
            "schedule_expression": self.schedule_expression,
            "action_name": self.action_name,
            "parameters": self.parameters,
            "timezone": self.timezone,
            "enabled": self.enabled,
            "priority": self.priority,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "dependencies": self.dependencies,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "run_count": self.run_count,
            "fail_count": self.fail_count,
        }


@dataclass
class JobExecution:
    """Job execution record."""
    execution_id: str
    job_id: str
    status: JobStatus
    started_at: Optional[str]
    completed_at: Optional[str] = None
    result: Any = None
    error_message: Optional[str] = None
    retry_count: int = 0
    duration_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "duration_ms": self.duration_ms,
        }


class SchedulerEngine:
    """Time-based scheduler engine."""
    
    def __init__(self):
        self._jobs: Dict[str, ScheduledJob] = {}
        self._executions: Dict[str, JobExecution] = {}
        self._execution_history: List[JobExecution] = []
        self._max_history_size = 1000
        self._action_registry: Dict[str, Callable] = {}
        
        # Register built-in actions
        self._register_builtin_actions()
    
    def _register_builtin_actions(self) -> None:
        """Register built-in scheduler actions."""
        self._action_registry["log"] = self._action_log
        self._action_registry["noop"] = self._action_noop
    
    def _action_log(self, **kwargs) -> Dict[str, Any]:
        """Log action."""
        message = kwargs.get("message", "")
        logger.info("Scheduled job log: %s", message)
        return {"logged": message}
    
    def _action_noop(self, **kwargs) -> Dict[str, Any]:
        """No-op action."""
        return {"status": "noop"}
    
    def register_action(self, action_name: str, handler: Callable) -> None:
        """Register a custom action handler."""
        self._action_registry[action_name] = handler
        logger.info("Scheduler action registered: %s", action_name)
    
    def create_job(self, name: str, description: str,
                  schedule_type: str, schedule_expression: str,
                  action_name: str, parameters: Optional[Dict[str, Any]] = None,
                  timezone: str = "UTC", priority: int = 0,
                  tags: Optional[List[str]] = None,
                  dependencies: Optional[List[str]] = None,
                  max_retries: int = 3,
                  timeout_seconds: int = 300) -> str:
        """Create a scheduled job."""
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        
        job = ScheduledJob(
            job_id=job_id,
            name=name,
            description=description,
            schedule_type=ScheduleType(schedule_type),
            schedule_expression=schedule_expression,
            action_name=action_name,
            parameters=parameters or {},
            timezone=timezone,
            priority=priority,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            tags=tags or [],
            dependencies=dependencies or [],
        )
        
        # Calculate next run time
        job.next_run = self._calculate_next_run(job)
        
        self._jobs[job_id] = job
        
        logger.info("Job created: %s (%s)", name, job_id)
        
        return job_id
    
    def _calculate_next_run(self, job: ScheduledJob) -> Optional[str]:
        """Calculate next run time for a job."""
        now = datetime.now(timezone.utc)
        
        if job.schedule_type == ScheduleType.ONCE:
            # Parse ISO datetime. Past one-off jobs remain due until they are
            # processed, which lets process_due_jobs() pick them up immediately.
            try:
                next_run = datetime.fromisoformat(job.schedule_expression.replace("Z", "+00:00"))
                return next_run.isoformat()
            except ValueError:
                return None
        
        elif job.schedule_type == ScheduleType.INTERVAL:
            # Add interval seconds to now (or to last_run)
            interval_seconds = int(job.schedule_expression)
            if job.last_run:
                base = datetime.fromisoformat(job.last_run)
            else:
                base = now
            next_run = base + timedelta(seconds=interval_seconds)
            return next_run.isoformat()
        
        elif job.schedule_type == ScheduleType.DAILY:
            # Parse time string (HH:MM)
            try:
                hour, minute = map(int, job.schedule_expression.split(":"))
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                return next_run.isoformat()
            except ValueError:
                return None
        
        elif job.schedule_type == ScheduleType.WEEKLY:
            # Parse day and time (e.g., "monday 09:00")
            try:
                parts = job.schedule_expression.split()
                day_name = parts[0].lower()
                time_str = parts[1] if len(parts) > 1 else "00:00"
                hour, minute = map(int, time_str.split(":"))
                
                days = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                       "friday": 4, "saturday": 5, "sunday": 6}
                target_weekday = days.get(day_name, 0)
                
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                days_ahead = target_weekday - next_run.weekday()
                if days_ahead < 0:
                    days_ahead += 7
                elif days_ahead == 0 and next_run <= now:
                    days_ahead = 7
                
                next_run += timedelta(days=days_ahead)
                return next_run.isoformat()
            except (ValueError, IndexError):
                return None
        
        elif job.schedule_type == ScheduleType.CRON:
            # Simplified cron parsing (only basic expressions)
            # Format: minute hour day month weekday
            try:
                parts = job.schedule_expression.split()
                if len(parts) >= 2:
                    minute, hour = int(parts[0]), int(parts[1])
                    next_run = now.replace(minute=minute, hour=hour, second=0, microsecond=0)
                    if next_run <= now:
                        # Add 1 hour
                        next_run += timedelta(hours=1)
                    return next_run.isoformat()
            except (ValueError, IndexError):
                pass
            return None
        
        return None
    
    def enable_job(self, job_id: str) -> bool:
        """Enable a job."""
        if job_id not in self._jobs:
            return False
        
        self._jobs[job_id].enabled = True
        self._jobs[job_id].next_run = self._calculate_next_run(self._jobs[job_id])
        return True
    
    def disable_job(self, job_id: str) -> bool:
        """Disable a job."""
        if job_id not in self._jobs:
            return False
        
        self._jobs[job_id].enabled = False
        self._jobs[job_id].next_run = None
        return True
    
    def pause_job(self, job_id: str) -> bool:
        """Pause a job."""
        if job_id not in self._jobs:
            return False
        
        self._jobs[job_id].enabled = False
        return True
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        if job_id not in self._jobs:
            return False
        
        self._jobs[job_id].enabled = True
        self._jobs[job_id].next_run = self._calculate_next_run(self._jobs[job_id])
        return True
    
    def run_job(self, job_id: str) -> Optional[str]:
        """Manually trigger a job."""
        if job_id not in self._jobs:
            return None
        
        job = self._jobs[job_id]
        
        # Check dependencies
        for dep_id in job.dependencies:
            if dep_id in self._jobs:
                dep_job = self._jobs[dep_id]
                if dep_job.run_count == 0:
                    logger.warning("Job %s dependency %s not yet run", job_id, dep_id)
                    return None
        
        return self._execute_job(job)
    
    def process_due_jobs(self, batch_size: int = 100) -> int:
        """Process all due jobs."""
        now = datetime.now(timezone.utc)
        processed = 0
        
        # Get enabled jobs that are due
        due_jobs = []
        for job in self._jobs.values():
            if not job.enabled or not job.next_run:
                continue
            
            next_run = datetime.fromisoformat(job.next_run)
            if next_run <= now:
                due_jobs.append(job)
        
        # Sort by priority (higher first)
        due_jobs.sort(key=lambda j: j.priority, reverse=True)
        
        for job in due_jobs[:batch_size]:
            self._execute_job(job)
            processed += 1
        
        return processed
    
    def _execute_job(self, job: ScheduledJob) -> Optional[str]:
        """Execute a job."""
        import time

        start_time = time.time()
        execution_id = f"exec_{uuid.uuid4().hex[:8]}"
        execution = JobExecution(
            execution_id=execution_id,
            job_id=job.job_id,
            status=JobStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._executions[execution_id] = execution

        attempts = max(1, job.max_retries)
        last_error: Optional[Exception] = None

        for attempt in range(attempts):
            try:
                if job.action_name not in self._action_registry:
                    raise ValueError(f"Unknown action: {job.action_name}")

                action = self._action_registry[job.action_name]
                result = action(**job.parameters)

                duration_ms = int((time.time() - start_time) * 1000)
                execution.status = JobStatus.COMPLETED
                execution.result = result
                execution.completed_at = datetime.now(timezone.utc).isoformat()
                execution.duration_ms = duration_ms

                job.run_count += 1
                job.last_run = execution.completed_at
                job.next_run = self._calculate_next_run(job)
                job.fail_count = 0

                logger.info("Job %s executed successfully in %dms", job.job_id, duration_ms)
                break
            except Exception as exc:
                last_error = exc
                execution.retry_count = attempt + 1
                logger.exception("Job %s failed: %s", job.job_id, exc)

                if attempt + 1 >= attempts:
                    execution.status = JobStatus.FAILED
                    execution.error_message = str(exc)
                    execution.completed_at = datetime.now(timezone.utc).isoformat()
                    execution.duration_ms = int((time.time() - start_time) * 1000)
                    job.fail_count += 1
                    job.last_run = execution.completed_at
                    job.next_run = self._calculate_next_run(job)
                    logger.error("Job %s exhausted retries", job.job_id)
                else:
                    logger.info("Job %s retrying (%d/%d)", job.job_id, attempt + 1, attempts)
                    continue

        self._execution_history.append(execution)
        if len(self._execution_history) > self._max_history_size:
            self._execution_history = self._execution_history[-self._max_history_size:]

        return execution_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details."""
        if job_id not in self._jobs:
            return None
        
        return self._jobs[job_id].to_dict()
    
    def get_all_jobs(self, status: Optional[str] = None,
                    tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all jobs with optional filters."""
        jobs = list(self._jobs.values())
        
        if status == "enabled":
            jobs = [j for j in jobs if j.enabled]
        elif status == "disabled":
            jobs = [j for j in jobs if not j.enabled]
        
        if tags:
            jobs = [j for j in jobs if any(t in j.tags for t in tags)]
        
        # Sort by priority (higher first)
        jobs.sort(key=lambda j: j.priority, reverse=True)
        
        return [j.to_dict() for j in jobs]
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        if job_id not in self._jobs:
            return False
        
        del self._jobs[job_id]
        return True
    
    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution details."""
        if execution_id not in self._executions:
            return None
        
        return self._executions[execution_id].to_dict()
    
    def get_executions_by_job(self, job_id: str,
                             limit: int = 50) -> List[Dict[str, Any]]:
        """Get executions for a job."""
        executions = [e for e in self._execution_history if e.job_id == job_id]
        
        # Sort by started_at (newest first)
        executions.sort(key=lambda e: e.started_at or "", reverse=True)
        
        return [e.to_dict() for e in executions[:limit]]
    
    def get_scheduler_summary(self) -> Dict[str, Any]:
        """Get scheduler summary."""
        total_jobs = len(self._jobs)
        enabled_jobs = len([j for j in self._jobs.values() if j.enabled])
        disabled_jobs = len([j for j in self._jobs.values() if not j.enabled])
        
        total_runs = sum(j.run_count for j in self._jobs.values())
        total_failures = sum(j.fail_count for j in self._jobs.values())
        
        due_soon = len([j for j in self._jobs.values() 
                       if j.enabled and j.next_run and 
                       datetime.fromisoformat(j.next_run) <= datetime.now(timezone.utc) + timedelta(minutes=5)])
        
        return {
            "total_jobs": total_jobs,
            "enabled_jobs": enabled_jobs,
            "disabled_jobs": disabled_jobs,
            "total_runs": total_runs,
            "total_failures": total_failures,
            "due_soon": due_soon,
            "registered_actions": len(self._action_registry),
        }
    
    def get_upcoming_jobs(self, hours_ahead: int = 24) -> List[Dict[str, Any]]:
        """Get jobs scheduled to run in the next N hours."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours_ahead)
        
        upcoming = []
        for job in self._jobs.values():
            if not job.enabled or not job.next_run:
                continue
            
            next_run = datetime.fromisoformat(job.next_run)
            if now <= next_run <= cutoff:
                upcoming.append(job.to_dict())
        
        # Sort by next_run (earliest first)
        upcoming.sort(key=lambda j: j.get("next_run", ""))
        
        return upcoming


def create_scheduler_engine() -> SchedulerEngine:
    """Factory function to create scheduler engine."""
    return SchedulerEngine()
