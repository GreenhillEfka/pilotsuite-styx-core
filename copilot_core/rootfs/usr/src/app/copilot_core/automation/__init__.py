"""Automation module for PilotSuite — Pattern Learning & Prediction."""

from .pattern_learner import PatternLearner  # noqa: F401
from .predictor import PredictiveAutomationEngine  # noqa: F401

__all__ = ["PatternLearner", "PredictiveAutomationEngine"]
