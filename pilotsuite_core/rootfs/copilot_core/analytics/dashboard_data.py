"""Dashboard Data Generator — aggregates analytics for dashboard consumption.

Provides unified data structures optimized for frontend dashboard rendering,
including time-bucketed metrics, module health cards, and KPI summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TimeBucketV1:
    """Single time-bucketed metric value."""
    timestamp: str
    value: float
    count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"timestamp": self.timestamp, "value": self.value, "count": self.count}


@dataclass
class ModuleHealthCardV1:
    """Health card for a single module in the dashboard."""
    module_id: str
    module_name: str
    health_score: float  # 0.0 – 1.0
    status: str          # healthy | warning | critical
    total_events: int
    key_metrics: dict[str, float] = field(default_factory=dict)
    trend_7d: float = 0.0
    trend_30d: float = 0.0
    last_updated: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "module_name": self.module_name,
            "health_score": self.health_score,
            "status": self.status,
            "total_events": self.total_events,
            "key_metrics": self.key_metrics,
            "trend_7d": self.trend_7d,
            "trend_30d": self.trend_30d,
            "last_updated": self.last_updated,
        }


@dataclass
class KPISummaryV1:
    """Key Performance Indicator summary."""
    kpi_id: str
    kpi_name: str
    current_value: float
    target_value: float
    unit: str
    delta_24h: float
    delta_7d: float
    status: str  # on_track | at_risk | off_track

    def to_dict(self) -> dict[str, Any]:
        return {
            "kpi_id": self.kpi_id,
            "kpi_name": self.kpi_name,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "unit": self.unit,
            "delta_24h": self.delta_24h,
            "delta_7d": self.delta_7d,
            "status": self.status,
        }


@dataclass
class DashboardDataV1:
    """Complete dashboard data payload."""
    generated_at: str
    time_range_days: int
    refresh_interval_seconds: int = 60

    # Module health cards
    module_cards: list[ModuleHealthCardV1] = field(default_factory=list)

    # Time-series data for charts
    timeseries: dict[str, list[TimeBucketV1]] = field(default_factory=dict)

    # KPI summaries
    kpis: list[KPISummaryV1] = field(default_factory=list)

    # Overall system health
    overall_health_score: float = 0.0
    overall_status: str = "unknown"

    # Active zones count
    zones_active: int = 0
    zones_total: int = 0

    # Anomalies requiring attention
    attention_required: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "time_range_days": self.time_range_days,
            "refresh_interval_seconds": self.refresh_interval_seconds,
            "module_cards": [c.to_dict() for c in self.module_cards],
            "timeseries": {k: [b.to_dict() for b in v] for k, v in self.timeseries.items()},
            "kpis": [k.to_dict() for k in self.kpis],
            "overall_health_score": self.overall_health_score,
            "overall_status": self.overall_status,
            "zones_active": self.zones_active,
            "zones_total": self.zones_total,
            "attention_required": self.attention_required,
        }


# ---------------------------------------------------------------------------
# Dashboard data generator
# ---------------------------------------------------------------------------

class DashboardDataGenerator:
    """Generate dashboard-optimized data from analytics stores."""

    def __init__(
        self,
        data_dir: str = "/data",
    ) -> None:
        self.data_dir = data_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, days_lookback: int = 30) -> DashboardDataV1:
        """Generate complete dashboard data."""
        now_iso = datetime.now(timezone.utc).isoformat()

        module_cards = self._build_module_cards(days_lookback)
        timeseries = self._build_timeseries(days_lookback)
        kpis = self._build_kpis(module_cards)
        overall_health = self._compute_overall_health(module_cards)
        attention = self._build_attention_list(module_cards)

        return DashboardDataV1(
            generated_at=now_iso,
            time_range_days=days_lookback,
            refresh_interval_seconds=60,
            module_cards=module_cards,
            timeseries=timeseries,
            kpis=kpis,
            overall_health_score=overall_health,
            overall_status=self._status_from_health(overall_health),
            zones_active=self._count_active_zones(module_cards),
            zones_total=5,  # Default zone count
            attention_required=attention,
        )

    # ------------------------------------------------------------------
    # Module cards
    # ------------------------------------------------------------------

    def _build_module_cards(self, days_lookback: int) -> list[ModuleHealthCardV1]:
        """Build health cards for all modules."""
        cards: list[ModuleHealthCardV1] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # Module definitions with simulated metrics
        modules = [
            {
                "id": "zone_truth",
                "name": "Zone Truth",
                "health": 0.87,
                "events": 1243,
                "metrics": {"sync_success": 0.93, "conflict_rate": 0.07},
                "trend_7d": 0.02,
                "trend_30d": 0.05,
            },
            {
                "id": "proposal_lifecycle",
                "name": "Proposal Lifecycle",
                "health": 0.72,
                "events": 856,
                "metrics": {"acceptance_rate": 0.61, "execution_rate": 0.89},
                "trend_7d": -0.03,
                "trend_30d": 0.01,
            },
            {
                "id": "action_closure",
                "name": "Action Closure",
                "health": 0.81,
                "events": 734,
                "metrics": {"completion_rate": 0.79, "failure_rate": 0.08},
                "trend_7d": 0.01,
                "trend_30d": 0.04,
            },
            {
                "id": "brain_neuron",
                "name": "Brain & Neuron",
                "health": 0.65,
                "events": 2105,
                "metrics": {"activation_rate": 0.55, "growth_rate": 0.12},
                "trend_7d": 0.04,
                "trend_30d": 0.08,
            },
            {
                "id": "chat_rag",
                "name": "Chat & RAG",
                "health": 0.91,
                "events": 3421,
                "metrics": {"response_rate": 0.88, "rag_usage": 0.67},
                "trend_7d": 0.00,
                "trend_30d": 0.03,
            },
        ]

        for mod in modules:
            status = "healthy"
            if mod["health"] < 0.5:
                status = "critical"
            elif mod["health"] < 0.7:
                status = "warning"

            cards.append(ModuleHealthCardV1(
                module_id=mod["id"],
                module_name=mod["name"],
                health_score=mod["health"],
                status=status,
                total_events=mod["events"],
                key_metrics=mod["metrics"],
                trend_7d=mod["trend_7d"],
                trend_30d=mod["trend_30d"],
                last_updated=now_iso,
            ))

        return cards

    # ------------------------------------------------------------------
    # Timeseries
    # ------------------------------------------------------------------

    def _build_timeseries(self, days_lookback: int) -> dict[str, list[TimeBucketV1]]:
        """Build time-series data for dashboard charts."""
        timeseries: dict[str, list[TimeBucketV1]] = {}
        now = datetime.now(timezone.utc)

        # Generate daily buckets for each metric
        metrics = [
            ("overall_health", 0.78, 0.05),
            ("total_events", 150, 20),
            ("acceptance_rate", 0.61, 0.08),
            ("completion_rate", 0.79, 0.06),
        ]

        for metric_name, base_value, variance in metrics:
            buckets: list[TimeBucketV1] = []
            for day_offset in range(days_lookback):
                ts = now - timedelta(days=days_lookback - day_offset - 1)
                # Add some variation
                import random
                random.seed(day_offset + hash(metric_name) % 100)
                value = base_value + (random.random() - 0.5) * 2 * variance
                value = max(0, value)

                buckets.append(TimeBucketV1(
                    timestamp=ts.isoformat(),
                    value=round(value, 3),
                    count=int(base_value * 10 + day_offset),
                ))
            timeseries[metric_name] = buckets

        return timeseries

    # ------------------------------------------------------------------
    # KPIs
    # ------------------------------------------------------------------

    def _build_kpis(
        self,
        module_cards: list[ModuleHealthCardV1],
    ) -> list[KPISummaryV1]:
        """Build KPI summaries from module data."""
        kpis: list[KPISummaryV1] = []

        # Overall system health KPI
        avg_health = sum(c.health_score for c in module_cards) / len(module_cards) if module_cards else 0
        kpis.append(KPISummaryV1(
            kpi_id="system_health",
            kpi_name="System Health",
            current_value=avg_health,
            target_value=0.85,
            unit="score",
            delta_24h=0.02,
            delta_7d=0.05,
            status="on_track" if avg_health >= 0.8 else "at_risk",
        ))

        # Total events KPI
        total_events = sum(c.total_events for c in module_cards)
        kpis.append(KPISummaryV1(
            kpi_id="total_events",
            kpi_name="Total Events",
            current_value=total_events,
            target_value=10000,
            unit="events",
            delta_24h=150,
            delta_7d=1200,
            status="on_track" if total_events >= 8000 else "at_risk",
        ))

        # Acceptance rate KPI
        acceptance_card = next((c for c in module_cards if c.module_id == "proposal_lifecycle"), None)
        if acceptance_card:
            acceptance_rate = acceptance_card.key_metrics.get("acceptance_rate", 0)
            kpis.append(KPISummaryV1(
                kpi_id="acceptance_rate",
                kpi_name="Proposal Acceptance",
                current_value=acceptance_rate,
                target_value=0.70,
                unit="rate",
                delta_24h=-0.01,
                delta_7d=-0.03,
                status="at_risk" if acceptance_rate < 0.65 else "on_track",
            ))

        return kpis

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _compute_overall_health(
        self,
        module_cards: list[ModuleHealthCardV1],
    ) -> float:
        """Compute weighted overall health score."""
        if not module_cards:
            return 0.0

        # Weighted average (chat_rag and zone_truth weighted higher)
        weights = {
            "zone_truth": 1.2,
            "proposal_lifecycle": 1.0,
            "action_closure": 1.0,
            "brain_neuron": 0.8,
            "chat_rag": 1.2,
        }

        total_weight = 0
        weighted_sum = 0.0
        for card in module_cards:
            w = weights.get(card.module_id, 1.0)
            weighted_sum += card.health_score * w
            total_weight += w

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _status_from_health(self, health: float) -> str:
        """Map health score to status string."""
        if health >= 0.8:
            return "healthy"
        elif health >= 0.6:
            return "warning"
        else:
            return "critical"

    def _count_active_zones(self, module_cards: list[ModuleHealthCardV1]) -> int:
        """Count active zones from module data."""
        # Simulated: assume 4 of 5 zones active
        return 4

    def _build_attention_list(
        self,
        module_cards: list[ModuleHealthCardV1],
    ) -> list[dict[str, Any]]:
        """Build list of items requiring attention."""
        attention: list[dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for card in module_cards:
            if card.status == "critical":
                attention.append({
                    "type": "critical_module",
                    "module": card.module_id,
                    "message": f"Module {card.module_name} is in critical state",
                    "health_score": card.health_score,
                    "detected_at": now_iso,
                })
            elif card.status == "warning":
                attention.append({
                    "type": "warning_module",
                    "module": card.module_id,
                    "message": f"Module {card.module_name} needs attention",
                    "health_score": card.health_score,
                    "detected_at": now_iso,
                })

            # Check for negative trends
            if card.trend_7d < -0.05:
                attention.append({
                    "type": "negative_trend",
                    "module": card.module_id,
                    "message": f"Module {card.module_name} showing negative 7-day trend",
                    "trend_7d": card.trend_7d,
                    "detected_at": now_iso,
                })

        return attention


__all__ = [
    "DashboardDataV1",
    "DashboardDataGenerator",
    "ModuleHealthCardV1",
    "KPISummaryV1",
    "TimeBucketV1",
]
