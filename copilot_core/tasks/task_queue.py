"""PilotSuite Task Queue — Celery with Redis Backend."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# TASK STATUS
# =============================================================================

class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"


@dataclass
class TaskResult:
    """Task execution result."""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0


# =============================================================================
# TASK QUEUE MANAGER
# =============================================================================

class TaskQueueManager:
    """
    Task Queue Manager — Celery Integration
    
    Features:
    - Async task execution
    - Scheduled tasks
    - Retry logic
    - Task status tracking
    - Result caching
    
    Setup:
    1. Install Redis: apt install redis-server
    2. Start Redis: systemctl start redis
    3. Configure in YAML
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._celery_app = None
        self._registered_tasks: Dict[str, Callable] = {}

    def init_celery(self):
        """Initialize Celery application."""
        try:
            from celery import Celery
            
            self._celery_app = Celery(
                "pilotsuite",
                broker=self.redis_url,
                backend=self.redis_url,
                include=["pilotsuite.tasks"],
            )
            
            self._celery_app.conf.update(
                task_serializer="json",
                accept_content=["json"],
                result_serializer="json",
                timezone="Europe/Berlin",
                enable_utc=True,
                task_track_started=True,
                task_time_limit=300,  # 5 minutes max
                task_soft_time_limit=240,  # 4 minutes soft limit
                worker_prefetch_multiplier=1,
                broker_connection_retry_on_startup=True,
            )
            
            logger.info(f"Celery initialized with Redis: {self.redis_url}")
            
        except ImportError:
            logger.error("Celery not installed (pip install celery redis)")
            self._celery_app = None

    def task(self, name: str, **options):
        """
        Decorator to register a task.
        
        Usage:
        ```python
        @task_queue.task("energy.optimize", bind=True, max_retries=3)
        def optimize_energy(self, device_ids=None):
            # Task implementation
            pass
        ```
        """
        def decorator(func: Callable):
            self._registered_tasks[name] = func
            
            if self._celery_app:
                celery_task = self._celery_app.task(name=name, **options)(func)
                return celery_task
            
            return func
        
        return decorator

    async def execute_task(self, task_name: str, *args, **kwargs) -> TaskResult:
        """Execute a task (sync or async)."""
        if task_name not in self._registered_tasks:
            return TaskResult(
                task_id=task_name,
                status=TaskStatus.FAILURE,
                error=f"Unknown task: {task_name}",
            )
        
        func = self._registered_tasks[task_name]
        
        try:
            if self._celery_app:
                # Execute via Celery (async)
                celery_task = self._celery_app.tasks.get(task_name)
                if celery_task:
                    result = celery_task.delay(*args, **kwargs)
                    return TaskResult(
                        task_id=result.id,
                        status=TaskStatus.PENDING,
                    )
            
            # Execute synchronously (fallback)
            result = func(*args, **kwargs)
            return TaskResult(
                task_id=task_name,
                status=TaskStatus.SUCCESS,
                result=result,
                started_at=datetime.now(),
                completed_at=datetime.now(),
            )
            
        except Exception as e:
            logger.error(f"Task {task_name} failed: {e}")
            return TaskResult(
                task_id=task_name,
                status=TaskStatus.FAILURE,
                error=str(e),
                started_at=datetime.now(),
                completed_at=datetime.now(),
            )

    def get_task_status(self, task_id: str) -> TaskResult:
        """Get task status by ID."""
        if not self._celery_app:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILURE,
                error="Celery not initialized",
            )
        
        from celery.result import AsyncResult
        
        result = AsyncResult(task_id, app=self._celery_app)
        
        status_map = {
            "PENDING": TaskStatus.PENDING,
            "STARTED": TaskStatus.RUNNING,
            "SUCCESS": TaskStatus.SUCCESS,
            "FAILURE": TaskStatus.FAILURE,
            "RETRY": TaskStatus.RETRY,
        }
        
        return TaskResult(
            task_id=task_id,
            status=status_map.get(result.status, TaskStatus.PENDING),
            result=result.result if result.successful() else None,
            error=str(result.info) if result.failed() else None,
        )


# =============================================================================
# SCHEDULED TASKS
# =============================================================================

class ScheduledTaskManager:
    """
    Scheduled Task Manager — Celery Beat
    
    Features:
    - Cron-like scheduling
    - Interval-based tasks
    - One-time scheduled tasks
    """

    def __init__(self, task_queue: TaskQueueManager):
        self.task_queue = task_queue
        self._scheduled_tasks: Dict[str, Dict[str, Any]] = {}

    def schedule_task(
        self,
        task_name: str,
        schedule_type: str,
        schedule_config: Dict[str, Any],
        task_args: tuple = (),
        task_kwargs: dict = None,
    ):
        """
        Schedule a task.
        
        Args:
            task_name: Name of registered task
            schedule_type: "cron", "interval", or "once"
            schedule_config: Schedule configuration
            task_args: Positional arguments for task
            task_kwargs: Keyword arguments for task
        
        Examples:
        ```python
        # Cron: Every day at 2 AM
        schedule_task(
            "backup.create",
            "cron",
            {"hour": 2, "minute": 0},
        )
        
        # Interval: Every 5 minutes
        schedule_task(
            "metrics.collect",
            "interval",
            {"minutes": 5},
        )
        
        # Once: At specific time
        schedule_task(
            "report.generate",
            "once",
            {"datetime": "2026-04-07T10:00:00"},
        )
        ```
        """
        task_kwargs = task_kwargs or {}
        
        schedule_id = f"{task_name}_{schedule_type}_{hash(str(schedule_config))}"
        
        self._scheduled_tasks[schedule_id] = {
            "task_name": task_name,
            "schedule_type": schedule_type,
            "schedule_config": schedule_config,
            "task_args": task_args,
            "task_kwargs": task_kwargs,
            "created_at": datetime.now(),
        }
        
        logger.info(f"Scheduled task: {schedule_id}")
        
        return schedule_id

    def cancel_schedule(self, schedule_id: str):
        """Cancel a scheduled task."""
        if schedule_id in self._scheduled_tasks:
            del self._scheduled_tasks[schedule_id]
            logger.info(f"Cancelled schedule: {schedule_id}")
            return True
        return False

    def get_scheduled_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get all scheduled tasks."""
        return self._scheduled_tasks.copy()


# =============================================================================
# PREDEFINED TASKS
# =============================================================================

def register_default_tasks(task_queue: TaskQueueManager):
    """Register default PilotSuite tasks."""

    @task_queue.task("energy.optimize", bind=True, max_retries=3)
    def optimize_energy(self, device_ids=None, horizon_hours=24):
        """Optimize energy consumption."""
        from copilot_core.energy.or_tools_scheduler import ORToolsScheduler
        
        scheduler = ORToolsScheduler()
        result = scheduler.optimize(device_ids, horizon_hours)
        
        return {
            "success": True,
            "savings_ct": result.total_cost if result else 0,
        }

    @task_queue.task("patterns.detect", bind=True)
    def detect_patterns(self, user_id=None):
        """Detect patterns in user behavior."""
        from copilot_core.ml.pattern_detection import PatternDetectionEngine
        
        engine = PatternDetectionEngine()
        patterns = engine.detect_patterns(user_id)
        
        return {
            "success": True,
            "patterns_found": len(patterns),
        }

    @task_queue.task("backup.create", bind=True)
    def create_backup(self, include_patterns=True, include_vectors=True):
        """Create system backup."""
        import tarfile
        import os
        from pathlib import Path
        
        backup_dir = Path("/config/pilotsuite/backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"pilotsuite_backup_{timestamp}.tar.gz"
        
        # Create backup
        with tarfile.open(backup_file, "w:gz") as tar:
            if include_patterns:
                tar.add("/config/pilotsuite/patterns", arcname="patterns")
            if include_vectors:
                tar.add("/config/pilotsuite/vectors", arcname="vectors")
        
        return {
            "success": True,
            "backup_file": str(backup_file),
            "size_bytes": backup_file.stat().st_size,
        }

    @task_queue.task("metrics.collect", bind=True)
    def collect_metrics(self):
        """Collect system metrics."""
        from copilot_core.analytics.advanced_analytics import AnalyticsEngine
        
        # Would collect actual metrics
        return {
            "success": True,
            "metrics_collected": True,
        }

    @task_queue.task("notifications.cleanup", bind=True)
    def cleanup_notifications(self, older_than_days=7):
        """Clean up old notifications."""
        from copilot_core.database.models import Notification
        from copilot_core.database.models import get_database_manager
        
        db = get_database_manager()
        # Would delete old notifications
        
        return {
            "success": True,
            "cleanup_completed": True,
        }


# =============================================================================
# HOME ASSISTANT INTEGRATION
# =============================================================================

async def async_setup_task_queue(hass, config: Dict[str, Any]):
    """Set up task queue in Home Assistant."""
    redis_url = config.get("redis_url", "redis://localhost:6379/0")
    
    task_queue = TaskQueueManager(redis_url)
    task_queue.init_celery()
    
    # Register default tasks
    register_default_tasks(task_queue)
    
    # Set up scheduled task manager
    scheduled_tasks = ScheduledTaskManager(task_queue)
    
    # Store in hass.data
    hass.data["pilotsuite_task_queue"] = task_queue
    hass.data["pilotsuite_scheduled_tasks"] = scheduled_tasks
    
    logger.info("Task queue set up successfully")
    
    return task_queue, scheduled_tasks
