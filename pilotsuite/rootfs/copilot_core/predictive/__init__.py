"""Predictive — Behavioral pattern engine for Slice 14.

Slice 14 — Predictive Automation

This module provides:
- BehavioralPattern: long-term learned pattern model
- PredictiveProposal: proposal that feeds into AutomationSuggestionEngine
- PredictiveAutomationEngine: generates proposals from observations

ALL predictive proposals MUST flow through the AutomationSuggestionEngine
proposal lifecycle (accept/reject/execute). This module does NOT implement
a parallel policy engine.

Pattern types:
- TIME_BASED: recurring at specific time
- PRESENCE_BASED: triggered by presence detection
- WEATHER_BASED: triggered by weather conditions
- CALENDAR_BASED: triggered by calendar events
- SEASONAL: seasonal patterns
- BEHAVIORAL: learned from user behavior
"""

from .automation_engine import (
    PatternType,
    PredictionConfidence,
    BehavioralPattern,
    PredictiveProposal,
    PredictiveAutomationEngine,
    create_predictive_automation_engine,
)

__all__ = [
    "PatternType",
    "PredictionConfidence",
    "BehavioralPattern",
    "PredictiveProposal",
    "PredictiveAutomationEngine",
    "create_predictive_automation_engine",
]
