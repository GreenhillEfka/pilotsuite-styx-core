"""Symbiosis Engines Tests — Comprehensive Coverage.
Tests for Rule Engine, Context Manager, and Sync Layers.
"""
import pytest
import time
from copilot_core.symbiosis.rule_engine import SymbioticRuleEngine, ContextManager

class TestSymbioticRuleEngine:
    """Tests for the Symbiotic Rule Engine."""

    def test_register_rule(self):
        engine = SymbioticRuleEngine()
        rule_id = engine.register_rule(
            zone_id="zone.living_room",
            rule_type="presence",
            condition={"sensor": "binary_sensor.motion"},
            action={"service": "light.turn_on"}
        )
        assert rule_id == "rule_1"
        assert rule_id in engine.rules
        assert engine.rules[rule_id]["zone_id"] == "zone.living_room"
        assert engine.rules[rule_id]["enabled"] is True

    def test_evaluate_zone_triggers(self):
        engine = SymbioticRuleEngine()
        engine.register_rule(
            zone_id="zone.living_room",
            rule_type="presence",
            condition={},
            action={"service": "light.turn_on"}
        )
        zone_data = {"zone_id": "zone.living_room"}
        events = [{"event_type": "presence", "data": {"detected": True}}]
        actions = engine.evaluate_zone(zone_data, events)
        assert len(actions) == 1
        assert actions[0]["service"] == "light.turn_on"

    def test_enable_disable_rule(self):
        engine = SymbioticRuleEngine()
        rule_id = engine.register_rule("zone.bedroom", "time", {}, {})
        assert engine.disable_rule(rule_id) is True
        assert engine.rules[rule_id]["enabled"] is False
        assert engine.enable_rule(rule_id) is True
        assert engine.rules[rule_id]["enabled"] is True

    def test_get_rules_for_zone(self):
        engine = SymbioticRuleEngine()
        engine.register_rule("zone.living_room", "presence", {}, {})
        engine.register_rule("zone.living_room", "time", {}, {})
        engine.register_rule("zone.bedroom", "presence", {}, {})
        rules = engine.get_rules_for_zone("zone.living_room")
        assert len(rules) == 2
        assert all(r["zone_id"] == "zone.living_room" for r in rules)

    def test_rule_counter_increments(self):
        engine = SymbioticRuleEngine()
        r1 = engine.register_rule("z1", "t", {}, {})
        r2 = engine.register_rule("z2", "t", {}, {})
        r3 = engine.register_rule("z3", "t", {}, {})
        assert r1 == "rule_1"
        assert r2 == "rule_2"
        assert r3 == "rule_3"


class TestContextManager:
    """Tests for the Context Manager."""

    def test_transition(self):
        cm = ContextManager()
        result = cm.transition("zone.living_room", "evening_mode")
        assert result["zone_id"] == "zone.living_room"
        assert result["new_context"] == "evening_mode"
        assert result["previous"] == "none"
        assert cm.get_active_context("zone.living_room") == "evening_mode"

    def test_transition_chain(self):
        cm = ContextManager()
        cm.transition("zone.lr", "morning")
        cm.transition("zone.lr", "day")
        cm.transition("zone.lr", "evening")
        assert cm.get_active_context("zone.lr") == "evening"
        assert len(cm.get_context_history("zone.lr")) == 3

    def test_revert_last(self):
        cm = ContextManager()
        cm.transition("zone.lr", "morning")
        cm.transition("zone.lr", "day")
        cm.transition("zone.lr", "evening")
        reverted = cm.revert_last("zone.lr")
        assert reverted == "day"
        assert cm.get_active_context("zone.lr") == "day"

    def test_revert_empty(self):
        cm = ContextManager()
        result = cm.revert_last("zone.nonexistent")
        assert result is None

    def test_transitions_logged(self):
        cm = ContextManager()
        cm.transition("zone.lr", "test", reason="automated")
        assert len(cm.transitions) == 1
        assert cm.transitions[0]["reason"] == "automated"
        assert cm.transitions[0]["from"] == "none"
        assert cm.transitions[0]["to"] == "test"


class TestSymbiosisIntegration:
    """Integration tests for Symbiosis components."""

    def test_rule_triggers_context_transition(self):
        engine = SymbioticRuleEngine()
        cm = ContextManager()
        
        # Register a rule that should trigger context change
        engine.register_rule(
            zone_id="zone.lr",
            rule_type="presence",
            condition={},
            action={"type": "context_change", "context": "occupied"}
        )
        
        zone_data = {"zone_id": "zone.lr"}
        events = [{"event_type": "presence"}]
        actions = engine.evaluate_zone(zone_data, events)
        
        # Execute action
        if actions and actions[0].get("type") == "context_change":
            cm.transition("zone.lr", actions[0]["context"])
        
        assert cm.get_active_context("zone.lr") == "occupied"

    def test_multiple_zones_isolation(self):
        cm = ContextManager()
        cm.transition("zone.lr", "evening")
        cm.transition("zone.br", "night")
        cm.transition("zone.kitchen", "cooking")
        
        assert cm.get_active_context("zone.lr") == "evening"
        assert cm.get_active_context("zone.br") == "night"
        assert cm.get_active_context("zone.kitchen") == "cooking"
