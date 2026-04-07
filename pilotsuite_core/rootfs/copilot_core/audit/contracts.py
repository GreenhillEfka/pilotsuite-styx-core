"""Audit Log / Behavioral Trail Contracts — Slice 69"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class AuditEventType(str, Enum):
    """Canonical audit event types for behavioral trail."""
    PROPOSAL_SUGGESTED = "proposal_suggested"
    PROPOSAL_ACCEPTED = "proposal_accepted"
    PROPOSAL_REJECTED = "proposal_rejected"
    PROPOSAL_SNOOZED = "proposal_snoozed"
    ACTION_INTENT_CREATED = "action_intent_created"
    ACTION_INTENT_EXECUTED = "action_intent_executed"
    ACTION_INTENT_FAILED = "action_intent_failed"
    ACTION_CLOSURE_CREATED = "action_closure_created"
    ACTION_CLOSURE_FEEDBACK = "action_closure_feedback"
    ACTION_CLOSURE_EXECUTION = "action_closure_execution"
    NOTIFICATION_SENT = "notification_sent"
    NOTIFICATION_DELIVERED = "notification_delivered"
    NOTIFICATION_FAILED = "notification_failed"
    HOLD_SET = "hold_set"
    HOLD_RELEASED = "hold_released"
    HOLD_EXPIRED = "hold_expired"
    ZONE_SYNC = "zone_sync"
    MODULE_EXECUTION = "module_execution"
    VOICE_COMMAND = "voice_command"
    SCHEDULER_JOB = "scheduler_job"
    HEALTH_CHECK = "health_check"
    CONFIG_CHANGE = "config_change"
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"


class AuditOutcome(str, Enum):
    """Outcome classification for audit events."""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditLogEntryV1:
    """Canonical audit log entry for behavioral trail."""
    entry_id: str
    event_type: str  # AuditEventType value
    event_at: str  # ISO-8601 timestamp
    outcome: str  # AuditOutcome value
    severity: str  # AuditSeverity value
    subject: str  # Human-readable summary
    
    # Context (optional)
    zone_id: Optional[str] = None
    module_id: Optional[str] = None
    proposal_id: Optional[str] = None
    action_closure_id: Optional[str] = None
    notification_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Payload
    details: dict = field(default_factory=dict)  # Structured event data
    metadata: dict = field(default_factory=dict)  # Technical metadata
    
    # Traceability
    revision: int = 1
    parent_entry_id: Optional[str] = None  # Link to causally prior event
    correlation_id: Optional[str] = None  # Group related events
    
    # Performance
    duration_ms: Optional[float] = None
    created_at: Optional[str] = None  # Storage timestamp
    
    @classmethod
    def from_event(
        cls,
        entry_id: str,
        event_type: AuditEventType,
        outcome: AuditOutcome,
        severity: AuditSeverity,
        subject: str,
        details: Optional[dict] = None,
        metadata: Optional[dict] = None,
        zone_id: Optional[str] = None,
        module_id: Optional[str] = None,
        proposal_id: Optional[str] = None,
        action_closure_id: Optional[str] = None,
        notification_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        parent_entry_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ) -> "AuditLogEntryV1":
        """Factory for creating audit entries from event data."""
        now = datetime.utcnow().isoformat() + "Z"
        return cls(
            entry_id=entry_id,
            event_type=event_type.value,
            event_at=now,
            outcome=outcome.value,
            severity=severity.value,
            subject=subject,
            details=details or {},
            metadata=metadata or {},
            zone_id=zone_id,
            module_id=module_id,
            proposal_id=proposal_id,
            action_closure_id=action_closure_id,
            notification_id=notification_id,
            user_id=user_id,
            session_id=session_id,
            parent_entry_id=parent_entry_id,
            correlation_id=correlation_id,
            duration_ms=duration_ms,
            created_at=now,
        )


@dataclass
class AuditLogSummaryV1:
    """Aggregated audit log summary for dashboards/APIs."""
    total_entries: int
    revision: int
    latest_entry_at: Optional[str]
    
    # Counts by outcome
    success_count: int = 0
    failure_count: int = 0
    pending_count: int = 0
    cancelled_count: int = 0
    skipped_count: int = 0
    
    # Counts by severity
    debug_count: int = 0
    info_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    critical_count: int = 0
    
    # Counts by event type (top-level aggregation)
    event_type_counts: dict = field(default_factory=dict)
    
    # Recent entries (for quick preview)
    recent_entries: list = field(default_factory=list)
    
    # Time range
    earliest_entry_at: Optional[str] = None
    
    # Filters applied
    zone_id: Optional[str] = None
    module_id: Optional[str] = None
    event_type: Optional[str] = None
    outcome: Optional[str] = None
    severity: Optional[str] = None
    since: Optional[str] = None
    until: Optional[str] = None


@dataclass
class AuditLogDeltaV1:
    """Delta response for incremental polling."""
    revision: int
    has_changes: bool
    new_entries: list = field(default_factory=list)
    changed_entries: list = field(default_factory=list)
    latest_entry_at: Optional[str] = None


@dataclass
class AuditExportV1:
    """Export format for audit logs (compliance/analysis)."""
    export_id: str
    generated_at: str
    format: str  # json, csv, ndjson
    filters: dict
    entry_count: int
    entries: list = field(default_factory=list)
    checksum: Optional[str] = None  # SHA-256 for integrity
