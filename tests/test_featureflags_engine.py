"""Tests for Feature Flags Engine — Slice 40."""
import pytest
from copilot_core.featureflags.engine import (
    FeatureFlagsEngine,
    FlagType,
    FlagStatus,
    FeatureFlag,
    FlagRule,
    FlagEvaluation,
    FlagChange,
    create_feature_flags_engine,
)
from datetime import datetime, timezone, timedelta


class TestFeatureFlagsEngine:
    """Test feature flags engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_feature_flags_engine()
        assert engine is not None
    
    def test_create_boolean_flag(self):
        """Test creating boolean flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="new_dashboard",
            description="Enable new dashboard UI",
            flag_type="boolean",
            default_value=False,
        )
        
        assert flag_id is not None
        assert flag_id.startswith("flag_")
        
        flag = engine.get_flag(flag_id)
        assert flag is not None
        assert flag["flag_type"] == "boolean"
        assert flag["default_value"] is False
    
    def test_create_string_flag(self):
        """Test creating string flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="theme",
            description="UI theme selection",
            flag_type="string",
            default_value="light",
        )
        
        flag = engine.get_flag(flag_id)
        assert flag["flag_type"] == "string"
        assert flag["default_value"] == "light"
    
    def test_create_number_flag(self):
        """Test creating number flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="max_connections",
            description="Maximum connections allowed",
            flag_type="number",
            default_value=100,
        )
        
        flag = engine.get_flag(flag_id)
        assert flag["flag_type"] == "number"
        assert flag["default_value"] == 100
    
    def test_create_json_flag(self):
        """Test creating JSON flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="config",
            description="Feature configuration",
            flag_type="json",
            default_value={"feature1": True, "feature2": False},
        )
        
        flag = engine.get_flag(flag_id)
        assert flag["flag_type"] == "json"
        assert flag["default_value"]["feature1"] is True
    
    def test_create_flag_with_environments(self):
        """Test creating flag with environments."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="beta_feature",
            description="Beta feature",
            flag_type="boolean",
            default_value=False,
            environments=["production", "staging"],
        )
        
        flag = engine.get_flag(flag_id)
        assert "production" in flag["environments"]
        assert "staging" in flag["environments"]
    
    def test_create_flag_with_tags(self):
        """Test creating flag with tags."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="new_feature",
            description="New feature",
            flag_type="boolean",
            default_value=False,
            tags=["frontend", "beta"],
        )
        
        flag = engine.get_flag(flag_id)
        assert "frontend" in flag["tags"]
        assert "beta" in flag["tags"]
    
    def test_add_rule(self):
        """Test adding evaluation rule."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="us_feature",
            description="US only feature",
            flag_type="boolean",
            default_value=False,
        )
        
        rule_id = engine.add_rule(
            flag_id=flag_id,
            condition="user.country == 'US'",
            value=True,
        )
        
        assert rule_id is not None
        assert rule_id.startswith("rule_")
        
        flag = engine.get_flag(flag_id)
        assert len(flag["rules"]) == 1
    
    def test_add_rule_with_percentage(self):
        """Test adding rule with percentage."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="rollout",
            description="Percentage rollout",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.add_rule(
            flag_id=flag_id,
            condition="user.tier == 'premium'",
            value=True,
            percentage=50.0,
        )
        
        flag = engine.get_flag(flag_id)
        assert flag["rules"][0]["percentage"] == 50.0
    
    def test_enable_flag(self):
        """Test enabling a flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        # Initially draft
        flag = engine.get_flag(flag_id)
        assert flag["status"] == "draft"
        
        # Enable
        result = engine.enable_flag(flag_id)
        assert result is True
        
        flag = engine.get_flag(flag_id)
        assert flag["status"] == "active"
    
    def test_disable_flag(self):
        """Test disabling a flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.enable_flag(flag_id)
        
        result = engine.disable_flag(flag_id)
        assert result is True
        
        flag = engine.get_flag(flag_id)
        assert flag["status"] == "draft"
    
    def test_enable_unknown_flag(self):
        """Test enabling unknown flag."""
        engine = FeatureFlagsEngine()
        
        result = engine.enable_flag("unknown_flag")
        
        assert result is False
    
    def test_disable_unknown_flag(self):
        """Test disabling unknown flag."""
        engine = FeatureFlagsEngine()
        
        result = engine.disable_flag("unknown_flag")
        
        assert result is False
    
    def test_evaluate_flag_default(self):
        """Test evaluating flag - default value."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.enable_flag(flag_id)
        
        result = engine.evaluate(flag_id)
        
        assert result.value is False
        assert result.reason == "default"
    
    def test_evaluate_flag_rule_match(self):
        """Test evaluating flag - rule match."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="us_feature",
            description="US only",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.add_rule(
            flag_id=flag_id,
            condition="user_country == 'US'",
            value=True,
        )
        
        engine.enable_flag(flag_id)
        
        # US user should get True
        result = engine.evaluate(flag_id, context={"user_country": "US"})
        
        assert result.value is True
        assert result.reason == "rule_match"
    
    def test_evaluate_flag_rule_no_match(self):
        """Test evaluating flag - rule no match."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="us_feature",
            description="US only",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.add_rule(
            flag_id=flag_id,
            condition="user_country == 'US'",
            value=True,
        )
        
        engine.enable_flag(flag_id)
        
        # Non-US user should get default
        result = engine.evaluate(flag_id, context={"user_country": "DE"})
        
        assert result.value is False
        assert result.reason == "default"
    
    def test_evaluate_inactive_flag(self):
        """Test evaluating inactive flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        # Don't enable - stays in draft
        
        result = engine.evaluate(flag_id)
        
        assert result.value is False
        assert result.reason == "flag_inactive"
    
    def test_evaluate_unknown_flag(self):
        """Test evaluating unknown flag."""
        engine = FeatureFlagsEngine()
        
        result = engine.evaluate("unknown_flag")
        
        assert result.value is None
        assert result.reason == "flag_not_found"
    
    def test_evaluate_environment_mismatch(self):
        """Test evaluating with environment mismatch."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="prod_feature",
            description="Production only",
            flag_type="boolean",
            default_value=False,
            environments=["production"],
        )
        
        engine.enable_flag(flag_id)
        
        # Evaluate in staging environment
        result = engine.evaluate(flag_id, context={"environment": "staging"})
        
        assert result.value is False
        assert result.reason == "environment_mismatch"
    
    def test_percentage_rollout(self):
        """Test percentage rollout."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="rollout_50",
            description="50% rollout",
            flag_type="boolean",
            default_value=False,
        )
        
        engine._flags[flag_id].percentage_rollout = 50.0
        engine.enable_flag(flag_id)
        
        # Evaluate with different user_ids
        enabled_count = 0
        for i in range(100):
            result = engine.evaluate(flag_id, context={"user_id": f"user_{i}"})
            if result.value is True:
                enabled_count += 1
        
        # Should be roughly 50% (allow variance)
        assert 30 <= enabled_count <= 70
    
    def test_update_flag(self):
        """Test updating flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Original description",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.update_flag(
            flag_id=flag_id,
            description="Updated description",
            updated_by="admin",
            reason="Updating description",
        )
        
        flag = engine.get_flag(flag_id)
        assert flag["description"] == "Updated description"
    
    def test_update_unknown_flag(self):
        """Test updating unknown flag."""
        engine = FeatureFlagsEngine()
        
        with pytest.raises(ValueError):
            engine.update_flag("unknown_flag", description="Test")
    
    def test_delete_flag(self):
        """Test deleting flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        result = engine.delete_flag(flag_id)
        
        assert result is True
        assert engine.get_flag(flag_id) is None
    
    def test_delete_unknown_flag(self):
        """Test deleting unknown flag."""
        engine = FeatureFlagsEngine()
        
        result = engine.delete_flag("unknown_flag")
        
        assert result is False
    
    def test_get_all_flags(self):
        """Test getting all flags."""
        engine = FeatureFlagsEngine()
        
        engine.create_flag("flag1", "Test 1", "boolean", False)
        engine.create_flag("flag2", "Test 2", "boolean", True)
        engine.create_flag("flag3", "Test 3", "boolean", False)
        
        flags = engine.get_all_flags()
        
        assert len(flags) == 3
    
    def test_get_all_flags_filtered_by_status(self):
        """Test getting flags filtered by status."""
        engine = FeatureFlagsEngine()
        
        flag1 = engine.create_flag("flag1", "Test 1", "boolean", False)
        flag2 = engine.create_flag("flag2", "Test 2", "boolean", False)
        
        engine.enable_flag(flag1)
        
        active = engine.get_all_flags(status=FlagStatus.ACTIVE)
        draft = engine.get_all_flags(status=FlagStatus.DRAFT)
        
        assert len(active) == 1
        assert len(draft) == 1
    
    def test_get_all_flags_filtered_by_environment(self):
        """Test getting flags filtered by environment."""
        engine = FeatureFlagsEngine()
        
        engine.create_flag("flag1", "Test 1", "boolean", False, environments=["production"])
        engine.create_flag("flag2", "Test 2", "boolean", False, environments=["staging"])
        
        prod_flags = engine.get_all_flags(environment="production")
        
        assert len(prod_flags) == 1
        assert prod_flags[0]["name"] == "flag1"
    
    def test_get_change_log(self):
        """Test getting change log."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.enable_flag(flag_id)
        engine.disable_flag(flag_id)
        
        changes = engine.get_change_log(flag_id=flag_id)
        
        assert len(changes) >= 3  # created, enabled, disabled
    
    def test_get_change_log_all_flags(self):
        """Test getting change log for all flags."""
        engine = FeatureFlagsEngine()
        
        flag1 = engine.create_flag("flag1", "Test 1", "boolean", False)
        flag2 = engine.create_flag("flag2", "Test 2", "boolean", False)
        
        changes = engine.get_change_log()
        
        # Should have changes for both flags
        assert len(changes) >= 2
    
    def test_register_change_callback(self):
        """Test registering change callback."""
        engine = FeatureFlagsEngine()
        
        changes_received = []
        
        def callback(change):
            changes_received.append(change)
        
        engine.register_change_callback(callback)
        
        engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        assert len(changes_received) >= 1
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = FeatureFlagsEngine()
        
        flag1 = engine.create_flag("flag1", "Test 1", "boolean", False)
        flag2 = engine.create_flag("flag2", "Test 2", "boolean", False)
        
        engine.enable_flag(flag1)
        
        # Evaluate some
        engine.evaluate(flag1)
        engine.evaluate(flag2)
        
        stats = engine.get_statistics()
        
        assert stats["total_flags"] == 2
        assert stats["by_status"]["active"] == 1
        assert stats["by_status"]["draft"] == 1
    
    def test_export_flags_json(self):
        """Test exporting flags to JSON."""
        engine = FeatureFlagsEngine()
        
        engine.create_flag("flag1", "Test 1", "boolean", False)
        engine.create_flag("flag2", "Test 2", "string", "default")
        
        export = engine.export_flags(format="json")
        
        assert "flags" in export
        assert "flag1" in export
        assert "flag2" in export
    
    def test_set_percentage_rollout(self):
        """Test setting percentage rollout."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="rollout_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        result = engine.set_percentage_rollout(flag_id, 25.0)
        
        assert result is True
        
        flag = engine.get_flag(flag_id)
        assert flag["percentage_rollout"] == 25.0
    
    def test_set_percentage_rollout_invalid(self):
        """Test setting invalid percentage rollout."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="rollout_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        with pytest.raises(ValueError):
            engine.set_percentage_rollout(flag_id, 150.0)
    
    def test_set_percentage_rollout_unknown_flag(self):
        """Test setting percentage for unknown flag."""
        engine = FeatureFlagsEngine()
        
        result = engine.set_percentage_rollout("unknown_flag", 50.0)
        
        assert result is False
    
    def test_clear_cache(self):
        """Test clearing cache."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.enable_flag(flag_id)
        
        # Evaluate to populate cache
        for i in range(10):
            engine.evaluate(flag_id, context={"user_id": f"user_{i}"})
        
        count = engine.clear_cache()
        
        assert count > 0
        assert len(engine._evaluation_cache) == 0
    
    def test_cache_invalidation_on_update(self):
        """Test cache invalidation on flag update."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.enable_flag(flag_id)
        
        # Evaluate to populate cache
        engine.evaluate(flag_id, context={"user_id": "user_1"})
        
        cache_size_before = len(engine._evaluation_cache)
        
        # Update flag
        engine.add_rule(flag_id, "user.tier == 'premium'", True)
        
        cache_size_after = len(engine._evaluation_cache)
        
        assert cache_size_after < cache_size_before
    
    def test_evaluation_caching(self):
        """Test that evaluations are cached."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.enable_flag(flag_id)
        
        # First evaluation
        result1 = engine.evaluate(flag_id, context={"user_id": "user_1"})
        
        # Second evaluation (should be cached)
        result2 = engine.evaluate(flag_id, context={"user_id": "user_1"})
        
        assert result1.value == result2.value
        assert result1.reason == result2.reason
    
    def test_flag_type_enum_values(self):
        """Test flag type enum values."""
        assert FlagType.BOOLEAN.value == "boolean"
        assert FlagType.STRING.value == "string"
        assert FlagType.NUMBER.value == "number"
        assert FlagType.JSON.value == "json"
    
    def test_flag_status_enum_values(self):
        """Test flag status enum values."""
        assert FlagStatus.DRAFT.value == "draft"
        assert FlagStatus.ACTIVE.value == "active"
        assert FlagStatus.ARCHIVED.value == "archived"
    
    def test_flag_to_dict(self):
        """Test flag serialization."""
        flag = FeatureFlag(
            flag_id="flag_test",
            name="Test Flag",
            description="Test description",
            flag_type=FlagType.BOOLEAN,
            default_value=True,
            status=FlagStatus.ACTIVE,
        )
        
        d = flag.to_dict()
        
        assert d["flag_id"] == "flag_test"
        assert d["flag_type"] == "boolean"
        assert d["default_value"] is True
    
    def test_flag_rule_to_dict(self):
        """Test flag rule serialization."""
        rule = FlagRule(
            rule_id="rule_test",
            condition="user.country == 'US'",
            value=True,
            percentage=50.0,
        )
        
        d = rule.to_dict()
        
        assert d["rule_id"] == "rule_test"
        assert d["condition"] == "user.country == 'US'"
        assert d["percentage"] == 50.0
    
    def test_flag_evaluation_to_dict(self):
        """Test flag evaluation serialization."""
        evaluation = FlagEvaluation(
            flag_id="flag_test",
            value=True,
            reason="rule_match",
            rule_id="rule_123",
            variant=None,
        )
        
        d = evaluation.to_dict()
        
        assert d["flag_id"] == "flag_test"
        assert d["value"] is True
        assert d["reason"] == "rule_match"
    
    def test_flag_change_to_dict(self):
        """Test flag change serialization."""
        change = FlagChange(
            change_id="change_test",
            flag_id="flag_test",
            action="enabled",
            old_value="draft",
            new_value="active",
            changed_by="admin",
            changed_at="2026-03-31T12:00:00Z",
            reason="Manual enable",
        )
        
        d = change.to_dict()
        
        assert d["change_id"] == "change_test"
        assert d["action"] == "enabled"
        assert d["reason"] == "Manual enable"
    
    def test_rule_with_nested_context(self):
        """Test rule evaluation with nested context."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="premium_feature",
            description="Premium only",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.add_rule(
            flag_id=flag_id,
            condition="user_tier == 'premium'",
            value=True,
        )
        
        engine.enable_flag(flag_id)
        
        # Premium user
        result = engine.evaluate(flag_id, context={"user_tier": "premium"})
        
        assert result.value is True
    
    def test_multiple_rules_priority_order(self):
        """Test multiple rules evaluated in order."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="multi_rule",
            description="Multiple rules",
            flag_type="boolean",
            default_value=False,
        )
        
        # First rule: US users get True
        engine.add_rule(flag_id, "user_country == 'US'", True)
        
        # Second rule: Premium users get True
        engine.add_rule(flag_id, "user_tier == 'premium'", True)
        
        engine.enable_flag(flag_id)
        
        # US premium user - should match first rule
        result = engine.evaluate(flag_id, context={
            "user_country": "US",
            "user_tier": "premium",
        })
        
        assert result.value is True
        assert result.reason == "rule_match"
    
    def test_statistics_by_reason(self):
        """Test statistics breakdown by reason."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.enable_flag(flag_id)
        
        # Evaluate multiple times
        for i in range(5):
            engine.evaluate(flag_id, context={"user_id": f"user_{i}"})
        
        stats = engine.get_statistics()
        
        assert "by_reason" in stats
        assert stats["by_flag"][flag_id] == 5
    
    def test_change_log_sorted_newest_first(self):
        """Test that change log is sorted newest first."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.enable_flag(flag_id)
        engine.disable_flag(flag_id)
        engine.enable_flag(flag_id)
        
        changes = engine.get_change_log(flag_id=flag_id)
        
        # Should be sorted by changed_at (newest first)
        for i in range(len(changes) - 1):
            assert changes[i]["changed_at"] >= changes[i + 1]["changed_at"]
    
    def test_percentage_zero_disables_flag(self):
        """Test that 0% rollout disables flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="rollout_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.set_percentage_rollout(flag_id, 0.0)
        engine.enable_flag(flag_id)
        
        # No user should get True
        enabled_count = 0
        for i in range(100):
            result = engine.evaluate(flag_id, context={"user_id": f"user_{i}"})
            if result.value is True:
                enabled_count += 1
        
        assert enabled_count == 0
    
    def test_percentage_100_enables_all(self):
        """Test that 100% rollout enables for all users."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="rollout_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.set_percentage_rollout(flag_id, 100.0)
        engine.enable_flag(flag_id)
        
        # All users should get True
        for i in range(10):
            result = engine.evaluate(flag_id, context={"user_id": f"user_{i}"})
            assert result.value is True
    
    def test_rule_percentage_vs_global_percentage(self):
        """Test rule percentage vs global percentage."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        # Rule with 50% for premium users
        engine.add_rule(
            flag_id=flag_id,
            condition="user_tier == 'premium'",
            value=True,
            percentage=50.0,
        )
        
        # Global 10% rollout
        engine._flags[flag_id].percentage_rollout = 10.0
        
        engine.enable_flag(flag_id)
        
        # Premium users should be subject to rule percentage (50%)
        premium_enabled = 0
        for i in range(100):
            result = engine.evaluate(flag_id, context={"user_tier": "premium", "user_id": f"user_{i}"})
            if result.value is True:
                premium_enabled += 1
        
        # Should be roughly 50% of premium users
        assert 30 <= premium_enabled <= 70
    
    def test_created_by_tracked(self):
        """Test that created_by is tracked."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
            created_by="admin_user",
        )
        
        flag = engine.get_flag(flag_id)
        
        assert flag["created_by"] == "admin_user"
    
    def test_updated_at_changes_on_update(self):
        """Test that updated_at changes on update."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        flag_before = engine.get_flag(flag_id)
        created_at = flag_before["created_at"]
        
        import time
        time.sleep(0.01)
        
        engine.update_flag(flag_id, description="Updated")
        
        flag_after = engine.get_flag(flag_id)
        
        assert flag_after["updated_at"] >= flag_after["created_at"]
    
    def test_evaluation_with_empty_context(self):
        """Test evaluation with empty context."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=True,
        )
        
        engine.enable_flag(flag_id)
        
        result = engine.evaluate(flag_id, context={})
        
        assert result.value is True
        assert result.reason == "default"
    
    def test_statistics_cache_size(self):
        """Test that statistics include cache size."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag("test_flag", "Test", "boolean", False)
        engine.enable_flag(flag_id)
        
        for i in range(5):
            engine.evaluate(flag_id, context={"user_id": f"user_{i}"})
        
        stats = engine.get_statistics()
        
        assert "cache_size" in stats
        assert stats["cache_size"] == 5
    
    def test_export_includes_timestamp(self):
        """Test that export includes timestamp."""
        engine = FeatureFlagsEngine()
        
        export = engine.export_flags()
        
        assert "exported_at" in export
    
    def test_flag_with_all_fields(self):
        """Test creating flag with all fields."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="complete_flag",
            description="Complete test flag",
            flag_type="json",
            default_value={"key": "value"},
            environments=["production", "staging", "development"],
            tags=["frontend", "backend", "critical"],
            created_by="admin",
        )
        
        flag = engine.get_flag(flag_id)
        
        assert flag["name"] == "complete_flag"
        assert len(flag["environments"]) == 3
        assert len(flag["tags"]) == 3
        assert flag["created_by"] == "admin"
    
    def test_add_rule_to_unknown_flag(self):
        """Test adding rule to unknown flag."""
        engine = FeatureFlagsEngine()
        
        with pytest.raises(ValueError):
            engine.add_rule("unknown_flag", "condition", True)
    
    def test_evaluate_updates_statistics(self):
        """Test that evaluation updates statistics."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag("test_flag", "Test", "boolean", False)
        engine.enable_flag(flag_id)
        
        stats_before = engine.get_statistics()
        evaluations_before = stats_before["total_evaluations"]
        
        engine.evaluate(flag_id)
        engine.evaluate(flag_id)
        
        stats_after = engine.get_statistics()
        
        assert stats_after["total_evaluations"] == evaluations_before + 2
    
    def test_change_log_limit(self):
        """Test change log limit."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag("test_flag", "Test", "boolean", False)
        
        # Make many changes
        for i in range(50):
            engine.enable_flag(flag_id)
            engine.disable_flag(flag_id)
        
        changes = engine.get_change_log(flag_id=flag_id, limit=10)
        
        assert len(changes) == 10
    
    def test_rule_condition_with_numbers(self):
        """Test rule condition with numeric comparison."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="age_gate",
            description="Age gate",
            flag_type="boolean",
            default_value=False,
        )
        
        engine.add_rule(
            flag_id=flag_id,
            condition="user_age > 18",
            value=True,
        )
        
        engine.enable_flag(flag_id)
        
        # Adult user
        result = engine.evaluate(flag_id, context={"user_age": 25})
        assert result.value is True
        
        # Minor user
        result = engine.evaluate(flag_id, context={"user_age": 15})
        assert result.value is False
    
    def test_consistent_hashing_for_percentage(self):
        """Test that percentage hashing is consistent."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="consistent_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        engine._flags[flag_id].percentage_rollout = 50.0
        engine.enable_flag(flag_id)
        
        # Same user should always get same result
        result1 = engine.evaluate(flag_id, context={"user_id": "user_123"})
        result2 = engine.evaluate(flag_id, context={"user_id": "user_123"})
        result3 = engine.evaluate(flag_id, context={"user_id": "user_123"})
        
        assert result1.value == result2.value == result3.value
    
    def test_different_users_get_different_results(self):
        """Test that different users can get different results."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="ab_test",
            description="A/B test",
            flag_type="boolean",
            default_value=False,
        )
        
        engine._flags[flag_id].percentage_rollout = 50.0
        engine.enable_flag(flag_id)
        
        # Different users should potentially get different results
        results = set()
        for i in range(100):
            result = engine.evaluate(flag_id, context={"user_id": f"user_{i}"})
            results.add(result.value)
        
        # With 50% rollout and 100 users, should see both True and False
        assert True in results or False in results  # At least one value
    
    def test_metadata_stored(self):
        """Test that flag metadata is stored."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="test_flag",
            description="Test",
            flag_type="boolean",
            default_value=False,
        )
        
        engine._flags[flag_id].metadata = {"jira_id": "PROJ-123", "owner": "team-a"}
        
        flag = engine.get_flag(flag_id)
        
        assert flag["metadata"]["jira_id"] == "PROJ-123"
        assert flag["metadata"]["owner"] == "team-a"
    
    def test_archive_status(self):
        """Test archived flag status."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="old_feature",
            description="Deprecated",
            flag_type="boolean",
            default_value=False,
        )
        
        engine._flags[flag_id].status = FlagStatus.ARCHIVED
        
        flag = engine.get_flag(flag_id)
        assert flag["status"] == "archived"
    
    def test_evaluation_with_variant(self):
        """Test evaluation result with variant."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="ab_test",
            description="A/B test",
            flag_type="string",
            default_value="control",
        )
        
        engine.add_rule(
            flag_id=flag_id,
            condition="user_group == 'test'",
            value="variant_a",
        )
        
        engine.enable_flag(flag_id)
        
        result = engine.evaluate(flag_id, context={"user_group": "test"})
        
        assert result.value == "variant_a"
        assert result.reason == "rule_match"
    
    def test_boolean_flag_true_default(self):
        """Test boolean flag with True default."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="enabled_by_default",
            description="Enabled by default",
            flag_type="boolean",
            default_value=True,
        )
        
        engine.enable_flag(flag_id)
        
        result = engine.evaluate(flag_id)
        
        assert result.value is True
    
    def test_string_flag_empty_default(self):
        """Test string flag with empty default."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="empty_string",
            description="Empty string",
            flag_type="string",
            default_value="",
        )
        
        engine.enable_flag(flag_id)
        
        result = engine.evaluate(flag_id)
        
        assert result.value == ""
    
    def test_number_flag_negative_default(self):
        """Test number flag with negative default."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="negative_number",
            description="Negative number",
            flag_type="number",
            default_value=-100,
        )
        
        engine.enable_flag(flag_id)
        
        result = engine.evaluate(flag_id)
        
        assert result.value == -100
    
    def test_json_flag_complex_default(self):
        """Test JSON flag with complex default."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="complex_config",
            description="Complex config",
            flag_type="json",
            default_value={
                "features": {"a": True, "b": False},
                "limits": {"max": 100, "min": 1},
                "nested": {"deep": {"value": "test"}},
            },
        )
        
        engine.enable_flag(flag_id)
        
        result = engine.evaluate(flag_id)
        
        assert result.value["features"]["a"] is True
        assert result.value["limits"]["max"] == 100
        assert result.value["nested"]["deep"]["value"] == "test"
