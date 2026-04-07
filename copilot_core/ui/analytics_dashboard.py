"""P6-003: Analytics Dashboard — Usage Metrics, Performance, Insights."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class AnalyticsInsight:
    """Generated analytics insight."""
    id: str
    title: str
    description: str
    severity: str  # info, warning, critical
    recommendation: str
    data: Dict[str, Any] = field(default_factory=dict)


class AnalyticsDashboard:
    """Analytics dashboard with metrics and insights."""

    def __init__(self, retention_days: int = 30):
        self.retention_days = retention_days
        self._metrics: Dict[str, List[MetricPoint]] = defaultdict(list)
        self._insights: List[AnalyticsInsight] = []
        self._aggregations: Dict[str, Dict[str, float]] = {}

    def record_metric(self, name: str, value: float, labels: Optional[Dict] = None):
        """Record a metric data point."""
        point = MetricPoint(
            timestamp=time.time(),
            value=value,
            labels=labels or {}
        )
        self._metrics[name].append(point)
        
        # Cleanup old data
        cutoff = time.time() - (self.retention_days * 24 * 3600)
        self._metrics[name] = [p for p in self._metrics[name] if p.timestamp > cutoff]

    def get_metric(self, name: str, start: Optional[float] = None, end: Optional[float] = None) -> List[MetricPoint]:
        """Get metric data points."""
        points = self._metrics.get(name, [])
        
        if start:
            points = [p for p in points if p.timestamp >= start]
        if end:
            points = [p for p in points if p.timestamp <= end]
        
        return points

    def calculate_aggregation(self, name: str, agg_type: str, window_seconds: int = 3600) -> Optional[float]:
        """Calculate metric aggregation."""
        points = self.get_metric(name, start=time.time() - window_seconds)
        
        if not points:
            return None
        
        values = [p.value for p in points]
        
        if agg_type == "avg":
            return sum(values) / len(values)
        elif agg_type == "sum":
            return sum(values)
        elif agg_type == "min":
            return min(values)
        elif agg_type == "max":
            return max(values)
        elif agg_type == "count":
            return len(values)
        
        return None

    def generate_insights(self) -> List[AnalyticsInsight]:
        """Generate analytics insights."""
        insights = []
        
        # Check API latency
        api_latency = self.calculate_aggregation("api_latency_ms", "avg", 3600)
        if api_latency and api_latency > 500:
            insights.append(AnalyticsInsight(
                id="high_api_latency",
                title="High API Latency",
                description=f"Average API latency is {api_latency:.0f}ms (threshold: 500ms)",
                severity="warning",
                recommendation="Consider optimizing database queries or adding caching",
                data={"latency_ms": api_latency}
            ))
        
        # Check error rate
        error_rate = self.calculate_aggregation("error_rate", "avg", 3600)
        if error_rate and error_rate > 0.05:
            insights.append(AnalyticsInsight(
                id="high_error_rate",
                title="High Error Rate",
                description=f"Error rate is {error_rate*100:.1f}% (threshold: 5%)",
                severity="critical",
                recommendation="Investigate error logs and fix root causes",
                data={"error_rate": error_rate}
            ))
        
        # Check usage patterns
        requests = self.calculate_aggregation("requests_total", "sum", 86400)
        if requests and requests > 10000:
            insights.append(AnalyticsInsight(
                id="high_usage",
                title="High System Usage",
                description=f"System processed {requests:.0f} requests in last 24h",
                severity="info",
                recommendation="Consider scaling resources if performance degrades",
                data={"requests_24h": requests}
            ))
        
        self._insights = insights
        return insights

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get complete dashboard data."""
        return {
            "metrics": {
                "api_latency_ms": {
                    "current": self.calculate_aggregation("api_latency_ms", "avg", 300),
                    "trend": self._calculate_trend("api_latency_ms"),
                },
                "requests_total": {
                    "current": self.calculate_aggregation("requests_total", "sum", 3600),
                    "trend": self._calculate_trend("requests_total"),
                },
                "error_rate": {
                    "current": self.calculate_aggregation("error_rate", "avg", 3600),
                    "trend": self._calculate_trend("error_rate"),
                },
            },
            "insights": [
                {
                    "id": i.id,
                    "title": i.title,
                    "severity": i.severity,
                    "recommendation": i.recommendation,
                }
                for i in self._insights
            ],
            "summary": {
                "total_metrics": len(self._metrics),
                "total_insights": len(self._insights),
                "critical_insights": len([i for i in self._insights if i.severity == "critical"]),
            }
        }

    def _calculate_trend(self, metric_name: str) -> str:
        """Calculate metric trend (increasing, decreasing, stable)."""
        points = self.get_metric(metric_name, start=time.time() - 7200)
        if len(points) < 10:
            return "unknown"
        
        first_half = [p.value for p in points[:len(points)//2]]
        second_half = [p.value for p in points[len(points)//2:]]
        
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        
        change = (avg_second - avg_first) / max(0.001, avg_first)
        
        if change > 0.1:
            return "increasing"
        elif change < -0.1:
            return "decreasing"
        return "stable"

    def get_stats(self) -> Dict[str, Any]:
        """Get analytics statistics."""
        return {
            "total_metrics": len(self._metrics),
            "total_data_points": sum(len(points) for points in self._metrics.values()),
            "total_insights": len(self._insights),
            "retention_days": self.retention_days,
        }


# Global default analytics
default_analytics: Optional[AnalyticsDashboard] = None


def init_analytics_dashboard(retention_days: int = 30) -> AnalyticsDashboard:
    """Initialize global analytics dashboard."""
    global default_analytics
    default_analytics = AnalyticsDashboard(retention_days)
    return default_analytics
