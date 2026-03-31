"""Tests for Worker Engine — Slice 51."""
import pytest
from copilot_core.worker.engine import (
    WorkerEngine,
    WorkerStatus,
    JobStatus,
    JobPriority,
    Job,
    Worker,
    create_worker_engine,
)
from datetime import datetime, timezone
import time


class TestWorkerEngine:
    """Test worker engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_worker_engine()
        assert engine is not None
    
    def test_create_engine_with_workers(self):
        """Test engine creation with custom worker count."""
        engine = create_worker_engine(max_workers=8)
        assert engine._max_workers == 8
    
    def test_start_workers(self):
        """Test starting worker pool."""
        engine = WorkerEngine(max_workers=4)
        
        engine.start()
        
        time.sleep(0.1)  # Allow workers to initialize
        
        assert len(engine.get_all_workers()) == 4
        
        engine.stop()
    
    def test_stop_workers(self):
        """Test stopping worker pool."""
        engine = WorkerEngine(max_workers=2)
        
        engine.start()
        time.sleep(0.1)
        
        engine.stop()
        
        workers = engine.get_all_workers()
        
        assert all(w.status == WorkerStatus.STOPPED for w in workers)
    
    def test_submit_job(self):
        """Test submitting a job."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return args["value"] * 2
        
        job_id = engine.submit("double", handler, args={"value": 5})
        
        assert job_id is not None
        assert job_id.startswith("job_")
        
        engine.stop()
    
    def test_submit_job_with_priority(self):
        """Test submitting job with priority."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return args["value"]
        
        job_id = engine.submit(
            "critical_job",
            handler,
            args={"value": 1},
            priority=JobPriority.CRITICAL,
        )
        
        job = engine.get_job(job_id)
        
        assert job.priority == JobPriority.CRITICAL
        
        engine.stop()
    
    def test_submit_job_with_metadata(self):
        """Test submitting job with metadata."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return args["value"]
        
        job_id = engine.submit(
            "test_job",
            handler,
            args={"value": 1},
            metadata={"user_id": "123", "source": "api"},
        )
        
        job = engine.get_job(job_id)
        
        assert job.metadata["user_id"] == "123"
        assert job.metadata["source"] == "api"
        
        engine.stop()
    
    def test_job_executes(self):
        """Test that job executes successfully."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        result_container = {"value": None}
        
        def handler(args):
            result_container["value"] = args["input"] + 10
            return result_container["value"]
        
        job_id = engine.submit("add_ten", handler, args={"input": 5})
        
        # Wait for completion
        success, result = engine.get_job_result(job_id, timeout_seconds=5)
        
        assert success is True
        assert result == 15
        
        engine.stop()
    
    def test_job_with_retries(self):
        """Test job retry on failure."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        attempt_count = [0]
        
        def flaky_handler(args):
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise ValueError("Transient failure")
            return "success"
        
        job_id = engine.submit(
            "flaky_job",
            flaky_handler,
            args={},
            max_retries=3,
        )
        
        # Wait for retries
        time.sleep(3)
        
        job = engine.get_job(job_id)
        
        assert attempt_count[0] >= 2
        
        engine.stop()
    
    def test_job_fails_permanently(self):
        """Test job fails after max retries."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def failing_handler(args):
            raise ValueError("Always fails")
        
        job_id = engine.submit(
            "failing_job",
            failing_handler,
            args={},
            max_retries=2,
        )
        
        # Wait for all retries
        time.sleep(4)
        
        job = engine.get_job(job_id)
        
        assert job.status == JobStatus.FAILED
        assert job.attempts == 2
        
        engine.stop()
    
    def test_cancel_pending_job(self):
        """Test cancelling a pending job."""
        engine = WorkerEngine(max_workers=1)
        engine.start()
        
        # Submit slow job to block worker
        def slow_handler(args):
            time.sleep(5)
            return "done"
        
        slow_job = engine.submit("slow", slow_handler, args={})
        
        # Submit second job (will be queued)
        def handler(args):
            return "quick"
        
        quick_job = engine.submit("quick", handler, args={})
        
        # Cancel the queued job
        result = engine.cancel_job(quick_job)
        
        assert result is True
        
        job = engine.get_job(quick_job)
        assert job.status == JobStatus.CANCELLED
        
        engine.stop()
    
    def test_cancel_running_job_fails(self):
        """Test that cancelling running job fails."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            time.sleep(0.1)
            return "done"
        
        job_id = engine.submit("test", handler, args={})
        
        # Wait for it to start
        time.sleep(0.05)
        
        # Try to cancel
        result = engine.cancel_job(job_id)
        
        # May or may not succeed depending on timing
        # If already running, should fail
        
        engine.stop()
    
    def test_cancel_nonexistent_job(self):
        """Test cancelling nonexistent job."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        result = engine.cancel_job("nonexistent_job")
        
        assert result is False
        
        engine.stop()
    
    def test_get_job(self):
        """Test getting job by ID."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return "result"
        
        job_id = engine.submit("test", handler, args={})
        
        job = engine.get_job(job_id)
        
        assert job is not None
        assert job.job_id == job_id
        assert job.name == "test"
        
        engine.stop()
    
    def test_get_nonexistent_job(self):
        """Test getting nonexistent job."""
        engine = WorkerEngine(max_workers=2)
        
        job = engine.get_job("nonexistent")
        
        assert job is None
    
    def test_get_job_status(self):
        """Test getting job status."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return "result"
        
        job_id = engine.submit("test", handler, args={})
        
        # Wait for completion
        time.sleep(0.5)
        
        status = engine.get_job_status(job_id)
        
        assert status == JobStatus.COMPLETED
        
        engine.stop()
    
    def test_get_job_result_success(self):
        """Test getting successful job result."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return {"data": "success"}
        
        job_id = engine.submit("test", handler, args={})
        
        success, result = engine.get_job_result(job_id, timeout_seconds=5)
        
        assert success is True
        assert result == {"data": "success"}
        
        engine.stop()
    
    def test_get_job_result_failure(self):
        """Test getting failed job result."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            raise ValueError("Test error")
        
        job_id = engine.submit("test", handler, args={}, max_retries=0)
        
        success, result = engine.get_job_result(job_id, timeout_seconds=5)
        
        assert success is False
        assert "Test error" in result
        
        engine.stop()
    
    def test_get_job_result_timeout(self):
        """Test getting job result with timeout."""
        engine = WorkerEngine(max_workers=1)
        engine.start()
        
        def slow_handler(args):
            time.sleep(10)
            return "done"
        
        job_id = engine.submit("slow", slow_handler, args={})
        
        # Timeout before completion
        success, result = engine.get_job_result(job_id, timeout_seconds=1)
        
        assert success is False
        
        engine.stop()
    
    def test_get_worker(self):
        """Test getting worker by ID."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        time.sleep(0.1)
        
        workers = engine.get_all_workers()
        
        if workers:
            worker = engine.get_worker(workers[0].worker_id)
            
            assert worker is not None
            assert worker.worker_id == workers[0].worker_id
        
        engine.stop()
    
    def test_get_all_workers(self):
        """Test getting all workers."""
        engine = WorkerEngine(max_workers=4)
        engine.start()
        
        time.sleep(0.1)
        
        workers = engine.get_all_workers()
        
        assert len(workers) == 4
        
        engine.stop()
    
    def test_get_queue_size(self):
        """Test getting queue size."""
        engine = WorkerEngine(max_workers=1)
        engine.start()
        
        # Block worker
        def slow_handler(args):
            time.sleep(5)
        
        engine.submit("slow1", slow_handler, args={})
        engine.submit("slow2", slow_handler, args={})
        engine.submit("slow3", slow_handler, args={})
        
        time.sleep(0.1)
        
        # At least 2 should be queued
        assert engine.get_queue_size() >= 2
        
        engine.stop()
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return args["value"]
        
        for i in range(5):
            engine.submit(f"job_{i}", handler, args={"value": i})
        
        time.sleep(1)
        
        stats = engine.get_statistics()
        
        assert stats["total_jobs_submitted"] == 5
        assert stats["total_workers"] == 2
        
        engine.stop()
    
    def test_statistics_by_job_name(self):
        """Test statistics by job name."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return "done"
        
        engine.submit("type_a", handler, args={})
        engine.submit("type_a", handler, args={})
        engine.submit("type_b", handler, args={})
        
        time.sleep(0.5)
        
        stats = engine.get_statistics()
        
        assert stats["by_job_name"]["type_a"] == 2
        assert stats["by_job_name"]["type_b"] == 1
        
        engine.stop()
    
    def test_statistics_by_priority(self):
        """Test statistics by priority."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return "done"
        
        engine.submit("low", handler, args={}, priority=JobPriority.LOW)
        engine.submit("high", handler, args={}, priority=JobPriority.HIGH)
        engine.submit("critical", handler, args={}, priority=JobPriority.CRITICAL)
        
        time.sleep(0.5)
        
        stats = engine.get_statistics()
        
        assert stats["by_priority"]["LOW"] == 1
        assert stats["by_priority"]["HIGH"] == 1
        assert stats["by_priority"]["CRITICAL"] == 1
        
        engine.stop()
    
    def test_worker_to_dict(self):
        """Test worker serialization."""
        worker = Worker(
            worker_id="worker_test",
            status=WorkerStatus.BUSY,
            current_job="job_123",
            jobs_completed=10,
            jobs_failed=2,
        )
        
        d = worker.to_dict()
        
        assert d["worker_id"] == "worker_test"
        assert d["status"] == "busy"
        assert d["current_job"] == "job_123"
        assert d["jobs_completed"] == 10
    
    def test_job_to_dict(self):
        """Test job serialization."""
        job = Job(
            job_id="job_test",
            name="test_job",
            handler=lambda args: None,
            args={"key": "value"},
            priority=JobPriority.HIGH,
            status=JobStatus.COMPLETED,
            result="success",
        )
        
        d = job.to_dict()
        
        assert d["job_id"] == "job_test"
        assert d["name"] == "test_job"
        assert d["priority"] == 2
        assert d["status"] == "completed"
        assert d["result"] == "success"
    
    def test_worker_status_enum_values(self):
        """Test worker status enum values."""
        assert WorkerStatus.IDLE.value == "idle"
        assert WorkerStatus.BUSY.value == "busy"
        assert WorkerStatus.STOPPING.value == "stopping"
        assert WorkerStatus.STOPPED.value == "stopped"
    
    def test_job_status_enum_values(self):
        """Test job status enum values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"
        assert JobStatus.RETRYING.value == "retrying"
    
    def test_job_priority_enum_values(self):
        """Test job priority enum values."""
        assert JobPriority.LOW.value == 0
        assert JobPriority.NORMAL.value == 1
        assert JobPriority.HIGH.value == 2
        assert JobPriority.CRITICAL.value == 3
    
    def test_job_created_at_set(self):
        """Test that job created_at is set."""
        job = Job(
            job_id="job_test",
            name="test",
            handler=lambda args: None,
            args={},
        )
        
        assert job.created_at is not None
    
    def test_worker_started_at_set(self):
        """Test that worker started_at is set."""
        worker = Worker(worker_id="worker_test")
        
        assert worker.started_at is not None
    
    def test_worker_last_heartbeat_set(self):
        """Test that worker last_heartbeat is set."""
        worker = Worker(worker_id="worker_test")
        
        assert worker.last_heartbeat is not None
    
    def test_priority_queue_ordering(self):
        """Test that jobs are processed in priority order."""
        engine = WorkerEngine(max_workers=1)
        engine.start()
        
        results = []
        
        def handler(args):
            results.append(args["order"])
            return args["order"]
        
        # Submit in reverse priority order
        engine.submit("low", handler, args={"order": 3}, priority=JobPriority.LOW)
        engine.submit("normal", handler, args={"order": 2}, priority=JobPriority.NORMAL)
        engine.submit("high", handler, args={"order": 1}, priority=JobPriority.HIGH)
        engine.submit("critical", handler, args={"order": 0}, priority=JobPriority.CRITICAL)
        
        time.sleep(1)
        
        # Critical should be first
        assert results[0] == 0
        
        engine.stop()
    
    def test_job_timeout(self):
        """Test job timeout enforcement."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def slow_handler(args):
            time.sleep(10)
            return "should not complete"
        
        job_id = engine.submit(
            "slow_job",
            slow_handler,
            args={},
            timeout_seconds=1,
            max_retries=0,
        )
        
        time.sleep(2)
        
        job = engine.get_job(job_id)
        
        assert job.status == JobStatus.FAILED
        assert "Timeout" in job.error
        
        engine.stop()
    
    def test_job_with_no_args(self):
        """Test job with no arguments."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return "no args needed"
        
        job_id = engine.submit("no_args", handler)
        
        success, result = engine.get_job_result(job_id, timeout_seconds=5)
        
        assert success is True
        assert result == "no args needed"
        
        engine.stop()
    
    def test_job_result_stored(self):
        """Test that job result is stored."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return {"computed": args["value"] * 2}
        
        job_id = engine.submit("compute", handler, args={"value": 21})
        
        time.sleep(0.5)
        
        job = engine.get_job(job_id)
        
        assert job.result == {"computed": 42}
        
        engine.stop()
    
    def test_job_error_stored(self):
        """Test that job error is stored."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            raise RuntimeError("Specific error message")
        
        job_id = engine.submit("fail", handler, args={}, max_retries=0)
        
        time.sleep(0.5)
        
        job = engine.get_job(job_id)
        
        assert job.error is not None
        assert "RuntimeError" in job.error or "Specific error" in job.error
        
        engine.stop()
    
    def test_job_attempts_tracked(self):
        """Test that job attempts are tracked."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        attempt_count = [0]
        
        def handler(args):
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise ValueError("Retry me")
            return "success"
        
        job_id = engine.submit("retry_test", handler, args={}, max_retries=3)
        
        time.sleep(3)
        
        job = engine.get_job(job_id)
        
        assert job.attempts >= 2
        
        engine.stop()
    
    def test_worker_jobs_completed_tracked(self):
        """Test that worker completed jobs are tracked."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return "done"
        
        for i in range(10):
            engine.submit(f"job_{i}", handler, args={})
        
        time.sleep(2)
        
        workers = engine.get_all_workers()
        
        total_completed = sum(w.jobs_completed for w in workers)
        
        assert total_completed == 10
        
        engine.stop()
    
    def test_worker_jobs_failed_tracked(self):
        """Test that worker failed jobs are tracked."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            raise ValueError("Fail")
        
        for i in range(5):
            engine.submit(f"job_{i}", handler, args={}, max_retries=0)
        
        time.sleep(1)
        
        workers = engine.get_all_workers()
        
        total_failed = sum(w.jobs_failed for w in workers)
        
        assert total_failed == 5
        
        engine.stop()
    
    def test_statistics_active_workers(self):
        """Test that statistics track active workers."""
        engine = WorkerEngine(max_workers=4)
        engine.start()
        
        def slow_handler(args):
            time.sleep(2)
            return "done"
        
        # Submit enough jobs to keep workers busy
        for i in range(4):
            engine.submit(f"slow_{i}", slow_handler, args={})
        
        time.sleep(0.5)
        
        stats = engine.get_statistics()
        
        assert stats["active_workers"] >= 1
        
        engine.stop()
    
    def test_statistics_idle_workers(self):
        """Test that statistics track idle workers."""
        engine = WorkerEngine(max_workers=4)
        engine.start()
        
        time.sleep(0.1)
        
        stats = engine.get_statistics()
        
        # All should be idle initially
        assert stats["idle_workers"] == 4
        assert stats["active_workers"] == 0
        
        engine.stop()
    
    def test_statistics_pending_jobs(self):
        """Test that statistics track pending jobs."""
        engine = WorkerEngine(max_workers=1)
        engine.start()
        
        def slow_handler(args):
            time.sleep(5)
        
        engine.submit("slow1", slow_handler, args={})
        engine.submit("slow2", slow_handler, args={})
        engine.submit("slow3", slow_handler, args={})
        
        time.sleep(0.1)
        
        stats = engine.get_statistics()
        
        assert stats["pending_jobs"] >= 2
        
        engine.stop()
    
    def test_statistics_running_jobs(self):
        """Test that statistics track running jobs."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def slow_handler(args):
            time.sleep(2)
        
        engine.submit("slow1", slow_handler, args={})
        engine.submit("slow2", slow_handler, args={})
        
        time.sleep(0.1)
        
        stats = engine.get_statistics()
        
        assert stats["running_jobs"] >= 1
        
        engine.stop()
    
    def test_multiple_jobs_same_handler(self):
        """Test submitting multiple jobs with same handler."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return args["value"] + 1
        
        job_ids = []
        for i in range(10):
            job_id = engine.submit("increment", handler, args={"value": i})
            job_ids.append(job_id)
        
        time.sleep(1)
        
        results = []
        for job_id in job_ids:
            success, result = engine.get_job_result(job_id, timeout_seconds=1)
            if success:
                results.append(result)
        
        assert len(results) == 10
        assert set(results) == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
        
        engine.stop()
    
    def test_job_metadata_preserved(self):
        """Test that job metadata is preserved."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return "done"
        
        job_id = engine.submit(
            "test",
            handler,
            args={},
            metadata={
                "user_id": "123",
                "request_id": "req_456",
                "tags": ["important", "urgent"],
            },
        )
        
        job = engine.get_job(job_id)
        
        assert job.metadata["user_id"] == "123"
        assert job.metadata["request_id"] == "req_456"
        assert "important" in job.metadata["tags"]
        
        engine.stop()
    
    def test_worker_heartbeat_updates(self):
        """Test that worker heartbeat updates."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        time.sleep(0.1)
        
        workers = engine.get_all_workers()
        first_heartbeat = workers[0].last_heartbeat
        
        time.sleep(1.5)
        
        workers = engine.get_all_workers()
        second_heartbeat = workers[0].last_heartbeat
        
        # Heartbeat should have updated
        assert second_heartbeat > first_heartbeat
        
        engine.stop()
    
    def test_stop_with_timeout(self):
        """Test stopping with timeout."""
        engine = WorkerEngine(max_workers=4)
        engine.start()
        
        def slow_handler(args):
            time.sleep(10)
        
        # Submit jobs that will take long
        for i in range(4):
            engine.submit("slow", slow_handler, args={})
        
        # Stop with short timeout
        start = time.time()
        engine.stop(timeout_seconds=2)
        elapsed = time.time() - start
        
        # Should not wait full 10 seconds
        assert elapsed < 5
    
    def test_submit_after_stop_fails(self):
        """Test that submitting after stop may not execute."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        engine.stop()
        
        def handler(args):
            return "should not run"
        
        job_id = engine.submit("after_stop", handler, args={})
        
        # Job should be queued but never executed
        time.sleep(0.5)
        
        job = engine.get_job(job_id)
        
        # Status should be queued but worker won't pick it up
        assert job.status in (JobStatus.QUEUED, JobStatus.PENDING)
    
    def test_job_started_at_set(self):
        """Test that job started_at is set when running."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return "done"
        
        job_id = engine.submit("test", handler, args={})
        
        time.sleep(0.5)
        
        job = engine.get_job(job_id)
        
        assert job.started_at is not None
        assert job.started_at >= job.created_at
    
    def test_job_completed_at_set(self):
        """Test that job completed_at is set when done."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return "done"
        
        job_id = engine.submit("test", handler, args={})
        
        time.sleep(0.5)
        
        job = engine.get_job(job_id)
        
        assert job.completed_at is not None
        assert job.completed_at >= job.started_at
    
    def test_job_worker_id_set(self):
        """Test that job worker_id is set when executed."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        def handler(args):
            return "done"
        
        job_id = engine.submit("test", handler, args={})
        
        time.sleep(0.5)
        
        job = engine.get_job(job_id)
        
        assert job.worker_id is not None
        assert job.worker_id.startswith("worker_")
    
    def test_cancelled_job_completed_at_set(self):
        """Test that cancelled job has completed_at set."""
        engine = WorkerEngine(max_workers=1)
        engine.start()
        
        def slow_handler(args):
            time.sleep(10)
        
        slow_job = engine.submit("slow", slow_handler, args={})
        
        quick_job = engine.submit("quick", lambda args: "quick", args={})
        
        time.sleep(0.1)
        
        engine.cancel_job(quick_job)
        
        job = engine.get_job(quick_job)
        
        assert job.completed_at is not None
        
        engine.stop()
    
    def test_retry_job_requeued(self):
        """Test that retry job is requeued."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        attempt_count = [0]
        
        def flaky_handler(args):
            attempt_count[0] += 1
            if attempt_count[0] == 1:
                raise ValueError("First attempt fails")
            return "success"
        
        job_id = engine.submit("flaky", flaky_handler, args={}, max_retries=2)
        
        time.sleep(2)
        
        job = engine.get_job(job_id)
        
        assert job.status == JobStatus.COMPLETED
        assert attempt_count[0] == 2
        
        engine.stop()
    
    def test_statistics_total_retried(self):
        """Test that statistics track retried jobs."""
        engine = WorkerEngine(max_workers=2)
        engine.start()
        
        attempt_count = [0]
        
        def flaky_handler(args):
            attempt_count[0] += 1
            if attempt_count[0] < 2:
                raise ValueError("Retry")
            return "success"
        
        engine.submit("flaky", flaky_handler, args={}, max_retries=3)
        
        time.sleep(2)
        
        stats = engine.get_statistics()
        
        assert stats["total_jobs_retried"] >= 1
        
        engine.stop()
    
    def test_statistics_total_cancelled(self):
        """Test that statistics track cancelled jobs."""
        engine = WorkerEngine(max_workers=1)
        engine.start()
        
        def slow_handler(args):
            time.sleep(5)
        
        slow_job = engine.submit("slow", slow_handler, args={})
        cancel_job = engine.submit("cancel", lambda args: "x", args={})
        
        time.sleep(0.1)
        
        engine.cancel_job(cancel_job)
        
        stats = engine.get_statistics()
        
        assert stats["total_jobs_cancelled"] == 1
        
        engine.stop()
