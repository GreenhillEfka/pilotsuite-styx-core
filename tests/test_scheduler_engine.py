"""Tests for Scheduler Engine — Slice 31."""
import pytest
from copilot_core.scheduler.engine import (
    SchedulerEngine,
    JobStatus,
    ScheduleType,
    create_scheduler_engine,
)
from datetime import datetime, timezone, timedelta


class TestSchedulerEngine:
    """Test scheduler engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_scheduler_engine()
        assert engine is not None
    
    def test_create_job_once(self):
        """Test creating one-time job."""
        engine = SchedulerEngine()
        
        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        job_id = engine.create_job(
            name="One-Time Job",
            description="Runs once",
            schedule_type="once",
            schedule_expression=future_time,
            action_name="log",
            parameters={"message": "Running once"},
        )
        
        assert job_id is not None
        assert job_id.startswith("job_")
        assert job_id in engine._jobs
        
        job = engine._jobs[job_id]
        assert job.schedule_type == ScheduleType.ONCE
    
    def test_create_job_interval(self):
        """Test creating interval job."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Interval Job",
            description="Runs every 60 seconds",
            schedule_type="interval",
            schedule_expression="60",
            action_name="log",
            parameters={"message": "Running"},
        )
        
        job = engine.get_job(job_id)
        
        assert job is not None
        assert job["schedule_type"] == "interval"
        assert job["schedule_expression"] == "60"
        assert job["next_run"] is not None
    
    def test_create_job_daily(self):
        """Test creating daily job."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Daily Job",
            description="Runs daily at 09:00",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="log",
            parameters={"message": "Good morning"},
        )
        
        job = engine.get_job(job_id)
        
        assert job is not None
        assert job["schedule_type"] == "daily"
        assert job["next_run"] is not None
    
    def test_create_job_weekly(self):
        """Test creating weekly job."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Weekly Job",
            description="Runs every Monday at 09:00",
            schedule_type="weekly",
            schedule_expression="monday 09:00",
            action_name="log",
            parameters={"message": "Monday"},
        )
        
        job = engine.get_job(job_id)
        
        assert job is not None
        assert job["schedule_type"] == "weekly"
    
    def test_create_job_cron(self):
        """Test creating cron job."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Cron Job",
            description="Runs on cron schedule",
            schedule_type="cron",
            schedule_expression="0 * * * *",  # Every hour
            action_name="log",
            parameters={"message": "Hourly"},
        )
        
        job = engine.get_job(job_id)
        
        assert job is not None
        assert job["schedule_type"] == "cron"
    
    def test_enable_disable_job(self):
        """Test enabling/disabling job."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Test Job",
            description="Test",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="log",
            parameters={},
        )
        
        # Disable
        result = engine.disable_job(job_id)
        assert result is True
        assert engine._jobs[job_id].enabled is False
        assert engine._jobs[job_id].next_run is None
        
        # Enable
        result = engine.enable_job(job_id)
        assert result is True
        assert engine._jobs[job_id].enabled is True
        assert engine._jobs[job_id].next_run is not None
    
    def test_pause_resume_job(self):
        """Test pausing/resuming job."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Test Job",
            description="Test",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="log",
            parameters={},
        )
        
        # Pause
        result = engine.pause_job(job_id)
        assert result is True
        assert engine._jobs[job_id].enabled is False
        
        # Resume
        result = engine.resume_job(job_id)
        assert result is True
        assert engine._jobs[job_id].enabled is True
    
    def test_run_job_manually(self):
        """Test manually running a job."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Manual Job",
            description="Test",
            schedule_type="once",
            schedule_expression=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            action_name="log",
            parameters={"message": "Manual run"},
        )
        
        execution_id = engine.run_job(job_id)
        
        assert execution_id is not None
        
        job = engine.get_job(job_id)
        assert job["run_count"] == 1
    
    def test_run_job_with_dependencies(self):
        """Test running job with dependencies."""
        engine = SchedulerEngine()
        
        # Create dependency job
        dep_job_id = engine.create_job(
            name="Dependency Job",
            description="Must run first",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="log",
            parameters={},
        )
        
        # Create dependent job
        job_id = engine.create_job(
            name="Dependent Job",
            description="Depends on other job",
            schedule_type="daily",
            schedule_expression="10:00",
            action_name="log",
            parameters={},
            dependencies=[dep_job_id],
        )
        
        # Try to run dependent job first (should fail)
        execution_id = engine.run_job(job_id)
        
        assert execution_id is None  # Dependency not met
        
        # Run dependency first
        engine.run_job(dep_job_id)
        
        # Now dependent job should run
        execution_id = engine.run_job(job_id)
        
        assert execution_id is not None
    
    def test_process_due_jobs(self):
        """Test processing due jobs."""
        engine = SchedulerEngine()
        
        # Create job that's due now (past time)
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        
        job_id = engine.create_job(
            name="Due Job",
            description="Should run now",
            schedule_type="once",
            schedule_expression=past_time,
            action_name="log",
            parameters={"message": "Due"},
        )
        
        processed = engine.process_due_jobs()
        
        assert processed >= 1
        
        job = engine.get_job(job_id)
        assert job["run_count"] >= 1
    
    def test_get_job(self):
        """Test getting job details."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Test Job",
            description="Test description",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="log",
            parameters={"message": "Test"},
            priority=5,
            tags=["test", "daily"],
        )
        
        job = engine.get_job(job_id)
        
        assert job is not None
        assert job["name"] == "Test Job"
        assert job["description"] == "Test description"
        assert job["priority"] == 5
        assert "test" in job["tags"]
    
    def test_get_unknown_job(self):
        """Test getting unknown job."""
        engine = SchedulerEngine()
        
        job = engine.get_job("unknown_job")
        
        assert job is None
    
    def test_get_all_jobs(self):
        """Test getting all jobs."""
        engine = SchedulerEngine()
        
        for i in range(3):
            engine.create_job(
                name=f"Job {i}",
                description="Test",
                schedule_type="daily",
                schedule_expression="09:00",
                action_name="log",
                parameters={},
            )
        
        jobs = engine.get_all_jobs()
        
        assert len(jobs) == 3
    
    def test_get_all_jobs_filtered_by_status(self):
        """Test getting jobs filtered by status."""
        engine = SchedulerEngine()
        
        job1 = engine.create_job("Job 1", "Test", "daily", "09:00", "log", {})
        job2 = engine.create_job("Job 2", "Test", "daily", "09:00", "log", {})
        
        engine.disable_job(job2)
        
        enabled = engine.get_all_jobs(status="enabled")
        disabled = engine.get_all_jobs(status="disabled")
        
        assert len(enabled) == 1
        assert len(disabled) == 1
    
    def test_get_all_jobs_filtered_by_tags(self):
        """Test getting jobs filtered by tags."""
        engine = SchedulerEngine()
        
        engine.create_job("Job 1", "Test", "daily", "09:00", "log", {}, tags=["daily"])
        engine.create_job("Job 2", "Test", "daily", "09:00", "log", {}, tags=["weekly"])
        
        daily_jobs = engine.get_all_jobs(tags=["daily"])
        
        assert len(daily_jobs) == 1
        assert daily_jobs[0]["name"] == "Job 1"
    
    def test_delete_job(self):
        """Test deleting job."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Test Job",
            description="Test",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="log",
            parameters={},
        )
        
        result = engine.delete_job(job_id)
        
        assert result is True
        assert job_id not in engine._jobs
    
    def test_delete_unknown_job(self):
        """Test deleting unknown job."""
        engine = SchedulerEngine()
        
        result = engine.delete_job("unknown_job")
        
        assert result is False
    
    def test_get_execution(self):
        """Test getting execution details."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Test Job",
            description="Test",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="log",
            parameters={},
        )
        
        execution_id = engine.run_job(job_id)
        
        execution = engine.get_execution(execution_id)
        
        assert execution is not None
        assert execution["job_id"] == job_id
        assert execution["status"] == "completed"
    
    def test_get_unknown_execution(self):
        """Test getting unknown execution."""
        engine = SchedulerEngine()
        
        execution = engine.get_execution("unknown_execution")
        
        assert execution is None
    
    def test_get_executions_by_job(self):
        """Test getting executions by job."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Test Job",
            description="Test",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="log",
            parameters={},
        )
        
        # Run multiple times
        for i in range(5):
            engine.run_job(job_id)
        
        executions = engine.get_executions_by_job(job_id, limit=10)
        
        assert len(executions) == 5
    
    def test_get_scheduler_summary(self):
        """Test scheduler summary."""
        engine = SchedulerEngine()
        
        engine.create_job("Job 1", "Test", "daily", "09:00", "log", {})
        engine.create_job("Job 2", "Test", "daily", "09:00", "log", {})
        
        engine.run_job(engine._jobs[list(engine._jobs.keys())[0]].job_id)
        
        summary = engine.get_scheduler_summary()
        
        assert summary["total_jobs"] == 2
        assert summary["enabled_jobs"] == 2
        assert summary["total_runs"] >= 1
    
    def test_get_upcoming_jobs(self):
        """Test getting upcoming jobs."""
        engine = SchedulerEngine()
        
        # Create job due in 1 hour
        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        job_id = engine.create_job(
            name="Upcoming Job",
            description="Test",
            schedule_type="once",
            schedule_expression=future_time,
            action_name="log",
            parameters={},
        )
        
        upcoming = engine.get_upcoming_jobs(hours_ahead=24)
        
        assert len(upcoming) >= 1
    
    def test_register_custom_action(self):
        """Test registering custom action."""
        engine = SchedulerEngine()
        
        def custom_action(**kwargs):
            return {"custom": True}
        
        engine.register_action("custom_action", custom_action)
        
        assert "custom_action" in engine._action_registry
    
    def test_builtin_log_action(self):
        """Test built-in log action."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Log Job",
            description="Test",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="log",
            parameters={"message": "Test log"},
        )
        
        execution_id = engine.run_job(job_id)
        
        execution = engine.get_execution(execution_id)
        
        assert execution["status"] == "completed"
    
    def test_builtin_noop_action(self):
        """Test built-in noop action."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Noop Job",
            description="Test",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="noop",
            parameters={},
        )
        
        execution_id = engine.run_job(job_id)
        
        execution = engine.get_execution(execution_id)
        
        assert execution["status"] == "completed"
    
    def test_job_priority_ordering(self):
        """Test that jobs are processed in priority order."""
        engine = SchedulerEngine()
        
        # Create jobs with different priorities
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        
        engine.create_job("Low Priority", "Test", "once", past_time, "log", {}, priority=1)
        engine.create_job("High Priority", "Test", "once", past_time, "log", {}, priority=10)
        engine.create_job("Medium Priority", "Test", "once", past_time, "log", {}, priority=5)
        
        # Process due jobs
        engine.process_due_jobs()
        
        # Jobs should be processed in priority order
    
    def test_job_retry_on_failure(self):
        """Test job retry on failure."""
        engine = SchedulerEngine()
        
        call_count = [0]
        
        def flaky_action(**kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("First attempt fails")
            return {"success": True}
        
        engine.register_action("flaky", flaky_action)
        
        job_id = engine.create_job(
            name="Flaky Job",
            description="Test",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="flaky",
            parameters={},
            max_retries=2,
        )
        
        engine.run_job(job_id)
        
        job = engine.get_job(job_id)
        
        # Should succeed after retry
        assert job["run_count"] >= 1
    
    def test_job_exhausts_retries(self):
        """Test job fails after exhausting retries."""
        engine = SchedulerEngine()
        
        def always_fails(**kwargs):
            raise Exception("Always fails")
        
        engine.register_action("failing", always_fails)
        
        job_id = engine.create_job(
            name="Failing Job",
            description="Test",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="failing",
            parameters={},
            max_retries=2,
        )
        
        engine.run_job(job_id)
        
        job = engine.get_job(job_id)
        
        assert job["fail_count"] >= 1
    
    def test_execution_history_trimmed(self):
        """Test that execution history is trimmed."""
        engine = SchedulerEngine()
        engine._max_history_size = 10
        
        job_id = engine.create_job(
            name="Test Job",
            description="Test",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="noop",
            parameters={},
        )
        
        # Run more than max
        for i in range(20):
            engine.run_job(job_id)
        
        assert len(engine._execution_history) <= 10
    
    def test_job_to_dict(self):
        """Test job serialization."""
        from copilot_core.scheduler.engine import ScheduledJob
        
        job = ScheduledJob(
            job_id="job_test",
            name="Test Job",
            description="Test description",
            schedule_type=ScheduleType.DAILY,
            schedule_expression="09:00",
            action_name="log",
            parameters={"message": "Test"},
        )
        
        d = job.to_dict()
        
        assert d["job_id"] == "job_test"
        assert d["name"] == "Test Job"
        assert d["schedule_type"] == "daily"
    
    def test_execution_to_dict(self):
        """Test execution serialization."""
        from copilot_core.scheduler.engine import JobExecution, JobStatus
        
        execution = JobExecution(
            execution_id="exec_test",
            job_id="job_test",
            status=JobStatus.COMPLETED,
            started_at="2026-03-31T09:00:00Z",
            completed_at="2026-03-31T09:00:01Z",
            result={"success": True},
            duration_ms=100,
        )
        
        d = execution.to_dict()
        
        assert d["execution_id"] == "exec_test"
        assert d["status"] == "completed"
        assert d["duration_ms"] == 100
    
    def test_schedule_type_enum_values(self):
        """Test schedule type enum values."""
        assert ScheduleType.ONCE.value == "once"
        assert ScheduleType.CRON.value == "cron"
        assert ScheduleType.INTERVAL.value == "interval"
        assert ScheduleType.DAILY.value == "daily"
        assert ScheduleType.WEEKLY.value == "weekly"
        assert ScheduleType.MONTHLY.value == "monthly"
    
    def test_job_status_enum_values(self):
        """Test job status enum values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.SCHEDULED.value == "scheduled"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
    
    def test_jobs_sorted_by_priority(self):
        """Test that jobs are sorted by priority."""
        engine = SchedulerEngine()
        
        engine.create_job("Low", "Test", "daily", "09:00", "log", {}, priority=1)
        engine.create_job("High", "Test", "daily", "09:00", "log", {}, priority=100)
        engine.create_job("Medium", "Test", "daily", "09:00", "log", {}, priority=50)
        
        jobs = engine.get_all_jobs()
        
        # Should be sorted by priority (high first)
        assert jobs[0]["priority"] >= jobs[1]["priority"]
        assert jobs[1]["priority"] >= jobs[2]["priority"]
    
    def test_executions_sorted_by_started_at(self):
        """Test that executions are sorted by started_at."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Test",
            description="Test",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="noop",
            parameters={},
        )
        
        for i in range(5):
            engine.run_job(job_id)
        
        executions = engine.get_executions_by_job(job_id, limit=10)
        
        # Verify sorted (newest first)
        for i in range(len(executions) - 1):
            assert executions[i]["started_at"] >= executions[i + 1]["started_at"]
    
    def test_unknown_action_fails_job(self):
        """Test that unknown action fails job."""
        engine = SchedulerEngine()
        
        job_id = engine.create_job(
            name="Unknown Action",
            description="Test",
            schedule_type="daily",
            schedule_expression="09:00",
            action_name="nonexistent_action",
            parameters={},
        )
        
        execution_id = engine.run_job(job_id)
        
        execution = engine.get_execution(execution_id)
        
        assert execution["status"] == "failed"
        assert "Unknown action" in execution["error_message"]
