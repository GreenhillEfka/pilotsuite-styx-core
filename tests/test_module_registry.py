"""Tests for Module Registry — Slice 79."""
import pytest
from copilot_core.registry.module_registry import (
    ModuleRegistry,
    ModuleMetadata,
    ModuleCapability,
    ModuleDependency,
    ModuleHealthStatus,
    ModuleRegistration,
    ModuleType,
    ModuleHealth,
    create_module_registry,
    create_module_metadata,
)
from datetime import datetime, timezone


class TestModuleType:
    def test_type_enum_values(self):
        assert ModuleType.SENSOR.value == "sensor"
        assert ModuleType.ACTUATOR.value == "actuator"
        assert ModuleType.LOGIC.value == "logic"


class TestModuleHealth:
    def test_health_enum_values(self):
        assert ModuleHealth.HEALTHY.value == "healthy"
        assert ModuleHealth.DEGRADED.value == "degraded"
        assert ModuleHealth.UNHEALTHY.value == "unhealthy"


class TestModuleCapability:
    def test_create_capability(self):
        cap = ModuleCapability(
            name="presence_detection",
            description="Detect presence in zone",
        )
        assert cap.name == "presence_detection"
    
    def test_capability_with_schemas(self):
        cap = ModuleCapability(
            name="light_control",
            description="Control lights",
            input_schema={"brightness": "float"},
            output_schema={"status": "string"},
        )
        assert cap.input_schema["brightness"] == "float"
    
    def test_capability_to_dict(self):
        cap = ModuleCapability(
            name="test_cap",
            description="Test",
            parameters={"param1": "value1"},
        )
        d = cap.to_dict()
        assert d["parameters"]["param1"] == "value1"


class TestModuleDependency:
    def test_create_dependency(self):
        dep = ModuleDependency(
            module_id="presence_module",
            required=True,
        )
        assert dep.required is True
    
    def test_dependency_with_versions(self):
        dep = ModuleDependency(
            module_id="light_module",
            required=False,
            min_version="1.0.0",
            max_version="2.0.0",
        )
        assert dep.min_version == "1.0.0"
    
    def test_dependency_to_dict(self):
        dep = ModuleDependency(
            module_id="test_mod",
            required=True,
            min_version="1.0.0",
        )
        d = dep.to_dict()
        assert d["required"] is True


class TestModuleMetadata:
    def test_create_metadata(self):
        meta = ModuleMetadata(
            module_id="test_module",
            name="Test Module",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
        )
        assert meta.module_type == ModuleType.SENSOR
        assert meta.license == "MIT"
    
    def test_metadata_with_tags(self):
        meta = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.LOGIC,
            tags=["automation", "presence"],
        )
        assert "automation" in meta.tags
    
    def test_metadata_to_dict(self):
        meta = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.UTILITY,
            author="Test Author",
            homepage="https://example.com",
        )
        d = meta.to_dict()
        assert d["author"] == "Test Author"
        assert d["homepage"] == "https://example.com"


class TestModuleHealthStatus:
    def test_create_health_status(self):
        health = ModuleHealthStatus(
            module_id="test_module",
            health=ModuleHealth.HEALTHY,
        )
        assert health.health == ModuleHealth.HEALTHY
    
    def test_health_with_error(self):
        health = ModuleHealthStatus(
            module_id="test_module",
            health=ModuleHealth.UNHEALTHY,
            error_message="Connection failed",
            error_count=3,
        )
        assert health.error_count == 3
    
    def test_health_to_dict(self):
        health = ModuleHealthStatus(
            module_id="test_module",
            health=ModuleHealth.DEGRADED,
            uptime_seconds=3600.0,
        )
        d = health.to_dict()
        assert d["uptime_seconds"] == 3600.0


class TestModuleRegistry:
    def test_create_registry(self):
        registry = create_module_registry()
        assert registry is not None
    
    def test_register_module(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test Module",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
        )
        
        result = registry.register(metadata, {"instance": "test"})
        
        assert result is True
        assert registry.get_module("test_module") is not None
    
    def test_register_duplicate_module(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
        )
        
        registry.register(metadata, {})
        
        result = registry.register(metadata, {})
        
        assert result is False
    
    def test_unregister_module(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
        )
        
        registry.register(metadata, {})
        
        result = registry.unregister("test_module")
        
        assert result is True
        assert registry.get_module("test_module") is None
    
    def test_unregister_nonexistent_module(self):
        registry = ModuleRegistry()
        
        result = registry.unregister("nonexistent")
        
        assert result is False
    
    def test_get_metadata(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
        )
        
        registry.register(metadata, {})
        
        retrieved = registry.get_metadata("test_module")
        
        assert retrieved.name == "Test"
    
    def test_get_health(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
        )
        
        registry.register(metadata, {})
        
        health = registry.get_health("test_module")
        
        assert health is not None
        assert health.module_id == "test_module"
    
    def test_check_health_with_callback(self):
        registry = ModuleRegistry()
        
        def health_check(instance):
            return True
        
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
        )
        
        registry.register(metadata, {}, health_check=health_check)
        
        health = registry.check_health("test_module")
        
        assert health == ModuleHealth.HEALTHY
    
    def test_check_health_failing_callback(self):
        registry = ModuleRegistry()
        
        def health_check(instance):
            raise Exception("Health check failed")
        
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
        )
        
        registry.register(metadata, {}, health_check=health_check)
        
        health = registry.check_health("test_module")
        
        assert health == ModuleHealth.UNHEALTHY
    
    def test_check_health_no_callback(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
        )
        
        registry.register(metadata, {})
        
        health = registry.check_health("test_module")
        
        # No callback = healthy
        assert health == ModuleHealth.HEALTHY
    
    def test_check_all_health(self):
        registry = ModuleRegistry()
        
        metadata1 = ModuleMetadata("mod1", "Mod1", "1.0.0", ModuleType.SENSOR)
        metadata2 = ModuleMetadata("mod2", "Mod2", "1.0.0", ModuleType.ACTUATOR)
        
        registry.register(metadata1, {})
        registry.register(metadata2, {})
        
        results = registry.check_all_health()
        
        assert "mod1" in results
        assert "mod2" in results
    
    def test_find_by_capability(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata(
            module_id="presence_module",
            name="Presence",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
            capabilities=[
                ModuleCapability("presence_detection", "Detect presence"),
            ],
        )
        
        registry.register(metadata, {})
        
        modules = registry.find_by_capability("presence_detection")
        
        assert "presence_module" in modules
    
    def test_find_by_capability_not_found(self):
        registry = ModuleRegistry()
        
        modules = registry.find_by_capability("nonexistent")
        
        assert len(modules) == 0
    
    def test_find_by_type(self):
        registry = ModuleRegistry()
        
        metadata1 = ModuleMetadata("mod1", "Mod1", "1.0.0", ModuleType.SENSOR)
        metadata2 = ModuleMetadata("mod2", "Mod2", "1.0.0", ModuleType.ACTUATOR)
        
        registry.register(metadata1, {})
        registry.register(metadata2, {})
        
        sensors = registry.find_by_type(ModuleType.SENSOR)
        
        assert "mod1" in sensors
        assert "mod2" not in sensors
    
    def test_find_by_tag(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
            tags=["automation", "presence"],
        )
        
        registry.register(metadata, {})
        
        modules = registry.find_by_tag("automation")
        
        assert "test_module" in modules
    
    def test_find_by_tags_any(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
            tags=["automation", "presence"],
        )
        
        registry.register(metadata, {})
        
        modules = registry.find_by_tags(["presence", "lighting"], match_all=False)
        
        assert "test_module" in modules
    
    def test_find_by_tags_all(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
            tags=["automation", "presence"],
        )
        
        registry.register(metadata, {})
        
        modules = registry.find_by_tags(["automation", "presence"], match_all=True)
        
        assert "test_module" in modules
    
    def test_list_modules(self):
        registry = ModuleRegistry()
        
        metadata1 = ModuleMetadata("mod1", "Mod1", "1.0.0", ModuleType.SENSOR)
        metadata2 = ModuleMetadata("mod2", "Mod2", "1.0.0", ModuleType.ACTUATOR)
        
        registry.register(metadata1, {})
        registry.register(metadata2, {})
        
        modules = registry.list_modules()
        
        assert len(modules) == 2
    
    def test_list_modules_enabled_only(self):
        registry = ModuleRegistry()
        
        metadata1 = ModuleMetadata("mod1", "Mod1", "1.0.0", ModuleType.SENSOR)
        metadata2 = ModuleMetadata("mod2", "Mod2", "1.0.0", ModuleType.ACTUATOR)
        
        registry.register(metadata1, {})
        registry.register(metadata2, {})
        
        registry.disable_module("mod1")
        
        modules = registry.list_modules(enabled_only=True)
        
        assert "mod1" not in modules
        assert "mod2" in modules
    
    def test_enable_module(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata("mod1", "Mod1", "1.0.0", ModuleType.SENSOR)
        registry.register(metadata, {})
        registry.disable_module("mod1")
        
        result = registry.enable_module("mod1")
        
        assert result is True
        
        modules = registry.list_modules(enabled_only=True)
        assert "mod1" in modules
    
    def test_disable_module(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata("mod1", "Mod1", "1.0.0", ModuleType.SENSOR)
        registry.register(metadata, {})
        
        result = registry.disable_module("mod1")
        
        assert result is True
        
        modules = registry.list_modules(enabled_only=True)
        assert "mod1" not in modules
    
    def test_get_statistics(self):
        registry = ModuleRegistry()
        
        metadata1 = ModuleMetadata("mod1", "Mod1", "1.0.0", ModuleType.SENSOR)
        metadata2 = ModuleMetadata("mod2", "Mod2", "1.0.0", ModuleType.SENSOR)
        metadata3 = ModuleMetadata("mod3", "Mod3", "1.0.0", ModuleType.ACTUATOR)
        
        registry.register(metadata1, {})
        registry.register(metadata2, {})
        registry.register(metadata3, {})
        
        stats = registry.get_statistics()
        
        assert stats["total_modules"] == 3
        assert stats["by_type"]["sensor"] == 2
        assert stats["by_type"]["actuator"] == 1
    
    def test_get_all_metadata(self):
        registry = ModuleRegistry()
        
        metadata1 = ModuleMetadata("mod1", "Mod1", "1.0.0", ModuleType.SENSOR)
        metadata2 = ModuleMetadata("mod2", "Mod2", "1.0.0", ModuleType.ACTUATOR)
        
        registry.register(metadata1, {})
        registry.register(metadata2, {})
        
        all_metadata = registry.get_all_metadata()
        
        assert len(all_metadata) == 2
        assert all_metadata["mod1"].name == "Mod1"
    
    def test_get_dependencies(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
            dependencies=[
                ModuleDependency("base_module", required=True),
            ],
        )
        
        registry.register(metadata, {})
        
        deps = registry.get_dependencies("test_module")
        
        assert len(deps) == 1
        assert deps[0].module_id == "base_module"
    
    def test_check_dependencies_satisfied(self):
        registry = ModuleRegistry()
        
        # Register dependency target
        base_meta = ModuleMetadata("base_module", "Base", "1.0.0", ModuleType.UTILITY)
        registry.register(base_meta, {})
        
        # Register module with dependency
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
            dependencies=[
                ModuleDependency("base_module", required=True),
            ],
        )
        registry.register(metadata, {})
        
        satisfied, missing = registry.check_dependencies_satisfied("test_module")
        
        assert satisfied is True
        assert len(missing) == 0
    
    def test_check_dependencies_missing(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
            dependencies=[
                ModuleDependency("missing_module", required=True),
            ],
        )
        registry.register(metadata, {})
        
        satisfied, missing = registry.check_dependencies_satisfied("test_module")
        
        assert satisfied is False
        assert len(missing) > 0
    
    def test_check_dependencies_version_constraint(self):
        registry = ModuleRegistry()
        
        # Register with specific version
        base_meta = ModuleMetadata("base_module", "Base", "0.9.0", ModuleType.UTILITY)
        registry.register(base_meta, {})
        
        # Require higher version
        metadata = ModuleMetadata(
            module_id="test_module",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
            dependencies=[
                ModuleDependency("base_module", required=True, min_version="1.0.0"),
            ],
        )
        registry.register(metadata, {})
        
        satisfied, missing = registry.check_dependencies_satisfied("test_module")
        
        assert satisfied is False
    
    def test_create_registry_returns_instance(self):
        assert isinstance(create_module_registry(), ModuleRegistry)
    
    def test_module_metadata_to_dict_all_fields(self):
        meta = ModuleMetadata(
            module_id="test",
            name="Test Module",
            version="1.0.0",
            module_type=ModuleType.LOGIC,
            description="Test description",
            author="Test Author",
            license="Apache-2.0",
            homepage="https://example.com",
            tags=["test", "demo"],
        )
        d = meta.to_dict()
        assert d["license"] == "Apache-2.0"
        assert len(d["tags"]) == 2
    
    def test_module_registration_to_dict(self):
        metadata = ModuleMetadata("mod1", "Mod1", "1.0.0", ModuleType.SENSOR)
        health = ModuleHealthStatus("mod1", ModuleHealth.HEALTHY)
        reg = ModuleRegistration(metadata=metadata, instance={}, health=health)
        
        d = reg.to_dict()
        
        assert "metadata" in d
        assert "health" in d
        assert "enabled" in d
    
    def test_health_uptime_tracked(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata("mod1", "Mod1", "1.0.0", ModuleType.SENSOR)
        registry.register(metadata, {})
        
        # Check health to update uptime
        registry.check_health("mod1")
        
        health = registry.get_health("mod1")
        
        assert health.uptime_seconds >= 0
    
    def test_health_error_count_incremented(self):
        registry = ModuleRegistry()
        
        def failing_check(instance):
            raise Exception("Fail")
        
        metadata = ModuleMetadata("mod1", "Mod1", "1.0.0", ModuleType.SENSOR)
        registry.register(metadata, {}, health_check=failing_check)
        
        registry.check_health("mod1")
        registry.check_health("mod1")
        
        health = registry.get_health("mod1")
        
        assert health.error_count >= 1
    
    def test_get_nonexistent_module(self):
        registry = ModuleRegistry()
        
        module = registry.get_module("nonexistent")
        
        assert module is None
    
    def test_get_nonexistent_metadata(self):
        registry = ModuleRegistry()
        
        metadata = registry.get_metadata("nonexistent")
        
        assert metadata is None
    
    def test_get_nonexistent_health(self):
        registry = ModuleRegistry()
        
        health = registry.get_health("nonexistent")
        
        assert health is None
    
    def test_enable_nonexistent_module(self):
        registry = ModuleRegistry()
        
        result = registry.enable_module("nonexistent")
        
        assert result is False
    
    def test_disable_nonexistent_module(self):
        registry = ModuleRegistry()
        
        result = registry.disable_module("nonexistent")
        
        assert result is False
    
    def test_get_dependencies_nonexistent_module(self):
        registry = ModuleRegistry()
        
        deps = registry.get_dependencies("nonexistent")
        
        assert deps == []
    
    def test_check_dependencies_nonexistent_module(self):
        registry = ModuleRegistry()
        
        satisfied, missing = registry.check_dependencies_satisfied("nonexistent")
        
        assert satisfied is False
        assert len(missing) > 0
    
    def test_statistics_by_health(self):
        registry = ModuleRegistry()
        
        metadata1 = ModuleMetadata("mod1", "Mod1", "1.0.0", ModuleType.SENSOR)
        metadata2 = ModuleMetadata("mod2", "Mod2", "1.0.0", ModuleType.SENSOR)
        
        registry.register(metadata1, {})
        registry.register(metadata2, {})
        
        stats = registry.get_statistics()
        
        assert "by_health" in stats
        assert "healthy" in stats["by_health"]
    
    def test_statistics_total_capabilities(self):
        registry = ModuleRegistry()
        
        metadata = ModuleMetadata(
            module_id="mod1",
            name="Mod1",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
            capabilities=[
                ModuleCapability("cap1", "Capability 1"),
                ModuleCapability("cap2", "Capability 2"),
            ],
        )
        registry.register(metadata, {})
        
        stats = registry.get_statistics()
        
        assert stats["total_capabilities"] == 2
    
    def test_create_module_metadata_helper(self):
        meta = create_module_metadata(
            module_id="test_mod",
            name="Test Module",
            version="1.0.0",
            module_type=ModuleType.UTILITY,
            description="Test",
            author="Tester",
            tags=["test"],
        )
        
        assert meta.module_id == "test_mod"
        assert meta.author == "Tester"
        assert "test" in meta.tags
    
    def test_create_module_metadata_defaults(self):
        meta = create_module_metadata(
            module_id="test_mod",
            name="Test",
            version="1.0.0",
            module_type=ModuleType.SENSOR,
        )
        
        assert meta.license == "MIT"
        assert meta.tags == []
