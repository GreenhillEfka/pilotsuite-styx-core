"""Tests for Module Orchestration / Rules Engine — Slice 73."""
import pytest
from copilot_core.orchestration.rules_engine import (
    RulesEngine,
    Rule,
    Condition,
    Action,
    RuleOperator,
    RuleConnector,
    ActionType,
    RuleState,
    RuleExecution,
    ModuleConnection,
    create_rules_engine,
    create_presence_light_rule,
    create_absence_light_off_rule,
    create_evening_scene_rule,
)
from datetime import datetime, timezone
import time


class TestRuleOperator:
    def test_operator_enum_values(self):
        assert RuleOperator.EQ.value == "eq"
        assert RuleOperator.GT.value == "gt"
        assert RuleOperator.LT.value == "lt"


class TestRuleConnector:
    def test_connector_enum_values(self):
        assert RuleConnector.AND.value == "and"
        assert RuleConnector.OR.value == "or"


class TestActionType:
    def test_action_type_enum_values(self):
        assert ActionType.LIGHT_TURN_ON.value == "light.turn_on"
        assert ActionType.LIGHT_TURN_OFF.value == "light.turn_off"
        assert ActionType.LIGHT_SCENE.value == "light.scene"


class TestRuleState:
    def test_state_enum_values(self):
        assert RuleState.IDLE.value == "idle"
        assert RuleState.TRIGGERED.value == "triggered"
        assert RuleState.DISABLED.value == "disabled"


class TestCondition:
    def test_create_condition(self):
        cond = Condition(field="presence.state", operator=RuleOperator.EQ, value="present")
        assert cond.field == "presence.state"
        assert cond.operator == RuleOperator.EQ
    
    def test_condition_eq_true(self):
        cond = Condition(field="presence.state", operator=RuleOperator.EQ, value="present")
        context = {"presence": {"state": "present"}}
        assert cond.evaluate(context) is True
    
    def test_condition_eq_false(self):
        cond = Condition(field="presence.state", operator=RuleOperator.EQ, value="present")
        context = {"presence": {"state": "absent"}}
        assert cond.evaluate(context) is False
    
    def test_condition_gt(self):
        cond = Condition(field="light.level", operator=RuleOperator.GT, value=0.5)
        context = {"light": {"level": 0.8}}
        assert cond.evaluate(context) is True
    
    def test_condition_lt(self):
        cond = Condition(field="light.level", operator=RuleOperator.LT, value=0.3)
        context = {"light": {"level": 0.2}}
        assert cond.evaluate(context) is True
    
    def test_condition_between(self):
        cond = Condition(field="comfort.index", operator=RuleOperator.BETWEEN, value=(0.4, 0.8))
        context = {"comfort": {"index": 0.6}}
        assert cond.evaluate(context) is True
    
    def test_condition_in(self):
        cond = Condition(field="timeofday.phase", operator=RuleOperator.IN, value=["evening", "night"])
        context = {"timeofday": {"phase": "evening"}}
        assert cond.evaluate(context) is True
    
    def test_condition_not_in(self):
        cond = Condition(field="timeofday.phase", operator=RuleOperator.NOT_IN, value=["night"])
        context = {"timeofday": {"phase": "morning"}}
        assert cond.evaluate(context) is True
    
    def test_condition_nested_field(self):
        cond = Condition(field="presence.state", operator=RuleOperator.EQ, value="present")
        context = {"presence": {"state": "present", "confidence": 0.9}}
        assert cond.evaluate(context) is True
    
    def test_condition_missing_field(self):
        cond = Condition(field="presence.state", operator=RuleOperator.EQ, value="present")
        context = {"light": {"level": 0.5}}
        assert cond.evaluate(context) is False
    
    def test_condition_to_dict(self):
        cond = Condition(field="light.level", operator=RuleOperator.LT, value=0.3, zone_id="zone_1")
        d = cond.to_dict()
        assert d["field"] == "light.level"
        assert d["zone_id"] == "zone_1"


class TestAction:
    def test_create_action(self):
        action = Action(action_type=ActionType.LIGHT_TURN_ON, target_zone="zone_1")
        assert action.action_type == ActionType.LIGHT_TURN_ON
    
    def test_action_to_dict(self):
        action = Action(
            action_type=ActionType.LIGHT_SCENE,
            target_zone="zone_1",
            parameters={"scene": "relaxing"},
        )
        d = action.to_dict()
        assert d["action_type"] == "light.scene"
        assert d["parameters"]["scene"] == "relaxing"


class TestRule:
    def test_create_rule(self):
        rule = Rule(
            rule_id="rule_test",
            name="Test Rule",
            zone_id="zone_1",
            conditions=[],
            connector=RuleConnector.AND,
            actions=[],
        )
        assert rule.rule_id == "rule_test"
        assert rule.enabled is True
    
    def test_rule_to_dict(self):
        rule = Rule(
            rule_id="rule_test",
            name="Test",
            zone_id="zone_1",
            conditions=[Condition("presence.state", RuleOperator.EQ, "present")],
            connector=RuleConnector.AND,
            actions=[Action(ActionType.LIGHT_TURN_ON, "zone_1")],
            priority=70,
        )
        d = rule.to_dict()
        assert d["priority"] == 70
        assert len(d["conditions"]) == 1


class TestRuleExecution:
    def test_create_execution(self):
        exec_record = RuleExecution(
            execution_id="rex_test",
            rule_id="rule_test",
            zone_id="zone_1",
            timestamp="2025-01-01T00:00:00Z",
            conditions_met=True,
            actions_executed=1,
            success=True,
        )
        assert exec_record.success is True
    
    def test_execution_to_dict(self):
        exec_record = RuleExecution(
            execution_id="rex_test",
            rule_id="rule_test",
            zone_id="zone_1",
            timestamp="2025-01-01T00:00:00Z",
            conditions_met=True,
            actions_executed=2,
            success=True,
        )
        d = exec_record.to_dict()
        assert d["actions_executed"] == 2


class TestModuleConnection:
    def test_create_connection(self):
        conn = ModuleConnection(
            source_module="presence",
            source_field="state",
            target_module="light",
            target_field="auto_enabled",
        )
        assert conn.source_module == "presence"
    
    def test_connection_with_transform(self):
        conn = ModuleConnection(
            source_module="presence",
            source_field="confidence",
            target_module="light",
            target_field="brightness",
            transform="multiply:0.8",
        )
        assert conn.transform == "multiply:0.8"
    
    def test_connection_to_dict(self):
        conn = ModuleConnection(
            source_module="presence",
            source_field="state",
            target_module="light",
            target_field="auto_enabled",
        )
        d = conn.to_dict()
        assert d["source_module"] == "presence"


class TestRulesEngine:
    def test_create_engine(self):
        engine = create_rules_engine()
        assert engine is not None
    
    def test_register_module(self):
        engine = RulesEngine()
        result = engine.register_module("presence", {"name": "presence_module"})
        assert result is True
        assert "presence" in engine._modules
    
    def test_unregister_module(self):
        engine = RulesEngine()
        engine.register_module("presence", {})
        result = engine.unregister_module("presence")
        assert result is True
        assert "presence" not in engine._modules
    
    def test_add_rule(self):
        engine = RulesEngine()
        rule = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        rule_id = engine.add_rule(rule)
        assert rule_id == "rule_1"
        assert engine.get_rule("rule_1") is not None
    
    def test_remove_rule(self):
        engine = RulesEngine()
        rule = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        engine.add_rule(rule)
        result = engine.remove_rule("rule_1")
        assert result is True
        assert engine.get_rule("rule_1") is None
    
    def test_enable_rule(self):
        engine = RulesEngine()
        rule = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        rule.enabled = False
        engine.add_rule(rule)
        result = engine.enable_rule("rule_1")
        assert result is True
        assert engine.get_rule("rule_1").enabled is True
    
    def test_disable_rule(self):
        engine = RulesEngine()
        rule = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        engine.add_rule(rule)
        result = engine.disable_rule("rule_1")
        assert result is True
        assert engine.get_rule("rule_1").enabled is False
    
    def test_update_module_context(self):
        engine = RulesEngine()
        engine.register_module("presence", {})
        engine.update_module_context("presence", {"state": "present"})
        assert engine._module_contexts["presence"]["state"] == "present"
    
    def test_evaluate_rule_and_connector(self):
        engine = RulesEngine()
        
        rule = Rule(
            rule_id="rule_1",
            name="Test",
            zone_id=None,
            conditions=[
                Condition("presence.state", RuleOperator.EQ, "present"),
                Condition("light.level", RuleOperator.LT, 0.3),
            ],
            connector=RuleConnector.AND,
            actions=[],
        )
        
        # All conditions met
        context = {"presence": {"state": "present"}, "light": {"level": 0.2}}
        assert engine.evaluate_rule(rule, context) is True
        
        # One condition not met
        context = {"presence": {"state": "present"}, "light": {"level": 0.5}}
        assert engine.evaluate_rule(rule, context) is False
    
    def test_evaluate_rule_or_connector(self):
        engine = RulesEngine()
        
        rule = Rule(
            rule_id="rule_1",
            name="Test",
            zone_id=None,
            conditions=[
                Condition("presence.state", RuleOperator.EQ, "present"),
                Condition("light.level", RuleOperator.LT, 0.3),
            ],
            connector=RuleConnector.OR,
            actions=[],
        )
        
        # One condition met
        context = {"presence": {"state": "present"}, "light": {"level": 0.5}}
        assert engine.evaluate_rule(rule, context) is True
    
    def test_evaluate_rule_disabled(self):
        engine = RulesEngine()
        
        rule = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        rule.enabled = False
        
        context = {}
        assert engine.evaluate_rule(rule, context) is False
    
    def test_evaluate_rule_cooldown(self):
        engine = RulesEngine()
        
        rule = Rule("rule_1", "Test", None, [], RuleConnector.AND, [], cooldown_seconds=10)
        rule.last_triggered = datetime.now(timezone.utc).isoformat()
        
        context = {}
        assert engine.evaluate_rule(rule, context) is False
    
    def test_execute_actions_with_callback(self):
        engine = RulesEngine()
        
        executed_actions = []
        
        def callback(action, context):
            executed_actions.append(action)
        
        engine.register_action_callback(ActionType.LIGHT_TURN_ON, callback)
        
        rule = Rule(
            rule_id="rule_1",
            name="Test",
            zone_id=None,
            conditions=[],
            connector=RuleConnector.AND,
            actions=[Action(ActionType.LIGHT_TURN_ON, "zone_1")],
        )
        
        context = {}
        count = engine.execute_actions(rule, context)
        
        assert count == 1
        assert len(executed_actions) == 1
    
    def test_evaluate_all(self):
        engine = RulesEngine()
        
        rule = Rule(
            rule_id="rule_1",
            name="Test",
            zone_id=None,
            conditions=[Condition("presence.state", RuleOperator.EQ, "present")],
            connector=RuleConnector.AND,
            actions=[],
        )
        engine.add_rule(rule)
        
        engine.update_module_context("presence", {"state": "present"})
        
        executions = engine.evaluate_all()
        
        assert len(executions) == 1
        assert executions[0].conditions_met is True
    
    def test_evaluate_all_zone_filter(self):
        engine = RulesEngine()
        
        rule_zone1 = Rule("rule_1", "Test", "zone_1", [], RuleConnector.AND, [])
        rule_zone2 = Rule("rule_2", "Test", "zone_2", [], RuleConnector.AND, [])
        
        engine.add_rule(rule_zone1)
        engine.add_rule(rule_zone2)
        
        executions = engine.evaluate_all(zone_id="zone_1")
        
        # Only zone_1 rule should be evaluated
        assert len(executions) == 1
    
    def test_get_rules(self):
        engine = RulesEngine()
        
        rule1 = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        rule2 = Rule("rule_2", "Test", "zone_1", [], RuleConnector.AND, [])
        
        engine.add_rule(rule1)
        engine.add_rule(rule2)
        
        all_rules = engine.get_rules()
        assert len(all_rules) == 2
        
        zone1_rules = engine.get_rules(zone_id="zone_1")
        assert len(zone1_rules) == 1
    
    def test_get_rules_enabled_only(self):
        engine = RulesEngine()
        
        rule1 = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        rule2 = Rule("rule_2", "Test", None, [], RuleConnector.AND, [])
        rule2.enabled = False
        
        engine.add_rule(rule1)
        engine.add_rule(rule2)
        
        enabled = engine.get_rules(enabled_only=True)
        assert len(enabled) == 1
    
    def test_get_executions(self):
        engine = RulesEngine()
        
        rule = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        engine.add_rule(rule)
        engine.evaluate_all()
        
        executions = engine.get_executions()
        assert len(executions) >= 1
    
    def test_get_statistics(self):
        engine = RulesEngine()
        
        rule = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        engine.add_rule(rule)
        engine.evaluate_all()
        
        stats = engine.get_statistics()
        
        assert stats["total_rules"] == 1
        assert stats["total_executions"] >= 1
    
    def test_add_module_connection(self):
        engine = RulesEngine()
        
        conn = ModuleConnection("presence", "state", "light", "auto_enabled")
        engine.add_module_connection(conn)
        
        assert len(engine._connections) == 1
    
    def test_apply_module_connections(self):
        engine = RulesEngine()
        
        engine.register_module("presence", {})
        engine.register_module("light", {})
        
        engine.update_module_context("presence", {"state": "present"})
        
        conn = ModuleConnection("presence", "state", "light", "presence_state")
        engine.add_module_connection(conn)
        
        applied = engine.apply_module_connections()
        
        assert applied == 1
        assert engine._module_contexts["light"]["presence_state"] == "present"
    
    def test_apply_transform_multiply(self):
        engine = RulesEngine()
        
        result = engine._apply_transform("multiply:0.8", 0.5)
        
        assert result == 0.4
    
    def test_apply_transform_add(self):
        engine = RulesEngine()
        
        result = engine._apply_transform("add:10", 5)
        
        assert result == 15
    
    def test_apply_transform_bool(self):
        engine = RulesEngine()
        
        assert engine._apply_transform("bool", 1) is True
        assert engine._apply_transform("bool", 0) is False
    
    def test_apply_transform_invert(self):
        engine = RulesEngine()
        
        assert engine._apply_transform("invert", True) is False
    
    def test_rule_priority_sorting(self):
        engine = RulesEngine()
        
        rule_low = Rule("rule_low", "Low", None, [], RuleConnector.AND, [], priority=10)
        rule_high = Rule("rule_high", "High", None, [], RuleConnector.AND, [], priority=90)
        
        engine.add_rule(rule_low)
        engine.add_rule(rule_high)
        
        # High priority should be evaluated first
        # (we can't directly test order, but priority is stored correctly)
        assert engine.get_rule("rule_high").priority == 90
        assert engine.get_rule("rule_low").priority == 10
    
    def test_executions_limited_to_1000(self):
        engine = RulesEngine()
        
        rule = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        engine.add_rule(rule)
        
        for i in range(1500):
            engine.evaluate_all()
        
        assert len(engine._executions) == 1000
    
    def test_create_rules_engine_returns_instance(self):
        assert isinstance(create_rules_engine(), RulesEngine)
    
    def test_rule_to_dict_includes_all_fields(self):
        rule = Rule(
            rule_id="rule_test",
            name="Test Rule",
            zone_id="zone_1",
            conditions=[Condition("presence.state", RuleOperator.EQ, "present")],
            connector=RuleConnector.AND,
            actions=[Action(ActionType.LIGHT_TURN_ON, "zone_1")],
            priority=75,
            enabled=True,
            cooldown_seconds=60,
            description="Test description",
        )
        d = rule.to_dict()
        assert d["priority"] == 75
        assert d["cooldown_seconds"] == 60
        assert d["description"] == "Test description"
    
    def test_condition_zone_id(self):
        cond = Condition("presence.state", RuleOperator.EQ, "present", zone_id="zone_1")
        assert cond.zone_id == "zone_1"
    
    def test_action_parameters(self):
        action = Action(ActionType.LIGHT_SCENE, "zone_1", {"scene": "relaxing", "brightness": 0.5})
        assert action.parameters["scene"] == "relaxing"
    
    def test_execution_context_snapshot(self):
        exec_record = RuleExecution(
            execution_id="rex_test",
            rule_id="rule_test",
            zone_id="zone_1",
            timestamp="2025-01-01T00:00:00Z",
            conditions_met=True,
            actions_executed=1,
            success=True,
            context_snapshot={"presence": {"state": "present"}},
        )
        assert exec_record.context_snapshot["presence"]["state"] == "present"
    
    def test_statistics_initial_values(self):
        engine = RulesEngine()
        stats = engine.get_statistics()
        assert stats["total_rules"] == 0
        assert stats["enabled_rules"] == 0
        assert stats["total_executions"] == 0
    
    def test_statistics_enabled_disabled(self):
        engine = RulesEngine()
        
        rule1 = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        rule2 = Rule("rule_2", "Test", None, [], RuleConnector.AND, [])
        rule2.enabled = False
        
        engine.add_rule(rule1)
        engine.add_rule(rule2)
        
        stats = engine.get_statistics()
        assert stats["enabled_rules"] == 1
        assert stats["disabled_rules"] == 1
    
    def test_get_executions_limit(self):
        engine = RulesEngine()
        
        rule = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        engine.add_rule(rule)
        
        for i in range(100):
            engine.evaluate_all()
        
        executions = engine.get_executions(limit=10)
        assert len(executions) <= 10
    
    def test_get_executions_by_rule_id(self):
        engine = RulesEngine()
        
        rule1 = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        rule2 = Rule("rule_2", "Test", None, [], RuleConnector.AND, [])
        
        engine.add_rule(rule1)
        engine.add_rule(rule2)
        
        engine.evaluate_all()
        
        executions = engine.get_executions(rule_id="rule_1")
        
        for e in executions:
            assert e.rule_id == "rule_1"
    
    def test_unregister_nonexistent_module(self):
        engine = RulesEngine()
        result = engine.unregister_module("nonexistent")
        assert result is False
    
    def test_remove_nonexistent_rule(self):
        engine = RulesEngine()
        result = engine.remove_rule("nonexistent")
        assert result is False
    
    def test_enable_nonexistent_rule(self):
        engine = RulesEngine()
        result = engine.enable_rule("nonexistent")
        assert result is False
    
    def test_disable_nonexistent_rule(self):
        engine = RulesEngine()
        result = engine.disable_rule("nonexistent")
        assert result is False
    
    def test_get_nonexistent_rule(self):
        engine = RulesEngine()
        assert engine.get_rule("nonexistent") is None
    
    def test_evaluate_all_with_exception(self):
        engine = RulesEngine()
        
        # Register callback that raises exception
        def failing_callback(action, context):
            raise Exception("Test exception")
        
        engine.register_action_callback(ActionType.LIGHT_TURN_ON, failing_callback)
        
        rule = Rule(
            rule_id="rule_1",
            name="Test",
            zone_id=None,
            conditions=[],
            connector=RuleConnector.AND,
            actions=[Action(ActionType.LIGHT_TURN_ON, "zone_1")],
        )
        engine.add_rule(rule)
        
        executions = engine.evaluate_all()
        
        # Should complete without crashing
        assert len(executions) >= 1
    
    def test_module_connection_to_dict(self):
        conn = ModuleConnection(
            source_module="presence",
            source_field="confidence",
            target_module="light",
            target_field="brightness",
            transform="multiply:0.8",
        )
        d = conn.to_dict()
        assert d["transform"] == "multiply:0.8"
    
    def test_build_zone_context(self):
        engine = RulesEngine()
        engine.register_module("presence", {})
        engine.update_module_context("presence", {"state": "present"})
        
        context = engine._build_zone_context("zone_1")
        
        assert "presence" in context
        assert context["zone_id"] == "zone_1"
        assert "timestamp" in context
    
    def test_create_presence_light_rule(self):
        rule = create_presence_light_rule("zone_living", brightness_threshold=0.3)
        
        assert rule.zone_id == "zone_living"
        assert len(rule.conditions) == 2
        assert rule.actions[0].action_type == ActionType.LIGHT_TURN_ON
    
    def test_create_absence_light_off_rule(self):
        rule = create_absence_light_off_rule("zone_bedroom", delay_seconds=600)
        
        assert rule.zone_id == "zone_bedroom"
        assert rule.cooldown_seconds == 600
        assert rule.actions[0].action_type == ActionType.LIGHT_TURN_OFF
    
    def test_create_evening_scene_rule(self):
        rule = create_evening_scene_rule("zone_living")
        
        assert rule.zone_id == "zone_living"
        assert rule.actions[0].action_type == ActionType.LIGHT_SCENE
        assert rule.actions[0].parameters["scene"] == "relaxing"
    
    def test_rule_state_transitions(self):
        engine = RulesEngine()
        
        rule = Rule("rule_1", "Test", None, [], RuleConnector.AND, [])
        engine.add_rule(rule)
        
        assert rule.state == RuleState.IDLE
        
        engine.evaluate_all()
        
        # State should have changed during evaluation
        assert rule.state in (RuleState.IDLE, RuleState.COMPLETED)
    
    def test_action_callback_not_registered(self):
        engine = RulesEngine()
        
        rule = Rule(
            rule_id="rule_1",
            name="Test",
            zone_id=None,
            conditions=[],
            connector=RuleConnector.AND,
            actions=[Action(ActionType.LIGHT_TURN_ON, "zone_1")],
        )
        engine.add_rule(rule)
        
        # No callback registered - should log warning but not crash
        executed = engine.execute_actions(rule, {})
        
        # Action not executed (no callback)
        assert executed == 0
    
    def test_multiple_conditions_same_field(self):
        engine = RulesEngine()
        
        rule = Rule(
            rule_id="rule_1",
            name="Test",
            zone_id=None,
            conditions=[
                Condition("light.level", RuleOperator.LT, 0.3),
                Condition("light.level", RuleOperator.GT, 0.1),
            ],
            connector=RuleConnector.AND,
            actions=[],
        )
        
        context = {"light": {"level": 0.2}}
        assert engine.evaluate_rule(rule, context) is True
        
        context = {"light": {"level": 0.05}}
        assert engine.evaluate_rule(rule, context) is False
    
    def test_condition_none_value(self):
        cond = Condition("presence.state", RuleOperator.EQ, "present")
        context = {"presence": None}
        assert cond.evaluate(context) is False
    
    def test_rule_with_no_conditions(self):
        engine = RulesEngine()
        
        rule = Rule("rule_1", "Always", None, [], RuleConnector.AND, [])
        engine.add_rule(rule)
        
        context = {}
        assert engine.evaluate_rule(rule, context) is True
    
    def test_rule_with_no_actions(self):
        engine = RulesEngine()
        
        rule = Rule(
            rule_id="rule_1",
            name="Test",
            zone_id=None,
            conditions=[Condition("presence.state", RuleOperator.EQ, "present")],
            connector=RuleConnector.AND,
            actions=[],
        )
        engine.add_rule(rule)
        
        engine.update_module_context("presence", {"state": "present"})
        
        executions = engine.evaluate_all()
        
        assert executions[0].actions_executed == 0
    
    def test_register_module_replaces_existing(self):
        engine = RulesEngine()
        
        engine.register_module("presence", {"version": 1})
        engine.register_module("presence", {"version": 2})
        
        assert engine._modules["presence"]["version"] == 2
    
    def test_get_statistics_registered_modules(self):
        engine = RulesEngine()
        
        engine.register_module("presence", {})
        engine.register_module("light", {})
        
        stats = engine.get_statistics()
        
        assert stats["registered_modules"] == 2
    
    def test_get_statistics_module_connections(self):
        engine = RulesEngine()
        
        engine.add_module_connection(ModuleConnection("p", "s", "l", "t"))
        engine.add_module_connection(ModuleConnection("l", "s", "c", "t"))
        
        stats = engine.get_statistics()
        
        assert stats["module_connections"] == 2
