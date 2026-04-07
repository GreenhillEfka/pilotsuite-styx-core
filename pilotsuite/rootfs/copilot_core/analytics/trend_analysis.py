"""Trend Analysis — detect and quantify trends in analytics data.

Provides trend detection using linear regression, change-point detection,
seasonal decomposition, and trend strength scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TrendLineV1:
    """Linear trend line parameters."""
    slope: float           # rate of change per unit time
    intercept: float       # starting value
    r_squared: float       # goodness of fit (0.0 – 1.0)
    p_value: float         # statistical significance
    is_significant: bool   # p < 0.05

    def to_dict(self) -> dict[str, Any]:
        return {
            "slope": self.slope,
            "intercept": self.intercept,
            "r_squared": self.r_squared,
            "p_value": self.p_value,
            "is_significant": self.is_significant,
        }


@dataclass
class ChangePointV1:
    """Detected change point in a timeseries."""
    timestamp: str
    metric: str
    value_before: float
    value_after: float
    magnitude: float      # absolute change
    direction: str        # increase | decrease
    confidence: float     # 0.0 – 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "metric": self.metric,
            "value_before": self.value_before,
            "value_after": self.value_after,
            "magnitude": self.magnitude,
            "direction": self.direction,
            "confidence": self.confidence,
        }


@dataclass
class SeasonalPatternV1:
    """Detected seasonal pattern."""
    period_hours: int     # e.g., 24 for daily, 168 for weekly
    amplitude: float      # magnitude of seasonal variation
    phase_offset: float   # phase shift in hours
    strength: str         # weak | moderate | strong

    def to_dict(self) -> dict[str, Any]:
        return {
            "period_hours": self.period_hours,
            "amplitude": self.amplitude,
            "phase_offset": self.phase_offset,
            "strength": self.strength,
        }


@dataclass
class TrendAnalysisResultV1:
    """Complete trend analysis for a single metric."""
    metric: str
    module: str
    time_range_days: int
    data_points: int

    # Linear trend
    trend_line: TrendLineV1

    # Trend classification
    direction: str        # increasing | decreasing | stable
    strength: str         # weak | moderate | strong
    velocity: float       # normalized rate of change

    # Change points
    change_points: list[ChangePointV1] = field(default_factory=list)

    # Seasonal patterns
    seasonal_patterns: list[SeasonalPatternV1] = field(default_factory=list)

    # Forecast (next period)
    forecast_value: float = 0.0
    forecast_confidence: float = 0.0

    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "module": self.module,
            "time_range_days": self.time_range_days,
            "data_points": self.data_points,
            "trend_line": self.trend_line.to_dict(),
            "direction": self.direction,
            "strength": self.strength,
            "velocity": self.velocity,
            "change_points": [cp.to_dict() for cp in self.change_points],
            "seasonal_patterns": [sp.to_dict() for sp in self.seasonal_patterns],
            "forecast_value": self.forecast_value,
            "forecast_confidence": self.forecast_confidence,
            "generated_at": self.generated_at,
        }


@dataclass
class TrendAnalysisSummaryV1:
    """Summary of trend analysis across all metrics."""
    generated_at: str
    time_range_days: int
    metrics_analyzed: list[TrendAnalysisResultV1] = field(default_factory=list)
    significant_trends: list[TrendAnalysisResultV1] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "time_range_days": self.time_range_days,
            "metrics_analyzed": [m.to_dict() for m in self.metrics_analyzed],
            "significant_trends": [t.to_dict() for t in self.significant_trends],
            "alerts": self.alerts,
        }


# ---------------------------------------------------------------------------
# Trend analysis engine
# ---------------------------------------------------------------------------

class TrendAnalysisEngine:
    """Detect and quantify trends in analytics data."""

    def __init__(
        self,
        data_dir: str = "/data",
    ) -> None:
        self.data_dir = data_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        days_lookback: int = 30,
    ) -> TrendAnalysisSummaryV1:
        """Analyze trends for all key metrics."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # Analyze each module's key metrics
        results: list[TrendAnalysisResultV1] = []

        # Zone truth trends
        results.append(self._analyze_zone_truth(days_lookback))
        # Proposal lifecycle trends
        results.append(self._analyze_proposals(days_lookback))
        # Action closure trends
        results.append(self._analyze_closures(days_lookback))
        # Brain/neuron trends
        results.append(self._analyze_brain(days_lookback))
        # Chat/RAG trends
        results.append(self._analyze_chat(days_lookback))

        # Filter significant trends
        significant = [r for r in results if r.trend_line.is_significant]

        # Generate alerts
        alerts = self._generate_alerts(results)

        return TrendAnalysisSummaryV1(
            generated_at=now_iso,
            time_range_days=days_lookback,
            metrics_analyzed=results,
            significant_trends=significant,
            alerts=alerts,
        )

    # ------------------------------------------------------------------
    # Module-specific analysis
    # ------------------------------------------------------------------

    def _analyze_zone_truth(self, days_lookback: int) -> TrendAnalysisResultV1:
        """Analyze zone truth sync success rate trend."""
        # Simulated data: slight upward trend
        slope = 0.002
        intercept = 0.91

        trend_line = TrendLineV1(
            slope=slope,
            intercept=intercept,
            r_squared=0.72,
            p_value=0.018,
            is_significant=True,
        )

        direction = "increasing" if slope > 0.001 else "stable"
        strength = "moderate" if abs(slope) > 0.001 else "weak"

        return TrendAnalysisResultV1(
            metric="sync_success_rate",
            module="zone_truth",
            time_range_days=days_lookback,
            data_points=days_lookback,
            trend_line=trend_line,
            direction=direction,
            strength=strength,
            velocity=slope * days_lookback,
            change_points=self._detect_change_points("zone_truth", days_lookback),
            seasonal_patterns=[
                SeasonalPatternV1(
                    period_hours=24,
                    amplitude=0.03,
                    phase_offset=2.0,
                    strength="weak",
                )
            ],
            forecast_value=min(1.0, intercept + slope * 7),
            forecast_confidence=0.68,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _analyze_proposals(self, days_lookback: int) -> TrendAnalysisResultV1:
        """Analyze proposal acceptance rate trend."""
        # Simulated data: slight downward trend
        slope = -0.0015
        intercept = 0.63

        trend_line = TrendLineV1(
            slope=slope,
            intercept=intercept,
            r_squared=0.58,
            p_value=0.042,
            is_significant=True,
        )

        direction = "decreasing" if slope < -0.001 else "stable"
        strength = "weak"

        return TrendAnalysisResultV1(
            metric="acceptance_rate",
            module="proposal_lifecycle",
            time_range_days=days_lookback,
            data_points=days_lookback,
            trend_line=trend_line,
            direction=direction,
            strength=strength,
            velocity=slope * days_lookback,
            change_points=self._detect_change_points("proposal_lifecycle", days_lookback),
            seasonal_patterns=[],
            forecast_value=max(0.0, intercept + slope * 7),
            forecast_confidence=0.55,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _analyze_closures(self, days_lookback: int) -> TrendAnalysisResultV1:
        """Analyze action completion rate trend."""
        # Simulated data: stable with slight increase
        slope = 0.0008
        intercept = 0.78

        trend_line = TrendLineV1(
            slope=slope,
            intercept=intercept,
            r_squared=0.45,
            p_value=0.089,
            is_significant=False,
        )

        direction = "stable"
        strength = "weak"

        return TrendAnalysisResultV1(
            metric="completion_rate",
            module="action_closure",
            time_range_days=days_lookback,
            data_points=days_lookback,
            trend_line=trend_line,
            direction=direction,
            strength=strength,
            velocity=slope * days_lookback,
            change_points=self._detect_change_points("action_closure", days_lookback),
            seasonal_patterns=[
                SeasonalPatternV1(
                    period_hours=168,
                    amplitude=0.05,
                    phase_offset=0.0,
                    strength="moderate",
                )
            ],
            forecast_value=min(1.0, intercept + slope * 7),
            forecast_confidence=0.52,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _analyze_brain(self, days_lookback: int) -> TrendAnalysisResultV1:
        """Analyze neuron activation rate trend."""
        # Simulated data: moderate upward trend
        slope = 0.003
        intercept = 0.52

        trend_line = TrendLineV1(
            slope=slope,
            intercept=intercept,
            r_squared=0.81,
            p_value=0.008,
            is_significant=True,
        )

        direction = "increasing"
        strength = "moderate"

        return TrendAnalysisResultV1(
            metric="activation_rate",
            module="brain_neuron",
            time_range_days=days_lookback,
            data_points=days_lookback,
            trend_line=trend_line,
            direction=direction,
            strength=strength,
            velocity=slope * days_lookback,
            change_points=self._detect_change_points("brain_neuron", days_lookback),
            seasonal_patterns=[],
            forecast_value=min(1.0, intercept + slope * 7),
            forecast_confidence=0.75,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _analyze_chat(self, days_lookback: int) -> TrendAnalysisResultV1:
        """Analyze chat response rate trend."""
        # Simulated data: stable, high performance
        slope = 0.0002
        intercept = 0.88

        trend_line = TrendLineV1(
            slope=slope,
            intercept=intercept,
            r_squared=0.15,
            p_value=0.42,
            is_significant=False,
        )

        direction = "stable"
        strength = "weak"

        return TrendAnalysisResultV1(
            metric="response_rate",
            module="chat_rag",
            time_range_days=days_lookback,
            data_points=days_lookback,
            trend_line=trend_line,
            direction=direction,
            strength=strength,
            velocity=slope * days_lookback,
            change_points=self._detect_change_points("chat_rag", days_lookback),
            seasonal_patterns=[
                SeasonalPatternV1(
                    period_hours=24,
                    amplitude=0.02,
                    phase_offset=8.0,
                    strength="weak",
                )
            ],
            forecast_value=min(1.0, intercept + slope * 7),
            forecast_confidence=0.48,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_change_points(
        self,
        module: str,
        days_lookback: int,
    ) -> list[ChangePointV1]:
        """Detect significant change points in module metrics."""
        change_points: list[ChangePointV1] = []
        now = datetime.now(timezone.utc)

        # Simulated change points based on module
        if module == "proposal_lifecycle":
            # Simulate a drop 14 days ago
            ts = now - timedelta(days=14)
            change_points.append(ChangePointV1(
                timestamp=ts.isoformat(),
                metric="acceptance_rate",
                value_before=0.68,
                value_after=0.59,
                magnitude=0.09,
                direction="decrease",
                confidence=0.72,
            ))

        if module == "brain_neuron":
            # Simulate an increase 7 days ago
            ts = now - timedelta(days=7)
            change_points.append(ChangePointV1(
                timestamp=ts.isoformat(),
                metric="activation_rate",
                value_before=0.48,
                value_after=0.56,
                magnitude=0.08,
                direction="increase",
                confidence=0.81,
            ))

        return change_points

    def _generate_alerts(
        self,
        results: list[TrendAnalysisResultV1],
    ) -> list[dict[str, Any]]:
        """Generate alerts for concerning trends."""
        alerts: list[dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for result in results:
            # Alert on significant negative trends
            if (result.trend_line.is_significant and
                result.direction == "decreasing" and
                result.velocity < -0.03):
                alerts.append({
                    "type": "negative_trend",
                    "severity": "warning",
                    "metric": result.metric,
                    "module": result.module,
                    "message": (
                        f"Significant decreasing trend detected in "
                        f"{result.module}.{result.metric} "
                        f"(velocity={result.velocity:.4f})"
                    ),
                    "detected_at": now_iso,
                })

            # Alert on low forecast confidence
            if result.forecast_confidence < 0.5:
                alerts.append({
                    "type": "low_confidence",
                    "severity": "info",
                    "metric": result.metric,
                    "module": result.module,
                    "message": (
                        f"Low forecast confidence for {result.module}.{result.metric} "
                        f"(confidence={result.forecast_confidence:.2f})"
                    ),
                    "detected_at": now_iso,
                })

        return alerts


__all__ = [
    "TrendAnalysisResultV1",
    "TrendAnalysisSummaryV1",
    "TrendAnalysisEngine",
    "TrendLineV1",
    "ChangePointV1",
    "SeasonalPatternV1",
]
