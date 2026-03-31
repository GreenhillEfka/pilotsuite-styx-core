"""Tests for Feature Flags Advanced Engine — Slice 59."""
import pytest
from copilot_core.featureflags_advanced.engine import (
    FeatureFlagsEngine,
    FlagType,
    RolloutStrategy,
    FeatureFlag,
    FlagVariant,
    EvaluationResult,
    create_feature_flags_engine,
)
from datetime import datetime, timezone, timedelta
import time


class TestFlagVariant:
    """Test flag variant."""
    
    def test_create_variant(self):
        """Test creating variant."""
        variant = FlagVariant(
            variant_id="var_test",
            name="Variant A",
            value={"color": "blue"},
            weight=0.5,
        )
        
        assert variant.variant_id == "var_test"
        assert variant.name == "Variant A"
        assert variant.weight == 0.5
    
    def test_variant_to_dict(self):
        """Test variant serialization."""
        variant = FlagVariant(
            variant_id="var_test",
            name="Test",
            value="test_value",
            weight=0.3,
            description="Test variant",
        )
        
        d = variant.to_dict()
        
        assert d["variant_id"] == "var_test"
        assert d["weight"] == 0.3
        assert d["description"] == "Test variant"


class TestFeatureFlag:
    """Test feature flag."""
    
    def test_create_flag(self):
        """Test creating feature flag."""
        flag = FeatureFlag(
            flag_id="flag_test",
            name="Test Flag",
            flag_type=FlagType.BOOLEAN,
            default_value=False,
        )
        
        assert flag.flag_id == "flag_test"
        assert flag.name == "Test Flag"
        assert flag.enabled is True
    
    def test_flag_to_dict(self):
        """Test flag serialization."""
        flag = FeatureFlag(
            flag_id="flag_test",
            name="Test",
            flag_type=FlagType.PERCENTAGE,
            default_value=True,
            rollout_percentage=50.0,
            target_users={"user1", "user2"},
        )
        
        d = flag.to_dict()
        
        assert d["flag_id"] == "flag_test"
        assert d["rollout_percentage"] == 50.0
        assert "user1" in d["target_users"]
    
    def test_flag_created_at_set(self):
        """Test that flag created_at is set."""
        flag = FeatureFlag(
            flag_id="flag_test",
            name="Test",
            flag_type=FlagType.BOOLEAN,
            default_value=False,
        )
        
        assert flag.created_at is not None


class TestEvaluationResult:
    """Test evaluation result."""
    
    def test_create_result(self):
        """Test creating evaluation result."""
        result = EvaluationResult(
            flag_id="flag_test",
            value=True,
            variant_id="var_a",
            reason="percentage_rollout",
        )
        
        assert result.flag_id == "flag_test"
        assert result.value is True
        assert result.variant_id == "var_a"
    
    def test_result_to_dict(self):
        """Test result serialization."""
        result = EvaluationResult(
            flag_id="flag_test",
            value="variant_b",
            variant_id="var_b",
            reason="variant_assigned",
            flag_enabled=True,
        )
        
        d = result.to_dict()
        
        assert d["flag_id"] == "flag_test"
        assert d["value"] == "variant_b"
        assert d["reason"] == "variant_assigned"


class TestFeatureFlagsEngine:
    """Test feature flags engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_feature_flags_engine()
        assert engine is not None
    
    def test_create_boolean_flag(self):
        """Test creating boolean flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("dark_mode", default=False)
        
        assert flag_id is not None
        assert flag_id.startswith("flag_")
        
        flag = engine.get_flag(flag_id)
        
        assert flag.flag_type == FlagType.BOOLEAN
        assert flag.default_value is False
    
    def test_create_percentage_flag(self):
        """Test creating percentage flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_percentage_flag("beta_feature", percentage=25.0)
        
        flag = engine.get_flag(flag_id)
        
        assert flag.flag_type == FlagType.PERCENTAGE
        assert flag.rollout_percentage == 25.0
    
    def test_create_variant_flag(self):
        """Test creating variant flag."""
        engine = FeatureFlagsEngine()
        
        variants = [
            FlagVariant("var_a", "Control", {"color": "blue"}, weight=0.5),
            FlagVariant("var_b", "Test", {"color": "red"}, weight=0.5),
        ]
        
        flag_id = engine.create_variant_flag("button_color", variants)
        
        flag = engine.get_flag(flag_id)
        
        assert flag.flag_type == FlagType.VARIANT
        assert len(flag.variants) == 2
    
    def test_create_flag_with_dependencies(self):
        """Test creating flag with dependencies."""
        engine = FeatureFlagsEngine()
        
        dep_id = engine.create_boolean_flag("prerequisite", default=True)
        
        flag_id = engine.create_flag(
            name="Dependent Flag",
            flag_type=FlagType.BOOLEAN,
            default_value=False,
            dependencies=[dep_id],
        )
        
        flag = engine.get_flag(flag_id)
        
        assert dep_id in flag.dependencies
    
    def test_create_flag_with_metadata(self):
        """Test creating flag with metadata."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="Test Flag",
            flag_type=FlagType.BOOLEAN,
            default_value=False,
            metadata={"team": "backend", "jira": "PROJ-123"},
        )
        
        flag = engine.get_flag(flag_id)
        
        assert flag.metadata["team"] == "backend"
        assert flag.metadata["jira"] == "PROJ-123"
    
    def test_update_flag(self):
        """Test updating flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=False)
        
        result = engine.update_flag(
            flag_id,
            enabled=False,
            rollout_percentage=50.0,
        )
        
        assert result is True
        
        flag = engine.get_flag(flag_id)
        
        assert flag.enabled is False
        assert flag.rollout_percentage == 50.0
    
    def test_update_nonexistent_flag(self):
        """Test updating nonexistent flag."""
        engine = FeatureFlagsEngine()
        
        result = engine.update_flag("nonexistent", enabled=False)
        
        assert result is False
    
    def test_delete_flag(self):
        """Test deleting flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=False)
        
        result = engine.delete_flag(flag_id)
        
        assert result is True
        assert engine.get_flag(flag_id) is None
    
    def test_delete_nonexistent_flag(self):
        """Test deleting nonexistent flag."""
        engine = FeatureFlagsEngine()
        
        result = engine.delete_flag("nonexistent")
        
        assert result is False
    
    def test_get_flag(self):
        """Test getting flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=False)
        
        flag = engine.get_flag(flag_id)
        
        assert flag is not None
        assert flag.name == "Test"
    
    def test_get_nonexistent_flag(self):
        """Test getting nonexistent flag."""
        engine = FeatureFlagsEngine()
        
        flag = engine.get_flag("nonexistent")
        
        assert flag is None
    
    def test_list_flags(self):
        """Test listing flags."""
        engine = FeatureFlagsEngine()
        
        engine.create_boolean_flag("Flag 1", default=False)
        engine.create_boolean_flag("Flag 2", default=True)
        engine.create_percentage_flag("Flag 3", percentage=50.0)
        
        flags = engine.list_flags()
        
        assert len(flags) == 3
    
    def test_list_flags_filtered_by_enabled(self):
        """Test listing flags filtered by enabled."""
        engine = FeatureFlagsEngine()
        
        flag1 = engine.create_boolean_flag("Enabled", default=True)
        flag2 = engine.create_boolean_flag("Disabled", default=False)
        
        engine.update_flag(flag2, enabled=False)
        
        enabled = engine.list_flags(enabled=True)
        disabled = engine.list_flags(enabled=False)
        
        assert len(enabled) == 1
        assert len(disabled) == 1
    
    def test_list_flags_filtered_by_type(self):
        """Test listing flags filtered by type."""
        engine = FeatureFlagsEngine()
        
        engine.create_boolean_flag("Bool Flag", default=True)
        engine.create_percentage_flag("Percent Flag", percentage=50.0)
        
        boolean_flags = engine.list_flags(flag_type=FlagType.BOOLEAN)
        percent_flags = engine.list_flags(flag_type=FlagType.PERCENTAGE)
        
        assert len(boolean_flags) == 1
        assert len(percent_flags) == 1
    
    def test_evaluate_enabled_flag(self):
        """Test evaluating enabled flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        result = engine.evaluate(flag_id)
        
        assert result.flag_enabled is True
        assert result.value is True
    
    def test_evaluate_disabled_flag(self):
        """Test evaluating disabled flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=False)
        
        engine.update_flag(flag_id, enabled=False)
        
        result = engine.evaluate(flag_id)
        
        assert result.flag_enabled is False
        assert result.reason == "flag_disabled"
    
    def test_evaluate_nonexistent_flag(self):
        """Test evaluating nonexistent flag."""
        engine = FeatureFlagsEngine()
        
        result = engine.evaluate("nonexistent")
        
        assert result.flag_enabled is False
        assert result.reason == "flag_not_found"
        assert result.value is None
    
    def test_evaluate_with_user_targeting(self):
        """Test evaluating with user targeting."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="Targeted",
            flag_type=FlagType.BOOLEAN,
            default_value=False,
            rollout_strategy=RolloutStrategy.USER_TARGETING,
        )
        
        engine.add_target_user(flag_id, "user_123")
        
        # Targeted user should get flag
        result = engine.evaluate(flag_id, user_id="user_123")
        
        assert result.flag_enabled is True
        
        # Non-targeted user should not
        result = engine.evaluate(flag_id, user_id="user_456")
        
        assert result.flag_enabled is False
    
    def test_evaluate_with_excluded_users(self):
        """Test evaluating with excluded users."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        engine.add_excluded_user(flag_id, "user_123")
        
        # Excluded user should not get flag
        result = engine.evaluate(flag_id, user_id="user_123")
        
        assert result.flag_enabled is False
        assert result.reason == "user_excluded"
    
    def test_evaluate_percentage_rollout(self):
        """Test evaluating percentage rollout."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_percentage_flag("Test", percentage=0.0)  # 0% rollout
        
        result = engine.evaluate(flag_id, user_id="user_123")
        
        # Should be disabled due to 0% rollout
        assert result.flag_enabled is False
        assert result.reason == "percentage_rollout"
    
    def test_evaluate_percentage_100(self):
        """Test evaluating 100% rollout."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_percentage_flag("Test", percentage=100.0)
        
        result = engine.evaluate(flag_id, user_id="user_123")
        
        # Should be enabled
        assert result.flag_enabled is True
    
    def test_evaluate_with_schedule_not_started(self):
        """Test evaluating flag before schedule start."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Scheduled", default=True)
        
        # Set future start time
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        engine.update_flag(flag_id, schedule_start=future)
        
        result = engine.evaluate(flag_id)
        
        assert result.flag_enabled is False
        assert result.reason == "outside_schedule"
    
    def test_evaluate_with_schedule_ended(self):
        """Test evaluating flag after schedule end."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Scheduled", default=True)
        
        # Set past end time
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        
        engine.update_flag(flag_id, schedule_end=past)
        
        result = engine.evaluate(flag_id)
        
        assert result.flag_enabled is False
        assert result.reason == "outside_schedule"
    
    def test_evaluate_with_dependency_disabled(self):
        """Test evaluating flag with disabled dependency."""
        engine = FeatureFlagsEngine()
        
        dep_id = engine.create_boolean_flag("Prerequisite", default=True)
        engine.update_flag(dep_id, enabled=False)
        
        flag_id = engine.create_flag(
            name="Dependent",
            flag_type=FlagType.BOOLEAN,
            default_value=False,
            dependencies=[dep_id],
        )
        
        result = engine.evaluate(flag_id)
        
        assert result.flag_enabled is False
        assert result.reason == "dependency_not_met"
    
    def test_evaluate_variant_flag(self):
        """Test evaluating variant flag."""
        engine = FeatureFlagsEngine()
        
        variants = [
            FlagVariant("var_a", "Control", "blue", weight=0.5),
            FlagVariant("var_b", "Test", "red", weight=0.5),
        ]
        
        flag_id = engine.create_variant_flag("button_color", variants)
        
        result = engine.evaluate(flag_id, user_id="user_123")
        
        assert result.flag_enabled is True
        assert result.variant_id in ("var_a", "var_b")
        assert result.value in ("blue", "red")
    
    def test_evaluate_variant_consistent(self):
        """Test that variant evaluation is consistent for same user."""
        engine = FeatureFlagsEngine()
        
        variants = [
            FlagVariant("var_a", "Control", "blue", weight=0.5),
            FlagVariant("var_b", "Test", "red", weight=0.5),
        ]
        
        flag_id = engine.create_variant_flag("button_color", variants)
        
        # Same user should get same variant
        result1 = engine.evaluate(flag_id, user_id="user_123")
        result2 = engine.evaluate(flag_id, user_id="user_123")
        
        assert result1.variant_id == result2.variant_id
        assert result1.value == result2.value
    
    def test_is_enabled_true(self):
        """Test is_enabled returns True."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        result = engine.is_enabled(flag_id)
        
        assert result is True
    
    def test_is_enabled_false(self):
        """Test is_enabled returns False."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=False)
        
        result = engine.is_enabled(flag_id)
        
        assert result is False
    
    def test_is_enabled_disabled_flag(self):
        """Test is_enabled for disabled flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        engine.update_flag(flag_id, enabled=False)
        
        result = engine.is_enabled(flag_id)
        
        assert result is False
    
    def test_get_value(self):
        """Test getting flag value."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="Config",
            flag_type=FlagType.STRING,
            default_value="production",
        )
        
        value = engine.get_value(flag_id)
        
        assert value == "production"
    
    def test_get_value_with_default(self):
        """Test getting value with default."""
        engine = FeatureFlagsEngine()
        
        value = engine.get_value("nonexistent", default="fallback")
        
        assert value == "fallback"
    
    def test_add_target_user(self):
        """Test adding target user."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="Targeted",
            flag_type=FlagType.BOOLEAN,
            default_value=False,
            rollout_strategy=RolloutStrategy.USER_TARGETING,
        )
        
        result = engine.add_target_user(flag_id, "user_123")
        
        assert result is True
        
        flag = engine.get_flag(flag_id)
        
        assert "user_123" in flag.target_users
    
    def test_add_target_user_nonexistent(self):
        """Test adding target user to nonexistent flag."""
        engine = FeatureFlagsEngine()
        
        result = engine.add_target_user("nonexistent", "user_123")
        
        assert result is False
    
    def test_remove_target_user(self):
        """Test removing target user."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="Targeted",
            flag_type=FlagType.BOOLEAN,
            default_value=False,
            rollout_strategy=RolloutStrategy.USER_TARGETING,
        )
        
        engine.add_target_user(flag_id, "user_123")
        
        result = engine.remove_target_user(flag_id, "user_123")
        
        assert result is True
        
        flag = engine.get_flag(flag_id)
        
        assert "user_123" not in flag.target_users
    
    def test_add_excluded_user(self):
        """Test adding excluded user."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        result = engine.add_excluded_user(flag_id, "user_123")
        
        assert result is True
        
        flag = engine.get_flag(flag_id)
        
        assert "user_123" in flag.excluded_users
    
    def test_remove_excluded_user(self):
        """Test removing excluded user."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        engine.add_excluded_user(flag_id, "user_123")
        
        result = engine.remove_excluded_user(flag_id, "user_123")
        
        assert result is True
        
        flag = engine.get_flag(flag_id)
        
        assert "user_123" not in flag.excluded_users
    
    def test_add_variant(self):
        """Test adding variant to flag."""
        engine = FeatureFlagsEngine()
        
        variants = [FlagVariant("var_a", "A", "value_a", weight=1.0)]
        
        flag_id = engine.create_variant_flag("Test", variants)
        
        new_variant = FlagVariant("var_b", "B", "value_b", weight=0.5)
        
        result = engine.add_variant(flag_id, new_variant)
        
        assert result is True
        
        flag = engine.get_flag(flag_id)
        
        assert len(flag.variants) == 2
    
    def test_add_variant_to_non_variant_flag(self):
        """Test adding variant to non-variant flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        variant = FlagVariant("var_a", "A", True, weight=1.0)
        
        result = engine.add_variant(flag_id, variant)
        
        assert result is False
    
    def test_evaluate_caching(self):
        """Test that evaluations are cached."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        # First evaluation
        result1 = engine.evaluate(flag_id, user_id="user_123")
        
        # Second evaluation (should use cache)
        result2 = engine.evaluate(flag_id, user_id="user_123")
        
        # Should be same result
        assert result1.value == result2.value
    
    def test_clear_cache_specific_flag(self):
        """Test clearing cache for specific flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        engine.evaluate(flag_id, user_id="user_123")
        engine.evaluate(flag_id, user_id="user_456")
        
        count = engine.clear_cache(flag_id)
        
        assert count == 2
    
    def test_clear_cache_all(self):
        """Test clearing all cache."""
        engine = FeatureFlagsEngine()
        
        flag1 = engine.create_boolean_flag("Flag 1", default=True)
        flag2 = engine.create_boolean_flag("Flag 2", default=True)
        
        engine.evaluate(flag1, user_id="user_123")
        engine.evaluate(flag2, user_id="user_123")
        
        count = engine.clear_cache()
        
        assert count == 2
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        engine.evaluate(flag_id, user_id="user_123")
        engine.evaluate(flag_id, user_id="user_456")
        
        stats = engine.get_statistics()
        
        assert stats["total_flags"] == 1
        assert stats["total_evaluations"] == 2
    
    def test_statistics_by_flag(self):
        """Test statistics by flag."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        for i in range(10):
            engine.evaluate(flag_id, user_id=f"user_{i}")
        
        stats = engine.get_statistics()
        
        assert stats["by_flag"][flag_id] == 10
    
    def test_statistics_by_variant(self):
        """Test statistics by variant."""
        engine = FeatureFlagsEngine()
        
        variants = [
            FlagVariant("var_a", "A", "a", weight=0.5),
            FlagVariant("var_b", "B", "b", weight=0.5),
        ]
        
        flag_id = engine.create_variant_flag("Test", variants)
        
        for i in range(20):
            engine.evaluate(flag_id, user_id=f"user_{i}")
        
        stats = engine.get_statistics()
        
        # Should have evaluations for both variants
        assert len(stats["by_variant"]) == 2
    
    def test_evaluate_rollout_none(self):
        """Test evaluating with rollout strategy NONE."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="None",
            flag_type=FlagType.BOOLEAN,
            default_value=False,
            rollout_strategy=RolloutStrategy.NONE,
        )
        
        result = engine.evaluate(flag_id)
        
        assert result.flag_enabled is False
        assert result.reason == "rollout_none"
    
    def test_flag_type_enum_values(self):
        """Test flag type enum values."""
        assert FlagType.BOOLEAN.value == "boolean"
        assert FlagType.PERCENTAGE.value == "percentage"
        assert FlagType.VARIANT.value == "variant"
        assert FlagType.NUMERIC.value == "numeric"
        assert FlagType.STRING.value == "string"
        assert FlagType.JSON.value == "json"
    
    def test_rollout_strategy_enum_values(self):
        """Test rollout strategy enum values."""
        assert RolloutStrategy.ALL.value == "all"
        assert RolloutStrategy.NONE.value == "none"
        assert RolloutStrategy.PERCENTAGE.value == "percentage"
        assert RolloutStrategy.USER_TARGETING.value == "user_targeting"
        assert RolloutStrategy.SCHEDULED.value == "scheduled"
        assert RolloutStrategy.CANARY.value == "canary"
    
    def test_flag_updated_at_changes(self):
        """Test that flag updated_at changes on update."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=False)
        
        flag1 = engine.get_flag(flag_id)
        
        time.sleep(0.01)
        
        engine.update_flag(flag_id, enabled=False)
        
        flag2 = engine.get_flag(flag_id)
        
        assert flag2.updated_at > flag1.updated_at
    
    def test_evaluate_anonymous_user_percentage(self):
        """Test evaluating percentage rollout for anonymous user."""
        engine = FeatureFlagsEngine()
        
        # 0% rollout
        flag_id = engine.create_percentage_flag("Test", percentage=0.0)
        
        result = engine.evaluate(flag_id)  # No user_id
        
        assert result.flag_enabled is False
    
    def test_evaluate_with_context(self):
        """Test evaluating with context."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        result = engine.evaluate(flag_id, user_id="user_123", context={"plan": "premium"})
        
        assert result.flag_enabled is True
    
    def test_create_flag_with_default_values(self):
        """Test creating flag with default values."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="Test",
            flag_type=FlagType.BOOLEAN,
            default_value=True,
        )
        
        flag = engine.get_flag(flag_id)
        
        assert flag.enabled is True
        assert flag.rollout_strategy == RolloutStrategy.ALL
        assert flag.rollout_percentage == 100.0
        assert len(flag.target_users) == 0
    
    def test_flag_id_unique(self):
        """Test that flag IDs are unique."""
        engine = FeatureFlagsEngine()
        
        ids = set()
        for i in range(50):
            flag_id = engine.create_boolean_flag(f"Flag {i}", default=False)
            ids.add(flag_id)
        
        assert len(ids) == 50
    
    def test_variant_id_unique(self):
        """Test that variant IDs should be unique (user-provided)."""
        # Variant IDs are user-provided, not auto-generated
        variant1 = FlagVariant("var_1", "Variant 1", "value1", weight=0.5)
        variant2 = FlagVariant("var_2", "Variant 2", "value2", weight=0.5)
        
        assert variant1.variant_id != variant2.variant_id
    
    def test_evaluate_updates_enabled_evaluations(self):
        """Test that evaluate updates enabled evaluations stat."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        engine.evaluate(flag_id)
        
        stats = engine.get_statistics()
        
        assert stats["enabled_evaluations"] == 1
    
    def test_evaluate_updates_disabled_evaluations(self):
        """Test that evaluate updates disabled evaluations stat."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=False)
        
        engine.evaluate(flag_id)
        
        stats = engine.get_statistics()
        
        assert stats["disabled_evaluations"] == 1
    
    def test_statistics_enabled_flags(self):
        """Test that statistics track enabled flags."""
        engine = FeatureFlagsEngine()
        
        engine.create_boolean_flag("Enabled", default=True)
        
        flag_id = engine.create_boolean_flag("Disabled", default=False)
        engine.update_flag(flag_id, enabled=False)
        
        stats = engine.get_statistics()
        
        assert stats["enabled_flags"] == 1
    
    def test_statistics_cached_evaluations(self):
        """Test that statistics track cached evaluations."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        for i in range(5):
            engine.evaluate(flag_id, user_id=f"user_{i}")
        
        stats = engine.get_statistics()
        
        assert stats["cached_evaluations"] == 5
    
    def test_list_flags_empty(self):
        """Test listing flags when empty."""
        engine = FeatureFlagsEngine()
        
        flags = engine.list_flags()
        
        assert flags == []
    
    def test_clear_cache_empty(self):
        """Test clearing empty cache."""
        engine = FeatureFlagsEngine()
        
        count = engine.clear_cache()
        
        assert count == 0
    
    def test_clear_cache_nonexistent_flag(self):
        """Test clearing cache for nonexistent flag."""
        engine = FeatureFlagsEngine()
        
        count = engine.clear_cache("nonexistent")
        
        assert count == 0
    
    def test_evaluate_boolean_flag_value(self):
        """Test that boolean flag returns boolean value."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        result = engine.evaluate(flag_id)
        
        assert isinstance(result.value, bool)
        assert result.value is True
    
    def test_get_value_nonexistent_with_default(self):
        """Test getting value from nonexistent flag with default."""
        engine = FeatureFlagsEngine()
        
        value = engine.get_value("nonexistent", default="fallback_value")
        
        assert value == "fallback_value"
    
    def test_get_value_nonexistent_no_default(self):
        """Test getting value from nonexistent flag without default."""
        engine = FeatureFlagsEngine()
        
        value = engine.get_value("nonexistent")
        
        assert value is None
    
    def test_is_enabled_nonexistent(self):
        """Test is_enabled for nonexistent flag."""
        engine = FeatureFlagsEngine()
        
        result = engine.is_enabled("nonexistent")
        
        assert result is False
    
    def test_add_variant_nonexistent_flag(self):
        """Test adding variant to nonexistent flag."""
        engine = FeatureFlagsEngine()
        
        variant = FlagVariant("var_a", "A", "value", weight=1.0)
        
        result = engine.add_variant("nonexistent", variant)
        
        assert result is False
    
    def test_remove_target_user_nonexistent(self):
        """Test removing target user from nonexistent flag."""
        engine = FeatureFlagsEngine()
        
        result = engine.remove_target_user("nonexistent", "user_123")
        
        assert result is False
    
    def test_add_excluded_user_nonexistent(self):
        """Test adding excluded user to nonexistent flag."""
        engine = FeatureFlagsEngine()
        
        result = engine.add_excluded_user("nonexistent", "user_123")
        
        assert result is False
    
    def test_remove_excluded_user_nonexistent(self):
        """Test removing excluded user from nonexistent flag."""
        engine = FeatureFlagsEngine()
        
        result = engine.remove_excluded_user("nonexistent", "user_123")
        
        assert result is False
    
    def test_update_flag_target_users(self):
        """Test updating flag target users."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="Test",
            flag_type=FlagType.BOOLEAN,
            default_value=False,
            rollout_strategy=RolloutStrategy.USER_TARGETING,
        )
        
        engine.update_flag(flag_id, target_users={"user1", "user2"})
        
        flag = engine.get_flag(flag_id)
        
        assert "user1" in flag.target_users
        assert "user2" in flag.target_users
    
    def test_update_flag_schedule(self):
        """Test updating flag schedule."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        start = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        
        engine.update_flag(flag_id, schedule_start=start, schedule_end=end)
        
        flag = engine.get_flag(flag_id)
        
        assert flag.schedule_start is not None
        assert flag.schedule_end is not None
    
    def test_evaluate_variant_weight_normalization(self):
        """Test that variant weights are normalized."""
        engine = FeatureFlagsEngine()
        
        # Weights don't sum to 1.0
        variants = [
            FlagVariant("var_a", "A", "a", weight=50),
            FlagVariant("var_b", "B", "b", weight=50),
        ]
        
        flag_id = engine.create_variant_flag("Test", variants)
        
        flag = engine.get_flag(flag_id)
        
        # Weights should be normalized to 0.5 each
        total = sum(v.weight for v in flag.variants)
        
        assert abs(total - 1.0) < 0.001
    
    def test_evaluate_canary_strategy(self):
        """Test evaluating with canary strategy."""
        engine = FeatureFlagsEngine()
        
        variants = [
            FlagVariant("var_control", "Control", "control", weight=0.9),
            FlagVariant("var_canary", "Canary", "canary", weight=0.1),
        ]
        
        flag_id = engine.create_flag(
            name="Canary",
            flag_type=FlagType.VARIANT,
            default_value="default",
            rollout_strategy=RolloutStrategy.CANARY,
            variants=variants,
        )
        
        result = engine.evaluate(flag_id, user_id="user_123")
        
        assert result.flag_enabled is True
        assert result.variant_id in ("var_control", "var_canary")
    
    def test_evaluation_result_flag_enabled_default(self):
        """Test that evaluation result flag_enabled defaults to True."""
        result = EvaluationResult(
            flag_id="flag_test",
            value=True,
        )
        
        assert result.flag_enabled is True
    
    def test_flag_target_users_as_list_in_dict(self):
        """Test that target_users is converted to list in to_dict."""
        flag = FeatureFlag(
            flag_id="flag_test",
            name="Test",
            flag_type=FlagType.BOOLEAN,
            default_value=True,
            target_users={"user1", "user2"},
        )
        
        d = flag.to_dict()
        
        assert isinstance(d["target_users"], list)
        assert "user1" in d["target_users"]
    
    def test_flag_excluded_users_as_list_in_dict(self):
        """Test that excluded_users is converted to list in to_dict."""
        flag = FeatureFlag(
            flag_id="flag_test",
            name="Test",
            flag_type=FlagType.BOOLEAN,
            default_value=True,
            excluded_users={"user1"},
        )
        
        d = flag.to_dict()
        
        assert isinstance(d["excluded_users"], list)
        assert "user1" in d["excluded_users"]
    
    def test_multiple_flags_independent(self):
        """Test that multiple flags are independent."""
        engine = FeatureFlagsEngine()
        
        flag1 = engine.create_boolean_flag("Flag 1", default=True)
        flag2 = engine.create_boolean_flag("Flag 2", default=False)
        
        result1 = engine.evaluate(flag1)
        result2 = engine.evaluate(flag2)
        
        assert result1.value is True
        assert result2.value is False
    
    def test_variant_flag_empty_variants(self):
        """Test variant flag with empty variants list."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_flag(
            name="Empty Variants",
            flag_type=FlagType.VARIANT,
            default_value="default",
            variants=[],
        )
        
        result = engine.evaluate(flag_id, user_id="user_123")
        
        # Should fall back to default
        assert result.value == "default"
    
    def test_get_statistics_total_flags(self):
        """Test that statistics track total flags."""
        engine = FeatureFlagsEngine()
        
        for i in range(10):
            engine.create_boolean_flag(f"Flag {i}", default=False)
        
        stats = engine.get_statistics()
        
        assert stats["total_flags"] == 10
    
    def test_evaluate_with_null_user_id(self):
        """Test evaluating with None user_id."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        result = engine.evaluate(flag_id, user_id=None)
        
        assert result.flag_enabled is True
    
    def test_evaluate_with_empty_context(self):
        """Test evaluating with empty context."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        result = engine.evaluate(flag_id, user_id="user_123", context={})
        
        assert result.flag_enabled is True
    
    def test_update_flag_metadata(self):
        """Test updating flag metadata."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        engine.update_flag(flag_id, metadata={"updated": True, "version": "2.0"})
        
        flag = engine.get_flag(flag_id)
        
        assert flag.metadata["updated"] is True
        assert flag.metadata["version"] == "2.0"
    
    def test_create_flag_variant_list_copied(self):
        """Test that variant list is copied when creating flag."""
        engine = FeatureFlagsEngine()
        
        variants = [FlagVariant("var_a", "A", "a", weight=1.0)]
        
        flag_id = engine.create_variant_flag("Test", variants)
        
        flag = engine.get_flag(flag_id)
        
        # Modify original list
        variants.append(FlagVariant("var_b", "B", "b", weight=0.5))
        
        # Flag should not be affected
        assert len(flag.variants) == 1
    
    def test_evaluate_consistent_hash_same_user(self):
        """Test that same user gets consistent hash result."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_percentage_flag("Test", percentage=50.0)
        
        # Same user should always get same result
        results = [engine.evaluate(flag_id, user_id="user_123").flag_enabled for _ in range(10)]
        
        # All results should be the same
        assert all(r == results[0] for r in results)
    
    def test_evaluate_different_users_different_results(self):
        """Test that different users can get different results."""
        engine = FeatureFlagsEngine()
        
        # 50% rollout
        flag_id = engine.create_percentage_flag("Test", percentage=50.0)
        
        results = {}
        for i in range(100):
            result = engine.evaluate(flag_id, user_id=f"user_{i}").flag_enabled
            results[result] = results.get(result, 0) + 1
        
        # Should have both enabled and disabled (statistically)
        assert True in results
        assert False in results
    
    def test_clear_cache_returns_correct_count(self):
        """Test that clear_cache returns correct count."""
        engine = FeatureFlagsEngine()
        
        flag_id = engine.create_boolean_flag("Test", default=True)
        
        # Add 5 cached evaluations
        for i in range(5):
            engine.evaluate(flag_id, user_id=f"user_{i}")
        
        count = engine.clear_cache(flag_id)
        
        assert count == 5
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = FeatureFlagsEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_evaluations"] == 0
        assert stats["enabled_evaluations"] == 0
        assert stats["disabled_evaluations"] == 0
        assert stats["total_flags"] == 0
        assert stats["cached_evaluations"] == 0
