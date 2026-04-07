"""
Canonical Insight Contracts for PilotSuite Core.

Insights are actionable, prioritized findings derived from analytics data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class InsightCategory(str, Enum):
    """Categories for insights."""
    PERFORMANCE = "performance"
    ANOMALY = "anomaly"
    TREND = "trend"
    OPTIMIZATION = "optimization"
    HEALTH = "health"
    USAGE = "usage"
    PREDICTION = "prediction"
    EFFICIENCY = "efficiency"


class InsightSeverity(str, Enum):
    """Severity levels for insights."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class InsightStatus(str, Enum):
    """Lifecycle status for insights."""
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class InsightSource(str, Enum):
    """Analytics sources that generate insights."""
    ZONE_TRUTH = "zone_truth"
    PROPOSAL_LIFECYCLE = "proposal_lifecycle"
    ACTION_CLOSURE = "action_closure"
    BRAIN_NEURON = "brain_neuron"
    ENERGY = "energy"
    PREDICTIVE = "predictive"
    MUSIC_MEDIA = "music_media"
    CAMERA = "camera"
    WEATHER = "weather"
    NOTIFICATIONS = "notifications"
    SCHEDULER = "scheduler"
    AUTOMATION = "automation"
    HEALTH = "health"
    MODULE = "module"
    VOICE = "voice"
    ZONE_PRESENCE = "zone_presence"


@dataclass
class InsightV1:
    """
    Canonical insight derived from analytics data.
    
    An insight represents an actionable finding with clear category,
    severity, and source attribution.
    """
    insight_id: str
    category: InsightCategory
    severity: InsightSeverity
    status: InsightStatus
    source: InsightSource
    title: str
    description: str
    recommendation: str
    created_at: datetime
    updated_at: datetime
    zone_id: Optional[str] = None
    module_id: Optional[str] = None
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    baseline_value: Optional[float] = None
    confidence: float = 0.0
    evidence: dict = field(default_factory=dict)
    related_insight_ids: list = field(default_factory=list)
    revision: int = 1
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "insight_id": self.insight_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "source": self.source.value,
            "title": self.title,
            "description": self.description,
            "recommendation": self.recommendation,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "baseline_value": self.baseline_value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "related_insight_ids": self.related_insight_ids,
            "revision": self.revision,
        }


@dataclass
class InsightSummaryV1:
    """
    Summary of insights with counts and revision tracking.
    """
    total_insights: int
    by_category: dict
    by_severity: dict
    by_status: dict
    by_source: dict
    new_count: int
    acknowledged_count: int
    in_progress_count: int
    resolved_count: int
    dismissed_count: int
    critical_count: int
    high_count: int
    latest_revision: int
    latest_change_at: datetime
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_insights": self.total_insights,
            "by_category": self.by_category,
            "by_severity": self.by_severity,
            "by_status": self.by_status,
            "by_source": self.by_source,
            "new_count": self.new_count,
            "acknowledged_count": self.acknowledged_count,
            "in_progress_count": self.in_progress_count,
            "resolved_count": self.resolved_count,
            "dismissed_count": self.dismissed_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "latest_revision": self.latest_revision,
            "latest_change_at": self.latest_change_at.isoformat(),
        }


@dataclass
class InsightDeltaV1:
    """
    Delta information for insight polling.
    """
    has_changes: bool
    revision: int
    changes_since_revision: list
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "has_changes": self.has_changes,
            "revision": self.revision,
            "changes_since_revision": self.changes_since_revision,
        }
