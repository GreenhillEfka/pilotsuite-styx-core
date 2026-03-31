"""Tests for Configuration Engine — Slice 42."""
import pytest
from copilot_core.config.engine import (
    ConfigurationEngine,
    ConfigType,
    ConfigSource,
    ConfigSchema,
    ConfigEntry,
    ConfigChange,
    create_configuration_engine,
)
from datetime import datetime, timezone, timedelta
import os


class TestConfigurationEngine:
    """Test configuration engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_configuration_engine()
        assert engine is not None
    
    def test_register_schema_string(self):
        """Test registering string schema."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="app.name",
            config_type="string",
            required=True,
            default="MyApp",
            description="Application name",
        )
        
        # Should have default value set
        value = engine.get_config("app.name")
        assert value == "MyApp"
    
    def test_register_schema_number(self):
        """Test registering number schema."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="server.port",
            config_type="number",
            required=True,
            default=8080,
            min_value=1,
            max_value=65535,
        )
        
        value = engine.get_config("server.port")
        assert value == 8080
    
    def test_register_schema_boolean(self):
        """Test registering boolean schema."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="feature.enabled",
            config_type="boolean",
            default=False,
        )
        
        value = engine.get_config("feature.enabled")
        assert value is False
    
    def test_register_schema_object(self):
        """Test registering object schema."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="database.config",
            config_type="object",
            default={"host": "localhost", "port": 5432},
        )
        
        value = engine.get_config("database.config")
        assert value["host"] == "localhost"
    
    def test_register_schema_array(self):
        """Test registering array schema."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="allowed_origins",
            config_type="array",
            default=["http://localhost:3000"],
        )
        
        value = engine.get_config("allowed_origins")
        assert len(value) == 1
    
    def test_register_schema_with_enum(self):
        """Test registering schema with enum values."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="log.level",
            config_type="string",
            enum_values=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
        )
        
        value = engine.get_config("log.level")
        assert value == "INFO"
    
    def test_register_schema_with_pattern(self):
        """Test registering schema with regex pattern."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="email.from",
            config_type="string",
            pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
            default="noreply@example.com",
        )
        
        value = engine.get_config("email.from")
        assert "@" in value
    
    def test_set_config_string(self):
        """Test setting string config."""
        engine = ConfigurationEngine()
        
        result = engine.set_config("app.name", "TestApp")
        
        assert result is True
        assert engine.get_config("app.name") == "TestApp"
    
    def test_set_config_number(self):
        """Test setting number config."""
        engine = ConfigurationEngine()
        
        engine.set_config("server.port", 3000)
        
        assert engine.get_config("server.port") == 3000
    
    def test_set_config_boolean(self):
        """Test setting boolean config."""
        engine = ConfigurationEngine()
        
        engine.set_config("feature.enabled", True)
        
        assert engine.get_config("feature.enabled") is True
    
    def test_set_config_object(self):
        """Test setting object config."""
        engine = ConfigurationEngine()
        
        engine.set_config("database.config", {"host": "db.example.com", "port": 5432})
        
        value = engine.get_config("database.config")
        assert value["host"] == "db.example.com"
    
    def test_set_config_array(self):
        """Test setting array config."""
        engine = ConfigurationEngine()
        
        engine.set_config("allowed_origins", ["http://a.com", "http://b.com"])
        
        value = engine.get_config("allowed_origins")
        assert len(value) == 2
    
    def test_set_config_validation_pass(self):
        """Test setting config passes validation."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="server.port",
            config_type="number",
            min_value=1,
            max_value=65535,
        )
        
        result = engine.set_config("server.port", 8080)
        
        assert result is True
    
    def test_set_config_validation_fail_type(self):
        """Test setting config fails type validation."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="server.port",
            config_type="number",
        )
        
        result = engine.set_config("server.port", "not_a_number")
        
        assert result is False
    
    def test_set_config_validation_fail_min(self):
        """Test setting config fails min validation."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="server.port",
            config_type="number",
            min_value=1,
        )
        
        result = engine.set_config("server.port", 0)
        
        assert result is False
    
    def test_set_config_validation_fail_max(self):
        """Test setting config fails max validation."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="server.port",
            config_type="number",
            max_value=65535,
        )
        
        result = engine.set_config("server.port", 70000)
        
        assert result is False
    
    def test_set_config_validation_fail_enum(self):
        """Test setting config fails enum validation."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="log.level",
            config_type="string",
            enum_values=["DEBUG", "INFO", "WARNING", "ERROR"],
        )
        
        result = engine.set_config("log.level", "INVALID")
        
        assert result is False
    
    def test_set_config_validation_fail_pattern(self):
        """Test setting config fails pattern validation."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="email.from",
            config_type="string",
            pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
        )
        
        result = engine.set_config("email.from", "not_an_email")
        
        assert result is False
    
    def test_get_config_default(self):
        """Test getting config with default."""
        engine = ConfigurationEngine()
        
        value = engine.get_config("nonexistent", default="default_value")
        
        assert value == "default_value"
    
    def test_get_config_schema_default(self):
        """Test getting config from schema default."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="app.name",
            config_type="string",
            default="DefaultApp",
        )
        
        value = engine.get_config("app.name")
        
        assert value == "DefaultApp"
    
    def test_get_config_entry(self):
        """Test getting config entry with metadata."""
        engine = ConfigurationEngine()
        
        engine.set_config("app.name", "TestApp", updated_by="admin")
        
        entry = engine.get_config_entry("app.name")
        
        assert entry is not None
        assert entry["key"] == "app.name"
        assert entry["value"] == "TestApp"
        assert entry["updated_by"] == "admin"
    
    def test_get_config_entry_not_found(self):
        """Test getting nonexistent config entry."""
        engine = ConfigurationEngine()
        
        entry = engine.get_config_entry("nonexistent")
        
        assert entry is None
    
    def test_get_all_configs(self):
        """Test getting all configs."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "value1")
        engine.set_config("key2", "value2")
        engine.set_config("key3", "value3")
        
        configs = engine.get_all_configs()
        
        assert len(configs) == 3
        assert configs["key1"] == "value1"
    
    def test_delete_config(self):
        """Test deleting config."""
        engine = ConfigurationEngine()
        
        engine.set_config("temp_key", "temp_value")
        
        result = engine.delete_config("temp_key")
        
        assert result is True
        assert engine.get_config("temp_key") is None
    
    def test_delete_nonexistent_config(self):
        """Test deleting nonexistent config."""
        engine = ConfigurationEngine()
        
        result = engine.delete_config("nonexistent")
        
        assert result is False
    
    def test_load_from_dict(self):
        """Test loading config from dict."""
        engine = ConfigurationEngine()
        
        data = {
            "app.name": "LoadedApp",
            "server.port": 3000,
            "feature.enabled": True,
        }
        
        count = engine.load_from_dict(data)
        
        assert count == 3
        assert engine.get_config("app.name") == "LoadedApp"
        assert engine.get_config("server.port") == 3000
    
    def test_load_from_env(self):
        """Test loading config from environment."""
        engine = ConfigurationEngine()
        
        # Set env vars
        os.environ["TEST_STRING"] = "hello"
        os.environ["TEST_NUMBER"] = "42"
        os.environ["TEST_BOOL"] = "true"
        
        count = engine.load_from_env(prefix="TEST_")
        
        assert count >= 3
        assert engine.get_config("STRING") == "hello"
        assert engine.get_config("NUMBER") == 42
        assert engine.get_config("BOOL") is True
        
        # Cleanup
        del os.environ["TEST_STRING"]
        del os.environ["TEST_NUMBER"]
        del os.environ["TEST_BOOL"]
    
    def test_parse_env_value_boolean_true(self):
        """Test parsing boolean true from env."""
        engine = ConfigurationEngine()
        
        assert engine._parse_env_value("true") is True
        assert engine._parse_env_value("True") is True
        assert engine._parse_env_value("TRUE") is True
        assert engine._parse_env_value("yes") is True
        assert engine._parse_env_value("1") is True
    
    def test_parse_env_value_boolean_false(self):
        """Test parsing boolean false from env."""
        engine = ConfigurationEngine()
        
        assert engine._parse_env_value("false") is False
        assert engine._parse_env_value("False") is False
        assert engine._parse_env_value("no") is False
        assert engine._parse_env_value("0") is False
    
    def test_parse_env_value_integer(self):
        """Test parsing integer from env."""
        engine = ConfigurationEngine()
        
        assert engine._parse_env_value("42") == 42
        assert engine._parse_env_value("-10") == -10
    
    def test_parse_env_value_float(self):
        """Test parsing float from env."""
        engine = ConfigurationEngine()
        
        assert engine._parse_env_value("3.14") == 3.14
        assert engine._parse_env_value("0.5") == 0.5
    
    def test_parse_env_value_json(self):
        """Test parsing JSON from env."""
        engine = ConfigurationEngine()
        
        value = engine._parse_env_value('{"key": "value"}')
        assert value == {"key": "value"}
        
        value = engine._parse_env_value('[1, 2, 3]')
        assert value == [1, 2, 3]
    
    def test_parse_env_value_string(self):
        """Test parsing string from env."""
        engine = ConfigurationEngine()
        
        assert engine._parse_env_value("plain_text") == "plain_text"
    
    def test_export_to_dict(self):
        """Test exporting config to dict."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "value1")
        engine.set_config("key2", 42)
        
        exported = engine.export_to_dict()
        
        assert exported["key1"] == "value1"
        assert exported["key2"] == 42
    
    def test_export_to_json(self):
        """Test exporting config to JSON."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "value1")
        engine.set_config("key2", 42)
        
        exported = engine.export_to_json()
        
        assert "key1" in exported
        assert "value1" in exported
    
    def test_register_change_callback(self):
        """Test registering change callback."""
        engine = ConfigurationEngine()
        
        changes = []
        
        def callback(key, value):
            changes.append((key, value))
        
        engine.register_change_callback("app.name", callback)
        
        engine.set_config("app.name", "NewName")
        
        assert len(changes) == 1
        assert changes[0] == ("app.name", "NewName")
    
    def test_register_wildcard_callback(self):
        """Test registering wildcard callback."""
        engine = ConfigurationEngine()
        
        changes = []
        
        def callback(key, value):
            changes.append((key, value))
        
        engine.register_change_callback("*", callback)
        
        engine.set_config("key1", "value1")
        engine.set_config("key2", "value2")
        
        assert len(changes) == 2
    
    def test_add_to_group(self):
        """Test adding keys to group."""
        engine = ConfigurationEngine()
        
        engine.set_config("db.host", "localhost")
        engine.set_config("db.port", 5432)
        engine.set_config("db.name", "mydb")
        
        engine.add_to_group("database", ["db.host", "db.port", "db.name"])
        
        group = engine.get_group("database")
        
        assert len(group) == 3
        assert group["db.host"] == "localhost"
    
    def test_get_group(self):
        """Test getting configuration group."""
        engine = ConfigurationEngine()
        
        engine.set_config("app.name", "TestApp")
        engine.set_config("app.version", "1.0.0")
        engine.set_config("server.port", 8080)
        
        engine.add_to_group("application", ["app.name", "app.version"])
        
        group = engine.get_group("application")
        
        assert len(group) == 2
        assert "server.port" not in group
    
    def test_get_nonexistent_group(self):
        """Test getting nonexistent group."""
        engine = ConfigurationEngine()
        
        group = engine.get_group("nonexistent")
        
        assert group == {}
    
    def test_get_change_log(self):
        """Test getting change log."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "value1")
        engine.set_config("key1", "value2")
        engine.set_config("key2", "value3")
        
        changes = engine.get_change_log()
        
        assert len(changes) >= 3
    
    def test_get_change_log_filtered_by_key(self):
        """Test getting change log filtered by key."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "value1")
        engine.set_config("key1", "value2")
        engine.set_config("key2", "value3")
        
        changes = engine.get_change_log(key="key1")
        
        assert len(changes) == 2
        assert all(c["key"] == "key1" for c in changes)
    
    def test_get_change_log_limit(self):
        """Test getting change log with limit."""
        engine = ConfigurationEngine()
        
        for i in range(50):
            engine.set_config(f"key_{i}", f"value_{i}")
        
        changes = engine.get_change_log(limit=10)
        
        assert len(changes) == 10
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = ConfigurationEngine()
        
        engine.register_schema("key1", "string", default="default")
        engine.set_config("key2", 42)
        engine.set_config("key3", True)
        
        stats = engine.get_statistics()
        
        assert stats["total_configs"] >= 3
        assert stats["schemas_registered"] >= 1
        assert "string" in stats["by_type"]
        assert "number" in stats["by_type"]
    
    def test_validate_all_pass(self):
        """Test validation passes."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="required_key",
            config_type="string",
            required=True,
            default="default",
        )
        
        result = engine.validate_all()
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
    
    def test_validate_all_missing_required(self):
        """Test validation fails for missing required."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="required_key",
            config_type="string",
            required=True,
        )
        
        result = engine.validate_all()
        
        assert result["valid"] is False
        assert len(result["errors"]) >= 1
    
    def test_validate_all_invalid_value(self):
        """Test validation fails for invalid value."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="port",
            config_type="number",
            max_value=100,
        )
        
        engine._set_config("port", 200, ConfigSource.OVERRIDE, "test", "Test")
        
        result = engine.validate_all()
        
        assert result["valid"] is False
    
    def test_reset_to_defaults(self):
        """Test resetting to defaults."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="app.name",
            config_type="string",
            default="DefaultApp",
        )
        
        engine.set_config("app.name", "CustomApp")
        
        count = engine.reset_to_defaults()
        
        assert count >= 1
        assert engine.get_config("app.name") == "DefaultApp"
    
    def test_clear_all(self):
        """Test clearing all configs."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "value1")
        engine.set_config("key2", "value2")
        engine.set_config("key3", "value3")
        
        count = engine.clear_all()
        
        assert count == 3
        assert engine.get_config("key1") is None
    
    def test_change_log_trimmed_to_max(self):
        """Test that change log is trimmed to max."""
        engine = ConfigurationEngine()
        engine._max_log_size = 100
        
        for i in range(200):
            engine.set_config(f"key_{i}", f"value_{i}")
        
        assert len(engine._change_log) <= 100
    
    def test_config_entry_to_dict(self):
        """Test config entry serialization."""
        entry = ConfigEntry(
            key="test_key",
            value="test_value",
            config_type=ConfigType.STRING,
            source=ConfigSource.OVERRIDE,
            updated_by="admin",
        )
        
        d = entry.to_dict()
        
        assert d["key"] == "test_key"
        assert d["value"] == "test_value"
        assert d["type"] == "string"
        assert d["source"] == "override"
    
    def test_config_schema_to_dict(self):
        """Test config schema serialization."""
        schema = ConfigSchema(
            key="test_key",
            config_type=ConfigType.NUMBER,
            required=True,
            default=42,
            min_value=0,
            max_value=100,
            description="Test schema",
        )
        
        d = schema.to_dict()
        
        assert d["key"] == "test_key"
        assert d["type"] == "number"
        assert d["required"] is True
        assert d["min_value"] == 0
    
    def test_config_change_to_dict(self):
        """Test config change serialization."""
        change = ConfigChange(
            change_id="cfg_test",
            key="test_key",
            old_value="old",
            new_value="new",
            changed_by="admin",
            changed_at="2026-03-31T12:00:00Z",
            reason="Testing",
            source=ConfigSource.OVERRIDE,
        )
        
        d = change.to_dict()
        
        assert d["change_id"] == "cfg_test"
        assert d["key"] == "test_key"
        assert d["old_value"] == "old"
        assert d["new_value"] == "new"
    
    def test_config_type_enum_values(self):
        """Test config type enum values."""
        assert ConfigType.STRING.value == "string"
        assert ConfigType.NUMBER.value == "number"
        assert ConfigType.BOOLEAN.value == "boolean"
        assert ConfigType.OBJECT.value == "object"
        assert ConfigType.ARRAY.value == "array"
    
    def test_config_source_enum_values(self):
        """Test config source enum values."""
        assert ConfigSource.DEFAULT.value == "default"
        assert ConfigSource.FILE.value == "file"
        assert ConfigSource.ENVIRONMENT.value == "environment"
        assert ConfigSource.REMOTE.value == "remote"
        assert ConfigSource.OVERRIDE.value == "override"
    
    def test_statistics_by_source(self):
        """Test statistics breakdown by source."""
        engine = ConfigurationEngine()
        
        engine.register_schema("key1", "string", default="default")  # DEFAULT
        engine.set_config("key2", "value2")  # OVERRIDE
        
        stats = engine.get_statistics()
        
        assert "default" in stats["by_source"]
        assert "override" in stats["by_source"]
    
    def test_change_log_sorted_newest_first(self):
        """Test that change log is sorted newest first."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "v1")
        
        import time
        time.sleep(0.01)
        
        engine.set_config("key1", "v2")
        engine.set_config("key1", "v3")
        
        changes = engine.get_change_log(key="key1")
        
        # Verify sorted (newest first)
        for i in range(len(changes) - 1):
            assert changes[i]["changed_at"] >= changes[i + 1]["changed_at"]
    
    def test_load_from_dict_with_source(self):
        """Test loading from dict with specific source."""
        engine = ConfigurationEngine()
        
        data = {"key1": "value1"}
        
        engine.load_from_dict(data, source=ConfigSource.REMOTE, loaded_by="remote_service")
        
        entry = engine.get_config_entry("key1")
        
        assert entry["source"] == "remote"
        assert entry["updated_by"] == "remote_service"
    
    def test_config_updated_at_tracked(self):
        """Test that updated_at is tracked."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "value1")
        
        entry = engine.get_config_entry("key1")
        
        assert "updated_at" in entry
        assert entry["updated_at"] is not None
    
    def test_config_updated_by_tracked(self):
        """Test that updated_by is tracked."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "value1", updated_by="test_user")
        
        entry = engine.get_config_entry("key1")
        
        assert entry["updated_by"] == "test_user"
    
    def test_multiple_callbacks_for_same_key(self):
        """Test multiple callbacks for same key."""
        engine = ConfigurationEngine()
        
        changes1 = []
        changes2 = []
        
        def callback1(key, value):
            changes1.append((key, value))
        
        def callback2(key, value):
            changes2.append((key, value))
        
        engine.register_change_callback("key1", callback1)
        engine.register_change_callback("key1", callback2)
        
        engine.set_config("key1", "value1")
        
        assert len(changes1) == 1
        assert len(changes2) == 1
    
    def test_callback_exception_handled(self):
        """Test that callback exceptions are handled."""
        engine = ConfigurationEngine()
        
        def failing_callback(key, value):
            raise Exception("Callback failed")
        
        def working_callback(key, value):
            pass
        
        engine.register_change_callback("key1", failing_callback)
        engine.register_change_callback("key1", working_callback)
        
        # Should not raise
        engine.set_config("key1", "value1")
    
    def test_statistics_total_changes(self):
        """Test that statistics track total changes."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "v1")
        engine.set_config("key1", "v2")
        engine.set_config("key1", "v3")
        
        stats = engine.get_statistics()
        
        assert stats["total_changes"] >= 3
    
    def test_validate_all_empty_engine(self):
        """Test validation with empty engine."""
        engine = ConfigurationEngine()
        
        result = engine.validate_all()
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
    
    def test_export_json_indent(self):
        """Test exporting JSON with custom indent."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "value1")
        
        exported = engine.export_to_json(indent=4)
        
        assert "    " in exported  # 4-space indent
    
    def test_load_from_env_no_prefix(self):
        """Test loading from env without prefix."""
        engine = ConfigurationEngine()
        
        os.environ["UNIQUE_TEST_KEY"] = "test_value"
        
        count = engine.load_from_env()
        
        # Should load all env vars
        assert count >= 1
        
        value = engine.get_config("UNIQUE_TEST_KEY")
        assert value == "test_value"
        
        # Cleanup
        del os.environ["UNIQUE_TEST_KEY"]
    
    def test_config_inferred_type_string(self):
        """Test type inference for string."""
        engine = ConfigurationEngine()
        
        config_type = engine._infer_type("hello")
        
        assert config_type == ConfigType.STRING
    
    def test_config_inferred_type_number_int(self):
        """Test type inference for int."""
        engine = ConfigurationEngine()
        
        config_type = engine._infer_type(42)
        
        assert config_type == ConfigType.NUMBER
    
    def test_config_inferred_type_number_float(self):
        """Test type inference for float."""
        engine = ConfigurationEngine()
        
        config_type = engine._infer_type(3.14)
        
        assert config_type == ConfigType.NUMBER
    
    def test_config_inferred_type_boolean(self):
        """Test type inference for boolean."""
        engine = ConfigurationEngine()
        
        config_type = engine._infer_type(True)
        
        assert config_type == ConfigType.BOOLEAN
    
    def test_config_inferred_type_object(self):
        """Test type inference for object."""
        engine = ConfigurationEngine()
        
        config_type = engine._infer_type({"key": "value"})
        
        assert config_type == ConfigType.OBJECT
    
    def test_config_inferred_type_array(self):
        """Test type inference for array."""
        engine = ConfigurationEngine()
        
        config_type = engine._infer_type([1, 2, 3])
        
        assert config_type == ConfigType.ARRAY
    
    def test_get_config_with_none_default(self):
        """Test getting config with None default."""
        engine = ConfigurationEngine()
        
        value = engine.get_config("nonexistent", default=None)
        
        assert value is None
    
    def test_set_config_overwrites_previous_value(self):
        """Test that set config overwrites previous value."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "value1")
        engine.set_config("key1", "value2")
        
        value = engine.get_config("key1")
        
        assert value == "value2"
    
    def test_change_log_includes_old_and_new_value(self):
        """Test that change log includes old and new values."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "old_value")
        engine.set_config("key1", "new_value")
        
        changes = engine.get_change_log(key="key1", limit=1)
        
        assert changes[0]["old_value"] == "old_value"
        assert changes[0]["new_value"] == "new_value"
    
    def test_change_log_includes_reason(self):
        """Test that change log includes reason."""
        engine = ConfigurationEngine()
        
        engine.set_config(
            "key1",
            "value1",
            updated_by="admin",
            reason="Configuration update",
        )
        
        changes = engine.get_change_log(key="key1", limit=1)
        
        assert changes[0]["reason"] == "Configuration update"
    
    def test_groups_can_overlap(self):
        """Test that keys can be in multiple groups."""
        engine = ConfigurationEngine()
        
        engine.set_config("shared_key", "value")
        
        engine.add_to_group("group1", ["shared_key"])
        engine.add_to_group("group2", ["shared_key"])
        
        group1 = engine.get_group("group1")
        group2 = engine.get_group("group2")
        
        assert "shared_key" in group1
        assert "shared_key" in group2
    
    def test_statistics_groups_defined(self):
        """Test that statistics include groups defined count."""
        engine = ConfigurationEngine()
        
        engine.add_to_group("group1", ["key1"])
        engine.add_to_group("group2", ["key2"])
        
        stats = engine.get_statistics()
        
        assert stats["groups_defined"] >= 2
    
    def test_clear_all_logs_changes(self):
        """Test that clear_all logs changes."""
        engine = ConfigurationEngine()
        
        engine.set_config("key1", "value1")
        engine.set_config("key2", "value2")
        
        engine.clear_all()
        
        changes = engine.get_change_log()
        
        # Should have delete changes
        assert len(changes) >= 2
    
    def test_reset_to_defaults_only_resets_schemas_with_defaults(self):
        """Test that reset only resets schemas with defaults."""
        engine = ConfigurationEngine()
        
        engine.register_schema("with_default", "string", default="default")
        engine.register_schema("without_default", "string")
        
        engine.set_config("with_default", "custom")
        engine.set_config("without_default", "custom2")
        
        engine.reset_to_defaults()
        
        assert engine.get_config("with_default") == "default"
        assert engine.get_config("without_default") == "custom2"  # Unchanged
    
    def test_load_from_dict_returns_count(self):
        """Test that load_from_dict returns count."""
        engine = ConfigurationEngine()
        
        data = {"key1": "v1", "key2": "v2", "key3": "v3"}
        
        count = engine.load_from_dict(data)
        
        assert count == 3
    
    def test_load_from_file_not_found(self):
        """Test loading from nonexistent file."""
        engine = ConfigurationEngine()
        
        count = engine.load_from_file("/nonexistent/path/config.json")
        
        assert count == 0
    
    def test_validate_all_warnings_empty(self):
        """Test that validation warnings is empty list."""
        engine = ConfigurationEngine()
        
        result = engine.validate_all()
        
        assert "warnings" in result
        assert result["warnings"] == []
    
    def test_config_source_reflects_origin(self):
        """Test that config source reflects origin."""
        engine = ConfigurationEngine()
        
        engine.register_schema("key1", "string", default="default")  # DEFAULT
        engine.set_config("key1", "override")  # OVERRIDE
        
        entry = engine.get_config_entry("key1")
        
        assert entry["source"] == "override"
    
    def test_schema_description_stored(self):
        """Test that schema description is stored."""
        engine = ConfigurationEngine()
        
        engine.register_schema(
            key="test_key",
            config_type="string",
            description="This is a test description",
        )
        
        schema = engine._schemas["test_key"]
        
        assert schema.description == "This is a test description"
    
    def test_multiple_keys_in_single_group(self):
        """Test adding multiple keys to single group."""
        engine = ConfigurationEngine()
        
        for i in range(10):
            engine.set_config(f"key_{i}", f"value_{i}")
        
        keys = [f"key_{i}" for i in range(10)]
        engine.add_to_group("test_group", keys)
        
        group = engine.get_group("test_group")
        
        assert len(group) == 10
    
    def test_get_all_configs_with_group_filter(self):
        """Test getting all configs with group filter."""
        engine = ConfigurationEngine()
        
        engine.set_config("group1.key1", "v1")
        engine.set_config("group1.key2", "v2")
        engine.set_config("group2.key1", "v3")
        
        engine.add_to_group("group1", ["group1.key1", "group1.key2"])
        
        configs = engine.get_all_configs(group="group1")
        
        assert len(configs) == 2
        assert "group2.key1" not in configs
