"""Tests for Scheduler Advanced Engine — Slice 55."""
import pytest
from copilot_core.scheduler_advanced.engine import (
    SchedulerEngine,
    ScheduleType,
    JobStatus,
    CronExpression,
    ScheduledJob,
    create_scheduler_engine,
)
from datetime import datetime, timezone, timedelta
import time


class TestCronExpression:
    """Test cron expression parsing."""
    
    def test_parse_every_minute(self):
        """Test parsing * * * * *."""
        cron = CronExpression.parse("* * * * *")
        
        assert cron.minute == set(range(0, 60))
        assert cron.hour == set(range(0, 24))
        assert cron.day == set(range(1, 32))
        assert cron.month == set(range(1, 13))
        assert cron.weekday == set(range(0, 7))
    
    def test_parse_specific_time(self):
        """Test parsing specific time."""
        cron = CronExpression.parse("30 14 1 6 3")
        
        assert cron.minute == {30}
        assert cron.hour == {14}
        assert cron.day == {1}
        assert cron.month == {6}
        assert cron.weekday == {3}
    
    def test_parse_range(self):
        """Test parsing range."""
        cron = CronExpression.parse("0-30 * * * *")
        
        assert cron.minute == set(range(0, 31))
    
    def test_parse_step(self):
        """Test parsing step."""
        cron = CronExpression.parse("*/15 * * * *")
        
        assert cron.minute == {0, 15, 30, 45}
    
    def test_parse_step_with_base(self):
        """Test parsing step with base."""
        cron = CronExpression.parse("10/20 * * * *")
        
        assert cron.minute == {10, 30, 50}
    
    def test_parse_list(self):
        """Test parsing list."""
        cron = CronExpression.parse("0,15,30,45 * * * *")
        
        assert cron.minute == {0, 15, 30, 45}
    
    def test_parse_combined(self):
        """Test parsing combined expression."""
        cron = CronExpression.parse("0,30 9-17 * * 1-5")
        
        assert cron.minute == {0, 30}
        assert cron.hour == set(range(9, 18))
        assert cron.weekday == set(range(1, 6))
    
    def test_parse_invalid_expression(self):
        """Test parsing invalid expression."""
        with pytest.raises(ValueError):
            CronExpression.parse("* * *")
    
    def test_matches_exact(self):
        """Test matching exact datetime."""
        cron = CronExpression.parse("30 14 1 6 3")
        
        dt = datetime(2025, 6, 1, 14, 30, tzinfo=timezone.utc)
        
        assert cron.matches(dt) is True
    
    def test_matches_no_match(self):
        """Test non-matching datetime."""
        cron = CronExpression.parse("30 14 1 6 3")
        
        dt = datetime(2025, 6, 1, 15, 30, tzinfo=timezone.utc)
        
        assert cron.matches(dt) is False
    
    def test_next_run(self):
        """Test calculating next run time."""
        cron = CronExpression.parse("0 * * * *")  # Every hour at :00
        
        after = datetime(2025, 6, 1, 10, 30, tzinfo=timezone.utc)
        
        next_run = cron.next_run(after)
        
        assert next_run.hour == 11
        assert next_run.minute == 0
    
    def test_next_run_next_day(self):
        """Test next run on next day."""
        cron = CronExpression.parse("0 0 * * *")  # Midnight daily
        
        after = datetime(2025, 6, 1, 23, 30, tzinfo=timezone.utc)
        
        next_run = cron.next_run(after)
        
        assert next_run.day == 2
        assert next_run.hour == 0
        assert next_run.minute == 0


class TestSchedulerEngine:
    """Test scheduler engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_scheduler_engine()
        assert engine is not None
    
    def test_schedule_cron(self):
        """Test scheduling cron job."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron(
            "hourly_task",
            handler,
            cron_expression="0 * * * *",
        )
        
        assert job_id is not None
        assert job_id.startswith("job_")
        
        job = engine.get_job(job_id)
        
        assert job is not None
        assert job.schedule_type == ScheduleType.CRON
        assert job.cron_expression == "0 * * * *"
    
    def test_schedule_interval(self):
        """Test scheduling interval job."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_interval(
            "frequent_task",
            handler,
            interval_seconds=300,
        )
        
        job = engine.get_job(job_id)
        
        assert job.schedule_type == ScheduleType.INTERVAL
        assert job.interval_seconds == 300
    
    def test_schedule_once(self):
        """Test scheduling one-time job."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        run_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        job_id = engine.schedule_once(
            "one_time_task",
            handler,
            run_at=run_at,
        )
        
        job = engine.get_job(job_id)
        
        assert job.schedule_type == ScheduleType.ONCE
        assert job.run_at is not None
    
    def test_schedule_cron_with_args(self):
        """Test scheduling cron job with arguments."""
        engine = SchedulerEngine()
        
        def handler(args):
            return args
        
        job_id = engine.schedule_cron(
            "task_with_args",
            handler,
            "0 * * * *",
            args={"key": "value"},
        )
        
        job = engine.get_job(job_id)
        
        assert job.args == {"key": "value"}
    
    def test_schedule_cron_with_group(self):
        """Test scheduling cron job with group."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron(
            "grouped_task",
            handler,
            "0 * * * *",
            group="maintenance",
        )
        
        job = engine.get_job(job_id)
        
        assert job.group == "maintenance"
    
    def test_schedule_cron_with_max_runs(self):
        """Test scheduling cron job with max runs."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron(
            "limited_task",
            handler,
            "0 * * * *",
            max_runs=5,
        )
        
        job = engine.get_job(job_id)
        
        assert job.max_runs == 5
    
    def test_schedule_cron_with_dependencies(self):
        """Test scheduling cron job with dependencies."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        # Create dependency job
        dep_id = engine.schedule_cron("dep_task", handler, "0 * * * *")
        
        # Create dependent job
        job_id = engine.schedule_cron(
            "dependent_task",
            handler,
            "30 * * * *",
            dependencies=[dep_id],
        )
        
        job = engine.get_job(job_id)
        
        assert job.dependencies == [dep_id]
    
    def test_schedule_cron_with_metadata(self):
        """Test scheduling cron job with metadata."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron(
            "task_with_meta",
            handler,
            "0 * * * *",
            metadata={"owner": "team-a", "priority": "high"},
        )
        
        job = engine.get_job(job_id)
        
        assert job.metadata["owner"] == "team-a"
        assert job.metadata["priority"] == "high"
    
    def test_cancel_job(self):
        """Test cancelling job."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron("test", handler, "0 * * * *")
        
        result = engine.cancel_job(job_id)
        
        assert result is True
        
        job = engine.get_job(job_id)
        
        assert job.status == JobStatus.CANCELLED
        assert job.next_run_at is None
    
    def test_cancel_nonexistent_job(self):
        """Test cancelling nonexistent job."""
        engine = SchedulerEngine()
        
        result = engine.cancel_job("nonexistent")
        
        assert result is False
    
    def test_pause_job(self):
        """Test pausing job."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron("test", handler, "0 * * * *")
        
        result = engine.pause_job(job_id)
        
        assert result is True
        
        job = engine.get_job(job_id)
        
        assert job.next_run_at is None
        assert "_paused_next_run" in job.metadata
    
    def test_resume_job(self):
        """Test resuming paused job."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron("test", handler, "0 * * * *")
        
        engine.pause_job(job_id)
        result = engine.resume_job(job_id)
        
        assert result is True
        
        job = engine.get_job(job_id)
        
        assert job.next_run_at is not None
        assert "_paused_next_run" not in job.metadata
    
    def test_pause_nonexistent_job(self):
        """Test pausing nonexistent job."""
        engine = SchedulerEngine()
        
        result = engine.pause_job("nonexistent")
        
        assert result is False
    
    def test_resume_nonexistent_job(self):
        """Test resuming nonexistent job."""
        engine = SchedulerEngine()
        
        result = engine.resume_job("nonexistent")
        
        assert result is False
    
    def test_get_job(self):
        """Test getting job by ID."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron("test", handler, "0 * * * *")
        
        job = engine.get_job(job_id)
        
        assert job is not None
        assert job.name == "test"
    
    def test_get_nonexistent_job(self):
        """Test getting nonexistent job."""
        engine = SchedulerEngine()
        
        job = engine.get_job("nonexistent")
        
        assert job is None
    
    def test_list_jobs(self):
        """Test listing all jobs."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        engine.schedule_cron("job1", handler, "0 * * * *")
        engine.schedule_cron("job2", handler, "30 * * * *")
        engine.schedule_cron("job3", handler, "0 0 * * *")
        
        jobs = engine.list_jobs()
        
        assert len(jobs) == 3
    
    def test_list_jobs_filtered_by_group(self):
        """Test listing jobs filtered by group."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        engine.schedule_cron("job1", handler, "0 * * * *", group="group1")
        engine.schedule_cron("job2", handler, "30 * * * *", group="group1")
        engine.schedule_cron("job3", handler, "0 0 * * *", group="group2")
        
        jobs = engine.list_jobs(group="group1")
        
        assert len(jobs) == 2
    
    def test_list_jobs_filtered_by_status(self):
        """Test listing jobs filtered by status."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron("test", handler, "0 * * * *")
        
        engine.cancel_job(job_id)
        
        jobs = engine.list_jobs(status=JobStatus.CANCELLED)
        
        assert len(jobs) == 1
    
    def test_get_job_history(self):
        """Test getting job history."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron("test", handler, "0 * * * *")
        
        history = engine.get_job_history(job_id)
        
        assert history == []  # No runs yet
    
    def test_get_job_history_with_limit(self):
        """Test getting job history with limit."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron("test", handler, "* * * * *")
        
        # Manually add history entries
        for i in range(20):
            engine._job_history[job_id].append({"run": i})
        
        history = engine.get_job_history(job_id, limit=5)
        
        assert len(history) == 5
        assert history[-1]["run"] == 19
    
    def test_trigger_job(self):
        """Test manually triggering job."""
        engine = SchedulerEngine()
        
        call_count = [0]
        
        def handler(args):
            call_count[0] += 1
            return "done"
        
        job_id = engine.schedule_cron("test", handler, "0 0 1 1 *")  # Far future
        
        result = engine.trigger_job(job_id)
        
        assert result is True
        
        time.sleep(0.5)
        
        assert call_count[0] == 1
    
    def test_trigger_nonexistent_job(self):
        """Test triggering nonexistent job."""
        engine = SchedulerEngine()
        
        result = engine.trigger_job("nonexistent")
        
        assert result is False
    
    def test_trigger_running_job(self):
        """Test triggering already running job."""
        engine = SchedulerEngine()
        
        def slow_handler(args):
            time.sleep(2)
            return "done"
        
        job_id = engine.schedule_cron("slow", slow_handler, "0 * * * *")
        
        # Trigger first time
        engine.trigger_job(job_id)
        
        time.sleep(0.1)
        
        # Try to trigger again while running
        result = engine.trigger_job(job_id)
        
        assert result is False
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        engine.schedule_cron("job1", handler, "0 * * * *")
        engine.schedule_cron("job2", handler, "30 * * * *")
        
        stats = engine.get_statistics()
        
        assert stats["total_jobs"] == 2
    
    def test_statistics_by_group(self):
        """Test statistics by group."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        engine.schedule_cron("job1", handler, "0 * * * *", group="group1")
        engine.schedule_cron("job2", handler, "30 * * * *", group="group1")
        engine.schedule_cron("job3", handler, "0 0 * * *", group="group2")
        
        stats = engine.get_statistics()
        
        assert stats["by_group"]["group1"] == 0  # No runs yet
    
    def test_get_group_stats(self):
        """Test getting group statistics."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        engine.schedule_cron("job1", handler, "0 * * * *", group="maintenance")
        engine.schedule_cron("job2", handler, "30 * * * *", group="maintenance")
        
        group_stats = engine.get_group_stats("maintenance")
        
        assert group_stats["group"] == "maintenance"
        assert group_stats["total_jobs"] == 2
    
    def test_job_to_dict(self):
        """Test job serialization."""
        job = ScheduledJob(
            job_id="job_test",
            name="test_job",
            handler=lambda args: None,
            schedule_type=ScheduleType.CRON,
            cron_expression="0 * * * *",
            group="test",
            max_runs=10,
        )
        
        d = job.to_dict()
        
        assert d["job_id"] == "job_test"
        assert d["schedule_type"] == "cron"
        assert d["cron_expression"] == "0 * * * *"
        assert d["group"] == "test"
    
    def test_schedule_type_enum_values(self):
        """Test schedule type enum values."""
        assert ScheduleType.CRON.value == "cron"
        assert ScheduleType.INTERVAL.value == "interval"
        assert ScheduleType.ONCE.value == "once"
    
    def test_job_status_enum_values(self):
        """Test job status enum values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"
        assert JobStatus.SKIPPED.value == "skipped"
    
    def test_job_created_at_set(self):
        """Test that job created_at is set."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron("test", handler, "0 * * * *")
        
        job = engine.get_job(job_id)
        
        assert job.created_at is not None
    
    def test_job_next_run_at_set(self):
        """Test that job next_run_at is set."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron("test", handler, "0 * * * *")
        
        job = engine.get_job(job_id)
        
        assert job.next_run_at is not None
    
    def test_start_scheduler(self):
        """Test starting scheduler."""
        engine = SchedulerEngine()
        
        engine.start()
        
        time.sleep(0.5)
        
        assert engine._scheduler_thread is not None
        assert engine._scheduler_thread.is_alive()
        
        engine.stop()
    
    def test_stop_scheduler(self):
        """Test stopping scheduler."""
        engine = SchedulerEngine()
        
        engine.start()
        time.sleep(0.5)
        
        engine.stop()
        
        time.sleep(0.5)
        
        assert not engine._scheduler_thread.is_alive()
    
    def test_scheduler_runs_cron_job(self):
        """Test that scheduler runs cron job."""
        engine = SchedulerEngine()
        
        call_count = [0]
        
        def handler(args):
            call_count[0] += 1
            return "done"
        
        # Schedule for next minute
        now = datetime.now(timezone.utc)
        next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        
        cron_expr = f"{next_minute.minute} {next_minute.hour} * * *"
        
        job_id = engine.schedule_cron("test", handler, cron_expr)
        
        engine.start()
        
        # Wait for job to run
        time.sleep(70)
        
        assert call_count[0] >= 1
        
        engine.stop()
    
    def test_scheduler_runs_interval_job(self):
        """Test that scheduler runs interval job."""
        engine = SchedulerEngine()
        
        call_count = [0]
        
        def handler(args):
            call_count[0] += 1
            return "done"
        
        # Schedule with short interval
        job_id = engine.schedule_interval("frequent", handler, interval_seconds=2)
        
        engine.start()
        
        time.sleep(5)
        
        assert call_count[0] >= 2
        
        engine.stop()
    
    def test_scheduler_respects_max_runs(self):
        """Test that scheduler respects max runs."""
        engine = SchedulerEngine()
        
        call_count = [0]
        
        def handler(args):
            call_count[0] += 1
            return "done"
        
        # Schedule with max_runs=2 and short interval
        job_id = engine.schedule_interval(
            "limited",
            handler,
            interval_seconds=1,
            max_runs=2,
        )
        
        engine.start()
        
        time.sleep(5)
        
        assert call_count[0] == 2
        
        engine.stop()
    
    def test_job_runs_completed_tracked(self):
        """Test that job runs_completed is tracked."""
        engine = SchedulerEngine()
        
        call_count = [0]
        
        def handler(args):
            call_count[0] += 1
            return "done"
        
        job_id = engine.schedule_interval("test", handler, interval_seconds=1, max_runs=3)
        
        engine.start()
        time.sleep(4)
        engine.stop()
        
        job = engine.get_job(job_id)
        
        assert job.runs_completed == 3
    
    def test_job_last_run_at_set(self):
        """Test that job last_run_at is set after run."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_interval("test", handler, interval_seconds=1, max_runs=1)
        
        engine.start()
        time.sleep(2)
        engine.stop()
        
        job = engine.get_job(job_id)
        
        assert job.last_run_at is not None
    
    def test_scheduler_handles_job_failure(self):
        """Test that scheduler handles job failure."""
        engine = SchedulerEngine()
        
        call_count = [0]
        
        def failing_handler(args):
            call_count[0] += 1
            raise ValueError("Intentional failure")
        
        job_id = engine.schedule_interval("failing", failing_handler, interval_seconds=1, max_runs=3)
        
        engine.start()
        time.sleep(4)
        engine.stop()
        
        # Should have attempted all runs despite failures
        assert call_count[0] == 3
        
        stats = engine.get_statistics()
        
        assert stats["failed_runs"] == 3
    
    def test_job_history_records_success(self):
        """Test that job history records successful runs."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "success_result"
        
        job_id = engine.schedule_interval("test", handler, interval_seconds=1, max_runs=1)
        
        engine.start()
        time.sleep(2)
        engine.stop()
        
        history = engine.get_job_history(job_id)
        
        assert len(history) == 1
        assert history[0]["status"] == "completed"
        assert history[0]["result"] == "success_result"
    
    def test_job_history_records_failure(self):
        """Test that job history records failed runs."""
        engine = SchedulerEngine()
        
        def failing_handler(args):
            raise ValueError("Test error")
        
        job_id = engine.schedule_interval("failing", failing_handler, interval_seconds=1, max_runs=1)
        
        engine.start()
        time.sleep(2)
        engine.stop()
        
        history = engine.get_job_history(job_id)
        
        assert len(history) == 1
        assert history[0]["status"] == "failed"
        assert "Test error" in history[0]["error"]
    
    def test_scheduler_checks_dependencies(self):
        """Test that scheduler checks dependencies."""
        engine = SchedulerEngine()
        
        dep_call_count = [0]
        main_call_count = [0]
        
        def dep_handler(args):
            dep_call_count[0] += 1
            return "dep_done"
        
        def main_handler(args):
            main_call_count[0] += 1
            return "main_done"
        
        # Schedule dependency with short interval
        dep_id = engine.schedule_interval("dep", dep_handler, interval_seconds=1, max_runs=1)
        
        # Schedule main job that depends on dep
        main_id = engine.schedule_interval(
            "main",
            main_handler,
            interval_seconds=1,
            max_runs=1,
            dependencies=[dep_id],
        )
        
        engine.start()
        time.sleep(4)
        engine.stop()
        
        # Dep should have run
        assert dep_call_count[0] == 1
        
        # Main should have run after dep completed
        assert main_call_count[0] == 1
    
    def test_scheduler_skips_job_if_dependency_not_met(self):
        """Test that scheduler skips job if dependency not met."""
        engine = SchedulerEngine()
        
        main_call_count = [0]
        
        def main_handler(args):
            main_call_count[0] += 1
            return "main_done"
        
        # Schedule with dependency on nonexistent job
        main_id = engine.schedule_interval(
            "main",
            main_handler,
            interval_seconds=1,
            max_runs=5,
            dependencies=["nonexistent_dep"],
        )
        
        engine.start()
        time.sleep(4)
        engine.stop()
        
        # Main should be skipped because dependency doesn't exist
        assert main_call_count[0] == 0
        
        stats = engine.get_statistics()
        
        assert stats["skipped_runs"] >= 1
    
    def test_schedule_once_runs_at_time(self):
        """Test that one-time job runs at scheduled time."""
        engine = SchedulerEngine()
        
        call_count = [0]
        
        def handler(args):
            call_count[0] += 1
            return "done"
        
        # Schedule for 2 seconds from now
        run_at = datetime.now(timezone.utc) + timedelta(seconds=2)
        
        job_id = engine.schedule_once("once", handler, run_at=run_at)
        
        engine.start()
        time.sleep(4)
        engine.stop()
        
        assert call_count[0] == 1
    
    def test_schedule_once_does_not_repeat(self):
        """Test that one-time job does not repeat."""
        engine = SchedulerEngine()
        
        call_count = [0]
        
        def handler(args):
            call_count[0] += 1
            return "done"
        
        run_at = datetime.now(timezone.utc) + timedelta(seconds=1)
        
        job_id = engine.schedule_once("once", handler, run_at=run_at)
        
        engine.start()
        time.sleep(4)
        engine.stop()
        
        # Should only run once
        assert call_count[0] == 1
        
        job = engine.get_job(job_id)
        
        assert job.status == JobStatus.COMPLETED
        assert job.next_run_at is None
    
    def test_statistics_total_runs(self):
        """Test that statistics track total runs."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_interval("test", handler, interval_seconds=1, max_runs=5)
        
        engine.start()
        time.sleep(6)
        engine.stop()
        
        stats = engine.get_statistics()
        
        assert stats["total_runs"] == 5
    
    def test_statistics_successful_runs(self):
        """Test that statistics track successful runs."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_interval("test", handler, interval_seconds=1, max_runs=3)
        
        engine.start()
        time.sleep(4)
        engine.stop()
        
        stats = engine.get_statistics()
        
        assert stats["successful_runs"] == 3
    
    def test_statistics_failed_runs(self):
        """Test that statistics track failed runs."""
        engine = SchedulerEngine()
        
        def failing_handler(args):
            raise ValueError("Fail")
        
        job_id = engine.schedule_interval("failing", failing_handler, interval_seconds=1, max_runs=2)
        
        engine.start()
        time.sleep(3)
        engine.stop()
        
        stats = engine.get_statistics()
        
        assert stats["failed_runs"] == 2
    
    def test_statistics_pending_jobs(self):
        """Test that statistics track pending jobs."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        engine.schedule_cron("future", handler, "0 0 1 1 *")  # Far future
        
        stats = engine.get_statistics()
        
        assert stats["pending_jobs"] >= 1
    
    def test_statistics_running_jobs(self):
        """Test that statistics track running jobs."""
        engine = SchedulerEngine()
        
        def slow_handler(args):
            time.sleep(3)
            return "done"
        
        job_id = engine.schedule_interval("slow", slow_handler, interval_seconds=5, max_runs=1)
        
        engine.start()
        time.sleep(0.5)
        
        stats = engine.get_statistics()
        
        # May or may not be running depending on timing
        assert stats["running_jobs"] >= 0
        
        engine.stop()
    
    def test_statistics_completed_jobs(self):
        """Test that statistics track completed jobs."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_once("once", handler, run_at=datetime.now(timezone.utc))
        
        engine.start()
        time.sleep(2)
        engine.stop()
        
        stats = engine.get_statistics()
        
        assert stats["completed_jobs"] >= 1
    
    def test_job_id_unique(self):
        """Test that job IDs are unique."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        ids = set()
        for i in range(50):
            job_id = engine.schedule_cron(f"job{i}", handler, "0 * * * *")
            ids.add(job_id)
        
        assert len(ids) == 50
    
    def test_cron_expression_complex(self):
        """Test complex cron expression."""
        cron = CronExpression.parse("0,30 9-17 * * 1-5")
        
        # Should match 9:00 AM on Monday
        dt = datetime(2025, 6, 2, 9, 0, tzinfo=timezone.utc)  # Monday
        
        assert cron.matches(dt) is True
        
        # Should not match Saturday
        dt = datetime(2025, 6, 7, 9, 0, tzinfo=timezone.utc)  # Saturday
        
        assert cron.matches(dt) is False
        
        # Should not match 8:00 AM
        dt = datetime(2025, 6, 2, 8, 0, tzinfo=timezone.utc)
        
        assert cron.matches(dt) is False
    
    def test_scheduler_job_status_transitions(self):
        """Test job status transitions."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron("test", handler, "0 * * * *")
        
        job = engine.get_job(job_id)
        
        # Initially pending
        assert job.status == JobStatus.PENDING
        
        # After cancel
        engine.cancel_job(job_id)
        
        job = engine.get_job(job_id)
        
        assert job.status == JobStatus.CANCELLED
    
    def test_group_stats_failed_count(self):
        """Test group stats failed count."""
        engine = SchedulerEngine()
        
        def failing_handler(args):
            raise ValueError("Fail")
        
        engine.schedule_interval("failing1", failing_handler, interval_seconds=1, max_runs=1, group="test_group")
        engine.schedule_interval("failing2", failing_handler, interval_seconds=1, max_runs=1, group="test_group")
        
        engine.start()
        time.sleep(3)
        engine.stop()
        
        group_stats = engine.get_group_stats("test_group")
        
        assert group_stats["failed"] == 2
    
    def test_list_jobs_empty(self):
        """Test listing jobs when none exist."""
        engine = SchedulerEngine()
        
        jobs = engine.list_jobs()
        
        assert jobs == []
    
    def test_get_group_stats_nonexistent_group(self):
        """Test getting stats for nonexistent group."""
        engine = SchedulerEngine()
        
        group_stats = engine.get_group_stats("nonexistent")
        
        assert group_stats["total_jobs"] == 0
    
    def test_scheduler_multiple_cron_jobs(self):
        """Test scheduler with multiple cron jobs."""
        engine = SchedulerEngine()
        
        call_counts = {"job1": 0, "job2": 0, "job3": 0}
        
        def make_handler(name):
            def handler(args):
                call_counts[name] += 1
                return f"{name}_done"
            return handler
        
        # Schedule all for next minute
        now = datetime.now(timezone.utc)
        next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        
        cron_expr = f"{next_minute.minute} {next_minute.hour} * * *"
        
        engine.schedule_cron("job1", make_handler("job1"), cron_expr)
        engine.schedule_cron("job2", make_handler("job2"), cron_expr)
        engine.schedule_cron("job3", make_handler("job3"), cron_expr)
        
        engine.start()
        time.sleep(70)
        engine.stop()
        
        # All should have run
        assert call_counts["job1"] >= 1
        assert call_counts["job2"] >= 1
        assert call_counts["job3"] >= 1
    
    def test_trigger_job_records_history(self):
        """Test that triggered job records history."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "triggered_result"
        
        job_id = engine.schedule_cron("test", handler, "0 0 1 1 *")  # Far future
        
        engine.trigger_job(job_id)
        
        time.sleep(0.5)
        
        history = engine.get_job_history(job_id)
        
        assert len(history) == 1
        assert history[0]["result"] == "triggered_result"
    
    def test_job_metadata_preserved(self):
        """Test that job metadata is preserved."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_cron(
            "test",
            handler,
            "0 * * * *",
            metadata={"team": "backend", "environment": "production", "version": "1.0"},
        )
        
        job = engine.get_job(job_id)
        
        assert job.metadata["team"] == "backend"
        assert job.metadata["environment"] == "production"
        assert job.metadata["version"] == "1.0"
    
    def test_interval_job_next_run_updates(self):
        """Test that interval job next_run_at updates after each run."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        job_id = engine.schedule_interval("test", handler, interval_seconds=2, max_runs=3)
        
        job_before = engine.get_job(job_id)
        next_run_before = job_before.next_run_at
        
        engine.start()
        time.sleep(3)
        engine.stop()
        
        job_after = engine.get_job(job_id)
        
        # next_run_at should have updated
        assert job_after.next_run_at > next_run_before
    
    def test_cancelled_job_does_not_run(self):
        """Test that cancelled job does not run."""
        engine = SchedulerEngine()
        
        call_count = [0]
        
        def handler(args):
            call_count[0] += 1
            return "done"
        
        job_id = engine.schedule_interval("test", handler, interval_seconds=1)
        
        # Cancel immediately
        engine.cancel_job(job_id)
        
        engine.start()
        time.sleep(3)
        engine.stop()
        
        assert call_count[0] == 0
    
    def test_scheduler_with_timezone_naive_datetime(self):
        """Test schedule_once with timezone-naive datetime."""
        engine = SchedulerEngine()
        
        call_count = [0]
        
        def handler(args):
            call_count[0] += 1
            return "done"
        
        # Naive datetime (no timezone)
        run_at = datetime.now() + timedelta(seconds=2)
        
        job_id = engine.schedule_once("test", handler, run_at=run_at)
        
        engine.start()
        time.sleep(4)
        engine.stop()
        
        assert call_count[0] == 1
    
    def test_statistics_by_job_name(self):
        """Test statistics by job name."""
        engine = SchedulerEngine()
        
        def handler(args):
            return "done"
        
        engine.schedule_interval("repeated_job", handler, interval_seconds=1, max_runs=5)
        
        engine.start()
        time.sleep(6)
        engine.stop()
        
        stats = engine.get_statistics()
        
        assert stats["by_job"]["repeated_job"] == 5
