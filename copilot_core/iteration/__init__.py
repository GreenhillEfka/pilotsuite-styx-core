"""
Continuous Improvement Engine — Iteration Package

Automatisierte Verbesserungsschleife für PilotSuite.
"""

from .iteration_loop import (
    ContinuousImprovementEngine,
    MetricsCollector,
    ImprovementIdentifier,
    LowRiskImplementer,
    HighRiskReporter,
    GitManager,
    IterationReport,
    Improvement,
    Metric,
    RiskLevel,
    ImprovementType
)

__all__ = [
    "ContinuousImprovementEngine",
    "MetricsCollector",
    "ImprovementIdentifier",
    "LowRiskImplementer",
    "HighRiskReporter",
    "GitManager",
    "IterationReport",
    "Improvement",
    "Metric",
    "RiskLevel",
    "ImprovementType"
]
