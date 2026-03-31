"""Tests for Rules Engine — Slice 30."""
import pytest
from copilot_core.rules.engine import (
    RulesEngine,
    RuleOperator,
    RuleLogical,
    RuleStatus,
    create_rules_engine,
)


class TestRulesEngine:
    """Test rules engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_rules_engine()
        assert engine is not None
    
    def test_create_rule(self):
        """Test rule creation."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Test Rule",
            description="A test rule",
            conditions=[
                {"field": "temperature", "operator": "gt", "value": 25},
            ],
            actions=[
                {"action_type": "log", "parameters": {"message": "Temperature high"}},
            ],
        )
        
        assert rule_id is not None
        assert rule_id.startswith("rule_")
        assert rule_id in engine._rules
    
    def test_create_rule_with_multiple_conditions(self):
        """Test rule with multiple conditions."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Multi-Condition Rule",
            description="Test",
            conditions=[
                {"field": "temperature", "operator": "gt", "value": 25},
                {"field": "humidity", "operator": "lt", "value": 50},
            ],
            actions=[
                {"action_type": "log", "parameters": {"message": "Hot and dry"}},
            ],
            logical_operator="and",
        )
        
        rule = engine.get_rule(rule_id)
        assert len(rule["conditions"]) == 2
    
    def test_create_rule_with_or_logic(self):
        """Test rule with OR logic."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="OR Rule",
            description="Test",
            conditions=[
                {"field": "motion", "operator": "eq", "value": True},
                {"field": "door_open", "operator": "eq", "value": True},
            ],
            actions=[
                {"action_type": "log", "parameters": {"message": "Activity detected"}},
            ],
            logical_operator="or",
        )
        
        rule = engine.get_rule(rule_id)
        assert rule["logical_operator"] == "or"
    
    def test_evaluate_rule_match(self):
        """Test rule evaluation - match."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Temp Rule",
            description="Test",
            conditions=[
                {"field": "temperature", "operator": "gt", "value": 25},
            ],
            actions=[
                {"action_type": "log", "parameters": {"message": "Hot"}},
            ],
        )
        
        result = engine.evaluate_rule(rule_id, {"temperature": 30})
        
        assert result.matched is True
        assert result.actions_executed == 1
    
    def test_evaluate_rule_no_match(self):
        """Test rule evaluation - no match."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Temp Rule",
            description="Test",
            conditions=[
                {"field": "temperature", "operator": "gt", "value": 25},
            ],
            actions=[
                {"action_type": "log", "parameters": {"message": "Hot"}},
            ],
        )
        
        result = engine.evaluate_rule(rule_id, {"temperature": 20})
        
        assert result.matched is False
        assert result.actions_executed == 0
    
    def test_evaluate_disabled_rule(self):
        """Test evaluating disabled rule."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Test Rule",
            description="Test",
            conditions=[
                {"field": "temperature", "operator": "gt", "value": 25},
            ],
            actions=[
                {"action_type": "log", "parameters": {"message": "Hot"}},
            ],
        )
        
        engine.disable_rule(rule_id)
        
        result = engine.evaluate_rule(rule_id, {"temperature": 30})
        
        assert result.matched is False
        assert result.error_message == "Rule disabled"
    
    def test_evaluate_unknown_rule(self):
        """Test evaluating unknown rule."""
        engine = RulesEngine()
        
        result = engine.evaluate_rule("unknown_rule", {"temperature": 30})
        
        assert result.matched is False
        assert result.error_message == "Rule not found"
    
    def test_evaluate_all_rules(self):
        """Test evaluating all rules."""
        engine = RulesEngine()
        
        engine.create_rule(
            name="Rule 1",
            description="Test",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "log", "parameters": {"message": "1"}}],
            priority=10,
        )
        
        engine.create_rule(
            name="Rule 2",
            description="Test",
            conditions=[{"field": "temp", "operator": "lt", "value": 30}],
            actions=[{"action_type": "log", "parameters": {"message": "2"}}],
            priority=5,
        )
        
        results = engine.evaluate_all_rules({"temp": 28})
        
        assert len(results) == 2
        # Higher priority should be first
        assert results[0]["rule_id"] != results[1]["rule_id"]
    
    def test_rule_with_and_logic(self):
        """Test rule with AND logic."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="AND Rule",
            description="Test",
            conditions=[
                {"field": "temp", "operator": "gt", "value": 25},
                {"field": "humidity", "operator": "gt", "value": 50},
            ],
            actions=[{"action_type": "log", "parameters": {"message": "Both"}}],
            logical_operator="and",
        )
        
        # Both conditions true
        result = engine.evaluate_rule(rule_id, {"temp": 30, "humidity": 60})
        assert result.matched is True
        
        # Only one condition true
        result = engine.evaluate_rule(rule_id, {"temp": 30, "humidity": 40})
        assert result.matched is False
    
    def test_rule_with_or_logic(self):
        """Test rule with OR logic."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="OR Rule",
            description="Test",
            conditions=[
                {"field": "motion", "operator": "eq", "value": True},
                {"field": "door", "operator": "eq", "value": True},
            ],
            actions=[{"action_type": "log", "parameters": {"message": "Activity"}}],
            logical_operator="or",
        )
        
        # One condition true
        result = engine.evaluate_rule(rule_id, {"motion": True, "door": False})
        assert result.matched is True
        
        # Both false
        result = engine.evaluate_rule(rule_id, {"motion": False, "door": False})
        assert result.matched is False
    
    def test_rule_with_negate(self):
        """Test rule with negated condition."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Negate Rule",
            description="Test",
            conditions=[
                {"field": "away", "operator": "eq", "value": True, "negate": True},
            ],
            actions=[{"action_type": "log", "parameters": {"message": "Home"}}],
        )
        
        # away=True, negated -> condition false
        result = engine.evaluate_rule(rule_id, {"away": True})
        assert result.matched is False
        
        # away=False, negated -> condition true
        result = engine.evaluate_rule(rule_id, {"away": False})
        assert result.matched is True
    
    def test_enable_disable_rule(self):
        """Test enabling/disabling rule."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Test Rule",
            description="Test",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "log", "parameters": {"message": "Hot"}}],
        )
        
        # Disable
        result = engine.disable_rule(rule_id)
        assert result is True
        assert engine._rules[rule_id].status == RuleStatus.DISABLED
        
        # Enable
        result = engine.enable_rule(rule_id)
        assert result is True
        assert engine._rules[rule_id].status == RuleStatus.ENABLED
    
    def test_enable_unknown_rule(self):
        """Test enabling unknown rule."""
        engine = RulesEngine()
        
        result = engine.enable_rule("unknown_rule")
        
        assert result is False
    
    def test_get_rule(self):
        """Test getting rule details."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Test Rule",
            description="Test description",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "log", "parameters": {"message": "Hot"}}],
            priority=5,
            tags=["temperature", "automation"],
        )
        
        rule = engine.get_rule(rule_id)
        
        assert rule is not None
        assert rule["name"] == "Test Rule"
        assert rule["description"] == "Test description"
        assert rule["priority"] == 5
        assert "temperature" in rule["tags"]
    
    def test_get_unknown_rule(self):
        """Test getting unknown rule."""
        engine = RulesEngine()
        
        rule = engine.get_rule("unknown_rule")
        
        assert rule is None
    
    def test_get_all_rules(self):
        """Test getting all rules."""
        engine = RulesEngine()
        
        for i in range(3):
            engine.create_rule(
                name=f"Rule {i}",
                description="Test",
                conditions=[{"field": "temp", "operator": "gt", "value": 25}],
                actions=[{"action_type": "log", "parameters": {"message": "Hot"}}],
            )
        
        rules = engine.get_all_rules()
        
        assert len(rules) == 3
    
    def test_get_all_rules_filtered_by_status(self):
        """Test getting rules filtered by status."""
        engine = RulesEngine()
        
        rule1 = engine.create_rule("Rule 1", "Test", [{"field": "temp", "operator": "gt", "value": 25}], [{"action_type": "log", "parameters": {}}])
        rule2 = engine.create_rule("Rule 2", "Test", [{"field": "temp", "operator": "gt", "value": 25}], [{"action_type": "log", "parameters": {}}])
        
        engine.disable_rule(rule2)
        
        enabled = engine.get_all_rules(status=RuleStatus.ENABLED)
        disabled = engine.get_all_rules(status=RuleStatus.DISABLED)
        
        assert len(enabled) == 1
        assert len(disabled) == 1
    
    def test_get_all_rules_filtered_by_tags(self):
        """Test getting rules filtered by tags."""
        engine = RulesEngine()
        
        engine.create_rule("Rule 1", "Test", [{"field": "temp", "operator": "gt", "value": 25}], [{"action_type": "log", "parameters": {}}], tags=["temp"])
        engine.create_rule("Rule 2", "Test", [{"field": "motion", "operator": "eq", "value": True}], [{"action_type": "log", "parameters": {}}], tags=["security"])
        
        temp_rules = engine.get_all_rules(tags=["temp"])
        
        assert len(temp_rules) == 1
        assert temp_rules[0]["name"] == "Rule 1"
    
    def test_delete_rule(self):
        """Test deleting rule."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Test Rule",
            description="Test",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "log", "parameters": {"message": "Hot"}}],
        )
        
        result = engine.delete_rule(rule_id)
        
        assert result is True
        assert rule_id not in engine._rules
    
    def test_delete_unknown_rule(self):
        """Test deleting unknown rule."""
        engine = RulesEngine()
        
        result = engine.delete_rule("unknown_rule")
        
        assert result is False
    
    def test_register_custom_action(self):
        """Test registering custom action."""
        engine = RulesEngine()
        
        def custom_action(context, **kwargs):
            return {"custom": True}
        
        engine.register_action("custom_action", custom_action)
        
        assert "custom_action" in engine._action_handlers
    
    def test_builtin_log_action(self):
        """Test built-in log action."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Log Rule",
            description="Test",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "log", "parameters": {"message": "Test log"}}],
        )
        
        result = engine.evaluate_rule(rule_id, {"temp": 30})
        
        assert result.actions_executed == 1
    
    def test_builtin_set_variable_action(self):
        """Test built-in set_variable action."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Set Var Rule",
            description="Test",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "set_variable", "parameters": {"name": "alert", "value": True}}],
        )
        
        context = {"temp": 30}
        result = engine.evaluate_rule(rule_id, context)
        
        assert result.actions_executed == 1
        assert context["alert"] is True
    
    def test_builtin_notify_action(self):
        """Test built-in notify action."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Notify Rule",
            description="Test",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "notify", "parameters": {"title": "Alert", "message": "Hot!"}}],
        )
        
        result = engine.evaluate_rule(rule_id, {"temp": 30})
        
        assert result.actions_executed == 1
    
    def test_rule_priority_ordering(self):
        """Test that rules are evaluated in priority order."""
        engine = RulesEngine()
        
        engine.create_rule("Low Priority", "Test", [{"field": "x", "operator": "eq", "value": 1}], [{"action_type": "log", "parameters": {}}], priority=1)
        engine.create_rule("High Priority", "Test", [{"field": "x", "operator": "eq", "value": 1}], [{"action_type": "log", "parameters": {}}], priority=10)
        engine.create_rule("Medium Priority", "Test", [{"field": "x", "operator": "eq", "value": 1}], [{"action_type": "log", "parameters": {}}], priority=5)
        
        results = engine.evaluate_all_rules({"x": 1})
        
        # Should be sorted by priority (high first)
        assert results[0]["rule_id"] != results[-1]["rule_id"]
    
    def test_get_evaluation_log(self):
        """Test getting evaluation log."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Test Rule",
            description="Test",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "log", "parameters": {"message": "Hot"}}],
        )
        
        # Evaluate multiple times
        engine.evaluate_rule(rule_id, {"temp": 30})
        engine.evaluate_rule(rule_id, {"temp": 20})
        engine.evaluate_rule(rule_id, {"temp": 35})
        
        logs = engine.get_evaluation_log(limit=10)
        
        assert len(logs) == 3
    
    def test_get_evaluation_log_filtered_by_rule(self):
        """Test getting log filtered by rule."""
        engine = RulesEngine()
        
        rule1 = engine.create_rule("Rule 1", "Test", [{"field": "a", "operator": "eq", "value": 1}], [{"action_type": "log", "parameters": {}}])
        rule2 = engine.create_rule("Rule 2", "Test", [{"field": "b", "operator": "eq", "value": 2}], [{"action_type": "log", "parameters": {}}])
        
        engine.evaluate_rule(rule1, {"a": 1})
        engine.evaluate_rule(rule2, {"b": 2})
        engine.evaluate_rule(rule1, {"a": 1})
        
        logs1 = engine.get_evaluation_log(rule_id=rule1)
        
        assert len(logs1) == 2
        assert all(l["rule_id"] == rule1 for l in logs1)
    
    def test_get_evaluation_log_matched_only(self):
        """Test getting log with matched only filter."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Test Rule",
            description="Test",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "log", "parameters": {"message": "Hot"}}],
        )
        
        # Some match, some don't
        engine.evaluate_rule(rule_id, {"temp": 30})  # Match
        engine.evaluate_rule(rule_id, {"temp": 20})  # No match
        engine.evaluate_rule(rule_id, {"temp": 35})  # Match
        
        matched_logs = engine.get_evaluation_log(matched_only=True)
        
        assert len(matched_logs) == 2
        assert all(l["matched"] is True for l in matched_logs)
    
    def test_get_rule_statistics(self):
        """Test getting rule statistics."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Test Rule",
            description="Test",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "log", "parameters": {"message": "Hot"}}],
        )
        
        # Evaluate multiple times
        for i in range(5):
            engine.evaluate_rule(rule_id, {"temp": 30})
        
        for i in range(3):
            engine.evaluate_rule(rule_id, {"temp": 20})
        
        stats = engine.get_rule_statistics(rule_id)
        
        assert stats["evaluations_total"] == 8
        assert stats["evaluations_matched"] == 5
        assert stats["match_rate"] == 5/8
    
    def test_get_rules_summary(self):
        """Test rules summary."""
        engine = RulesEngine()
        
        engine.create_rule("Rule 1", "Test", [{"field": "a", "operator": "eq", "value": 1}], [{"action_type": "log", "parameters": {}}])
        engine.create_rule("Rule 2", "Test", [{"field": "b", "operator": "eq", "value": 2}], [{"action_type": "log", "parameters": {}}])
        
        engine.evaluate_rule(engine._rules["rule_1"].rule_id if "rule_1" in engine._rules else list(engine._rules.keys())[0], {"a": 1})
        
        summary = engine.get_rules_summary()
        
        assert summary["total_rules"] == 2
        assert summary["enabled_rules"] == 2
    
    def test_detect_conflicts_duplicate_conditions(self):
        """Test conflict detection for duplicate conditions."""
        engine = RulesEngine()
        
        engine.create_rule(
            name="Rule A",
            description="Test",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "log", "parameters": {"message": "A"}}],
        )
        
        engine.create_rule(
            name="Rule B",
            description="Test",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "log", "parameters": {"message": "B"}}],
        )
        
        conflicts = engine.detect_conflicts()
        
        assert len(conflicts) >= 1
        assert conflicts[0]["type"] == "duplicate_conditions"
    
    def test_rule_trigger_count(self):
        """Test rule trigger count."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Test Rule",
            description="Test",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "log", "parameters": {"message": "Hot"}}],
        )
        
        # Trigger multiple times
        for i in range(5):
            engine.evaluate_rule(rule_id, {"temp": 30})
        
        rule = engine.get_rule(rule_id)
        
        assert rule["trigger_count"] == 5
    
    def test_rule_last_triggered(self):
        """Test rule last_triggered timestamp."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Test Rule",
            description="Test",
            conditions=[{"field": "temp", "operator": "gt", "value": 25}],
            actions=[{"action_type": "log", "parameters": {"message": "Hot"}}],
        )
        
        engine.evaluate_rule(rule_id, {"temp": 30})
        
        rule = engine.get_rule(rule_id)
        
        assert rule["last_triggered"] is not None
    
    def test_condition_operator_eq(self):
        """Test equals operator."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="EQ Rule",
            description="Test",
            conditions=[{"field": "status", "operator": "eq", "value": "active"}],
            actions=[{"action_type": "log", "parameters": {"message": "Active"}}],
        )
        
        result = engine.evaluate_rule(rule_id, {"status": "active"})
        assert result.matched is True
        
        result = engine.evaluate_rule(rule_id, {"status": "inactive"})
        assert result.matched is False
    
    def test_condition_operator_contains(self):
        """Test contains operator."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Contains Rule",
            description="Test",
            conditions=[{"field": "message", "operator": "contains", "value": "error"}],
            actions=[{"action_type": "log", "parameters": {"message": "Error found"}}],
        )
        
        result = engine.evaluate_rule(rule_id, {"message": "An error occurred"})
        assert result.matched is True
        
        result = engine.evaluate_rule(rule_id, {"message": "All good"})
        assert result.matched is False
    
    def test_condition_operator_in(self):
        """Test in operator."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="In Rule",
            description="Test",
            conditions=[{"field": "day", "operator": "in", "value": ["monday", "tuesday", "wednesday"]}],
            actions=[{"action_type": "log", "parameters": {"message": "Weekday"}}],
        )
        
        result = engine.evaluate_rule(rule_id, {"day": "monday"})
        assert result.matched is True
        
        result = engine.evaluate_rule(rule_id, {"day": "saturday"})
        assert result.matched is False
    
    def test_condition_operator_exists(self):
        """Test exists operator."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Exists Rule",
            description="Test",
            conditions=[{"field": "user", "operator": "exists", "value": None}],
            actions=[{"action_type": "log", "parameters": {"message": "User present"}}],
        )
        
        result = engine.evaluate_rule(rule_id, {"user": "john"})
        assert result.matched is True
        
        result = engine.evaluate_rule(rule_id, {})
        assert result.matched is False
    
    def test_dot_notation_field_access(self):
        """Test dot notation for nested fields."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Nested Rule",
            description="Test",
            conditions=[{"field": "sensor.temperature", "operator": "gt", "value": 25}],
            actions=[{"action_type": "log", "parameters": {"message": "Hot"}}],
        )
        
        result = engine.evaluate_rule(rule_id, {"sensor": {"temperature": 30}})
        assert result.matched is True
        
        result = engine.evaluate_rule(rule_id, {"sensor": {"temperature": 20}})
        assert result.matched is False
    
    def test_rule_evaluation_result_to_dict(self):
        """Test evaluation result serialization."""
        from copilot_core.rules.engine import RuleEvaluationResult
        
        result = RuleEvaluationResult(
            rule_id="rule_test",
            matched=True,
            conditions_evaluated=3,
            conditions_matched=3,
            actions_executed=2,
            actions_failed=0,
            evaluation_time_ms=5,
        )
        
        d = result.to_dict()
        
        assert d["rule_id"] == "rule_test"
        assert d["matched"] is True
        assert d["conditions_evaluated"] == 3
        assert d["evaluation_time_ms"] == 5
    
    def test_rule_to_dict(self):
        """Test rule serialization."""
        from copilot_core.rules.engine import Rule, RuleCondition, RuleAction
        
        condition = RuleCondition(
            field="temperature",
            operator=RuleOperator.GT,
            value=25,
        )
        
        action = RuleAction(
            action_id="action_test",
            action_type="log",
            parameters={"message": "Hot"},
        )
        
        rule = Rule(
            rule_id="rule_test",
            name="Test Rule",
            description="Test",
            conditions=[condition],
            actions=[action],
            priority=5,
        )
        
        d = rule.to_dict()
        
        assert d["rule_id"] == "rule_test"
        assert d["name"] == "Test Rule"
        assert len(d["conditions"]) == 1
        assert len(d["actions"]) == 1
    
    def test_rule_condition_to_dict(self):
        """Test condition serialization."""
        from copilot_core.rules.engine import RuleCondition
        
        condition = RuleCondition(
            field="temperature",
            operator=RuleOperator.GT,
            value=25,
            negate=False,
        )
        
        d = condition.to_dict()
        
        assert d["field"] == "temperature"
        assert d["operator"] == "gt"
        assert d["value"] == 25
    
    def test_rule_action_to_dict(self):
        """Test action serialization."""
        from copilot_core.rules.engine import RuleAction
        
        action = RuleAction(
            action_id="action_test",
            action_type="notify",
            parameters={"title": "Alert", "message": "Test"},
        )
        
        d = action.to_dict()
        
        assert d["action_id"] == "action_test"
        assert d["action_type"] == "notify"
        assert d["parameters"]["title"] == "Alert"
    
    def test_rule_operator_enum_values(self):
        """Test rule operator enum values."""
        assert RuleOperator.EQ.value == "eq"
        assert RuleOperator.NE.value == "ne"
        assert RuleOperator.GT.value == "gt"
        assert RuleOperator.LT.value == "lt"
        assert RuleOperator.CONTAINS.value == "contains"
        assert RuleOperator.IN.value == "in"
    
    def test_rule_logical_enum_values(self):
        """Test rule logical operator enum values."""
        assert RuleLogical.AND.value == "and"
        assert RuleLogical.OR.value == "or"
        assert RuleLogical.NOT.value == "not"
    
    def test_rule_status_enum_values(self):
        """Test rule status enum values."""
        assert RuleStatus.ENABLED.value == "enabled"
        assert RuleStatus.DISABLED.value == "disabled"
        assert RuleStatus.ERROR.value == "error"
    
    def test_evaluation_log_trimmed_to_max(self):
        """Test that evaluation log is trimmed to max size."""
        engine = RulesEngine()
        engine._max_log_size = 10
        
        rule_id = engine.create_rule(
            name="Test",
            description="Test",
            conditions=[{"field": "x", "operator": "eq", "value": 1}],
            actions=[{"action_type": "log", "parameters": {}}],
        )
        
        # Evaluate more than max
        for i in range(20):
            engine.evaluate_rule(rule_id, {"x": 1})
        
        assert len(engine._evaluation_log) <= 10
    
    def test_rules_sorted_by_priority(self):
        """Test that rules are sorted by priority."""
        engine = RulesEngine()
        
        engine.create_rule("Low", "Test", [{"field": "x", "operator": "eq", "value": 1}], [{"action_type": "log", "parameters": {}}], priority=1)
        engine.create_rule("High", "Test", [{"field": "x", "operator": "eq", "value": 1}], [{"action_type": "log", "parameters": {}}], priority=100)
        engine.create_rule("Medium", "Test", [{"field": "x", "operator": "eq", "value": 1}], [{"action_type": "log", "parameters": {}}], priority=50)
        
        rules = engine.get_all_rules()
        
        # Should be sorted by priority (high first)
        assert rules[0]["priority"] >= rules[1]["priority"]
        assert rules[1]["priority"] >= rules[2]["priority"]
    
    def test_unknown_action_type_fails(self):
        """Test that unknown action type fails."""
        engine = RulesEngine()
        
        rule_id = engine.create_rule(
            name="Unknown Action",
            description="Test",
            conditions=[{"field": "x", "operator": "eq", "value": 1}],
            actions=[{"action_type": "unknown_action", "parameters": {}}],
        )
        
        result = engine.evaluate_rule(rule_id, {"x": 1})
        
        assert result.matched is True  # Rule matches
        assert result.actions_failed == 1  # But action fails
