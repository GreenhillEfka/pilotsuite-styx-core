"""Advanced Analytics API endpoints — v15.3.24.

Provides REST API endpoints for the Advanced Analytics Dashboard:
- GET /api/v1/analytics/overview — High-level system analytics summary
- GET /api/v1/analytics/trends — Trend analysis and change detection
- GET /api/v1/analytics/predictions — Predictive insights and forecasts
- GET /api/v1/analytics/patterns — Behavioral patterns and correlations

Usage:
    from copilot_core.api.v1.advanced_analytics import advanced_analytics_bp
    app.register_blueprint(advanced_analytics_bp)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from copilot_core.analytics.advanced_analytics import (
    AdvancedAnalyticsEngine,
    AdvancedAnalyticsV1,
)
from copilot_core.analytics.dashboard_data import (
    DashboardDataGenerator,
    DashboardDataV1,
)
from copilot_core.analytics.trend_analysis import (
    TrendAnalysisEngine,
    TrendAnalysisSummaryV1,
)
from copilot_core.analytics.predictive_analytics import (
    PredictiveAnalyticsEngine,
    PredictiveInsightsV1,
)

_LOGGER = logging.getLogger(__name__)

# Create blueprint
advanced_analytics_bp = Blueprint(
    "advanced_analytics",
    __name__,
    url_prefix="/api/v1/analytics",
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _parse_int(value: Any, default: int) -> int:
    """Parse integer from request parameter with default."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _get_advanced_analytics_engine() -> AdvancedAnalyticsEngine:
    """Get or create advanced analytics engine."""
    engine = getattr(current_app, "_advanced_analytics_engine", None)
    if isinstance(engine, AdvancedAnalyticsEngine):
        return engine

    data_dir = current_app.config.get("COPILOT_DATA_DIR", "/data")
    engine = AdvancedAnalyticsEngine(data_dir=data_dir)
    current_app._advanced_analytics_engine = engine
    return engine


def _get_dashboard_data_generator() -> DashboardDataGenerator:
    """Get or create dashboard data generator."""
    generator = getattr(current_app, "_dashboard_data_generator", None)
    if isinstance(generator, DashboardDataGenerator):
        return generator

    data_dir = current_app.config.get("COPILOT_DATA_DIR", "/data")
    generator = DashboardDataGenerator(data_dir=data_dir)
    current_app._dashboard_data_generator = generator
    return generator


def _get_trend_analysis_engine() -> TrendAnalysisEngine:
    """Get or create trend analysis engine."""
    engine = getattr(current_app, "_trend_analysis_engine", None)
    if isinstance(engine, TrendAnalysisEngine):
        return engine

    data_dir = current_app.config.get("COPILOT_DATA_DIR", "/data")
    engine = TrendAnalysisEngine(data_dir=data_dir)
    current_app._trend_analysis_engine = engine
    return engine


def _get_predictive_analytics_engine() -> PredictiveAnalyticsEngine:
    """Get or create predictive analytics engine."""
    engine = getattr(current_app, "_predictive_analytics_engine", None)
    if isinstance(engine, PredictiveAnalyticsEngine):
        return engine

    data_dir = current_app.config.get("COPILOT_DATA_DIR", "/data")
    engine = PredictiveAnalyticsEngine(data_dir=data_dir)
    current_app._predictive_analytics_engine = engine
    return engine


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@advanced_analytics_bp.get("/overview")
def get_analytics_overview():
    """Get high-level analytics overview for dashboard.

    Query Parameters:
        days (int): Number of days to look back (default: 30)

    Returns:
        JSON response with dashboard data including:
        - Module health cards
        - Time-series data
        - KPI summaries
        - Overall system health
        - Attention-required items
    """
    days_lookback = _parse_int(request.args.get("days"), 30)

    try:
        generator = _get_dashboard_data_generator()
        dashboard_data: DashboardDataV1 = generator.generate(days_lookback=days_lookback)

        return jsonify({
            "ok": True,
            "data": dashboard_data.to_dict(),
        })

    except Exception as e:
        _LOGGER.exception("Error generating analytics overview")
        return jsonify({
            "ok": False,
            "error": "Failed to generate analytics overview",
            "details": str(e),
        }), 500


@advanced_analytics_bp.get("/trends")
def get_analytics_trends():
    """Get trend analysis for all key metrics.

    Query Parameters:
        days (int): Number of days to analyze (default: 30)
        module (str): Optional filter by module name

    Returns:
        JSON response with trend analysis including:
        - Linear trend lines for each metric
        - Change point detection
        - Seasonal pattern analysis
        - Trend direction and strength
        - Alerts for concerning trends
    """
    days_lookback = _parse_int(request.args.get("days"), 30)
    module_filter = request.args.get("module")

    try:
        engine = _get_trend_analysis_engine()
        summary: TrendAnalysisSummaryV1 = engine.analyze(days_lookback=days_lookback)

        # Filter by module if specified
        if module_filter:
            summary.metrics_analyzed = [
                m for m in summary.metrics_analyzed
                if m.module == module_filter
            ]
            summary.significant_trends = [
                t for t in summary.significant_trends
                if t.module == module_filter
            ]

        return jsonify({
            "ok": True,
            "data": summary.to_dict(),
        })

    except Exception as e:
        _LOGGER.exception("Error analyzing trends")
        return jsonify({
            "ok": False,
            "error": "Failed to analyze trends",
            "details": str(e),
        }), 500


@advanced_analytics_bp.get("/predictions")
def get_analytics_predictions():
    """Get predictive insights and forecasts.

    Query Parameters:
        horizon (int): Prediction horizon in hours (default: 168 = 7 days)
        include_recommendations (bool): Include recommendations (default: true)

    Returns:
        JSON response with predictive insights including:
        - Metric predictions with confidence intervals
        - Capacity forecasts
        - Behavioral patterns
        - Actionable recommendations
    """
    horizon_hours = _parse_int(request.args.get("horizon"), 168)
    include_recommendations = request.args.get(
        "include_recommendations", "true"
    ).lower() == "true"

    try:
        engine = _get_predictive_analytics_engine()
        insights: PredictiveInsightsV1 = engine.generate_insights(
            horizon_hours=horizon_hours
        )

        # Filter recommendations if not requested
        if not include_recommendations:
            insights.recommendations = []
            insights.actionable_recommendations = 0

        return jsonify({
            "ok": True,
            "data": insights.to_dict(),
        })

    except Exception as e:
        _LOGGER.exception("Error generating predictions")
        return jsonify({
            "ok": False,
            "error": "Failed to generate predictions",
            "details": str(e),
        }), 500


@advanced_analytics_bp.get("/patterns")
def get_analytics_patterns():
    """Get behavioral patterns and module correlations.

    Query Parameters:
        days (int): Number of days to analyze (default: 30)
        include_correlations (bool): Include correlation matrix (default: true)
        include_distributions (bool): Include metric distributions (default: true)

    Returns:
        JSON response with pattern analysis including:
        - Advanced analytics (distributions, correlations, accelerations)
        - Behavioral patterns
        - Anomaly severity scores
    """
    days_lookback = _parse_int(request.args.get("days"), 30)
    include_correlations = request.args.get(
        "include_correlations", "true"
    ).lower() == "true"
    include_distributions = request.args.get(
        "include_distributions", "true"
    ).lower() == "true"

    try:
        # Get advanced analytics
        adv_engine = _get_advanced_analytics_engine()
        adv_analytics: AdvancedAnalyticsV1 = adv_engine.compute(
            days_lookback=days_lookback
        )

        # Get predictive patterns
        pred_engine = _get_predictive_analytics_engine()
        pred_insights: PredictiveInsightsV1 = pred_engine.generate_insights(
            horizon_hours=days_lookback * 24
        )

        # Build combined response
        result = {
            "generated_at": adv_analytics.generated_at,
            "time_range_days": adv_analytics.time_range_days,
            "behavioral_patterns": [
                p.to_dict() for p in pred_insights.behavioral_patterns
            ],
            "anomalies": [a.to_dict() for a in adv_analytics.anomalies],
        }

        if include_correlations:
            result["correlations"] = [
                c.to_dict() for c in adv_analytics.correlations
            ]

        if include_distributions:
            result["distributions"] = [
                d.to_dict() for d in adv_analytics.distributions
            ]

        # Add trend accelerations
        result["trend_accelerations"] = [
            a.to_dict() for a in adv_analytics.accelerations
        ]

        return jsonify({
            "ok": True,
            "data": result,
        })

    except Exception as e:
        _LOGGER.exception("Error analyzing patterns")
        return jsonify({
            "ok": False,
            "error": "Failed to analyze patterns",
            "details": str(e),
        }), 500


# ---------------------------------------------------------------------------
# Blueprint registration helper
# ---------------------------------------------------------------------------

def init_app(app) -> None:
    """Initialize advanced analytics API with Flask app."""
    app.register_blueprint(advanced_analytics_bp)
    _LOGGER.info("Registered Advanced Analytics API blueprint")


__all__ = [
    "advanced_analytics_bp",
    "init_app",
]
