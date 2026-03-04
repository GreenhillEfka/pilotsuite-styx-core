"""
Integration package — Module communication bus and protocol.

Provides:
- IntegrationBus: Event-based pub/sub bus for cross-module communication
- ModuleProtocol: Standardized interface for all bus-aware modules

Event Types:
    neuron.evaluated    — Pipeline completed (14 neuron values)
    mood.changed        — Dominant mood changed
    pattern.discovered  — Habitus miner found new A→B pattern
    suggestion.created  — New suggestion generated
    suggestion.accepted — User accepted a suggestion
    suggestion.rejected — User rejected a suggestion
    graph.updated       — BrainGraph nodes/edges changed
    module.state_changed — ModuleRegistry state transition
"""

from .bus import IntegrationBus, BusEvent
from .protocol import ModuleProtocol

__all__ = ["IntegrationBus", "BusEvent", "ModuleProtocol"]
