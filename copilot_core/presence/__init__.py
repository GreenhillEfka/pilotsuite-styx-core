"""Bayesian Presence Detection — Wilson Score Interval + Bayesian Fusion.

This module provides robust presence detection by combining:
1. Wilson Score Interval for confidence-bounded sensor readings
2. Bayesian Fusion for multi-sensor data combination with priors
3. Temporal smoothing for state stability
"""
from .bayesian_fusion import BayesianPresenceFusion, PresenceState, SensorReading
from .wilson_interval import WilsonScoreInterval
from .detector import PresenceDetector, PresenceConfig
from .priors import PriorManager, PresencePrior

__all__ = [
    "BayesianPresenceFusion",
    "PresenceState",
    "SensorReading",
    "WilsonScoreInterval",
    "PresenceDetector",
    "PresenceConfig",
    "PriorManager",
    "PresencePrior",
]
