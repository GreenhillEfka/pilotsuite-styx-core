"""Automation Analytics — Execution History, Rule Patterns, Effectiveness Metrics — Slice 54."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class AutomationStatus(str, Enum):
    """Automation-Status für Analytics."""
    TRIGGERED = "triggered"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class AutomationTriggerType(str, Enum):
    """Trigger-Typen für Automation-Analytics."""
    STATE_CHANGE = "state_change"
    TIME = "time"
    SUN_EVENT = "sun_event"
    PRESENCE = "presence"
    VOICE = "voice"
    PROPOSAL = "proposal"
    SCENE = "scene"
    ROUTINE = "routine"
    MANUAL = "manual"
    WEBHOOK = "webhook"


@dataclass(frozen=True)
class AutomationExecutionEntryV1:
    """Einzelner Automation-Execution-Eintrag für Historie."""

    entry_id: str
    automation_id: str
    automation_name: str
    trigger_type: str  # AutomationTriggerType
    status: str  # AutomationStatus
    zone_id: Optional[str]
    zone_name: Optional[str]
    module_id: Optional[str]
    module_name: Optional[str]
    triggered_at: str  # ISO-8601
    started_at: Optional[str]  # ISO-8601
    completed_at: Optional[str]  # ISO-8601
    duration_seconds: Optional[float]
    error_message: Optional[str]
    actions_executed: int
    actions_failed: int
    entities_affected: int
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class AutomationExecutionHistoryV1:
    """Aggregierte Automation-Execution-Historie."""

    entries: List[AutomationExecutionEntryV1]
    total_executions: int
    total_completed: int
    total_failed: int
    total_skipped: int
    total_blocked: int
    avg_duration_seconds: Optional[float]
    revision: int
    latest_change_at: str
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None


@dataclass(frozen=True)
class AutomationRulePatternEntryV1:
    """Automation-Pattern für eine einzelne Rule."""

    automation_id: str
    automation_name: str
    trigger_type: str
    total_executions: int
    completed_count: int
    failed_count: int
    skipped_count: int
    success_rate: float  # 0.0–1.0
    avg_duration_seconds: Optional[float]
    avg_actions_executed: Optional[float]
    avg_entities_affected: Optional[float]
    failure_rate: float  # 0.0–1.0
    last_execution_at: Optional[str]
    executions_last_24_hours: int
    executions_last_7_days: int
    most_common_trigger: Optional[str]
    peak_execution_hour: Optional[int]  # 0-23
    zones_affected: List[str]


@dataclass(frozen=True)
class AutomationRulePatternsV1:
    """Rule-spezifische Automation-Patterns."""

    patterns: List[AutomationRulePatternEntryV1]
    total_automations: int
    automations_with_executions: int
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class AutomationEffectivenessMetricsV1:
    """Automation-Effectiveness-Metriken."""

    total_executions_analyzed: int
    executions_by_status: Dict[str, int]  # status → count
    executions_by_trigger: Dict[str, int]  # trigger_type → count
    overall_success_rate: float  # 0.0–1.0
    overall_failure_rate: float  # 0.0–1.0
    avg_duration_by_trigger: Dict[str, float]  # trigger_type → avg seconds
    failure_rate_by_trigger: Dict[str, float]  # trigger_type → failure rate
    automations_with_regular_executions: int  # >10 executions
    automations_with_rare_executions: int  # <=10 executions
    peak_automation_time: Optional[str]  # morning/day/evening/night
    reliability_score: float  # 0.0–1.0 composite score
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class AutomationAnalyticsSummaryV1:
    """Zusammenfassung aller Automation-Analytics."""

    usage: AutomationExecutionHistoryV1
    patterns: AutomationRulePatternsV1
    effectiveness: AutomationEffectivenessMetricsV1
    summary_revision: int
    latest_change_at: str
