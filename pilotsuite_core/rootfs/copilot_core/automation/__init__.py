"""Automation Analytics — Slice 54."""

from .analytics import (
    AutomationExecutionEntryV1,
    AutomationExecutionHistoryV1,
    AutomationRulePatternEntryV1,
    AutomationRulePatternsV1,
    AutomationEffectivenessMetricsV1,
    AutomationAnalyticsSummaryV1,
    AutomationStatus,
    AutomationTriggerType,
)
from .analytics_store import AutomationAnalyticsStore, get_automation_analytics_store

__all__ = [
    "AutomationExecutionEntryV1",
    "AutomationExecutionHistoryV1",
    "AutomationRulePatternEntryV1",
    "AutomationRulePatternsV1",
    "AutomationEffectivenessMetricsV1",
    "AutomationAnalyticsSummaryV1",
    "AutomationStatus",
    "AutomationTriggerType",
    "AutomationAnalyticsStore",
    "get_automation_analytics_store",
]
