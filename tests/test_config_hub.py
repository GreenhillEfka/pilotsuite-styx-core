"""Tests for Config Hub — Slice 74."""
import pytest
from copilot_core.config.config_hub import (
    ConfigHub,
    ConfigField,
    ModuleConfig,
    ConfigChange,
    ZoneProfile,
    ConfigScope,
    ConfigType,
    create_config_hub,
    get_presence_config_schema,
    get_light_config_schema,
    get_timeofday_config_schema,
)
from datetime import datetime, timezone


class TestConfigScope:
    def test_scope_enum_values(self):
        assert ConfigScope.GLOBAL.value == "global"
        assert ConfigScope.ZONE.value == "zone"
        assert ConfigScope.MODULE.value == "module"


class TestConfigType:
    def test_type_enum_values(self):
        assert ConfigType.STRING.value == "string"
        assert ConfigType.INTEGER.value == "integer"
        assert ConfigType.FLOAT.value == "float"
        assert ConfigType.BOOLEAN.value == "boolean"


class TestConfigField:
    def test_create_field(self):
        field = ConfigField(
            name="test_field",
            config_type=ConfigType.STRING,
            description="Test field",
        )
        assert field.name == "test_field"
        assert field.required is False
    
    def test_field_validate_string(self):
        field = ConfigField("name", ConfigType.STRING, "Name")
        valid, error = field.validate("test")
        assert valid is True
        
        valid, error = field.validate(123)
        assert valid is False
    
    def test_field_validate_integer(self):
        field = ConfigField("count", ConfigType.INTEGER, "Count", min_value=0, max_value=100)
        valid, error = field.validate(50)
        assert valid is True
        
        valid, error = field.validate(-1)
        assert valid is False
        
        valid, error = field.validate(101)
        assert valid is False
    
    def test_field_validate_float(self):
        field = ConfigField("ratio", ConfigType.FLOAT, "Ratio", min_value=0.0, max_value=1.0)
        valid, error = field.validate(0.5)
        assert valid is True
        
        valid, error = field.validate(1.5)
        assert valid is False
    
    def test_field_validate_boolean(self):
        field = ConfigField("enabled", ConfigType.BOOLEAN, "Enabled")
        valid, error = field.validate(True)
        assert valid is True
        
        valid, error = field.validate("yes")
        assert valid is False
    
    def test_field_validate_enum(self):
        field = ConfigField("mode", ConfigType.ENUM, "Mode", options=["auto", "manual"])
        valid, error = field.validate("auto")
        assert valid is True
        
        valid, error = field.validate("invalid")
        assert valid is False
    
    def test_field_validate_required(self):
        field = ConfigField("name", ConfigType.STRING, "Name", required=True)
        valid, error = field.validate(None)
        assert valid is False
    
    def test_field_to_dict(self):
        field = ConfigField(
            name="test",
            config_type=ConfigType.INTEGER,
            description="Test field",
            default=10,
            min_value=0,
            max_value=100,
        )
        d = field.to_dict()
        assert d["type"] == "integer"
        assert d["default"] == 10


class TestModuleConfig:
    def test_create_module_config(self):
        config = ModuleConfig(
            module_id="presence_zone_1",
            module_name="presence",
            zone_id="zone_1",
        )
        assert config.module_name == "presence"
        assert config.enabled is True
    
    def test_module_config_to_dict(self):
        config = ModuleConfig(
            module_id="light_zone_1",
            module_name="light",
            zone_id="zone_1",
            fields={"brightness": 0.8},
        )
        d = config.to_dict()
        assert d["fields"]["brightness"] == 0.8


class TestConfigChange:
    def test_create_change(self):
        change = ConfigChange(
            change_id="cfg_test",
            module_id="presence",
            zone_id="zone_1",
            field_name="off_delay",
            old_value=300,
            new_value=600,
        )
        assert change.old_value == 300
        assert change.new_value == 600
    
    def test_change_to_dict(self):
        change = ConfigChange(
            change_id="cfg_test",
            module_id="presence",
            zone_id="zone_1",
            field_name="off_delay",
            old_value=300,
            new_value=600,
            changed_by="user",
            reason="Testing",
        )
        d = change.to_dict()
        assert d["changed_by"] == "user"
        assert d["reason"] == "Testing"


class TestZoneProfile:
    def test_create_profile(self):
        profile = ZoneProfile(
            profile_id="profile_1",
            name="Living Room Profile",
            zone_id="zone_living",
        )
        assert profile.is_default is False
    
    def test_profile_to_dict(self):
        profile = ZoneProfile(
            profile_id="profile_1",
            name="Test",
            zone_id="zone_1",
            module_configs={"presence": {"off_delay": 300}},
        )
        d = profile.to_dict()
        assert d["module_configs"]["presence"]["off_delay"] == 300


class TestConfigHub:
    def test_create_hub(self):
        hub = create_config_hub()
        assert hub is not None
    
    def test_register_module_schema(self):
        hub = ConfigHub()
        schema = get_presence_config_schema()
        result = hub.register_module_schema("presence", schema)
        assert result is True
        assert hub.get_module_schema("presence") is not None
    
    def test_set_zone_config(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        result = hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
        assert result is True
    
    def test_set_zone_config_validation_fails(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        # Invalid value (out of range)
        result = hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 9999})
        assert result is False
    
    def test_get_zone_config(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
        
        config = hub.get_zone_config("zone_1", "presence")
        assert config is not None
        assert config.fields["off_delay_seconds"] == 600
    
    def test_get_effective_config(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        # Global default
        hub.set_global_default("presence", "off_delay_seconds", 300)
        
        # Zone override
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
        
        effective = hub.get_effective_config("zone_1", "presence")
        
        assert effective["off_delay_seconds"] == 600
    
    def test_get_effective_config_no_override(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        # Only global default, no zone override
        effective = hub.get_effective_config("zone_1", "presence")
        
        assert effective["off_delay_seconds"] == 300  # Global default
    
    def test_get_global_defaults(self):
        hub = ConfigHub()
        
        defaults = hub.get_global_defaults("presence")
        
        assert "off_delay_seconds" in defaults
    
    def test_set_global_default(self):
        hub = ConfigHub()
        
        hub.set_global_default("presence", "custom_field", 123)
        
        defaults = hub.get_global_defaults("presence")
        assert defaults["custom_field"] == 123
    
    def test_create_zone_profile(self):
        hub = ConfigHub()
        
        profile = ZoneProfile(
            profile_id="profile_1",
            name="Test Profile",
            zone_id="zone_1",
        )
        
        result = hub.create_zone_profile(profile)
        assert result == "profile_1"
        assert hub.get_zone_profile("zone_1") is not None
    
    def test_delete_zone_profile(self):
        hub = ConfigHub()
        
        profile = ZoneProfile("profile_1", "Test", "zone_1")
        hub.create_zone_profile(profile)
        
        result = hub.delete_zone_profile("zone_1")
        assert result is True
        assert hub.get_zone_profile("zone_1") is None
    
    def test_get_change_history(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 900})
        
        changes = hub.get_change_history(module_name="presence", zone_id="zone_1")
        
        assert len(changes) >= 1
    
    def test_change_history_limited_to_1000(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        for i in range(1500):
            hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 300 + i})
        
        assert len(hub._change_history) == 1000
    
    def test_register_callback(self):
        hub = ConfigHub()
        
        callback_called = []
        
        def callback(module_name, zone_id, fields):
            callback_called.append((module_name, zone_id, fields))
        
        hub.register_callback(callback)
        
        hub.register_module_schema("presence", get_presence_config_schema())
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
        
        assert len(callback_called) == 1
    
    def test_export_config(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
        
        export = hub.export_config()
        
        assert "global_defaults" in export
        assert "module_configs" in export
        assert "exported_at" in export
    
    def test_import_config(self):
        hub = ConfigHub()
        
        import_data = {
            "global_defaults": {
                "presence": {"off_delay_seconds": 450},
            },
            "zone_profiles": {},
            "module_configs": {},
        }
        
        result = hub.import_config(import_data)
        assert result is True
        
        defaults = hub.get_global_defaults("presence")
        assert defaults["off_delay_seconds"] == 450
    
    def test_get_statistics(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
        
        stats = hub.get_statistics()
        
        assert stats["registered_schemas"] >= 1
        assert stats["total_configs"] >= 1
    
    def test_validate_config_valid(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        valid, errors = hub.validate_config("presence", {"off_delay_seconds": 600})
        
        assert valid is True
        assert len(errors) == 0
    
    def test_validate_config_invalid(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        valid, errors = hub.validate_config("presence", {"off_delay_seconds": 9999})
        
        assert valid is False
        assert len(errors) > 0
    
    def test_get_all_zone_configs(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
        hub.set_zone_config("zone_2", "presence", {"off_delay_seconds": 300})
        
        configs = hub.get_all_zone_configs("presence")
        
        assert len(configs) == 2
    
    def test_create_hub_returns_instance(self):
        assert isinstance(create_config_hub(), ConfigHub)
    
    def test_config_field_none_value_optional(self):
        field = ConfigField("name", ConfigType.STRING, "Name", required=False)
        valid, error = field.validate(None)
        assert valid is True
    
    def test_config_field_list_type(self):
        field = ConfigField("items", ConfigType.LIST, "Items")
        valid, error = field.validate(["a", "b", "c"])
        assert valid is True
        
        valid, error = field.validate("not a list")
        assert valid is False
    
    def test_config_field_dict_type(self):
        field = ConfigField("data", ConfigType.DICT, "Data")
        valid, error = field.validate({"key": "value"})
        assert valid is True
        
        valid, error = field.validate("not a dict")
        assert valid is False
    
    def test_zone_config_inherits_from_profile(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        profile = ZoneProfile(
            profile_id="profile_1",
            name="Test",
            zone_id="zone_1",
            module_configs={"presence": {"off_delay_seconds": 450}},
        )
        hub.create_zone_profile(profile)
        
        effective = hub.get_effective_config("zone_1", "presence")
        
        assert effective["off_delay_seconds"] == 450
    
    def test_zone_override_over_profile(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        profile = ZoneProfile(
            profile_id="profile_1",
            name="Test",
            zone_id="zone_1",
            module_configs={"presence": {"off_delay_seconds": 450}},
        )
        hub.create_zone_profile(profile)
        
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
        
        effective = hub.get_effective_config("zone_1", "presence")
        
        assert effective["off_delay_seconds"] == 600  # Zone override wins
    
    def test_get_nonexistent_zone_config(self):
        hub = ConfigHub()
        
        config = hub.get_zone_config("nonexistent", "presence")
        
        assert config is None
    
    def test_get_nonexistent_module_schema(self):
        hub = ConfigHub()
        
        schema = hub.get_module_schema("nonexistent")
        
        assert schema is None
    
    def test_import_config_merge_true(self):
        hub = ConfigHub()
        
        # Set initial default
        hub.set_global_default("presence", "existing_field", 100)
        
        import_data = {
            "global_defaults": {
                "presence": {"new_field": 200},
            },
        }
        
        hub.import_config(import_data, merge=True)
        
        defaults = hub.get_global_defaults("presence")
        assert defaults["existing_field"] == 100  # Preserved
        assert defaults["new_field"] == 200  # Added
    
    def test_import_config_merge_false(self):
        hub = ConfigHub()
        
        hub.set_global_default("presence", "existing_field", 100)
        
        import_data = {
            "global_defaults": {
                "presence": {"new_field": 200},
            },
        }
        
        hub.import_config(import_data, merge=False)
        
        defaults = hub.get_global_defaults("presence")
        assert "existing_field" not in defaults  # Replaced
    
    def test_export_config_zone_filter(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
        hub.set_zone_config("zone_2", "presence", {"off_delay_seconds": 300})
        
        export = hub.export_config(zone_ids=["zone_1"])
        
        assert "zone_1" in str(export)
    
    def test_get_change_history_limit(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        for i in range(100):
            hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 300 + i})
        
        changes = hub.get_change_history(limit=10)
        
        assert len(changes) <= 10
    
    def test_get_change_history_empty(self):
        hub = ConfigHub()
        
        changes = hub.get_change_history()
        
        assert changes == []
    
    def test_validate_config_missing_required(self):
        hub = ConfigHub()
        
        schema = [ConfigField("required_field", ConfigType.STRING, "Required", required=True)]
        hub.register_module_schema("test", schema)
        
        valid, errors = hub.validate_config("test", {})
        
        assert valid is False
        assert any("required" in e.lower() for e in errors)
    
    def test_statistics_zones_with_config(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
        hub.set_zone_config("zone_2", "presence", {"off_delay_seconds": 300})
        
        stats = hub.get_statistics()
        
        assert stats["zones_with_config"] >= 2
    
    def test_config_change_timestamp_set(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
        
        changes = hub.get_change_history()
        
        assert changes[0].timestamp is not None
    
    def test_module_config_timestamps_set(self):
        hub = ConfigHub()
        hub.register_module_schema("presence", get_presence_config_schema())
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
        
        config = hub.get_zone_config("zone_1", "presence")
        
        assert config.created_at is not None
        assert config.updated_at is not None
    
    def test_zone_profile_to_dict_includes_all_fields(self):
        profile = ZoneProfile(
            profile_id="profile_1",
            name="Test Profile",
            zone_id="zone_1",
            description="Test description",
            is_default=True,
        )
        d = profile.to_dict()
        assert d["description"] == "Test description"
        assert d["is_default"] is True
    
    def test_get_presence_config_schema(self):
        schema = get_presence_config_schema()
        
        assert len(schema) >= 4
        assert any(f.name == "off_delay_seconds" for f in schema)
    
    def test_get_light_config_schema(self):
        schema = get_light_config_schema()
        
        assert len(schema) >= 4
        assert any(f.name == "brightness_threshold" for f in schema)
    
    def test_get_timeofday_config_schema(self):
        schema = get_timeofday_config_schema()
        
        assert len(schema) >= 3
        assert any(f.name == "night_start" for f in schema)
    
    def test_callback_exception_handled(self):
        hub = ConfigHub()
        
        def failing_callback(module_name, zone_id, fields):
            raise Exception("Test exception")
        
        hub.register_callback(failing_callback)
        
        hub.register_module_schema("presence", get_presence_config_schema())
        
        # Should not crash
        hub.set_zone_config("zone_1", "presence", {"off_delay_seconds": 600})
    
    def test_set_zone_config_no_schema(self):
        hub = ConfigHub()
        
        # No schema registered - should still work (no validation)
        result = hub.set_zone_config("zone_1", "unknown_module", {"field": "value"})
        
        assert result is True
    
    def test_get_effective_config_empty_module(self):
        hub = ConfigHub()
        
        effective = hub.get_effective_config("zone_1", "nonexistent_module")
        
        assert effective == {}
    
    def test_import_config_with_zone_profiles(self):
        hub = ConfigHub()
        
        import_data = {
            "zone_profiles": {
                "zone_1": {
                    "profile_id": "profile_1",
                    "name": "Imported Profile",
                    "zone_id": "zone_1",
                    "module_configs": {"presence": {"off_delay_seconds": 500}},
                },
            },
        }
        
        hub.import_config(import_data)
        
        profile = hub.get_zone_profile("zone_1")
        assert profile is not None
        assert profile.name == "Imported Profile"
    
    def test_import_config_with_module_configs(self):
        hub = ConfigHub()
        
        import_data = {
            "module_configs": {
                "presence_zone_1": {
                    "module_id": "presence_zone_1",
                    "module_name": "presence",
                    "zone_id": "zone_1",
                    "fields": {"off_delay_seconds": 600},
                },
            },
        }
        
        hub.import_config(import_data)
        
        config = hub.get_zone_config("zone_1", "presence")
        assert config is not None
        assert config.fields["off_delay_seconds"] == 600
