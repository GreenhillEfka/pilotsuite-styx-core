"""Tests for Rules Engine Extensions — Slice 78."""
import pytest
from copilot_core.orchestration.rules_extended import (
    RulesEngineExtended,
    RuleTemplateType,
    ConflictType,
    RuleChainNode,
    RuleDependency,
    RuleVariable,
    ConflictRecord,
    RuleStatistics,
    create_rules_engine_extended,
)
from datetime import datetime, timezone


class TestRuleTemplateType:
    def test_template_enum_values(self):
        assert RuleTemplateType.PRESENCE_LIGHT.value == "presence_light"
        assert RuleTemplateType.ABSENCE_OFF.value == "absence_off"
        assert RuleTemplateType.SUNRISE_WAKE.value == "sunrise_wake"


class TestConflictType:
    def test_conflict_enum_values(self):
        assert ConflictType.ACTION_CONFLICT.value == "action_conflict"
        assert ConflictType.PRIORITY_CONFLICT.value == "priority_conflict"


class TestRuleChainNode:
    def test_create_node(self):
        node = RuleChainNode("rule_1")
        assert node.rule_id == "rule_1"
        assert node.triggered_by is None
    
    def test_node_with_trigger(self):
        node = RuleChainNode("rule_2", triggered_by="rule_1")
        assert node.triggered_by == "rule_1"


class TestRuleDependency:
    def test_create_dependency(self):
        dep = RuleDependency(
            dependency_id="dep_1",
            rule_id="rule_2",
            depends_on_rule_ids=["rule_1"],
        )
        assert dep.condition == "all"
        assert dep.timeout_seconds == 0
    
    def test_dependency_any_condition(self):
        dep = RuleDependency(
            dependency_id="dep_1",
            rule_id="rule_2",
            depends_on_rule_ids=["rule_1", "rule_3"],
            condition="any",
        )
        assert dep.condition == "any"
    
    def test_dependency_to_dict(self):
        dep = RuleDependency(
            dependency_id="dep_1",
            rule_id="rule_2",
            depends_on_rule_ids=["rule_1"],
            timeout_seconds=60,
        )
        d = dep.to_dict()
        assert d["timeout_seconds"] == 60


class TestRuleVariable:
    def test_create_variable(self):
        var = RuleVariable(
            name="brightness_multiplier",
            value_type="number",
            default_value=0.8,
        )
        assert var.value_type == "number"
        assert var.read_only is False
    
    def test_variable_evaluate_default(self):
        var = RuleVariable(
            name="test_var",
            value_type="number",
            default_value=42,
        )
        assert var.evaluate({}) == 42
    
    def test_variable_evaluate_expression(self):
        var = RuleVariable(
            name="calc_var",
            value_type="number",
            expression="10 + 5",
        )
        assert var.evaluate({}) == 15
    
    def test_variable_evaluate_with_context(self):
        var = RuleVariable(
            name="dynamic_var",
            value_type="number",
            expression="${value} * 2",
        )
        assert var.evaluate({"value": 5}) == 10
    
    def test_variable_read_only(self):
        var = RuleVariable(
            name="constant",
            value_type="number",
            default_value=3.14,
            read_only=True,
        )
        assert var.read_only is True
    
    def test_variable_to_dict(self):
        var = RuleVariable(
            name="test",
            value_type="string",
            default_value="hello",
            expression=None,
            read_only=False,
        )
        d = var.to_dict()
        assert d["value_type"] == "string"
        assert d["default_value"] == "hello"


class TestConflictRecord:
    def test_create_conflict(self):
        conflict = ConflictRecord(
            conflict_id="conflict_1",
            conflict_type=ConflictType.ACTION_CONFLICT,
            rule_ids=["rule_1", "rule_2"],
            description="Test conflict",
        )
        assert conflict.resolved is False
    
    def test_conflict_to_dict(self):
        conflict = ConflictRecord(
            conflict_id="conflict_1",
            conflict_type=ConflictType.PRIORITY_CONFLICT,
            rule_ids=["rule_1"],
            description="Test",
            resolution="Resolved by priority",
            resolved=True,
        )
        d = conflict.to_dict()
        assert d["resolved"] is True
        assert d["resolution"] == "Resolved by priority"


class TestRuleStatistics:
    def test_create_statistics(self):
        stats = RuleStatistics(rule_id="rule_1")
        assert stats.total_executions == 0
        assert stats.success_rate == 0.0
    
    def test_success_rate_calculation(self):
        stats = RuleStatistics(rule_id="rule_1")
        stats.total_executions = 10
        stats.successful_executions = 8
        stats.failed_executions = 2
        
        assert stats.success_rate == 0.8
    
    def test_statistics_to_dict(self):
        stats = RuleStatistics(rule_id="rule_1")
        stats.total_executions = 5
        stats.successful_executions = 5
        
        d = stats.to_dict()
        assert d["success_rate"] == 1.0
        assert d["total_executions"] == 5


class TestRulesEngineExtended:
    def test_create_engine(self):
        engine = create_rules_engine_extended()
        assert engine is not None
    
    def test_register_template(self):
        engine = RulesEngineExtended()
        
        def custom_factory(zone_id, **kwargs):
            return {"zone_id": zone_id}
        
        engine.register_template(RuleTemplateType.CUSTOM, custom_factory)
        
        assert RuleTemplateType.CUSTOM in engine._templates
    
    def test_create_rule_from_template_presence_light(self):
        engine = RulesEngineExtended()
        
        rule = engine.create_rule_from_template(
            RuleTemplateType.PRESENCE_LIGHT,
            "zone_living",
            brightness_threshold=0.3,
        )
        
        assert rule is not None
        assert rule.zone_id == "zone_living"
    
    def test_create_rule_from_template_absence_off(self):
        engine = RulesEngineExtended()
        
        rule = engine.create_rule_from_template(
            RuleTemplateType.ABSENCE_OFF,
            "zone_bedroom",
            delay_seconds=600,
        )
        
        assert rule is not None
        assert rule.cooldown_seconds == 600
    
    def test_create_rule_from_template_sunrise_wake(self):
        engine = RulesEngineExtended()
        
        rule = engine.create_rule_from_template(
            RuleTemplateType.SUNRISE_WAKE,
            "zone_living",
            brightness=0.7,
        )
        
        assert rule is not None
    
    def test_create_rule_from_template_sunset_lights(self):
        engine = RulesEngineExtended()
        
        rule = engine.create_rule_from_template(
            RuleTemplateType.SUNSET_LIGHTS,
            "zone_living",
        )
        
        assert rule is not None
    
    def test_create_rule_from_template_away_security(self):
        engine = RulesEngineExtended()
        
        rule = engine.create_rule_from_template(
            RuleTemplateType.AWAY_SECURITY,
            "zone_living",
        )
        
        assert rule is not None
    
    def test_create_rule_from_template_energy_saver(self):
        engine = RulesEngineExtended()
        
        rule = engine.create_rule_from_template(
            RuleTemplateType.ENERGY_SAVER,
            "zone_living",
        )
        
        assert rule is not None
    
    def test_create_rule_from_template_morning_routine(self):
        engine = RulesEngineExtended()
        
        rule = engine.create_rule_from_template(
            RuleTemplateType.MORNING_ROUTINE,
            "zone_living",
        )
        
        assert rule is not None
    
    def test_create_rule_from_template_evening_routine(self):
        engine = RulesEngineExtended()
        
        rule = engine.create_rule_from_template(
            RuleTemplateType.EVENING_ROUTINE,
            "zone_living",
        )
        
        assert rule is not None
    
    def test_create_rule_from_template_night_mode(self):
        engine = RulesEngineExtended()
        
        rule = engine.create_rule_from_template(
            RuleTemplateType.NIGHT_MODE,
            "zone_living",
        )
        
        assert rule is not None
    
    def test_create_rule_from_unknown_template(self):
        engine = RulesEngineExtended()
        
        rule = engine.create_rule_from_template("unknown_type", "zone_1")
        
        assert rule is None
    
    def test_add_dependency(self):
        engine = RulesEngineExtended()
        
        dep = RuleDependency(
            dependency_id="dep_1",
            rule_id="rule_2",
            depends_on_rule_ids=["rule_1"],
        )
        
        result = engine.add_dependency(dep)
        
        assert result is True
    
    def test_add_duplicate_dependency(self):
        engine = RulesEngineExtended()
        
        dep = RuleDependency("dep_1", "rule_2", ["rule_1"])
        engine.add_dependency(dep)
        
        result = engine.add_dependency(dep)
        
        assert result is False
    
    def test_remove_dependency(self):
        engine = RulesEngineExtended()
        
        dep = RuleDependency("dep_1", "rule_2", ["rule_1"])
        engine.add_dependency(dep)
        
        result = engine.remove_dependency("rule_2")
        
        assert result is True
    
    def test_check_dependencies_all(self):
        engine = RulesEngineExtended()
        
        dep = RuleDependency(
            dependency_id="dep_1",
            rule_id="rule_2",
            depends_on_rule_ids=["rule_1", "rule_3"],
            condition="all",
        )
        engine.add_dependency(dep)
        
        # All satisfied
        result = engine.check_dependencies("rule_2", {"rule_1": True, "rule_3": True})
        assert result is True
        
        # One not satisfied
        result = engine.check_dependencies("rule_2", {"rule_1": True, "rule_3": False})
        assert result is False
    
    def test_check_dependencies_any(self):
        engine = RulesEngineExtended()
        
        dep = RuleDependency(
            dependency_id="dep_1",
            rule_id="rule_2",
            depends_on_rule_ids=["rule_1", "rule_3"],
            condition="any",
        )
        engine.add_dependency(dep)
        
        # One satisfied is enough
        result = engine.check_dependencies("rule_2", {"rule_1": True, "rule_3": False})
        assert result is True
    
    def test_check_no_dependencies(self):
        engine = RulesEngineExtended()
        
        result = engine.check_dependencies("rule_no_deps", {})
        
        assert result is True  # No dependencies = always satisfied
    
    def test_add_variable(self):
        engine = RulesEngineExtended()
        
        var = RuleVariable(
            name="test_var",
            value_type="number",
            default_value=42,
        )
        
        result = engine.add_variable(var)
        
        assert result is True
    
    def test_add_duplicate_variable(self):
        engine = RulesEngineExtended()
        
        var = RuleVariable("test_var", "number", default_value=42)
        engine.add_variable(var)
        
        result = engine.add_variable(var)
        
        assert result is False
    
    def test_get_variable(self):
        engine = RulesEngineExtended()
        
        var = RuleVariable("test_var", "number", default_value=100)
        engine.add_variable(var)
        
        value = engine.get_variable("test_var")
        
        assert value == 100
    
    def test_get_variable_with_expression(self):
        engine = RulesEngineExtended()
        
        var = RuleVariable("calc_var", "number", expression="50 + 25")
        engine.add_variable(var)
        
        value = engine.get_variable("calc_var")
        
        assert value == 75
    
    def test_get_variable_with_context(self):
        engine = RulesEngineExtended()
        
        var = RuleVariable("dynamic_var", "number", expression="${x} * 3")
        engine.add_variable(var)
        
        value = engine.get_variable("dynamic_var", context={"x": 10})
        
        assert value == 30
    
    def test_get_nonexistent_variable(self):
        engine = RulesEngineExtended()
        
        value = engine.get_variable("nonexistent")
        
        assert value is None
    
    def test_detect_conflicts_action_conflict(self):
        engine = RulesEngineExtended()
        
        # Create mock rules with conflicting actions
        class MockRule:
            def __init__(self, rule_id, zone_id, actions):
                self.rule_id = rule_id
                self.zone_id = zone_id
                self.actions = actions
        
        class MockAction:
            def __init__(self, action_type):
                from copilot_core.orchestration.rules_engine import ActionType
                self.action_type = ActionType(action_type)
        
        rule1 = MockRule("rule_on", "zone_1", [MockAction("light.turn_on")])
        rule2 = MockRule("rule_off", "zone_1", [MockAction("light.turn_off")])
        
        conflicts = engine.detect_conflicts([rule1, rule2])
        
        assert len(conflicts) >= 1
        assert conflicts[0].conflict_type == ConflictType.ACTION_CONFLICT
    
    def test_resolve_conflict(self):
        engine = RulesEngineExtended()
        
        conflict = ConflictRecord(
            conflict_id="conflict_1",
            conflict_type=ConflictType.ACTION_CONFLICT,
            rule_ids=["rule_1"],
            description="Test",
        )
        engine._conflicts.append(conflict)
        
        result = engine.resolve_conflict("conflict_1", "Resolved manually")
        
        assert result is True
        
        conflicts = engine.get_conflicts(unresolved_only=True)
        assert len(conflicts) == 0
    
    def test_resolve_nonexistent_conflict(self):
        engine = RulesEngineExtended()
        
        result = engine.resolve_conflict("nonexistent", "Test")
        
        assert result is False
    
    def test_record_execution(self):
        engine = RulesEngineExtended()
        
        engine.record_execution("rule_1", success=True, execution_ms=10.5)
        
        stats = engine.get_statistics(rule_id="rule_1")
        
        assert stats["total_executions"] == 1
        assert stats["successful_executions"] == 1
    
    def test_record_execution_failure(self):
        engine = RulesEngineExtended()
        
        engine.record_execution("rule_1", success=False, execution_ms=5.0)
        
        stats = engine.get_statistics(rule_id="rule_1")
        
        assert stats["failed_executions"] == 1
    
    def test_record_trigger(self):
        engine = RulesEngineExtended()
        
        engine.record_trigger("rule_1")
        engine.record_trigger("rule_1")
        
        stats = engine.get_statistics(rule_id="rule_1")
        
        assert stats["trigger_count"] == 2
    
    def test_record_condition_met(self):
        engine = RulesEngineExtended()
        
        engine.record_condition_met("rule_1")
        
        stats = engine.get_statistics(rule_id="rule_1")
        
        assert stats["conditions_met_count"] == 1
    
    def test_add_rule_chain(self):
        engine = RulesEngineExtended()
        
        result = engine.add_rule_chain("rule_1", ["rule_2", "rule_3"])
        
        assert result is True
    
    def test_add_duplicate_rule_chain(self):
        engine = RulesEngineExtended()
        
        engine.add_rule_chain("rule_1", ["rule_2"])
        
        result = engine.add_rule_chain("rule_1", ["rule_3"])
        
        assert result is False
    
    def test_execute_chain(self):
        engine = RulesEngineExtended()
        
        engine.add_rule_chain("rule_1", ["rule_2", "rule_3"])
        
        chain = engine.execute_chain("rule_1")
        
        assert len(chain) == 2
        assert chain[0].rule_id == "rule_2"
        assert chain[0].triggered_by == "rule_1"
    
    def test_get_statistics_overall(self):
        engine = RulesEngineExtended()
        
        engine.record_execution("rule_1", True, 10.0)
        engine.record_execution("rule_2", True, 20.0)
        engine.record_execution("rule_3", False, 5.0)
        
        stats = engine.get_statistics()
        
        assert stats["total_rules_tracked"] == 3
        assert stats["total_executions"] == 3
        assert stats["total_success"] == 2
    
    def test_get_statistics_single_rule(self):
        engine = RulesEngineExtended()
        
        engine.record_execution("rule_1", True, 10.0)
        engine.record_execution("rule_1", True, 15.0)
        
        stats = engine.get_statistics(rule_id="rule_1")
        
        assert stats["total_executions"] == 2
        assert stats["success_rate"] == 1.0
    
    def test_get_statistics_nonexistent_rule(self):
        engine = RulesEngineExtended()
        
        stats = engine.get_statistics(rule_id="nonexistent")
        
        assert stats == {}
    
    def test_get_conflicts_unresolved(self):
        engine = RulesEngineExtended()
        
        conflict = ConflictRecord("c1", ConflictType.ACTION_CONFLICT, ["r1"], "Test")
        conflict.resolved = True
        engine._conflicts.append(conflict)
        
        conflicts = engine.get_conflicts(unresolved_only=True)
        
        assert len(conflicts) == 0
    
    def test_get_conflicts_all(self):
        engine = RulesEngineExtended()
        
        conflict = ConflictRecord("c1", ConflictType.ACTION_CONFLICT, ["r1"], "Test")
        engine._conflicts.append(conflict)
        
        conflicts = engine.get_conflicts(unresolved_only=False)
        
        assert len(conflicts) == 1
    
    def test_get_chain_history(self):
        engine = RulesEngineExtended()
        
        engine.add_rule_chain("rule_1", ["rule_2"])
        engine.execute_chain("rule_1")
        
        history = engine.get_chain_history("rule_1")
        
        assert len(history) >= 1
    
    def test_create_engine_returns_instance(self):
        assert isinstance(create_rules_engine_extended(), RulesEngineExtended)
    
    def test_conflict_record_timestamp_set(self):
        conflict = ConflictRecord(
            conflict_id="c1",
            conflict_type=ConflictType.ACTION_CONFLICT,
            rule_ids=["r1"],
            description="Test",
        )
        assert conflict.detected_at is not None
    
    def test_rule_statistics_success_rate_zero_division(self):
        stats = RuleStatistics(rule_id="rule_1")
        
        assert stats.success_rate == 0.0
    
    def test_variable_expression_invalid(self):
        var = RuleVariable(
            name="bad_var",
            value_type="number",
            expression="invalid code here!",
        )
        
        # Should return default on invalid expression
        value = var.evaluate({})
        
        assert value is None  # Default is None
    
    def test_dependency_to_dict_all_fields(self):
        dep = RuleDependency(
            dependency_id="dep_1",
            rule_id="rule_2",
            depends_on_rule_ids=["rule_1", "rule_3"],
            condition="any",
            timeout_seconds=120,
        )
        d = dep.to_dict()
        assert d["condition"] == "any"
        assert d["timeout_seconds"] == 120
    
    def test_rule_chain_node_timestamp(self):
        node = RuleChainNode("rule_1")
        
        assert node.timestamp is not None
    
    def test_statistics_average_execution_ms(self):
        engine = RulesEngineExtended()
        
        engine.record_execution("rule_1", True, 10.0)
        engine.record_execution("rule_1", True, 20.0)
        
        stats = engine.get_statistics(rule_id="rule_1")
        
        assert stats["average_execution_ms"] == 15.0
    
    def test_template_factory_error_handling(self):
        engine = RulesEngineExtended()
        
        def failing_factory(zone_id, **kwargs):
            raise Exception("Template error")
        
        engine.register_template(RuleTemplateType.CUSTOM, failing_factory)
        
        rule = engine.create_rule_from_template(RuleTemplateType.CUSTOM, "zone_1")
        
        assert rule is None
    
    def test_check_dependencies_missing_result(self):
        engine = RulesEngineExtended()
        
        dep = RuleDependency(
            dependency_id="dep_1",
            rule_id="rule_2",
            depends_on_rule_ids=["rule_1", "rule_missing"],
            condition="all",
        )
        engine.add_dependency(dep)
        
        result = engine.check_dependencies("rule_2", {"rule_1": True})
        
        # Missing rule = False
        assert result is False
    
    def test_conflicts_limited(self):
        engine = RulesEngineExtended()
        
        for i in range(1500):
            conflict = ConflictRecord(
                f"c{i}",
                ConflictType.ACTION_CONFLICT,
                ["r1"],
                f"Conflict {i}",
            )
            engine._conflicts.append(conflict)
        
        # Should be limited to 1000
        assert len(engine._conflicts) <= 1000
    
    def test_get_statistics_conflicts_counts(self):
        engine = RulesEngineExtended()
        
        c1 = ConflictRecord("c1", ConflictType.ACTION_CONFLICT, ["r1"], "Test")
        c2 = ConflictRecord("c2", ConflictType.ACTION_CONFLICT, ["r1"], "Test", resolved=True)
        engine._conflicts.extend([c1, c2])
        
        stats = engine.get_statistics()
        
        assert stats["conflicts_detected"] == 1
        assert stats["conflicts_resolved"] == 1
