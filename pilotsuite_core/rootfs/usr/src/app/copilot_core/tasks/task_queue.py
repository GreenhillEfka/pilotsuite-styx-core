"""
Task Queue for PilotSuite Core.

Background job processing with priority queue and scheduled tasks.
"""
from __future__ import annotations
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional
from queue import PriorityQueue, Empty
import json

_LOGGER = logging.getLogger(__name__)


class TaskPriority(IntEnum):
    """Task priority levels (lower = higher priority)."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class TaskStatus:
    """Task status constants."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Background task."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    status: str = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


class TaskQueue:
    """Background task queue with priority support."""

    def __init__(self, max_workers: int = 4) -> None:
        """Initialize task queue."""
        self._queue: PriorityQueue = PriorityQueue()
        self._tasks: Dict[str, Task] = {}
        self._workers: List[threading.Thread] = []
        self._max_workers = max_workers
        self._running = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start worker threads."""
        if self._running:
            return
        self._running = True
        for i in range(self._max_workers):
            t = threading.Thread(target=self._worker, name=f"TaskWorker-{i}", daemon=True)
            t.start()
            self._workers.append(t)
        _LOGGER.info("Task queue started with %d workers", self._max_workers)

    def stop(self) -> None:
        """Stop worker threads."""
        self._running = False
        for t in self._workers:
            t.join(timeout=1.0)
        self._workers.clear()
        _LOGGER.info("Task queue stopped")

    def submit(
        self,
        name: str,
        func: Callable,
        args: tuple = (),
        kwargs: Dict[str, Any] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        scheduled_at: Optional[datetime] = None,
        max_retries: int = 3,
    ) -> str:
        """Submit a task to the queue."""
        task = Task(
            name=name,
            priority=priority,
            scheduled_at=scheduled_at,
            max_retries=max_retries,
        )
        kwargs = kwargs or {}
        
        with self._lock:
            self._tasks[task.id] = task
        
        self._queue.put((priority.value, task.id, func, args, kwargs))
        _LOGGER.debug("Task submitted: %s (priority=%s)", task.id, priority.name)
        return task.id

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        """List all tasks, optionally filtered by status."""
        with self._lock:
            tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                return True
        return False

    def _worker(self) -> None:
        """Worker thread main loop."""
        while self._running:
            try:
                priority, task_id, func, args, kwargs = self._queue.get(timeout=1.0)
            except Empty:
                continue

            with self._lock:
                task = self._tasks.get(task_id)
                if not task or task.status == TaskStatus.CANCELLED:
                    continue
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()

            try:
                result = func(*args, **kwargs)
                with self._lock:
                    task.result = result
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now()
                _LOGGER.debug("Task completed: %s", task_id)
            except Exception as e:
                _LOGGER.error("Task failed: %s - %s", task_id, e)
                with self._lock:
                    task.error = str(e)
                    task.retry_count += 1
                    if task.retry_count < task.max_retries:
                        task.status = TaskStatus.PENDING
                        self._queue.put((priority, task_id, func, args, kwargs))
                    else:
                        task.status = TaskStatus.FAILED
                        task.completed_at = datetime.now()
            finally:
                self._queue.task_done()


class TaskScheduler:
    """Cron-like task scheduler."""

    def __init__(self, task_queue: TaskQueue) -> None:
        """Initialize scheduler."""
        self._task_queue = task_queue
        self._scheduled_tasks: Dict[str, Dict] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def add_cron_job(
        self,
        name: str,
        func: Callable,
        minute: str = "*",
        hour: str = "*",
        day: str = "*",
        month: str = "*",
        weekday: str = "*",
        **kwargs,
    ) -> str:
        """Add a cron-like scheduled task."""
        job_id = str(uuid.uuid4())[:8]
        self._scheduled_tasks[job_id] = {
            "name": name,
            "func": func,
            "cron": {"minute": minute, "hour": hour, "day": day, "month": month, "weekday": weekday},
            "kwargs": kwargs,
        }
        _LOGGER.info("Cron job added: %s (%s)", name, job_id)
        return job_id

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job."""
        if job_id in self._scheduled_tasks:
            del self._scheduled_tasks[job_id]
            return True
        return False

    def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        _LOGGER.info("Task scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        _LOGGER.info("Task scheduler stopped")

    def _run(self) -> None:
        """Scheduler main loop."""
        while self._running:
            now = datetime.now()
            for job_id, job in list(self._scheduled_tasks.items()):
                if self._should_run(now, job["cron"]):
                    self._task_queue.submit(job["name"], job["func"], **job["kwargs"])
            time.sleep(60)  # Check every minute

    def _should_run(self, now: datetime, cron: Dict[str, str]) -> bool:
        """Check if cron expression matches current time."""
        def matches(value: str, current: int) -> bool:
            if value == "*":
                return True
            if "," in value:
                return str(current) in value.split(",")
            if "/" in value:
                step, remainder = divmod(current, int(value.split("/")[1]))
                return remainder == 0
            return str(current) == value
        return (
            matches(cron["minute"], now.minute) and
            matches(cron["hour"], now.hour) and
            matches(cron["day"], now.day) and
            matches(cron["month"], now.month) and
            matches(cron["weekday"], now.weekday())
        )


# Global instances
_task_queue: Optional[TaskQueue] = None
_task_scheduler: Optional[TaskScheduler] = None


def get_task_queue() -> TaskQueue:
    """Get global task queue."""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
        _task_queue.start()
    return _task_queue


def get_task_scheduler() -> TaskScheduler:
    """Get global task scheduler."""
    global _task_scheduler
    if _task_scheduler is None:
        _task_scheduler = TaskScheduler(get_task_queue())
        _task_scheduler.start()
    return _task_scheduler


__all__ = [
    "TaskQueue",
    "TaskScheduler",
    "Task",
    "TaskPriority",
    "TaskStatus",
    "get_task_queue",
    "get_task_scheduler",
]
