"""Scheduler Analytics Contract Tests — Slice 53."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from copilot_core.scheduler.analytics import (
    SchedulerJobExecutionEntryV1,
    SchedulerJobExecutionHistoryV1,
    SchedulerJobPatternEntryV1,
    SchedulerJobPatternsV1,
    SchedulerEffectivenessMetricsV1,
    JobStatus,
    JobType,
)
from copilot_core.scheduler.analytics_store import SchedulerAnalyticsStore, get_scheduler_analytics_store


class TestSchedulerJobExecutionEntryV1:
    """Tests für SchedulerJobExecutionEntryV1."""

    def test_entry_creation(self):
        """Entry-Erstellung mit allen Feldern."""
        now = datetime.now(timezone.utc).isoformat()
        entry = SchedulerJobExecutionEntryV1(
            entry_id="entry_001",
            job_id="job_001",
            job_name="Test Job",
            job_type="cron",
            status="completed",
            scheduled_at=now,
            started_at=now,
            completed_at=now,
            duration_seconds=5.5,
            error_message=None,
            retry_count=0,
            triggered_by="cron",
            zone_id="living",
            zone_name="Wohnbereich",
        )

        assert entry.entry_id == "entry_001"
        assert entry.job_id == "job_001"
        assert entry.job_type == "cron"
        assert entry.status == "completed"
        assert entry.duration_seconds == 5.5


class TestSchedulerAnalyticsStore:
    """Tests für SchedulerAnalyticsStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Store mit temporärer DB."""
        db_path = tmp_path / "scheduler_analytics.db"
        return SchedulerAnalyticsStore(db_path=str(db_path))

    def test_add_execution_entry(self, store):
        """Execution-Eintrag hinzufügen."""
        now = datetime.now(timezone.utc).isoformat()
        entry = SchedulerJobExecutionEntryV1(
            entry_id="entry_001",
            job_id="job_001",
            job_name="Test Job",
            job_type="cron",
            status="completed",
            scheduled_at=now,
            started_at=now,
            completed_at=now,
            duration_seconds=5.5,
            error_message=None,
            retry_count=0,
            triggered_by="cron",
            zone_id="living",
            zone_name="Wohnbereich",
        )

        store.add_execution_entry(entry)

        # Verify entry was added
        history = store.build_execution_history(job_id="job_001")
        assert len(history.entries) == 1
        assert history.entries[0].entry_id == "entry_001"
        assert history.total_completed == 1

    def test_build_execution_history(self, store):
        """Execution-Historie aufbauen."""
        now = datetime.now(timezone.utc)

        # Add multiple entries
        for i in range(5):
            entry = SchedulerJobExecutionEntryV1(
                entry_id=f"entry_{i:03d}",
                job_id="job_001",
                job_name="Test Job",
                job_type="cron",
                status="completed",
                scheduled_at=now.isoformat(),
                started_at=now.isoformat(),
                completed_at=now.isoformat(),
                duration_seconds=5.0 + i,
                error_message=None,
                retry_count=0,
                triggered_by="cron",
                zone_id="living",
                zone_name="Wohnbereich",
            )
            store.add_execution_entry(entry)

        history = store.build_execution_history(job_id="job_001")

        assert history.total_executions == 5
        assert history.total_completed == 5
        assert history.total_failed == 0
        assert history.revision == 5

    def test_build_execution_history_with_filters(self, store):
        """Execution-Historie mit Filtern."""
        now = datetime.now(timezone.utc)

        # Add entries for different jobs and statuses
        for job_id in ["job_001", "job_002", "job_003"]:
            for status in ["completed", "failed"]:
                entry = SchedulerJobExecutionEntryV1(
                    entry_id=f"entry_{job_id}_{status}",
                    job_id=job_id,
                    job_name=f"Job {job_id}",
                    job_type="cron",
                    status=status,
                    scheduled_at=now.isoformat(),
                    started_at=now.isoformat(),
                    completed_at=now.isoformat() if status == "completed" else None,
                    duration_seconds=5.0 if status == "completed" else None,
                    error_message="Error" if status == "failed" else None,
                    retry_count=1 if status == "failed" else 0,
                    triggered_by="cron",
                    zone_id="living",
                    zone_name="Wohnbereich",
                )
                store.add_execution_entry(entry)

        # Filter by job_id
        job1_history = store.build_execution_history(job_id="job_001")
        assert job1_history.total_executions == 2
        assert job1_history.entries[0].job_id == "job_001"

        # Filter by status
        failed_history = store.build_execution_history(status="failed")
        assert failed_history.total_executions == 3
        assert failed_history.total_failed == 3

    def test_build_job_patterns(self, store):
        """Job-Patterns aufbauen."""
        now = datetime.now(timezone.utc)

        # Add multiple entries for job_001
        for i in range(10):
            entry = SchedulerJobExecutionEntryV1(
                entry_id=f"entry_job1_{i}",
                job_id="job_001",
                job_name="Test Job 1",
                job_type="cron",
                status="completed",
                scheduled_at=now.isoformat(),
                started_at=now.isoformat(),
                completed_at=now.isoformat(),
                duration_seconds=5.0,
                error_message=None,
                retry_count=0,
                triggered_by="cron",
                zone_id="living",
                zone_name="Wohnbereich",
            )
            store.add_execution_entry(entry)

        # Add entries for job_002
        for i in range(3):
            entry = SchedulerJobExecutionEntryV1(
                entry_id=f"entry_job2_{i}",
                job_id="job_002",
                job_name="Test Job 2",
                job_type="interval",
                status="failed",
                scheduled_at=now.isoformat(),
                started_at=now.isoformat(),
                completed_at=None,
                duration_seconds=None,
                error_message="Test error",
                retry_count=1,
                triggered_by="interval",
                zone_id="kitchen",
                zone_name="Küche",
            )
            store.add_execution_entry(entry)

        patterns = store.build_job_patterns()

        assert patterns.total_jobs == 2
        assert patterns.jobs_with_executions == 2

        job1_pattern = next(p for p in patterns.patterns if p.job_id == "job_001")
        assert job1_pattern.total_executions == 10
        assert job1_pattern.success_rate == 1.0
        assert job1_pattern.failure_rate == 0.0
        assert job1_pattern.most_common_status == "completed"

    def test_get_effectiveness_metrics(self, store):
        """Effectiveness-Metriken berechnen."""
        now = datetime.now(timezone.utc)

        # Add diverse executions
        job_types = ["cron", "interval", "one_shot"]
        statuses = ["completed", "failed", "skipped"]
        for job_type in job_types:
            for status in statuses:
                for i in range(3):
                    entry = SchedulerJobExecutionEntryV1(
                        entry_id=f"entry_{job_type}_{status}_{i}",
                        job_id=f"job_{job_type}_{i}",
                        job_name=f"Job {job_type} {i}",
                        job_type=job_type,
                        status=status,
                        scheduled_at=now.isoformat(),
                        started_at=now.isoformat(),
                        completed_at=now.isoformat() if status == "completed" else None,
                        duration_seconds=5.0 if status == "completed" else None,
                        error_message="Error" if status == "failed" else None,
                        retry_count=1 if status == "failed" else 0,
                        triggered_by=job_type,
                        zone_id="living",
                        zone_name="Wohnbereich",
                    )
                    store.add_execution_entry(entry)

        metrics = store.get_effectiveness_metrics()

        assert metrics.total_executions_analyzed == 27  # 3 types * 3 statuses * 3 iterations
        assert "completed" in metrics.executions_by_status
        assert "cron" in metrics.executions_by_type
        assert 0.0 <= metrics.overall_success_rate <= 1.0
        assert 0.0 <= metrics.overall_failure_rate <= 1.0
        assert 0.0 <= metrics.reliability_score <= 1.0

    def test_revision_tracking(self, store):
        """Revision-Tracking bei Änderungen."""
        now = datetime.now(timezone.utc)

        initial_revision = store._revision

        entry = SchedulerJobExecutionEntryV1(
            entry_id="entry_001",
            job_id="job_001",
            job_name="Test Job",
            job_type="cron",
            status="completed",
            scheduled_at=now.isoformat(),
            started_at=now.isoformat(),
            completed_at=now.isoformat(),
            duration_seconds=5.0,
            error_message=None,
            retry_count=0,
            triggered_by="cron",
            zone_id="living",
            zone_name="Wohnbereich",
        )
        store.add_execution_entry(entry)

        assert store._revision == initial_revision + 1

    def test_build_summary(self, store):
        """Analytics Summary aufbauen."""
        now = datetime.now(timezone.utc)

        # Add some data
        for i in range(5):
            entry = SchedulerJobExecutionEntryV1(
                entry_id=f"entry_{i}",
                job_id="job_001",
                job_name="Test Job",
                job_type="cron",
                status="completed",
                scheduled_at=now.isoformat(),
                started_at=now.isoformat(),
                completed_at=now.isoformat(),
                duration_seconds=5.0,
                error_message=None,
                retry_count=0,
                triggered_by="cron",
                zone_id="living",
                zone_name="Wohnbereich",
            )
            store.add_execution_entry(entry)

        summary = store.build_summary()

        assert summary.usage.total_executions == 5
        assert summary.patterns.jobs_with_executions >= 1
        assert summary.effectiveness.total_executions_analyzed == 5
        assert summary.summary_revision == summary.usage.revision


class TestJobStatus:
    """Tests für JobStatus Enum."""

    def test_statuses(self):
        """Alle Status verfügbar."""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.RUNNING == "running"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.SKIPPED == "skipped"
        assert JobStatus.CANCELLED == "cancelled"


class TestJobType:
    """Tests für JobType Enum."""

    def test_types(self):
        """Alle Typen verfügbar."""
        assert JobType.CRON == "cron"
        assert JobType.INTERVAL == "interval"
        assert JobType.ONE_SHOT == "one_shot"
        assert JobType.TRIGGER == "trigger"
        assert JobType.MAINTENANCE == "maintenance"
        assert JobType.NOTIFICATION == "notification"
        assert JobType.SYNC == "sync"
        assert JobType.BACKUP == "backup"


class TestSchedulerAnalyticsStoreIntegration:
    """Integrationstests für SchedulerAnalyticsStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Store mit temporärer DB."""
        db_path = tmp_path / "scheduler_analytics.db"
        return SchedulerAnalyticsStore(db_path=str(db_path))

    def test_full_workflow(self, store):
        """Kompletter Workflow: Add → History → Patterns → Metrics → Summary."""
        now = datetime.now(timezone.utc)

        # Add diverse executions
        for job_type in ["cron", "interval"]:
            for status in ["completed", "failed"]:
                for i in range(2):
                    entry = SchedulerJobExecutionEntryV1(
                        entry_id=f"entry_{job_type}_{status}_{i}",
                        job_id=f"job_{job_type}_{i}",
                        job_name=f"Job {job_type} {i}",
                        job_type=job_type,
                        status=status,
                        scheduled_at=now.isoformat(),
                        started_at=now.isoformat(),
                        completed_at=now.isoformat() if status == "completed" else None,
                        duration_seconds=5.0 if status == "completed" else None,
                        error_message="Error" if status == "failed" else None,
                        retry_count=1 if status == "failed" else 0,
                        triggered_by=job_type,
                        zone_id="living",
                        zone_name="Wohnbereich",
                    )
                    store.add_execution_entry(entry)

        # Build all read models
        history = store.build_execution_history()
        patterns = store.build_job_patterns()
        metrics = store.get_effectiveness_metrics()
        summary = store.build_summary()

        # Verify consistency
        assert history.total_executions == 8  # 2 types * 2 statuses * 2 iterations
        assert patterns.total_jobs == 4
        assert metrics.total_executions_analyzed == 8
        assert summary.usage.total_executions == 8
        assert summary.patterns.jobs_with_executions == 4

    def test_time_range_filtering(self, store):
        """Zeitbereichs-Filterung."""
        now = datetime.now(timezone.utc)

        # Add entries at different times
        for days_ago in [1, 3, 7, 14, 30]:
            entry = SchedulerJobExecutionEntryV1(
                entry_id=f"entry_{days_ago}d",
                job_id="job_001",
                job_name="Test Job",
                job_type="cron",
                status="completed",
                scheduled_at=(now - timedelta(days=days_ago)).isoformat(),
                started_at=(now - timedelta(days=days_ago)).isoformat(),
                completed_at=(now - timedelta(days=days_ago)).isoformat(),
                duration_seconds=5.0,
                error_message=None,
                retry_count=0,
                triggered_by="cron",
                zone_id="living",
                zone_name="Wohnbereich",
            )
            store.add_execution_entry(entry)

        # Last 7 days - should include 1, 3, 7 days ago entries
        start_7d = (now - timedelta(days=7)).isoformat()
        history_7d = store.build_execution_history(time_range_start=start_7d)
        assert history_7d.total_executions >= 3  # At least 1, 3, 7 days ago

        # Last 30 days - should include all 5 entries
        start_30d = (now - timedelta(days=30)).isoformat()
        history_30d = store.build_execution_history(time_range_start=start_30d)
        assert history_30d.total_executions == 5


class TestGetSchedulerAnalyticsStore:
    """Tests für Singleton-Getter."""

    def test_singleton_behavior(self):
        """Singleton verhält sich korrekt."""
        store1 = get_scheduler_analytics_store()
        store2 = get_scheduler_analytics_store()

        # Should be same instance (or at least same type)
        assert type(store1) == type(store2)
