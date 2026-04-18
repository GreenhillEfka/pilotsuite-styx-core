"""Advanced Analytics API — v1.0.0.

Endpoints:
- GET /api/v1/analytics/overview — Dashboard metrics overview
- GET /api/v1/analytics/trends — Trend analysis
- GET /api/v1/analytics/predictions — Predictive analytics
- GET /api/v1/analytics/patterns — Usage pattern analysis
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/v1/analytics")

# Module-level analytics engine (initialized lazily)
_engine = None


def _get_engine():
    """Get or create the analytics engine."""
    global _engine
    if _engine is None:
        try:
            from copilot_core.analytics.advanced_analytics import AnalyticsEngine, MetricType
            _engine = AnalyticsEngine(retention_days=30)
            _engine.register_metric("api_requests", MetricType.COUNTER, "API requests", "requests")
            _engine.register_metric("response_time_ms", MetricType.HISTOGRAM, "Response time", "ms")
            _engine.register_metric("active_zones", MetricType.GAUGE, "Active zones", "zones")
            _engine.register_metric("presence_events", MetricType.COUNTER, "Presence events", "events")
            _LOGGER.info("Analytics engine initialized")
        except Exception as e:
            _LOGGER.warning("Analytics engine unavailable: %s", e)
            return None
    return _engine


@analytics_bp.route("/overview", methods=["GET"])
@require_token
def analytics_overview():
    """Dashboard metrics overview."""
    engine = _get_engine()
    if engine is None:
        return jsonify({"status": "unavailable", "message": "Analytics engine not initialized"}), 503

    try:
        now = datetime.now()
        return jsonify({
            "status": "ok",
            "generated_at": now.isoformat(),
            "overview": {
                "total_metrics": len(engine._metrics),
                "metrics": [
                    {
                        "name": m.name,
                        "type": m.type.value,
                        "description": m.description,
                        "unit": m.unit,
                    }
                    for m in engine._metrics.values()
                ],
            },
        })
    except Exception as e:
        _LOGGER.exception("analytics_overview failed")
        return jsonify({"status": "error", "message": str(e)}), 500


@analytics_bp.route("/trends", methods=["GET"])
@require_token
def analytics_trends():
    """Trend analysis for registered metrics."""
    engine = _get_engine()
    if engine is None:
        return jsonify({"status": "unavailable"}), 503

    try:
        metric_name = request.args.get("metric")
        window_hours = int(request.args.get("window_hours", 24))
        now = datetime.now()
        cutoff = now - timedelta(hours=window_hours)

        trends = {}
        for name, metric in engine._metrics.items():
            if metric_name and name != metric_name:
                continue
            points = [p for p in metric.points if p.timestamp >= cutoff]
            if points:
                values = [p.value for p in points]
                trends[name] = {
                    "window_hours": window_hours,
                    "data_points": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "latest": values[-1],
                }

        return jsonify({
            "status": "ok",
            "generated_at": now.isoformat(),
            "trends": trends,
        })
    except Exception as e:
        _LOGGER.exception("analytics_trends failed")
        return jsonify({"status": "error", "message": str(e)}), 500


@analytics_bp.route("/predictions", methods=["GET"])
@require_token
def analytics_predictions():
    """Predictive analytics — simple linear projection."""
    engine = _get_engine()
    if engine is None:
        return jsonify({"status": "unavailable"}), 503

    try:
        metric_name = request.args.get("metric")
        horizon_hours = int(request.args.get("horizon_hours", 6))
        now = datetime.now()

        predictions = {}
        for name, metric in engine._metrics.items():
            if metric_name and name != metric_name:
                continue
            points = sorted(metric.points, key=lambda p: p.timestamp)
            if len(points) < 2:
                continue

            # Simple linear regression projection
            recent = points[-6:] if len(points) >= 6 else points
            n = len(recent)
            if n < 2:
                continue

            xs = [(p.timestamp - recent[0].timestamp).total_seconds() for p in recent]
            ys = [p.value for p in recent]
            x_mean = sum(xs) / n
            y_mean = sum(ys) / n
            slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / max(sum((x - x_mean) ** 2 for x in xs), 1e-6)
            intercept = y_mean - slope * x_mean

            horizon_secs = horizon_hours * 3600
            projected_value = intercept + slope * horizon_secs
            projected_time = points[-1].timestamp.isoformat()

            predictions[name] = {
                "horizon_hours": horizon_hours,
                "projected_value": round(projected_value, 4),
                "projected_at": projected_time,
                "confidence": "low" if n < 6 else "medium",
                "data_points": n,
            }

        return jsonify({
            "status": "ok",
            "generated_at": now.isoformat(),
            "predictions": predictions,
        })
    except Exception as e:
        _LOGGER.exception("analytics_predictions failed")
        return jsonify({"status": "error", "message": str(e)}), 500


@analytics_bp.route("/patterns", methods=["GET"])
@require_token
def analytics_patterns():
    """Usage pattern analysis."""
    engine = _get_engine()
    if engine is None:
        return jsonify({"status": "unavailable"}), 503

    try:
        now = datetime.now()
        patterns = {}

        for name, metric in engine._metrics.items():
            points = sorted(metric.points, key=lambda p: p.timestamp)
            if len(points) < 10:
                continue

            # Simple pattern detection: hourly distribution
            hourly = [0.0] * 24
            daily = [0.0] * 7
            for p in points:
                hourly[p.timestamp.hour] += p.value
                daily[p.timestamp.weekday()] += p.value

            patterns[name] = {
                "total_samples": len(points),
                "hourly_peak": hourly.index(max(hourly)) if max(hourly) > 0 else None,
                "daily_peak": daily.index(max(daily)) if max(daily) > 0 else None,
                "hourly_distribution": [round(v, 4) for v in hourly],
                "daily_distribution": [round(v, 4) for v in daily],
            }

        return jsonify({
            "status": "ok",
            "generated_at": now.isoformat(),
            "patterns": patterns,
        })
    except Exception as e:
        _LOGGER.exception("analytics_patterns failed")
        return jsonify({"status": "error", "message": str(e)}), 500