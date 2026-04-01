"""Scheduler Advanced Engine — Slice 55.

Advanced scheduling for PilotSuite Core.

Features:
- Cron-based scheduling
- Interval-based scheduling
- One-time scheduling
- Job dependencies
- Job groups
- Schedule persistence
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable, Set
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    """Schedule types."""
    CRON = "cron"
    INTERVAL = "interval"
    ONCE = "once"


class JobStatus(Enum):
    """Job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass
class CronExpression:
    """Parsed cron expression."""
    minute: Set[int]  # 0-59
    hour: Set[int]  # 0-23
    day: Set[int]  # 1-31
    month: Set[int]  # 1-12
    weekday: Set[int]  # 0-6 (Cron style: Sunday=0, Monday=1)
    
    @classmethod
    def parse(cls, expr: str) -> "CronExpression":
        """Parse cron expression."""
        parts = expr.split()
        
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {expr}")
        
        return cls(
            minute=cls._parse_field(parts[0], 0, 59),
            hour=cls._parse_field(parts[1], 0, 23),
            day=cls._parse_field(parts[2], 1, 31),
            month=cls._parse_field(parts[3], 1, 12),
            weekday=cls._parse_field(parts[4], 0, 6),
        )
    
    @staticmethod
    def _parse_field(field: str, min_val: int, max_val: int) -> Set[int]:
        """Parse cron field."""
        if field == "*":
            return set(range(min_val, max_val + 1))
        
        values = set()
        
        for part in field.split(","):
            if "-" in part:
                start, end = map(int, part.split("-"))
                values.update(range(start, end + 1))
            elif "/" in part:
                base, step = part.split("/")
                if base == "*":
                    start = min_val
                else:
                    start = int(base)
                values.update(range(start, max_val + 1, int(step)))
            else:
                values.add(int(part))
        
        return values
    
    def matches(self, dt: datetime) -> bool:
        """Check if datetime matches cron expression.

        Cron semantics treat day-of-month and day-of-week as an OR when both are
        explicitly restricted. When either field is a wildcard, the other field
        must match normally.
        """
        minute_match = dt.minute in self.minute
        hour_match = dt.hour in self.hour
        month_match = dt.month in self.month
        day_match = dt.day in self.day
        cron_weekday = (dt.weekday() + 1) % 7
        weekday_match = cron_weekday in self.weekday

        full_day = set(range(1, 32))
        full_weekday = set(range(0, 7))
        if self.day != full_day and self.weekday != full_weekday:
            day_component_match = day_match or weekday_match
        else:
            day_component_match = day_match and weekday_match

        return minute_match and hour_match and month_match and day_component_match
    
    def next_run(self, after: datetime) -> datetime:
        """Calculate next run time after given datetime."""
        # Simple implementation - check minute by minute
        current = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
        
        # Search for next match (max 1 year)
        max_iterations = 366 * 24 * 60
        
        for _ in range(max_iterations):
            if self.matches(current):
                return current
            current += timedelta(minutes=1)
        
        raise ValueError("Could not find next run time within 1 year")


@dataclass
class ScheduledJob:
    """Scheduled job."""
    job_id: str
    name: str
    handler: Callable[[Dict[str, Any]], Any]
    schedule_type: ScheduleType
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    run_at: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    group: Optional[str] = None
    max_runs: Optional[int] = None
    runs_completed: int = 0
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "cron_expression": self.cron_expression,
            "interval_seconds": self.interval_seconds,
            "run_at": self.run_at,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "group": self.group,
            "max_runs": self.max_runs,
            "runs_completed": self.runs_completed,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class SchedulerEngine:
    """Advanced scheduler engine."""
    
    def __init__(self):
        self._jobs: Dict[str, ScheduledJob] = {}
        self._job_history: Dict[str, List[Dict[str, Any]]] = {}
        self._running: Set[str] = set()
        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            "total_jobs": 0,
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "skipped_runs": 0,
            "by_job": {},
            "by_group": {},
        }
    
    def start(self) -> None:
        """Start scheduler."""
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        logger.info("Scheduler started")
    
    def stop(self) -> None:
        """Stop scheduler."""
        self._stop_event.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        logger.info("Scheduler stopped")
    
    def schedule_cron(self, name: str, handler: Callable[[Dict[str, Any]], Any],
                     cron_expression: str, args: Optional[Dict[str, Any]] = None,
                     group: Optional[str] = None,
                     max_runs: Optional[int] = None,
                     dependencies: Optional[List[str]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """Schedule a cron-based job."""
        job_id = f"job_{uuid.uuid4().hex[:16]}"
        
        # Parse cron to validate
        cron = CronExpression.parse(cron_expression)
        
        now = datetime.now(timezone.utc)
        next_run = cron.next_run(now)
        
        job = ScheduledJob(
            job_id=job_id,
            name=name,
            handler=handler,
            schedule_type=ScheduleType.CRON,
            cron_expression=cron_expression,
            args=args or {},
            group=group,
            max_runs=max_runs,
            dependencies=dependencies or [],
            next_run_at=next_run.isoformat(),
            metadata=metadata or {},
        )
        
        with self._lock:
            self._jobs[job_id] = job
            self._job_history[job_id] = []
            self._stats["total_jobs"] += 1
            if group:
                self._stats["by_group"].setdefault(group, 0)
        
        logger.info("Cron job scheduled: %s (%s)", name, cron_expression)
        
        return job_id
    
    def schedule_interval(self, name: str, handler: Callable[[Dict[str, Any]], Any],
                         interval_seconds: int, args: Optional[Dict[str, Any]] = None,
                         group: Optional[str] = None,
                         max_runs: Optional[int] = None,
                         dependencies: Optional[List[str]] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """Schedule an interval-based job."""
        job_id = f"job_{uuid.uuid4().hex[:16]}"
        
        now = datetime.now(timezone.utc)
        next_run = now + timedelta(seconds=interval_seconds)
        
        job = ScheduledJob(
            job_id=job_id,
            name=name,
            handler=handler,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=interval_seconds,
            args=args or {},
            group=group,
            max_runs=max_runs,
            dependencies=dependencies or [],
            next_run_at=next_run.isoformat(),
            metadata=metadata or {},
        )
        
        with self._lock:
            self._jobs[job_id] = job
            self._job_history[job_id] = []
            self._stats["total_jobs"] += 1
            if group:
                self._stats["by_group"].setdefault(group, 0)
        
        logger.info("Interval job scheduled: %s (%ds)", name, interval_seconds)
        
        return job_id
    
    def schedule_once(self, name: str, handler: Callable[[Dict[str, Any]], Any],
                     run_at: datetime, args: Optional[Dict[str, Any]] = None,
                     group: Optional[str] = None,
                     dependencies: Optional[List[str]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """Schedule a one-time job."""
        job_id = f"job_{uuid.uuid4().hex[:16]}"
        
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
        
        job = ScheduledJob(
            job_id=job_id,
            name=name,
            handler=handler,
            schedule_type=ScheduleType.ONCE,
            run_at=run_at.isoformat(),
            args=args or {},
            group=group,
            dependencies=dependencies or [],
            next_run_at=run_at.isoformat(),
            metadata=metadata or {},
        )
        
        with self._lock:
            self._jobs[job_id] = job
            self._job_history[job_id] = []
            self._stats["total_jobs"] += 1
            if group:
                self._stats["by_group"].setdefault(group, 0)
        
        logger.info("One-time job scheduled: %s (%s)", name, run_at)
        
        return job_id
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a scheduled job."""
        with self._lock:
            job = self._jobs.get(job_id)
            
            if not job:
                return False
            
            job.status = JobStatus.CANCELLED
            job.next_run_at = None
        
        logger.info("Job cancelled: %s", job_id)
        
        return True
    
    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job."""
        with self._lock:
            job = self._jobs.get(job_id)
            
            if not job:
                return False
            
            # Store next_run_at in metadata and clear it
            if job.next_run_at:
                job.metadata["_paused_next_run"] = job.next_run_at
            job.next_run_at = None
        
        return True
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        with self._lock:
            job = self._jobs.get(job_id)
            
            if not job:
                return False
            
            # Restore next_run_at from metadata
            if "_paused_next_run" in job.metadata:
                job.next_run_at = job.metadata["_paused_next_run"]
                del job.metadata["_paused_next_run"]
        
        return True
    
    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    def list_jobs(self, group: Optional[str] = None,
                 status: Optional[JobStatus] = None) -> List[ScheduledJob]:
        """List jobs with filters."""
        with self._lock:
            jobs = list(self._jobs.values())
            
            if group:
                jobs = [j for j in jobs if j.group == group]
            
            if status:
                jobs = [j for j in jobs if j.status == status]
            
            return jobs
    
    def get_job_history(self, job_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get job execution history."""
        with self._lock:
            history = self._job_history.get(job_id, [])
            return history[-limit:]
    
    def trigger_job(self, job_id: str) -> bool:
        """Manually trigger a job."""
        with self._lock:
            job = self._jobs.get(job_id)
            
            if not job:
                return False
            
            if job.status == JobStatus.RUNNING:
                return False
        
        # Run immediately in background
        thread = threading.Thread(target=self._run_job, args=(job_id,))
        thread.daemon = True
        thread.start()
        
        return True
    
    def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while not self._stop_event.is_set():
            try:
                self._check_and_run_jobs()
            except Exception as e:
                logger.exception("Scheduler error: %s", e)
            
            time.sleep(1)  # Check every second
    
    def _check_and_run_jobs(self) -> None:
        """Check and run due jobs."""
        now = datetime.now(timezone.utc)
        
        with self._lock:
            for job_id, job in list(self._jobs.items()):
                # Skip cancelled jobs
                if job.status == JobStatus.CANCELLED:
                    continue
                
                # Skip paused jobs
                if job.next_run_at is None:
                    continue
                
                # Skip running jobs
                if job_id in self._running:
                    continue
                
                # Check if due
                next_run = datetime.fromisoformat(job.next_run_at.replace('Z', '+00:00'))
                
                if now >= next_run:
                    # Check dependencies
                    if not self._dependencies_satisfied(job):
                        job.status = JobStatus.SKIPPED
                        self._stats["skipped_runs"] += 1
                        self._update_next_run(job, now)
                        continue
                    
                    # Run job
                    self._running.add(job_id)
                    thread = threading.Thread(target=self._run_job, args=(job_id,))
                    thread.daemon = True
                    thread.start()
    
    def _dependencies_satisfied(self, job: ScheduledJob) -> bool:
        """Check if job dependencies are satisfied."""
        if not job.dependencies:
            return True
        
        for dep_id in job.dependencies:
            dep_job = self._jobs.get(dep_id)
            
            if not dep_job:
                return False
            
            if dep_job.status != JobStatus.COMPLETED:
                return False
        
        return True
    
    def _run_job(self, job_id: str) -> None:
        """Run a job."""
        job = self._jobs.get(job_id)
        
        if not job:
            return
        
        try:
            job.status = JobStatus.RUNNING
            job.last_run_at = datetime.now(timezone.utc).isoformat()
            
            # Execute handler
            result = job.handler(job.args)
            
            job.status = JobStatus.COMPLETED
            job.runs_completed += 1
            
            self._stats["successful_runs"] += 1
            self._stats["total_runs"] += 1
            
            if job.group:
                self._stats["by_group"][job.group] = self._stats["by_group"].get(job.group, 0) + 1
            
            self._stats["by_job"][job.name] = self._stats["by_job"].get(job.name, 0) + 1
            
            # Record history
            with self._lock:
                self._job_history[job_id].append({
                    "run_at": job.last_run_at,
                    "status": "completed",
                    "result": result,
                })
            
            logger.debug("Job completed: %s", job_id)
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.runs_completed += 1
            
            self._stats["failed_runs"] += 1
            self._stats["total_runs"] += 1
            
            # Record history
            with self._lock:
                self._job_history[job_id].append({
                    "run_at": job.last_run_at,
                    "status": "failed",
                    "error": str(e),
                })
            
            logger.error("Job failed: %s - %s", job_id, e)
        
        finally:
            with self._lock:
                self._running.discard(job_id)
                
                # Update next run time
                if job.status != JobStatus.CANCELLED:
                    self._update_next_run(job, datetime.now(timezone.utc))
    
    def _update_next_run(self, job: ScheduledJob, now: datetime) -> None:
        """Update job's next run time."""
        # Check max runs
        if job.max_runs and job.runs_completed >= job.max_runs:
            if job.status not in {JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.SKIPPED}:
                job.status = JobStatus.COMPLETED
            job.next_run_at = None
            return
        
        if job.schedule_type == ScheduleType.CRON:
            cron = CronExpression.parse(job.cron_expression)
            job.next_run_at = cron.next_run(now).isoformat()
        
        elif job.schedule_type == ScheduleType.INTERVAL:
            anchor = now
            if job.next_run_at:
                anchor = datetime.fromisoformat(job.next_run_at.replace('Z', '+00:00'))
            elif job.last_run_at:
                anchor = datetime.fromisoformat(job.last_run_at.replace('Z', '+00:00'))
            
            next_run = anchor + timedelta(seconds=job.interval_seconds)
            while next_run <= now:
                next_run += timedelta(seconds=job.interval_seconds)
            
            job.next_run_at = next_run.isoformat()
        
        elif job.schedule_type == ScheduleType.ONCE:
            job.next_run_at = None
            job.status = JobStatus.COMPLETED
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        with self._lock:
            pending = len([j for j in self._jobs.values() if j.status == JobStatus.PENDING])
            running = len(self._running)
            completed = len([j for j in self._jobs.values() if j.status == JobStatus.COMPLETED])
            
            return {
                **self._stats,
                "total_jobs": len(self._jobs),
                "pending_jobs": pending,
                "running_jobs": running,
                "completed_jobs": completed,
            }
    
    def get_group_stats(self, group: str) -> Dict[str, Any]:
        """Get statistics for a job group."""
        with self._lock:
            jobs = [j for j in self._jobs.values() if j.group == group]
            
            return {
                "group": group,
                "total_jobs": len(jobs),
                "pending": len([j for j in jobs if j.status == JobStatus.PENDING]),
                "running": len([j for j in jobs if j.job_id in self._running]),
                "completed": len([j for j in jobs if j.status == JobStatus.COMPLETED]),
                "failed": len([j for j in jobs if j.status == JobStatus.FAILED]),
                "total_runs": sum(j.runs_completed for j in jobs),
            }


def create_scheduler_engine() -> SchedulerEngine:
    """Factory function to create scheduler engine."""
    return SchedulerEngine()
