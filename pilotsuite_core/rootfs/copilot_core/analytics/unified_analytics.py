"""Unified Analytics Dashboard Surface — Slice 63."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .action_closure_analytics import ClosureAnalyticsStore
from .brain_analytics import BrainAnalyticsStore
from .chat_analytics import ChatAnalyticsStore
from .proposal_lifecycle_analytics import ProposalAnalyticsStore
from .zone_truth_analytics import ZoneAnalyticsStore


@dataclass
class AnalyticsModuleSummaryV1:
    """Summary for a single analytics module."""
    module: str
    total_events: int
    revision: int
    last_event_at: float | None
    health_score: float  # 0.0 - 1.0
    key_metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "total_events": self.total_events,
            "revision": self.revision,
            "last_event_at": self.last_event_at,
            "health_score": self.health_score,
            "key_metrics": self.key_metrics,
        }


@dataclass
class UnifiedAnalyticsDashboardV1:
    """Unified analytics dashboard across all modules."""
    generated_at: float
    global_revision: int
    time_range_days: int
    modules: list[AnalyticsModuleSummaryV1]
    overall_health_score: float
    total_events_all_modules: int
    zones_active: list[str]
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "global_revision": self.global_revision,
            "time_range_days": self.time_range_days,
            "modules": [m.to_dict() for m in self.modules],
            "overall_health_score": self.overall_health_score,
            "total_events_all_modules": self.total_events_all_modules,
            "zones_active": self.zones_active,
            "anomalies": self.anomalies,
            "recommendations": self.recommendations,
        }


class UnifiedAnalyticsDashboard:
    """Unified analytics dashboard aggregator."""

    def __init__(
        self,
        data_dir: Path | str,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize all analytics stores
        self.zone_store = ZoneAnalyticsStore(self.data_dir / "zone_truth_analytics.db")
        self.proposal_store = ProposalAnalyticsStore(self.data_dir / "proposal_lifecycle_analytics.db")
        self.closure_store = ClosureAnalyticsStore(self.data_dir / "action_closure_analytics.db")
        self.brain_store = BrainAnalyticsStore(self.data_dir / "brain_analytics.db")
        self.chat_store = ChatAnalyticsStore(self.data_dir / "chat_analytics.db")

    def _calculate_health_score(
        self,
        total_events: int,
        error_rate: float = 0.0,
        completion_rate: float = 1.0,
    ) -> float:
        """Calculate health score for a module."""
        if total_events == 0:
            return 0.5  # Neutral if no data

        # Base score from activity level (normalized)
        activity_score = min(1.0, total_events / 100.0)

        # Penalty for errors
        error_penalty = error_rate * 0.5

        # Bonus for completions
        completion_bonus = completion_rate * 0.3

        score = (activity_score * 0.4) + ((1.0 - error_penalty) * 0.4) + (completion_bonus * 0.2)
        return max(0.0, min(1.0, score))

    def _build_zone_summary(self, days_lookback: int) -> AnalyticsModuleSummaryV1:
        """Build zone truth analytics summary."""
        effectiveness = self.zone_store.get_effectiveness_metrics(days_lookback=days_lookback)

        return AnalyticsModuleSummaryV1(
            module="zone_truth",
            total_events=effectiveness.total_zones,
            revision=effectiveness.revision,
            last_event_at=None,
            health_score=self._calculate_health_score(
                total_events=effectiveness.total_zones,
                error_rate=effectiveness.overall_conflict_rate,
                completion_rate=effectiveness.overall_sync_success_rate,
            ),
            key_metrics={
                "sync_success_rate": effectiveness.overall_sync_success_rate,
                "conflict_rate": effectiveness.overall_conflict_rate,
                "stability_score": effectiveness.topology_stability_score,
                "zones_healthy": effectiveness.zones_healthy,
                "zones_with_conflicts": effectiveness.zones_with_conflicts,
            },
        )

    def _build_proposal_summary(self, days_lookback: int) -> AnalyticsModuleSummaryV1:
        """Build proposal lifecycle analytics summary."""
        effectiveness = self.proposal_store.get_effectiveness_metrics(days_lookback=days_lookback)

        return AnalyticsModuleSummaryV1(
            module="proposal_lifecycle",
            total_events=effectiveness.total_proposals,
            revision=effectiveness.revision,
            last_event_at=None,
            health_score=self._calculate_health_score(
                total_events=effectiveness.total_proposals,
                error_rate=effectiveness.overall_failure_rate,
                completion_rate=effectiveness.overall_acceptance_rate,
            ),
            key_metrics={
                "acceptance_rate": effectiveness.overall_acceptance_rate,
                "execution_rate": effectiveness.overall_execution_rate,
                "failure_rate": effectiveness.overall_failure_rate,
                "zones_with_proposals": effectiveness.zones_with_proposals,
            },
        )

    def _build_closure_summary(self, days_lookback: int) -> AnalyticsModuleSummaryV1:
        """Build action closure analytics summary."""
        effectiveness = self.closure_store.get_effectiveness_metrics(days_lookback=days_lookback)

        return AnalyticsModuleSummaryV1(
            module="action_closure",
            total_events=effectiveness.total_closures,
            revision=effectiveness.revision,
            last_event_at=None,
            health_score=self._calculate_health_score(
                total_events=effectiveness.total_closures,
                error_rate=effectiveness.overall_failure_rate,
                completion_rate=effectiveness.overall_completion_rate,
            ),
            key_metrics={
                "completion_rate": effectiveness.overall_completion_rate,
                "failure_rate": effectiveness.overall_failure_rate,
                "rejection_rate": effectiveness.overall_rejection_rate,
                "zones_with_closures": effectiveness.zones_with_closures,
            },
        )

    def _build_brain_summary(self, days_lookback: int) -> AnalyticsModuleSummaryV1:
        """Build brain/neuron analytics summary."""
        effectiveness = self.brain_store.get_effectiveness_metrics(days_lookback=days_lookback)

        return AnalyticsModuleSummaryV1(
            module="brain_neuron",
            total_events=effectiveness.total_events,
            revision=effectiveness.revision,
            last_event_at=None,
            health_score=self._calculate_health_score(
                total_events=effectiveness.total_events,
                error_rate=0.0,  # No explicit error tracking yet
                completion_rate=effectiveness.evaluation_rate,
            ),
            key_metrics={
                "total_neurons": effectiveness.total_neurons,
                "activation_rate": effectiveness.activation_rate,
                "evaluation_rate": effectiveness.evaluation_rate,
                "growth_rate": effectiveness.growth_rate,
                "zones_with_activity": effectiveness.zones_with_activity,
            },
        )

    def _build_chat_summary(self, days_lookback: int) -> AnalyticsModuleSummaryV1:
        """Build chat/RAG analytics summary."""
        effectiveness = self.chat_store.get_effectiveness_metrics(days_lookback=days_lookback)

        return AnalyticsModuleSummaryV1(
            module="chat_rag",
            total_events=effectiveness.total_events,
            revision=effectiveness.revision,
            last_event_at=None,
            health_score=self._calculate_health_score(
                total_events=effectiveness.total_events,
                error_rate=effectiveness.error_rate,
                completion_rate=effectiveness.response_rate,
            ),
            key_metrics={
                "total_sessions": effectiveness.total_sessions,
                "response_rate": effectiveness.response_rate,
                "rag_usage_rate": effectiveness.rag_usage_rate,
                "error_rate": effectiveness.error_rate,
                "zones_with_activity": effectiveness.zones_with_activity,
            },
        )

    def _detect_anomalies(self, modules: list[AnalyticsModuleSummaryV1]) -> list[dict[str, Any]]:
        """Detect anomalies across modules."""
        anomalies = []

        for module in modules:
            # Check for low health score
            if module.health_score < 0.3:
                anomalies.append({
                    "type": "low_health",
                    "module": module.module,
                    "severity": "high" if module.health_score < 0.2 else "medium",
                    "message": f"Module {module.module} has low health score ({module.health_score:.2f})",
                })

            # Check for high error rates
            if "error_rate" in module.key_metrics and module.key_metrics["error_rate"] > 0.2:
                anomalies.append({
                    "type": "high_error_rate",
                    "module": module.module,
                    "severity": "high" if module.key_metrics["error_rate"] > 0.5 else "medium",
                    "message": f"Module {module.module} has high error rate ({module.key_metrics['error_rate']:.2f})",
                })

            # Check for conflict rates in zone truth
            if module.module == "zone_truth" and module.key_metrics.get("conflict_rate", 0) > 0.3:
                anomalies.append({
                    "type": "high_conflict_rate",
                    "module": module.module,
                    "severity": "medium",
                    "message": f"Zone truth has high conflict rate ({module.key_metrics['conflict_rate']:.2f})",
                })

        return anomalies

    def _generate_recommendations(
        self,
        modules: list[AnalyticsModuleSummaryV1],
        anomalies: list[dict[str, Any]],
    ) -> list[str]:
        """Generate recommendations based on analytics."""
        recommendations = []

        # Check for modules with no activity
        inactive_modules = [m for m in modules if m.total_events == 0]
        if inactive_modules:
            recommendations.append(
                f"Consider enabling event tracking for: {', '.join(m.module for m in inactive_modules)}"
            )

        # Check for high error rates
        for anomaly in anomalies:
            if anomaly["type"] == "high_error_rate" and anomaly["severity"] == "high":
                recommendations.append(
                    f"Investigate high error rate in {anomaly['module']} module"
                )

        # Check for low acceptance rates
        proposal_module = next((m for m in modules if m.module == "proposal_lifecycle"), None)
        if proposal_module and proposal_module.key_metrics.get("acceptance_rate", 0) < 0.5:
            recommendations.append(
                "Review proposal quality - acceptance rate below 50%"
            )

        # Check for low completion rates
        closure_module = next((m for m in modules if m.module == "action_closure"), None)
        if closure_module and closure_module.key_metrics.get("completion_rate", 0) < 0.7:
            recommendations.append(
                "Investigate action completion bottlenecks - completion rate below 70%"
            )

        return recommendations

    def build_dashboard(
        self,
        days_lookback: int = 30,
    ) -> UnifiedAnalyticsDashboardV1:
        """Build unified analytics dashboard."""
        # Build summaries for all modules
        modules = [
            self._build_zone_summary(days_lookback),
            self._build_proposal_summary(days_lookback),
            self._build_closure_summary(days_lookback),
            self._build_brain_summary(days_lookback),
            self._build_chat_summary(days_lookback),
        ]

        # Calculate global revision (max of all modules)
        global_revision = max(m.revision for m in modules)

        # Calculate total events
        total_events = sum(m.total_events for m in modules)

        # Calculate overall health score (weighted average)
        if modules:
            overall_health = sum(m.health_score for m in modules) / len(modules)
        else:
            overall_health = 0.0

        # Collect active zones
        zones_active = set()
        for module in modules:
            if "zones_with_activity" in module.key_metrics:
                # We don't have exact zone IDs, just counts
                pass
            if "zones_with_proposals" in module.key_metrics:
                pass
            if "zones_with_closures" in module.key_metrics:
                pass

        # Detect anomalies
        anomalies = self._detect_anomalies(modules)

        # Generate recommendations
        recommendations = self._generate_recommendations(modules, anomalies)

        return UnifiedAnalyticsDashboardV1(
            generated_at=time.time(),
            global_revision=global_revision,
            time_range_days=days_lookback,
            modules=modules,
            overall_health_score=overall_health,
            total_events_all_modules=total_events,
            zones_active=list(zones_active),
            anomalies=anomalies,
            recommendations=recommendations,
        )
