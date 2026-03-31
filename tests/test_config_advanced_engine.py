"""Tests for Configuration Advanced Engine — Slice 61."""
import pytest
from copilot_core.config_advanced.engine import (
    ConfigurationEngine,
    ConfigType,
    ChangeType,
    ConfigValue,
    ConfigChange,
    ConfigSchema,
    create_configuration_engine,
)
from datetime import datetime, timezone
import os


class TestConfigValue:
    """Test configuration value."""
    
    def test_create_value(self):
        """Test creating config value."""
        value = ConfigValue(
            key="test.key",
            value="test_value",
            value_type=ConfigType.STRING,
        )
        
        assert value.key == "test.key"
        assert value.value == "test_value"
        assert value.source == "default"
    
    def test_value_to_dict(self):
        """Test value serialization."""
        value = ConfigValue(
            key="test.key",
            value="secret123",
            value_type=ConfigType.STRING,
            is_secret=True,
            version=5,
        )
        
        d = value.to_dict(mask_secrets=True)
        
        assert d["key"] == "test.key"
        assert d["value"] == "***REDACTED***"
        assert d["version"] == 5
    
    def test_value_to_dict_unmasked(self):
        """Test value serialization without masking."""
        value = ConfigValue(
            key="test.key",
            value="secret123",
            value_type=ConfigType.STRING,
            is_secret=True,
        )
        
        d = value.to_dict(mask_secrets=False)
        
        assert d["value"] == "secret123"
    
    def test_value_timestamp_set(self):
        """Test that value timestamp is set."""
        value = ConfigValue(
            key="test.key",
            value=42,
            value_type=ConfigType.INTEGER,
        )
        
        assert value.updated_at is not None


class TestConfigChange:
    """Test configuration change."""
    
    def test_create_change(self):
        """Test creating config change."""
        change = ConfigChange(
            change_id="cc_test",
            key="test.key",
            change_type=ChangeType.UPDATED,
            old_value="old",
            new_value="new",
            source="api",
        )
        
        assert change.change_id == "cc_test"
        assert change.change_type == ChangeType.UPDATED
    
    def test_change_to_dict(self):
        """Test change serialization."""
        change = ConfigChange(
            change_id="cc_test",
            key="test.key",
            change_type=ChangeType.ADDED,
            old_value=None,
            new_value=100,
            source="env",
        )
        
        d = change.to_dict()
        
        assert d["change_type"] == "added"
        assert d["new_value"] == 100
        assert d["source"] == "env"


class TestConfigSchema:
    """Test configuration schema."""
    
    def test_create_schema(self):
        """Test creating config schema."""
        schema = ConfigSchema(
            key="app.port",
            value_type=ConfigType.INTEGER,
            required=True,
            default=8080,
            min_value=1,
            max_value=65535,
        )
        
        assert schema.key == "app.port"
        assert schema.required is True
        assert schema.default == 8080


class TestConfigurationEngine:
    """Test configuration engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_configuration_engine()
        assert engine is not None
    
    def test_set_string(self):
        """Test setting string value."""
        engine = ConfigurationEngine()
        
        result = engine.set("app.name", "MyApp")
        
        assert result is True
        assert engine.get("app.name") == "MyApp"
    
    def test_set_integer(self):
        """Test setting integer value."""
        engine = ConfigurationEngine()
        
        engine.set("app.port", 8080)
        
        assert engine.get("app.port") == 8080
    
    def test_set_float(self):
        """Test setting float value."""
        engine = ConfigurationEngine()
        
        engine.set("app.timeout", 30.5)
        
        assert engine.get("app.timeout") == 30.5
    
    def test_set_boolean(self):
        """Test setting boolean value."""
        engine = ConfigurationEngine()
        
        engine.set("app.enabled", True)
        
        assert engine.get("app.enabled") is True
    
    def test_set_list(self):
        """Test setting list value."""
        engine = ConfigurationEngine()
        
        engine.set("app.hosts", ["localhost", "127.0.0.1"])
        
        assert engine.get("app.hosts") == ["localhost", "127.0.0.1"]
    
    def test_set_dict(self):
        """Test setting dict value."""
        engine = ConfigurationEngine()
        
        engine.set("app.config", {"key": "value", "nested": {"a": 1}})
        
        assert engine.get("app.config")["key"] == "value"
    
    def test_set_secret(self):
        """Test setting secret value."""
        engine = ConfigurationEngine()
        
        engine.set("db.password", "secret123", is_secret=True)
        
        typed = engine.get_typed("db.password")
        
        assert typed is not None
        assert typed.is_secret is True
    
    def test_set_with_source(self):
        """Test setting value with source."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp", source="file")
        
        typed = engine.get_typed("app.name")
        
        assert typed.source == "file"
    
    def test_set_with_description(self):
        """Test setting value with description."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp", description="Application name")
        
        typed = engine.get_typed("app.name")
        
        assert typed.description == "Application name"
    
    def test_get_nonexistent(self):
        """Test getting nonexistent key."""
        engine = ConfigurationEngine()
        
        value = engine.get("nonexistent")
        
        assert value is None
    
    def test_get_with_default(self):
        """Test getting with default value."""
        engine = ConfigurationEngine()
        
        value = engine.get("nonexistent", default="fallback")
        
        assert value == "fallback"
    
    def test_get_typed(self):
        """Test getting typed value."""
        engine = ConfigurationEngine()
        
        engine.set("app.port", 8080, source="env")
        
        typed = engine.get_typed("app.port")
        
        assert typed is not None
        assert typed.value == 8080
        assert typed.value_type == ConfigType.INTEGER
    
    def test_get_typed_nonexistent(self):
        """Test getting typed nonexistent value."""
        engine = ConfigurationEngine()
        
        typed = engine.get_typed("nonexistent")
        
        assert typed is None
    
    def test_has(self):
        """Test checking key existence."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        
        assert engine.has("app.name") is True
        assert engine.has("nonexistent") is False
    
    def test_delete(self):
        """Test deleting key."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        
        result = engine.delete("app.name")
        
        assert result is True
        assert engine.has("app.name") is False
    
    def test_delete_nonexistent(self):
        """Test deleting nonexistent key."""
        engine = ConfigurationEngine()
        
        result = engine.delete("nonexistent")
        
        assert result is False
    
    def test_get_all(self):
        """Test getting all configuration."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        engine.set("app.port", 8080)
        engine.set("db.password", "secret", is_secret=True)
        
        all_config = engine.get_all(mask_secrets=True)
        
        assert len(all_config) == 3
        assert all_config["db.password"]["value"] == "***REDACTED***"
    
    def test_get_all_unmasked(self):
        """Test getting all configuration unmasked."""
        engine = ConfigurationEngine()
        
        engine.set("db.password", "secret123", is_secret=True)
        
        all_config = engine.get_all(mask_secrets=False)
        
        assert all_config["db.password"]["value"] == "secret123"
    
    def test_get_keys(self):
        """Test getting keys."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        engine.set("app.port", 8080)
        engine.set("db.host", "localhost")
        
        keys = engine.get_keys()
        
        assert len(keys) == 3
        assert "app.name" in keys
    
    def test_get_keys_with_prefix(self):
        """Test getting keys with prefix."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        engine.set("app.port", 8080)
        engine.set("db.host", "localhost")
        
        keys = engine.get_keys(prefix="app.")
        
        assert len(keys) == 2
        assert "db.host" not in keys
    
    def test_load_from_dict(self):
        """Test loading from dictionary."""
        engine = ConfigurationEngine()
        
        data = {
            "app.name": "MyApp",
            "app.port": 8080,
            "app.enabled": True,
        }
        
        count = engine.load_from_dict(data)
        
        assert count == 3
        assert engine.get("app.name") == "MyApp"
    
    def test_load_from_env(self):
        """Test loading from environment."""
        engine = ConfigurationEngine()
        
        # Set env vars
        os.environ["TEST_APP_NAME"] = "TestApp"
        os.environ["TEST_APP_PORT"] = "9090"
        
        count = engine.load_from_env(prefix="TEST_")
        
        assert count >= 2
        assert engine.get("app_name") is not None
    
    def test_load_from_env_with_mapping(self):
        """Test loading from environment with mapping."""
        engine = ConfigurationEngine()
        
        os.environ["MY_PORT"] = "8080"
        
        mapping = {"server.port": "MY_PORT"}
        
        count = engine.load_from_env(mapping=mapping)
        
        assert count >= 1
        assert engine.get("server.port") == "8080"
    
    def test_define_schema(self):
        """Test defining schema."""
        engine = ConfigurationEngine()
        
        engine.define_schema(
            "app.port",
            ConfigType.INTEGER,
            required=True,
            default=8080,
            min_value=1,
            max_value=65535,
        )
        
        # Should set default
        assert engine.get("app.port") == 8080
    
    def test_schema_validation_type_mismatch(self):
        """Test schema validation with type mismatch."""
        engine = ConfigurationEngine()
        
        engine.define_schema("app.port", ConfigType.INTEGER)
        
        result = engine.set("app.port", "not_a_number")
        
        assert result is False
    
    def test_schema_validation_min_value(self):
        """Test schema validation with min value."""
        engine = ConfigurationEngine()
        
        engine.define_schema("app.port", ConfigType.INTEGER, min_value=1)
        
        result = engine.set("app.port", 0)
        
        assert result is False
    
    def test_schema_validation_max_value(self):
        """Test schema validation with max value."""
        engine = ConfigurationEngine()
        
        engine.define_schema("app.port", ConfigType.INTEGER, max_value=100)
        
        result = engine.set("app.port", 200)
        
        assert result is False
    
    def test_schema_validation_min_length(self):
        """Test schema validation with min length."""
        engine = ConfigurationEngine()
        
        engine.define_schema("app.name", ConfigType.STRING, min_length=3)
        
        result = engine.set("app.name", "AB")
        
        assert result is False
    
    def test_schema_validation_max_length(self):
        """Test schema validation with max length."""
        engine = ConfigurationEngine()
        
        engine.define_schema("app.name", ConfigType.STRING, max_length=5)
        
        result = engine.set("app.name", "VeryLongName")
        
        assert result is False
    
    def test_schema_validation_allowed_values(self):
        """Test schema validation with allowed values."""
        engine = ConfigurationEngine()
        
        engine.define_schema(
            "app.env",
            ConfigType.STRING,
            allowed_values=["dev", "staging", "prod"],
        )
        
        result = engine.set("app.env", "invalid")
        
        assert result is False
    
    def test_schema_validation_success(self):
        """Test schema validation with valid value."""
        engine = ConfigurationEngine()
        
        engine.define_schema(
            "app.port",
            ConfigType.INTEGER,
            min_value=1,
            max_value=65535,
        )
        
        result = engine.set("app.port", 8080)
        
        assert result is True
    
    def test_add_listener(self):
        """Test adding change listener."""
        engine = ConfigurationEngine()
        
        calls = []
        
        def listener(key, change):
            calls.append((key, change))
        
        engine.add_listener(listener)
        
        engine.set("app.name", "MyApp")
        
        assert len(calls) == 1
        assert calls[0][0] == "app.name"
    
    def test_remove_listener(self):
        """Test removing change listener."""
        engine = ConfigurationEngine()
        
        calls = []
        
        def listener(key, change):
            calls.append((key, change))
        
        engine.add_listener(listener)
        engine.remove_listener(listener)
        
        engine.set("app.name", "MyApp")
        
        assert len(calls) == 0
    
    def test_get_history(self):
        """Test getting change history."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        engine.set("app.name", "NewApp")
        engine.set("app.name", "FinalApp")
        
        history = engine.get_history("app.name", limit=2)
        
        assert len(history) == 2
    
    def test_get_history_default_limit(self):
        """Test getting history with default limit."""
        engine = ConfigurationEngine()
        
        for i in range(15):
            engine.set("app.counter", i)
        
        history = engine.get_history("app.counter")
        
        assert len(history) == 10
    
    def test_get_version(self):
        """Test getting configuration version."""
        engine = ConfigurationEngine()
        
        assert engine.get_version() == 0
        
        engine.set("app.name", "MyApp")
        
        assert engine.get_version() == 1
        
        engine.set("app.port", 8080)
        
        assert engine.get_version() == 2
    
    def test_delete_updates_version(self):
        """Test that delete updates version."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        
        v1 = engine.get_version()
        
        engine.delete("app.name")
        
        assert engine.get_version() > v1
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        engine.set("app.port", 8080)
        engine.get("app.name")
        
        stats = engine.get_statistics()
        
        assert stats["total_keys"] == 2
        assert stats["total_sets"] == 2
        assert stats["total_gets"] == 1
    
    def test_statistics_by_key(self):
        """Test statistics by key."""
        engine = ConfigurationEngine()
        
        for _ in range(5):
            engine.set("app.name", f"value_{_}")
        
        stats = engine.get_statistics()
        
        assert stats["by_key"]["app.name"] == 5
    
    def test_clear(self):
        """Test clearing all configuration."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        engine.set("app.port", 8080)
        
        count = engine.clear()
        
        assert count == 2
        assert engine.get_keys() == []
    
    def test_clear_history_specific_key(self):
        """Test clearing history for specific key."""
        engine = ConfigurationEngine()
        
        for i in range(10):
            engine.set("app.counter", i)
        
        count = engine.clear_history("app.counter")
        
        assert count == 10
        
        history = engine.get_history("app.counter", limit=100)
        
        assert len(history) == 0
    
    def test_clear_history_all(self):
        """Test clearing all history."""
        engine = ConfigurationEngine()
        
        engine.set("app.a", 1)
        engine.set("app.b", 2)
        
        count = engine.clear_history()
        
        assert count > 0
    
    def test_clear_history_empty(self):
        """Test clearing empty history."""
        engine = ConfigurationEngine()
        
        count = engine.clear_history()
        
        assert count == 0
    
    def test_clear_history_nonexistent_key(self):
        """Test clearing history for nonexistent key."""
        engine = ConfigurationEngine()
        
        count = engine.clear_history("nonexistent")
        
        assert count == 0
    
    def test_export_json(self):
        """Test exporting to JSON."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        engine.set("app.port", 8080)
        
        json_str = engine.export_json()
        
        assert "app.name" in json_str
        assert "MyApp" in json_str
    
    def test_import_json(self):
        """Test importing from JSON."""
        engine = ConfigurationEngine()
        
        json_str = '{"app.name": "Imported", "app.port": 9090}'
        
        count = engine.import_json(json_str)
        
        assert count == 2
        assert engine.get("app.name") == "Imported"
    
    def test_import_json_invalid(self):
        """Test importing invalid JSON."""
        engine = ConfigurationEngine()
        
        json_str = 'not valid json'
        
        count = engine.import_json(json_str)
        
        assert count == 0
    
    def test_config_type_enum_values(self):
        """Test config type enum values."""
        assert ConfigType.STRING.value == "string"
        assert ConfigType.INTEGER.value == "integer"
        assert ConfigType.FLOAT.value == "float"
        assert ConfigType.BOOLEAN.value == "boolean"
        assert ConfigType.LIST.value == "list"
        assert ConfigType.DICT.value == "dict"
    
    def test_change_type_enum_values(self):
        """Test change type enum values."""
        assert ChangeType.ADDED.value == "added"
        assert ChangeType.UPDATED.value == "updated"
        assert ChangeType.DELETED.value == "deleted"
    
    def test_set_updates_value_timestamp(self):
        """Test that set updates value timestamp."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        
        typed1 = engine.get_typed("app.name")
        
        import time
        time.sleep(0.01)
        
        engine.set("app.name", "NewApp")
        
        typed2 = engine.get_typed("app.name")
        
        assert typed2.updated_at > typed1.updated_at
        assert typed2.version == 2
    
    def test_value_version_increments(self):
        """Test that value version increments on update."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        engine.set("app.name", "NewApp")
        engine.set("app.name", "FinalApp")
        
        typed = engine.get_typed("app.name")
        
        assert typed.version == 3
    
    def test_schema_default_applied(self):
        """Test that schema default is applied."""
        engine = ConfigurationEngine()
        
        engine.define_schema("app.timeout", ConfigType.INTEGER, default=30)
        
        value = engine.get("app.timeout")
        
        assert value == 30
    
    def test_set_without_schema_infers_type(self):
        """Test that set infers type without schema."""
        engine = ConfigurationEngine()
        
        engine.set("app.string", "text")
        engine.set("app.int", 42)
        engine.set("app.float", 3.14)
        engine.set("app.bool", True)
        engine.set("app.list", [1, 2, 3])
        engine.set("app.dict", {"a": 1})
        
        assert engine.get_typed("app.string").value_type == ConfigType.STRING
        assert engine.get_typed("app.int").value_type == ConfigType.INTEGER
        assert engine.get_typed("app.float").value_type == ConfigType.FLOAT
        assert engine.get_typed("app.bool").value_type == ConfigType.BOOLEAN
        assert engine.get_typed("app.list").value_type == ConfigType.LIST
        assert engine.get_typed("app.dict").value_type == ConfigType.DICT
    
    def test_boolean_not_treated_as_integer(self):
        """Test that boolean is not treated as integer."""
        engine = ConfigurationEngine()
        
        engine.define_schema("app.flag", ConfigType.INTEGER)
        
        # Boolean should fail integer validation
        result = engine.set("app.flag", True)
        
        assert result is False
    
    def test_get_keys_sorted(self):
        """Test that get_keys returns sorted list."""
        engine = ConfigurationEngine()
        
        engine.set("zebra", 1)
        engine.set("alpha", 2)
        engine.set("middle", 3)
        
        keys = engine.get_keys()
        
        assert keys == sorted(keys)
    
    def test_statistics_validation_errors(self):
        """Test that statistics track validation errors."""
        engine = ConfigurationEngine()
        
        engine.define_schema("app.port", ConfigType.INTEGER)
        
        engine.set("app.port", "not_a_number")
        
        stats = engine.get_statistics()
        
        assert stats["validation_errors"] == 1
    
    def test_statistics_secret_count(self):
        """Test that statistics track secret count."""
        engine = ConfigurationEngine()
        
        engine.set("public.key", "value")
        engine.set("secret.key", "value", is_secret=True)
        engine.set("another.secret", "value", is_secret=True)
        
        stats = engine.get_statistics()
        
        assert stats["secret_count"] == 2
    
    def test_statistics_total_schema(self):
        """Test that statistics track schema count."""
        engine = ConfigurationEngine()
        
        engine.define_schema("app.a", ConfigType.STRING)
        engine.define_schema("app.b", ConfigType.INTEGER)
        engine.define_schema("app.c", ConfigType.BOOLEAN)
        
        stats = engine.get_statistics()
        
        assert stats["total_schema"] == 3
    
    def test_listener_exception_handled(self):
        """Test that listener exceptions are handled."""
        engine = ConfigurationEngine()
        
        def failing_listener(key, change):
            raise RuntimeError("Listener error")
        
        def working_listener(key, change):
            working_listener.called = True
        
        working_listener.called = False
        
        engine.add_listener(failing_listener)
        engine.add_listener(working_listener)
        
        # Should not raise
        engine.set("app.name", "MyApp")
        
        # Working listener should still be called
        assert working_listener.called is True
    
    def test_change_history_limited_to_100(self):
        """Test that change history is limited to 100 entries."""
        engine = ConfigurationEngine()
        
        for i in range(150):
            engine.set("app.counter", i)
        
        history = engine._history["app.counter"]
        
        assert len(history) == 100
    
    def test_key_unique(self):
        """Test that keys are unique (last write wins)."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "First")
        engine.set("app.name", "Second")
        
        assert engine.get("app.name") == "Second"
    
    def test_get_all_empty(self):
        """Test getting all when empty."""
        engine = ConfigurationEngine()
        
        all_config = engine.get_all()
        
        assert all_config == {}
    
    def test_get_keys_empty(self):
        """Test getting keys when empty."""
        engine = ConfigurationEngine()
        
        keys = engine.get_keys()
        
        assert keys == []
    
    def test_change_id_unique(self):
        """Test that change IDs are unique."""
        engine = ConfigurationEngine()
        
        ids = set()
        for i in range(50):
            engine.set(f"app.key_{i}", i)
        
        for key in engine._history:
            for change in engine._history[key]:
                ids.add(change.change_id)
        
        assert len(ids) == 50
    
    def test_load_from_dict_partial_failure(self):
        """Test loading from dict with partial validation failures."""
        engine = ConfigurationEngine()
        
        engine.define_schema("app.port", ConfigType.INTEGER)
        
        data = {
            "app.name": "MyApp",  # Valid
            "app.port": "invalid",  # Invalid
            "app.enabled": True,  # Valid
        }
        
        count = engine.load_from_dict(data)
        
        # Only valid entries should be loaded
        assert count == 2
        assert engine.has("app.name")
        assert not engine.has("app.port")
        assert engine.has("app.enabled")
    
    def test_set_description_from_schema(self):
        """Test that description can come from schema."""
        engine = ConfigurationEngine()
        
        engine.define_schema(
            "app.name",
            ConfigType.STRING,
            description="The application name",
        )
        
        engine.set("app.name", "MyApp")
        
        typed = engine.get_typed("app.name")
        
        assert typed.description == "The application name"
    
    def test_change_type_correct(self):
        """Test that change type is correct for add/update/delete."""
        engine = ConfigurationEngine()
        
        changes = []
        
        def listener(key, change):
            changes.append((key, change.change_type))
        
        engine.add_listener(listener)
        
        # Add
        engine.set("app.name", "MyApp")
        # Update
        engine.set("app.name", "NewApp")
        # Delete
        engine.delete("app.name")
        
        assert changes[0][1] == ChangeType.ADDED
        assert changes[1][1] == ChangeType.UPDATED
        assert changes[2][1] == ChangeType.DELETED
    
    def test_get_version_initial(self):
        """Test that initial version is 0."""
        engine = ConfigurationEngine()
        
        assert engine.get_version() == 0
    
    def test_clear_updates_version(self):
        """Test that clear updates version."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        
        v1 = engine.get_version()
        
        engine.clear()
        
        assert engine.get_version() > v1
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = ConfigurationEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_gets"] == 0
        assert stats["total_sets"] == 0
        assert stats["total_deletes"] == 0
        assert stats["validation_errors"] == 0
        assert stats["total_keys"] == 0
        assert stats["version"] == 0
    
    def test_multiple_keys_independent(self):
        """Test that multiple keys are independent."""
        engine = ConfigurationEngine()
        
        engine.set("app.a", 1)
        engine.set("app.b", 2)
        engine.set("app.c", 3)
        
        assert engine.get("app.a") == 1
        assert engine.get("app.b") == 2
        assert engine.get("app.c") == 3
        
        engine.delete("app.b")
        
        assert engine.get("app.a") == 1
        assert engine.get("app.b") is None
        assert engine.get("app.c") == 3
    
    def test_schema_without_default(self):
        """Test schema without default doesn't create value."""
        engine = ConfigurationEngine()
        
        engine.define_schema("app.timeout", ConfigType.INTEGER, required=True)
        
        value = engine.get("app.timeout")
        
        assert value is None
    
    def test_change_timestamp_set(self):
        """Test that change timestamp is set."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        
        history = engine.get_history("app.name")
        
        assert len(history) == 1
        assert history[0].timestamp is not None
    
    def test_value_source_default(self):
        """Test that value source defaults to 'default'."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        
        typed = engine.get_typed("app.name")
        
        assert typed.source == "api"  # Default source for set()
    
    def test_load_from_dict_source(self):
        """Test that load_from_dict sets correct source."""
        engine = ConfigurationEngine()
        
        engine.load_from_dict({"app.name": "MyApp"}, source="file")
        
        typed = engine.get_typed("app.name")
        
        assert typed.source == "file"
    
    def test_nested_dict_value(self):
        """Test setting nested dict value."""
        engine = ConfigurationEngine()
        
        nested = {
            "level1": {
                "level2": {
                    "level3": "deep_value"
                }
            }
        }
        
        engine.set("app.config", nested)
        
        value = engine.get("app.config")
        
        assert value["level1"]["level2"]["level3"] == "deep_value"
    
    def test_list_value_preserved(self):
        """Test that list value is preserved."""
        engine = ConfigurationEngine()
        
        original = [1, 2, 3, 4, 5]
        
        engine.set("app.list", original)
        
        # Modify original
        original.append(6)
        
        # Stored value should be unchanged
        assert engine.get("app.list") == [1, 2, 3, 4, 5]
    
    def test_get_keys_prefix_no_match(self):
        """Test get_keys with prefix that has no matches."""
        engine = ConfigurationEngine()
        
        engine.set("app.name", "MyApp")
        engine.set("db.host", "localhost")
        
        keys = engine.get_keys(prefix="cache.")
        
        assert keys == []
    
    def test_history_empty_for_nonexistent_key(self):
        """Test getting history for nonexistent key."""
        engine = ConfigurationEngine()
        
        history = engine.get_history("nonexistent")
        
        assert history == []
    
    def test_remove_nonexistent_listener(self):
        """Test removing nonexistent listener."""
        engine = ConfigurationEngine()
        
        def listener(key, change):
            pass
        
        result = engine.remove_listener(listener)
        
        assert result is False
    
    def test_schema_min_max_float(self):
        """Test schema with float min/max."""
        engine = ConfigurationEngine()
        
        engine.define_schema(
            "app.ratio",
            ConfigType.FLOAT,
            min_value=0.0,
            max_value=1.0,
        )
        
        assert engine.set("app.ratio", 0.5) is True
        assert engine.set("app.ratio", 1.5) is False
    
    def test_export_json_masks_secrets_by_default(self):
        """Test that export_json masks secrets by default."""
        engine = ConfigurationEngine()
        
        engine.set("public.key", "public_value")
        engine.set("secret.key", "secret_value", is_secret=True)
        
        json_str = engine.export_json()
        
        assert "public_value" in json_str
        assert "secret_value" not in json_str
        assert "***REDACTED***" in json_str
    
    def test_import_json_updates_version(self):
        """Test that import_json updates version."""
        engine = ConfigurationEngine()
        
        v1 = engine.get_version()
        
        engine.import_json('{"app.name": "Imported"}')
        
        assert engine.get_version() > v1
    
    def test_delete_nonexistent_key_stats(self):
        """Test that deleting nonexistent key doesn't update stats."""
        engine = ConfigurationEngine()
        
        engine.delete("nonexistent")
        
        stats = engine.get_statistics()
        
        assert stats["total_deletes"] == 0
