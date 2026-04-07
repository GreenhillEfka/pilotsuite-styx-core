"""Worker Engine — Slice 51.

Background worker for PilotSuite Core.

Features:
- Worker pool management
- Job execution with retries
- Job scheduling and prioritization
- Worker health monitoring
- Job result caching
- Graceful shutdown
"""
from __future__ import annotations

import logging
import threading
import queue
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable, Tuple
from enum import Enum
import uuid
import traceback

logger = logging.getLogger(__name__)


class WorkerStatus(Enum):
    """Worker status."""
    IDLE = "idle"
    BUSY = "busy"
    STOPPING = "stopping"
    STOPPED = "stopped"


class JobStatus(Enum):
    """Job status."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobPriority(Enum):
    """Job priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Job:
    """Background job."""
    job_id: str
    name: str
    handler: Callable[[Dict[str, Any]], Any]
    args: Dict[str, Any]
    priority: JobPriority = JobPriority.NORMAL
    max_retries: int = 3
    timeout_seconds: int = 300
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    result: Any = None
    error: Optional[str] = None
    worker_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "priority": self.priority.value,
            "status": self.status.value,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "worker_id": self.worker_id,
            "metadata": self.metadata,
        }


@dataclass
class Worker:
    """Worker instance."""
    worker_id: str
    status: WorkerStatus = WorkerStatus.IDLE
    current_job: Optional[str] = None
    jobs_completed: int = 0
    jobs_failed: int = 0
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_heartbeat: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "status": self.status.value,
            "current_job": self.current_job,
            "jobs_completed": self.jobs_completed,
            "jobs_failed": self.jobs_failed,
            "started_at": self.started_at,
            "last_heartbeat": self.last_heartbeat,
        }


class WorkerEngine:
    """Background worker engine."""
    
    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers
        self._workers: Dict[str, Worker] = {}
        self._job_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._jobs: Dict[str, Job] = {}
        self._results: Dict[str, Any] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            "total_jobs_submitted": 0,
            "total_jobs_completed": 0,
            "total_jobs_failed": 0,
            "total_jobs_retried": 0,
            "total_jobs_cancelled": 0,
            "by_job_name": {},
            "by_priority": {},
        }
    
    def start(self) -> None:
        """Start worker pool."""
        logger.info("Starting worker pool with %d workers", self._max_workers)
        
        for i in range(self._max_workers):
            self._create_worker()
    
    def stop(self, timeout_seconds: int = 30) -> None:
        """Stop all workers gracefully."""
        logger.info("Stopping worker pool...")
        
        self._stop_event.set()
        
        # Signal all workers to stop
        for worker_id in list(self._workers.keys()):
            self._workers[worker_id].status = WorkerStatus.STOPPING
        
        # Wait for threads to finish
        for worker_id, thread in self._threads.items():
            thread.join(timeout=timeout_seconds / len(self._threads) if self._threads else 1)
        
        # Update worker status
        for worker in self._workers.values():
            worker.status = WorkerStatus.STOPPED
        
        logger.info("Worker pool stopped")
    
    def submit(self, name: str, handler: Callable[[Dict[str, Any]], Any],
               args: Optional[Dict[str, Any]] = None,
               priority: JobPriority = JobPriority.NORMAL,
               max_retries: int = 3,
               timeout_seconds: int = 300,
               metadata: Optional[Dict[str, Any]] = None) -> str:
        """Submit a job for background execution."""
        job_id = f"job_{uuid.uuid4().hex[:16]}"
        
        job = Job(
            job_id=job_id,
            name=name,
            handler=handler,
            args=args or {},
            priority=priority,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            metadata=metadata or {},
        )
        
        with self._lock:
            self._jobs[job_id] = job
            job.status = JobStatus.QUEUED
            
            # Priority queue: lower number = higher priority (negate for max-heap behavior)
            priority_value = -job.priority.value
            timestamp = datetime.now(timezone.utc).timestamp()
            self._job_queue.put((priority_value, timestamp, job_id))
            
            self._stats["total_jobs_submitted"] += 1
            self._stats["by_job_name"][name] = self._stats["by_job_name"].get(name, 0) + 1
            self._stats["by_priority"][job.priority.name] = self._stats["by_priority"].get(job.priority.name, 0) + 1
        
        logger.debug("Job submitted: %s (%s)", job_id, name)
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """Get job status."""
        job = self._jobs.get(job_id)
        return job.status if job else None
    
    def get_job_result(self, job_id: str, timeout_seconds: int = 0) -> Tuple[bool, Any]:
        """Get job result, optionally waiting for completion."""
        job = self._jobs.get(job_id)
        
        if not job:
            return False, None
        
        if timeout_seconds > 0:
            start = time.time()
            while job.status in (JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.RETRYING):
                if time.time() - start > timeout_seconds:
                    return False, None
                time.sleep(0.1)
                job = self._jobs.get(job_id)
        
        if job.status == JobStatus.COMPLETED:
            return True, job.result
        
        if job.status == JobStatus.FAILED:
            return False, job.error
        
        return False, None
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or queued job."""
        with self._lock:
            job = self._jobs.get(job_id)
            
            if not job:
                return False
            
            if job.status not in (JobStatus.PENDING, JobStatus.QUEUED):
                return False
            
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now(timezone.utc).isoformat()
            
            self._stats["total_jobs_cancelled"] += 1
        
        logger.info("Job cancelled: %s", job_id)
        
        return True
    
    def get_worker(self, worker_id: str) -> Optional[Worker]:
        """Get worker by ID."""
        return self._workers.get(worker_id)
    
    def get_all_workers(self) -> List[Worker]:
        """Get all workers."""
        return list(self._workers.values())
    
    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self._job_queue.qsize()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get worker statistics."""
        active_workers = len([w for w in self._workers.values() if w.status == WorkerStatus.BUSY])
        idle_workers = len([w for w in self._workers.values() if w.status == WorkerStatus.IDLE])
        
        return {
            **self._stats,
            "total_workers": len(self._workers),
            "active_workers": active_workers,
            "idle_workers": idle_workers,
            "queue_size": self.get_queue_size(),
            "pending_jobs": len([j for j in self._jobs.values() if j.status in (JobStatus.PENDING, JobStatus.QUEUED)]),
            "running_jobs": len([j for j in self._jobs.values() if j.status == JobStatus.RUNNING]),
        }
    
    def _create_worker(self) -> str:
        """Create a new worker."""
        worker_id = f"worker_{uuid.uuid4().hex[:8]}"
        
        worker = Worker(worker_id=worker_id)
        
        with self._lock:
            self._workers[worker_id] = worker
            
            thread = threading.Thread(target=self._worker_loop, args=(worker_id,), daemon=True)
            self._threads[worker_id] = thread
            thread.start()
        
        logger.debug("Worker created: %s", worker_id)
        
        return worker_id
    
    def _worker_loop(self, worker_id: str) -> None:
        """Main worker loop."""
        worker = self._workers[worker_id]
        
        while not self._stop_event.is_set():
            try:
                # Try to get a job
                try:
                    _, _, job_id = self._job_queue.get(timeout=1.0)
                except queue.Empty:
                    worker.last_heartbeat = datetime.now(timezone.utc).isoformat()
                    continue
                
                # Get and execute job
                job = self._jobs.get(job_id)
                if not job:
                    continue
                
                worker.status = WorkerStatus.BUSY
                worker.current_job = job_id
                worker.last_heartbeat = datetime.now(timezone.utc).isoformat()
                
                self._execute_job(job, worker)
                
                self._job_queue.task_done()
                
            except Exception as e:
                logger.exception("Worker error: %s", e)
                worker.last_heartbeat = datetime.now(timezone.utc).isoformat()
        
        worker.status = WorkerStatus.STOPPED
    
    def _execute_job(self, job: Job, worker: Worker) -> None:
        """Execute a job with error handling and retries."""
        job.started_at = datetime.now(timezone.utc).isoformat()
        job.status = JobStatus.RUNNING
        job.worker_id = worker.worker_id
        job.attempts += 1
        
        logger.debug("Executing job: %s (attempt %d/%d)", job.job_id, job.attempts, job.max_retries)
        
        try:
            # Execute handler with timeout
            result = self._execute_with_timeout(job)
            
            job.status = JobStatus.COMPLETED
            job.result = result
            job.completed_at = datetime.now(timezone.utc).isoformat()
            
            worker.jobs_completed += 1
            self._stats["total_jobs_completed"] += 1
            
            logger.debug("Job completed: %s", job.job_id)
            
        except TimeoutError as e:
            self._handle_job_failure(job, worker, f"Timeout: {str(e)}")
            
        except Exception as e:
            self._handle_job_failure(job, worker, f"{type(e).__name__}: {str(e)}")
        
        finally:
            worker.current_job = None
            worker.status = WorkerStatus.IDLE
            worker.last_heartbeat = datetime.now(timezone.utc).isoformat()
    
    def _execute_with_timeout(self, job: Job) -> Any:
        """Execute job handler with timeout."""
        result_container = {"result": None, "error": None}
        
        def run_handler():
            try:
                result_container["result"] = job.handler(job.args)
            except Exception as e:
                result_container["error"] = e
        
        thread = threading.Thread(target=run_handler)
        thread.start()
        thread.join(timeout=job.timeout_seconds)
        
        if thread.is_alive():
            raise TimeoutError(f"Job timed out after {job.timeout_seconds}s")
        
        if result_container["error"]:
            raise result_container["error"]
        
        return result_container["result"]
    
    def _handle_job_failure(self, job: Job, worker: Worker, error: str) -> None:
        """Handle job failure with retry logic."""
        job.error = error
        worker.jobs_failed += 1
        
        if job.attempts < job.max_retries:
            # Schedule retry
            job.status = JobStatus.RETRYING
            self._stats["total_jobs_retried"] += 1
            
            # Re-queue with backoff
            backoff_seconds = min(1, 2 ** max(job.attempts - 1, 0))
            job.started_at = None
            
            logger.warning("Job %s failed, retrying in %ds: %s", job.job_id, backoff_seconds, error)
            
            # Schedule retry
            retry_thread = threading.Thread(target=self._retry_job, args=(job, backoff_seconds))
            retry_thread.daemon = True
            retry_thread.start()
        else:
            # Max retries exceeded
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc).isoformat()
            self._stats["total_jobs_failed"] += 1
            
            logger.error("Job %s failed permanently after %d attempts: %s", job.job_id, job.attempts, error)
    
    def _retry_job(self, job: Job, delay_seconds: int) -> None:
        """Retry a job after delay."""
        time.sleep(delay_seconds)
        
        if self._stop_event.is_set():
            return
        
        with self._lock:
            job.status = JobStatus.QUEUED
            
            priority_value = -job.priority.value
            timestamp = datetime.now(timezone.utc).timestamp()
            self._job_queue.put((priority_value, timestamp, job.job_id))


def create_worker_engine(max_workers: int = 4) -> WorkerEngine:
    """Factory function to create worker engine."""
    return WorkerEngine(max_workers=max_workers)
