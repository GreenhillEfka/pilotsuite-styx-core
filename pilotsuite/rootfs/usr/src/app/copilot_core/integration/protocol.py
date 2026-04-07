"""
Module Protocol — Standardized interface for bus-aware modules.

Any module that wants to participate in the integration bus should
implement this protocol. This is a structural (duck-typing) protocol —
modules don't need to inherit from it, just implement the methods.

Usage::

    class MyModule(ModuleProtocol):
        def get_id(self) -> str:
            return "my_module"

        def get_layer(self) -> int:
            return 1  # State layer

        def get_dependencies(self) -> list[str]:
            return ["neuron_manager", "brain_graph"]

        def on_bus_event(self, event: BusEvent) -> None:
            if event.event_type == "mood.changed":
                self.handle_mood(event.data)

        def get_state_summary(self) -> dict:
            return {"status": "active", "items_processed": 42}
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .bus import BusEvent

_LOGGER = logging.getLogger(__name__)


class ModuleProtocol(ABC):
    """Standardized interface for integration-bus-aware modules.

    Layers:
        0 — Context (raw HA sensor data)
        1 — State (derived/smoothed values)
        2 — Mood (aggregated emotional states)
        3 — Meta (cross-cutting: habitus, brain_graph, calendar, ...)
    """

    @abstractmethod
    def get_id(self) -> str:
        """Return the unique module identifier (e.g. ``'habitus_miner'``)."""

    @abstractmethod
    def get_layer(self) -> int:
        """Return the module's conceptual layer (0-3)."""

    @abstractmethod
    def get_dependencies(self) -> List[str]:
        """Return IDs of modules this module depends on."""

    @abstractmethod
    def on_bus_event(self, event: BusEvent) -> None:
        """Handle an event from the integration bus.

        This is called synchronously by the bus. Keep processing fast
        or offload to a background thread for heavy work.
        """

    @abstractmethod
    def get_state_summary(self) -> Dict[str, Any]:
        """Return a snapshot of this module's current state for diagnostics."""
