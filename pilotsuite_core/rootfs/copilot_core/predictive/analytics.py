"""Predictive Analytics Read Models — Slice 48.

Predictive-Usage-Historie, Zone-spezifische Predictive-Patterns und Predictive-Effectiveness-Metriken
aus derselben Predictive-/Proposal-Wahrheit materialisieren.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass(frozen=True)
class PredictiveUsageEntryV1:
    """Einzelner Predictive-Usage-Eintrag für Historie."""

    proposal_id: str
    pattern_id: str
    zone_id: str
    module_id: str
    prediction_type: str  # time_based | presence_based | calendar_based | seasonal | behavioral
    confidence_score: float  # 0.0–1.0
    outcome: str  # accepted | rejected | expired | pending
    accepted_at: Optional[str]  # ISO-8601 oder None
    rejected_at: Optional[str]  # ISO-8601 oder None
    expired_at: Optional[str]  # ISO-8601 oder None
    feedback: Optional[str]  # User feedback bei rejection
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class PredictiveUsageHistoryV1:
    """Aggregierte Predictive-Usage-Historie über alle Zonen."""

    entries: List[PredictiveUsageEntryV1]
    total_proposals: int
    total_accepted: int
    total_rejected: int
    total_expired: int
    total_pending: int
    acceptance_rate: float  # 0.0–1.0
    avg_confidence_score: Optional[float]
    revision: int
    latest_change_at: str
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None


@dataclass(frozen=False)
class PredictiveZonePatternEntryV1:
    """Predictive-Pattern für eine einzelne Zone."""

    zone_id: str
    zone_name: Optional[str]
    total_proposals: int
    accepted_count: int
    rejected_count: int
    expired_count: int
    acceptance_rate: float  # 0.0–1.0
    avg_confidence_score: Optional[float]
    most_common_prediction_type: str  # time_based | presence_based | calendar_based | etc.
    last_proposal_at: Optional[str]
    proposals_last_7_days: int
    proposals_last_30_days: int
    dominant_pattern_ids: List[str]  # Top patterns by occurrence
    revision: int = 0


@dataclass(frozen=True)
class PredictiveZonePatternsV1:
    """Zone-spezifische Predictive-Patterns."""

    patterns: List[PredictiveZonePatternEntryV1]
    total_zones: int
    zones_with_proposals: int
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class PredictiveEffectivenessMetricsV1:
    """Predictive-Effectiveness-Metriken."""

    total_proposals_analyzed: int
    high_confidence_proposals: int  # confidence >= 0.8
    high_confidence_acceptance_rate: float  # 0.0–1.0
    low_confidence_proposals: int  # confidence < 0.4
    low_confidence_acceptance_rate: float  # 0.0–1.0
    avg_time_to_accept_minutes: Optional[float]  # avg Zeit von Proposal bis Accept
    avg_time_to_reject_minutes: Optional[float]  # avg Zeit von Proposal bis Reject
    pattern_reinforcement_count: int  # Wie oft Patterns durch Accept verstärkt
    pattern_degradation_count: int  # Wie oft Patterns durch Reject geschwächt
    seasonal_adaptation_events: int  # Wie oft Seasonal-Adaptation ausgelöst
    effectiveness_score: float  # 0.0–1.0 composite score
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class PredictiveAnalyticsSummaryV1:
    """Zusammenfassung aller Predictive-Analytics."""

    usage: PredictiveUsageHistoryV1
    patterns: PredictiveZonePatternsV1
    effectiveness: PredictiveEffectivenessMetricsV1
    summary_revision: int
    latest_change_at: str


@dataclass
class PredictiveTrendEntryV1:
    """Einzelner Trend-Eintrag für Zeitreihen."""

    period: str  # hourly | daily | weekly
    timestamp: str  # ISO-8601
    proposals_count: int
    accepted_count: int
    rejected_count: int
    avg_confidence: float
    acceptance_rate: float


@dataclass(frozen=True)
class PredictiveTrendsV1:
    """Predictive-Trends über Zeit."""

    trends: List[PredictiveTrendEntryV1]
    period: str
    total_periods: int
    trend_direction: str  # improving | declining | stable
    trend_slope: float  # rate of change
    revision: int
    latest_change_at: str
