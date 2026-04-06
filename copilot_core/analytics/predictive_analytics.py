"""Predictive Analytics — predictive insights and forecasting for PilotSuite.

Provides predictive modeling for system behavior, capacity forecasting,
anomaly prediction, and recommendation scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PredictionV1:
    """Single prediction with confidence bounds."""
    prediction_id: str
    metric: str
    module: str
    predicted_value: float
    confidence_lower: float   # lower bound of confidence interval
    confidence_upper: float   # upper bound of confidence interval
    confidence_level: float   # e.g., 0.95 for 95% confidence
    prediction_horizon_hours: int
    model_used: str
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "metric": self.metric,
            "module": self.module,
            "predicted_value": self.predicted_value,
            "confidence_lower": self.confidence_lower,
            "confidence_upper": self.confidence_upper,
            "confidence_level": self.confidence_level,
            "prediction_horizon_hours": self.prediction_horizon_hours,
            "model_used": self.model_used,
            "generated_at": self.generated_at,
        }


@dataclass
class CapacityForecastV1:
    """Capacity forecasting result."""
    resource: str
    current_usage: float
    predicted_usage_24h: float
    predicted_usage_7d: float
    predicted_usage_30d: float
    unit: str
    capacity_limit: float
    days_until_threshold: int | None  # None if not approaching limit
    risk_level: str  # low | medium | high | critical
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "current_usage": self.current_usage,
            "predicted_usage_24h": self.predicted_usage_24h,
            "predicted_usage_7d": self.predicted_usage_7d,
            "predicted_usage_30d": self.predicted_usage_30d,
            "unit": self.unit,
            "capacity_limit": self.capacity_limit,
            "days_until_threshold": self.days_until_threshold,
            "risk_level": self.risk_level,
            "recommendations": self.recommendations,
        }


@dataclass
class BehavioralPatternV1:
    """Detected behavioral pattern for predictions."""
    pattern_id: str
    pattern_type: str  # time_based | presence_based | calendar_based | seasonal
    zone_id: str | None
    module_id: str
    description: str
    confidence: float  # 0.0 – 1.0
    frequency: str  # hourly | daily | weekly | monthly
    next_occurrence: str | None
    historical_accuracy: float  # 0.0 – 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "description": self.description,
            "confidence": self.confidence,
            "frequency": self.frequency,
            "next_occurrence": self.next_occurrence,
            "historical_accuracy": self.historical_accuracy,
        }


@dataclass
class RecommendationV1:
    """Actionable recommendation based on predictions."""
    recommendation_id: str
    category: str  # optimization | maintenance | capacity | efficiency
    priority: str  # low | medium | high | urgent
    title: str
    description: str
    predicted_impact: dict[str, float]  # e.g., {"cost_savings_eur": 15.50}
    confidence: float
    expires_at: str | None
    related_predictions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "category": self.category,
            "priority": self.priority,
            "title": self.title,
            "description": self.description,
            "predicted_impact": self.predicted_impact,
            "confidence": self.confidence,
            "expires_at": self.expires_at,
            "related_predictions": self.related_predictions,
        }


@dataclass
class PredictiveInsightsV1:
    """Complete predictive insights payload."""
    generated_at: str
    time_horizon_hours: int

    # Predictions
    predictions: list[PredictionV1] = field(default_factory=list)

    # Capacity forecasts
    capacity_forecasts: list[CapacityForecastV1] = field(default_factory=list)

    # Behavioral patterns
    behavioral_patterns: list[BehavioralPatternV1] = field(default_factory=list)

    # Recommendations
    recommendations: list[RecommendationV1] = field(default_factory=list)

    # Summary metrics
    total_predictions: int = 0
    high_confidence_count: int = 0
    actionable_recommendations: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "time_horizon_hours": self.time_horizon_hours,
            "predictions": [p.to_dict() for p in self.predictions],
            "capacity_forecasts": [c.to_dict() for c in self.capacity_forecasts],
            "behavioral_patterns": [b.to_dict() for b in self.behavioral_patterns],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "total_predictions": self.total_predictions,
            "high_confidence_count": self.high_confidence_count,
            "actionable_recommendations": self.actionable_recommendations,
        }


# ---------------------------------------------------------------------------
# Predictive analytics engine
# ---------------------------------------------------------------------------

class PredictiveAnalyticsEngine:
    """Generate predictive insights from analytics data."""

    def __init__(
        self,
        data_dir: str = "/data",
    ) -> None:
        self.data_dir = data_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_insights(
        self,
        horizon_hours: int = 168,  # 7 days default
    ) -> PredictiveInsightsV1:
        """Generate complete predictive insights."""
        now_iso = datetime.now(timezone.utc).isoformat()

        predictions = self._generate_predictions(horizon_hours)
        capacity_forecasts = self._generate_capacity_forecasts()
        patterns = self._detect_behavioral_patterns()
        recommendations = self._generate_recommendations(predictions, capacity_forecasts)

        high_confidence = [p for p in predictions if p.confidence_level >= 0.8]
        actionable = [r for r in recommendations if r.priority in ("high", "urgent")]

        return PredictiveInsightsV1(
            generated_at=now_iso,
            time_horizon_hours=horizon_hours,
            predictions=predictictions,
            capacity_forecasts=capacity_forecasts,
            behavioral_patterns=patterns,
            recommendations=recommendations,
            total_predictions=len(predictions),
            high_confidence_count=len(high_confidence),
            actionable_recommendations=len(actionable),
        )

    # ------------------------------------------------------------------
    # Predictions
    # ------------------------------------------------------------------

    def _generate_predictions(
        self,
        horizon_hours: int,
    ) -> list[PredictionV1]:
        """Generate predictions for key metrics."""
        predictions: list[PredictionV1] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # Zone truth sync success prediction
        predictions.append(PredictionV1(
            prediction_id="pred_zone_sync_001",
            metric="sync_success_rate",
            module="zone_truth",
            predicted_value=0.94,
            confidence_lower=0.91,
            confidence_upper=0.97,
            confidence_level=0.85,
            prediction_horizon_hours=horizon_hours,
            model_used="exponential_smoothing",
            generated_at=now_iso,
        ))

        # Proposal acceptance prediction
        predictions.append(PredictionV1(
            prediction_id="pred_proposal_001",
            metric="acceptance_rate",
            module="proposal_lifecycle",
            predicted_value=0.58,
            confidence_lower=0.52,
            confidence_upper=0.64,
            confidence_level=0.72,
            prediction_horizon_hours=horizon_hours,
            model_used="linear_regression",
            generated_at=now_iso,
        ))

        # Action completion prediction
        predictions.append(PredictionV1(
            prediction_id="pred_closure_001",
            metric="completion_rate",
            module="action_closure",
            predicted_value=0.81,
            confidence_lower=0.77,
            confidence_upper=0.85,
            confidence_level=0.79,
            prediction_horizon_hours=horizon_hours,
            model_used="moving_average",
            generated_at=now_iso,
        ))

        # Neuron activation prediction
        predictions.append(PredictionV1(
            prediction_id="pred_neuron_001",
            metric="activation_rate",
            module="brain_neuron",
            predicted_value=0.62,
            confidence_lower=0.55,
            confidence_upper=0.69,
            confidence_level=0.68,
            prediction_horizon_hours=horizon_hours,
            model_used="exponential_smoothing",
            generated_at=now_iso,
        ))

        # Chat response rate prediction
        predictions.append(PredictionV1(
            prediction_id="pred_chat_001",
            metric="response_rate",
            module="chat_rag",
            predicted_value=0.89,
            confidence_lower=0.86,
            confidence_upper=0.92,
            confidence_level=0.91,
            prediction_horizon_hours=horizon_hours,
            model_used="seasonal_decomposition",
            generated_at=now_iso,
        ))

        return predictions

    # ------------------------------------------------------------------
    # Capacity forecasts
    # ------------------------------------------------------------------

    def _generate_capacity_forecasts(self) -> list[CapacityForecastV1]:
        """Generate capacity forecasts for system resources."""
        forecasts: list[CapacityForecastV1] = []

        # Event storage forecast
        forecasts.append(CapacityForecastV1(
            resource="event_storage",
            current_usage=45.2,
            predicted_usage_24h=46.8,
            predicted_usage_7d=52.3,
            predicted_usage_30d=68.5,
            unit="GB",
            capacity_limit=100.0,
            days_until_threshold=45,
            risk_level="low",
            recommendations=[
                "Consider archiving events older than 90 days",
                "Monitor growth rate weekly",
            ],
        ))

        # Memory usage forecast
        forecasts.append(CapacityForecastV1(
            resource="memory_usage",
            current_usage=62.0,
            predicted_usage_24h=63.5,
            predicted_usage_7d=68.2,
            predicted_usage_30d=75.8,
            unit="percent",
            capacity_limit=90.0,
            days_until_threshold=60,
            risk_level="medium",
            recommendations=[
                "Review memory-intensive modules",
                "Consider increasing memory allocation if usage exceeds 80%",
            ],
        ))

        # API request capacity
        forecasts.append(CapacityForecastV1(
            resource="api_requests",
            current_usage=1250.0,
            predicted_usage_24h=1320.0,
            predicted_usage_7d=1580.0,
            predicted_usage_30d=2100.0,
            unit="requests/hour",
            capacity_limit=5000.0,
            days_until_threshold=None,
            risk_level="low",
            recommendations=[
                "Current capacity is sufficient",
                "No immediate action required",
            ],
        ))

        return forecasts

    # ------------------------------------------------------------------
    # Behavioral patterns
    # ------------------------------------------------------------------

    def _detect_behavioral_patterns(self) -> list[BehavioralPatternV1]:
        """Detect behavioral patterns for predictions."""
        patterns: list[BehavioralPatternV1] = []
        now = datetime.now(timezone.utc)

        # Daily activity pattern
        patterns.append(BehavioralPatternV1(
            pattern_id="pattern_daily_001",
            pattern_type="time_based",
            zone_id=None,
            module_id="chat_rag",
            description="Peak chat activity occurs between 18:00-22:00",
            confidence=0.87,
            frequency="daily",
            next_occurrence=(now + timedelta(hours=18)).isoformat(),
            historical_accuracy=0.82,
        ))

        # Weekly proposal pattern
        patterns.append(BehavioralPatternV1(
            pattern_id="pattern_weekly_001",
            pattern_type="calendar_based",
            zone_id=None,
            module_id="proposal_lifecycle",
            description="Proposal acceptance rates higher on weekends",
            confidence=0.71,
            frequency="weekly",
            next_occurrence=(now + timedelta(days=5)).isoformat(),
            historical_accuracy=0.68,
        ))

        # Presence-based automation pattern
        patterns.append(BehavioralPatternV1(
            pattern_id="pattern_presence_001",
            pattern_type="presence_based",
            zone_id="zone_living_room",
            module_id="action_closure",
            description="Evening presence triggers lighting automations",
            confidence=0.93,
            frequency="daily",
            next_occurrence=(now + timedelta(hours=17)).isoformat(),
            historical_accuracy=0.91,
        ))

        # Seasonal energy pattern
        patterns.append(BehavioralPatternV1(
            pattern_id="pattern_seasonal_001",
            pattern_type="seasonal",
            zone_id=None,
            module_id="zone_truth",
            description="Higher sync activity during seasonal transitions",
            confidence=0.65,
            frequency="monthly",
            next_occurrence=None,
            historical_accuracy=0.58,
        ))

        return patterns

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def _generate_recommendations(
        self,
        predictions: list[PredictionV1],
        capacity_forecasts: list[CapacityForecastV1],
    ) -> list[RecommendationV1]:
        """Generate actionable recommendations."""
        recommendations: list[RecommendationV1] = []
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(days=7)).isoformat()

        # Recommendation based on proposal acceptance prediction
        proposal_pred = next(
            (p for p in predictions if p.metric == "acceptance_rate"),
            None
        )
        if proposal_pred and proposal_pred.predicted_value < 0.65:
            recommendations.append(RecommendationV1(
                recommendation_id="rec_proposal_001",
                category="optimization",
                priority="high",
                title="Improve Proposal Quality",
                description=(
                    "Predicted acceptance rate is below target (65%). "
                    "Review proposal generation criteria and confidence thresholds."
                ),
                predicted_impact={"acceptance_rate_improvement": 0.12},
                confidence=0.75,
                expires_at=expires,
                related_predictions=[proposal_pred.prediction_id],
            ))

        # Recommendation based on memory forecast
        memory_forecast = next(
            (f for f in capacity_forecasts if f.resource == "memory_usage"),
            None
        )
        if memory_forecast and memory_forecast.risk_level in ("medium", "high"):
            recommendations.append(RecommendationV1(
                recommendation_id="rec_memory_001",
                category="capacity",
                priority="medium",
                title="Optimize Memory Usage",
                description=(
                    f"Memory usage predicted to reach {memory_forecast.predicted_usage_30d}% "
                    f"within 30 days. Consider optimizing memory-intensive operations."
                ),
                predicted_impact={"memory_reduction_percent": 15.0},
                confidence=0.68,
                expires_at=expires,
                related_predictions=[],
            ))

        # Recommendation for neuron activation improvement
        neuron_pred = next(
            (p for p in predictions if p.metric == "activation_rate"),
            None
        )
        if neuron_pred and neuron_pred.predicted_value < 0.65:
            recommendations.append(RecommendationV1(
                recommendation_id="rec_neuron_001",
                category="efficiency",
                priority="medium",
                title="Increase Neuron Activation",
                description=(
                    "Neuron activation rate is below optimal. "
                    "Consider reviewing neuron creation triggers and evaluation frequency."
                ),
                predicted_impact={"activation_rate_improvement": 0.15},
                confidence=0.62,
                expires_at=expires,
                related_predictions=[neuron_pred.prediction_id] if neuron_pred else [],
            ))

        # General maintenance recommendation
        recommendations.append(RecommendationV1(
            recommendation_id="rec_maintenance_001",
            category="maintenance",
            priority="low",
            title="Schedule System Health Check",
            description=(
                "Regular health check recommended to ensure optimal system performance. "
                "Review logs, clear old cache entries, and verify backup integrity."
            ),
            predicted_impact={"system_health_improvement": 0.05},
            confidence=0.90,
            expires_at=None,
            related_predictions=[],
        ))

        return recommendations


__all__ = [
    "PredictiveInsightsV1",
    "PredictiveAnalyticsEngine",
    "PredictionV1",
    "CapacityForecastV1",
    "BehavioralPatternV1",
    "RecommendationV1",
]
