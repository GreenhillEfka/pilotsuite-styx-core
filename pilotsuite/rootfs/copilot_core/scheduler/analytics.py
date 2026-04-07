"""Scheduler Analytics — Job Execution History, Job Patterns, Effectiveness Metrics — Slice 53."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class JobStatus(str, Enum):
    """Job-Status für Scheduler-Analytics."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Job-Typen für Scheduler-Analytics."""
    CRON = "cron"
    INTERVAL = "interval"
    ONE_SHOT = "one_shot"
    TRIGGER = "trigger"
    MAINTENANCE = "maintenance"
    NOTIFICATION = "notification"
    SYNC = "sync"
    BACKUP = "backup"


@dataclass(frozen=True)
class SchedulerJobExecutionEntryV1:
    """Einzelner Scheduler-Job-Execution-Eintrag für Historie."""

    entry_id: str
    job_id: str
    job_name: str
    job_type: str  # JobType
    status: str  # JobStatus
    scheduled_at: str  # ISO-8601
    started_at: Optional[str]  # ISO-8601
    completed_at: Optional[str]  # ISO-8601
    duration_seconds: Optional[float]
    error_message: Optional[str]
    retry_count: int
    triggered_by: Optional[str]  # cron/interval/manual/trigger
    zone_id: Optional[str]
    zone_name: Optional[str]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class SchedulerJobExecutionHistoryV1:
    """Aggregierte Scheduler-Job-Execution-Historie."""

    entries: List[SchedulerJobExecutionEntryV1]
    total_executions: int
    total_completed: int
    total_failed: int
    total_skipped: int
    total_cancelled: int
    avg_duration_seconds: Optional[float]
    revision: int
    latest_change_at: str
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None


@dataclass(frozen=True)
class SchedulerJobPatternEntryV1:
    """Scheduler-Pattern für einen einzelnen Job."""

    job_id: str
    job_name: str
    job_type: str
    total_executions: int
    completed_count: int
    failed_count: int
    skipped_count: int
    success_rate: float  # 0.0–1.0
    avg_duration_seconds: Optional[float]
    min_duration_seconds: Optional[float]
    max_duration_seconds: Optional[float]
    failure_rate: float  # 0.0–1.0
    last_execution_at: Optional[str]
    next_scheduled_at: Optional[str]
    executions_last_24_hours: int
    executions_last_7_days: int
    most_common_status: Optional[str]
    peak_execution_hour: Optional[int]  # 0-23


@dataclass(frozen=True)
class SchedulerJobPatternsV1:
    """Job-spezifische Scheduler-Patterns."""

    patterns: List[SchedulerJobPatternEntryV1]
    total_jobs: int
    jobs_with_executions: int
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class SchedulerEffectivenessMetricsV1:
    """Scheduler-Effectiveness-Metriken."""

    total_executions_analyzed: int
    executions_by_status: Dict[str, int]  # status → count
    executions_by_type: Dict[str, int]  # job_type → count
    overall_success_rate: float  # 0.0–1.0
    overall_failure_rate: float  # 0.0–1.0
    avg_duration_by_job_type: Dict[str, float]  # job_type → avg seconds
    failure_rate_by_job_type: Dict[str, float]  # job_type → failure rate
    jobs_with_regular_executions: int  # >10 executions
    jobs_with_rare_executions: int  # <=10 executions
    peak_execution_time: Optional[str]  # morning/day/evening/night
    reliability_score: float  # 0.0–1.0 composite score
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class SchedulerAnalyticsSummaryV1:
    """Zusammenfassung aller Scheduler-Analytics."""

    usage: SchedulerJobExecutionHistoryV1
    patterns: SchedulerJobPatternsV1
    effectiveness: SchedulerEffectivenessMetricsV1
    summary_revision: int
    latest_change_at: str
