"""Compatibility rules facade for integration tests."""
from __future__ import annotations

from typing import Any, Dict


class RulesEngine:
    """Small event-driven rules facade expected by legacy integration tests."""

    def __init__(self, event_bus: Any = None, zone_registry: Any = None):
        self.event_bus = event_bus
        self.zone_registry = zone_registry

    def activate_rule(self, rule_name: str, zone_id: str) -> Dict[str, Any]:
        payload = {
            "rule": rule_name,
            "zone_id": zone_id,
            "action": "dim",
            "brightness": 20,
        }
        if self.event_bus and hasattr(self.event_bus, "publish"):
            self.event_bus.publish("rules_activate", payload)
        return payload
