"""Rule Engine — Deep Symbiosis Layer.
Implements the actual logic for Habitus Rules and Context transitions.
"""
import logging
from typing import List, Dict

_LOGGER = logging.getLogger(__name__)

class SymbioticRuleEngine:
    def __init__(self):
        self.rules = {}
        self.rule_counter = 0

    def register_rule(self, zone_id: str, rule_type: str, condition: dict, action: dict) -> str:
        """Register a new rule for a zone."""
        self.rule_counter += 1
        rule_id = f"rule_{self.rule_counter}"
        self.rules[rule_id] = {
            "zone_id": zone_id,
            "type": rule_type,
            "condition": condition,
            "action": action,
            "enabled": True,
            "triggered_count": 0
        }
        _LOGGER.info(f"Registered rule {rule_id} for zone {zone_id}")
        return rule_id

    def evaluate_zone(self, zone_data: dict, current_events: List[dict]) -> List[dict]:
        """Evaluates all rules for a specific zone."""
        _LOGGER.info(f"Evaluating rules for zone {zone_data.get('zone_id')}")
        triggered_actions = []
        for rule_id, rule in self.rules.items():
            if not rule["enabled"] or rule["zone_id"] != zone_data.get("zone_id"):
                continue
            # Simple condition check
            if rule["type"] == "presence" and any(e.get("event_type") == "presence" for e in current_events):
                rule["triggered_count"] += 1
                triggered_actions.append(rule["action"])
        return triggered_actions

    def enable_rule(self, rule_id: str) -> bool:
        if rule_id in self.rules:
            self.rules[rule_id]["enabled"] = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        if rule_id in self.rules:
            self.rules[rule_id]["enabled"] = False
            return True
        return False

    def get_rules_for_zone(self, zone_id: str) -> List[dict]:
        return [r for r in self.rules.values() if r["zone_id"] == zone_id]

class ContextManager:
    def __init__(self):
        self.active_contexts = {}
        self.context_history = {}
        self.transitions = []

    def transition(self, zone_id: str, new_context: str, reason: str = "manual") -> dict:
        """Manages stateful transitions between contexts."""
        old_context = self.active_contexts.get(zone_id, "none")
        _LOGGER.info(f"Transitioning zone {zone_id} from {old_context} to {new_context}")
        self.active_contexts[zone_id] = new_context
        self.transitions.append({
            "zone_id": zone_id,
            "from": old_context,
            "to": new_context,
            "reason": reason,
            "timestamp": "now"
        })
        if zone_id not in self.context_history:
            self.context_history[zone_id] = []
        self.context_history[zone_id].append(new_context)
        return {"zone_id": zone_id, "new_context": new_context, "previous": old_context}

    def get_active_context(self, zone_id: str) -> str:
        return self.active_contexts.get(zone_id, "ready")

    def get_context_history(self, zone_id: str) -> List[str]:
        return self.context_history.get(zone_id, [])

    def revert_last(self, zone_id: str) -> str:
        if zone_id in self.context_history and len(self.context_history[zone_id]) > 1:
            self.context_history[zone_id].pop()
            prev = self.context_history[zone_id][-1]
            self.active_contexts[zone_id] = prev
            return prev
        return None
