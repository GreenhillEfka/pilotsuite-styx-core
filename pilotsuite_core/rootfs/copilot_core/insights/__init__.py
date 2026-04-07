"""
Insights module for PilotSuite Core.

Provides actionable insights derived from analytics data.
"""

from .contracts import (
    InsightV1,
    InsightSummaryV1,
    InsightDeltaV1,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    InsightSource,
)
from .store import InsightStore
from .generators import (
    InsightGenerator,
    PerformanceInsightGenerator,
    AnomalyInsightGenerator,
    TrendInsightGenerator,
    OptimizationInsightGenerator,
    HealthInsightGenerator,
    UsageInsightGenerator,
    PredictionInsightGenerator,
    EfficiencyInsightGenerator,
    run_all_generators,
)

__all__ = [
    "InsightV1",
    "InsightSummaryV1",
    "InsightDeltaV1",
    "InsightCategory",
    "InsightSeverity",
    "InsightStatus",
    "InsightSource",
    "InsightStore",
    "InsightGenerator",
    "PerformanceInsightGenerator",
    "AnomalyInsightGenerator",
    "TrendInsightGenerator",
    "OptimizationInsightGenerator",
    "HealthInsightGenerator",
    "UsageInsightGenerator",
    "PredictionInsightGenerator",
    "EfficiencyInsightGenerator",
    "run_all_generators",
]
