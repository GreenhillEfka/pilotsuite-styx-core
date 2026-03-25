"""Automation module for PilotSuite — Pattern Learning & Prediction."""

from .pattern_learner import PatternLearner  # noqa: F401
from .predictor import PredictiveAutomationEngine  # noqa: F401
from .synapse_integration import (  # noqa: F401
    SynapseLink,
    SynapseRegistry,
    get_synapse_registry,
    resolve_entity_to_neuron,
    scan_automation_entities,
    register_automation_synapse,
    get_zone_automation_synapses,
    get_affected_automations_on_entity_change,
)

__all__ = [
    "PatternLearner",
    "PredictiveAutomationEngine",
    "SynapseLink",
    "SynapseRegistry",
    "get_synapse_registry",
    "resolve_entity_to_neuron",
    "scan_automation_entities",
    "register_automation_synapse",
    "get_zone_automation_synapses",
    "get_affected_automations_on_entity_change",
]
