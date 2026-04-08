"""Synapses module for PilotSuite neural connections.

Synapses connect neurons to each other and to suggestions.
They define how signals propagate through the neural network.

Architecture:
    Context Neurons → State Neurons → Mood Neurons → Suggestions
    
Each synapse has:
- Source: Input neuron
- Target: Output neuron or suggestion
- Weight: Signal strength (-1.0 to 1.0)
- Threshold: Minimum input to fire
"""
from .manager import SynapseManager
from .models import Synapse, SynapseType, SynapseState

__all__ = [
    "SynapseManager",
    "Synapse",
    "SynapseType",
    "SynapseState",
]