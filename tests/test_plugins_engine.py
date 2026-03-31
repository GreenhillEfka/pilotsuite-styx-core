"""Tests for Plugin Engine — Slice 44."""
import pytest
from copilot_core.plugins.engine import (
    PluginEngine,
    PluginStatus,
    PluginHook,
    PluginManifest,
    Plugin,
    HookRegistration,
    create_plugin_engine,
)
from datetime import datetime, timezone
import json
import tempfile
import os
from pathlib import Path


class TestPluginEngine:
    """Test plugin engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_plugin_engine()
        assert engine is not None
    
    def test_create_engine_with_dirs(self):
        """Test engine creation with plugin directories."""
        engine = create_plugin_engine(plugin_dirs=["/custom/plugins"])
        assert engine._plugin_dirs == ["/custom/plugins"]
    
    def test_discover_plugins_empty_dir(self):
        """Test discovering plugins in empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = create_plugin_engine(plugin_dirs=[tmpdir])
            
            count = engine.discover_plugins()
            
            assert count == 0
    
    def test_discover_plugins_with_manifest(self):
        """Test discovering plugins with manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create plugin directory
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            # Create manifest
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
                "description": "A test plugin",
            }
            
            with open(plugin_dir / "plugin.json", "w") as f:
                json.dump(manifest, f)
            
            # Create module
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("# Test plugin module\n")
            
            engine = create_plugin_engine(plugin_dirs=[tmpdir])
            
            count = engine.discover_plugins()
            
            assert count == 1
            
            plugin = engine.get_plugin("test_plugin")
            assert plugin is not None
            assert plugin["manifest"]["name"] == "Test Plugin"
    
    def test_discover_plugins_without_manifest(self):
        """Test that plugins without manifest are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "no_manifest"
            plugin_dir.mkdir()
            
            # Create module but no manifest
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("# Test plugin\n")
            
            engine = create_plugin_engine(plugin_dirs=[tmpdir])
            
            count = engine.discover_plugins()
            
            assert count == 0
    
    def test_load_plugin(self):
        """Test loading a plugin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
            }
            
            with open(plugin_dir / "plugin.json", "w") as f:
                json.dump(manifest, f)
            
            module_code = """
def on_enable(config):
    pass

def on_disable():
    pass
"""
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write(module_code)
            
            engine = create_plugin_engine(plugin_dirs=[tmpdir])
            engine.discover_plugins()
            
            result = engine.load_plugin("test_plugin")
            
            assert result is True
            
            plugin = engine.get_plugin("test_plugin")
            assert plugin["status"] == "loaded"
    
    def test_load_unknown_plugin(self):
        """Test loading unknown plugin."""
        engine = create_plugin_engine()
        
        result = engine.load_plugin("unknown_plugin")
        
        assert result is False
    
    def test_enable_plugin(self):
        """Test enabling a plugin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
            }
            
            with open(plugin_dir / "plugin.json", "w") as f:
                json.dump(manifest, f)
            
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("def on_enable(config): pass\n")
            
            engine = create_plugin_engine(plugin_dirs=[tmpdir])
            engine.discover_plugins()
            
            result = engine.enable_plugin("test_plugin")
            
            assert result is True
            
            plugin = engine.get_plugin("test_plugin")
            assert plugin["status"] == "enabled"
    
    def test_enable_plugin_with_config(self):
        """Test enabling plugin with config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
            }
            
            with open(plugin_dir / "plugin.json", "w") as f:
                json.dump(manifest, f)
            
            config_received = {}
            
            module_code = f"""
config_ref = {id(config_received)}

def on_enable(config):
    import ctypes
    ref = ctypes.cast({id(config_received)}, ctypes.py_object).value
    ref.update(config)
"""
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write(module_code)
            
            engine = create_plugin_engine(plugin_dirs=[tmpdir])
            engine.discover_plugins()
            
            engine.enable_plugin("test_plugin", config={"key": "value"})
            
            plugin = engine.get_plugin("test_plugin")
            assert plugin["config"]["key"] == "value"
    
    def test_disable_plugin(self):
        """Test disabling a plugin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
            }
            
            with open(plugin_dir / "plugin.json", "w") as f:
                json.dump(manifest, f)
            
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("def on_disable(): pass\n")
            
            engine = create_plugin_engine(plugin_dirs=[tmpdir])
            engine.discover_plugins()
            engine.enable_plugin("test_plugin")
            
            result = engine.disable_plugin("test_plugin")
            
            assert result is True
            
            plugin = engine.get_plugin("test_plugin")
            assert plugin["status"] == "disabled"
    
    def test_disable_unknown_plugin(self):
        """Test disabling unknown plugin."""
        engine = create_plugin_engine()
        
        result = engine.disable_plugin("unknown_plugin")
        
        assert result is False
    
    def test_unload_plugin(self):
        """Test unloading a plugin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
            }
            
            with open(plugin_dir / "plugin.json", "w") as f:
                json.dump(manifest, f)
            
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("def on_unload(): pass\n")
            
            engine = create_plugin_engine(plugin_dirs=[tmpdir])
            engine.discover_plugins()
            engine.load_plugin("test_plugin")
            
            result = engine.unload_plugin("test_plugin")
            
            assert result is True
            
            plugin = engine.get_plugin("test_plugin")
            assert plugin["status"] == "unloaded"
    
    def test_unload_plugin_disables_first(self):
        """Test that unload disables enabled plugin first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
            }
            
            with open(plugin_dir / "plugin.json", "w") as f:
                json.dump(manifest, f)
            
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("def on_disable(): pass\ndef on_unload(): pass\n")
            
            engine = create_plugin_engine(plugin_dirs=[tmpdir])
            engine.discover_plugins()
            engine.enable_plugin("test_plugin")
            
            engine.unload_plugin("test_plugin")
            
            plugin = engine.get_plugin("test_plugin")
            assert plugin["status"] == "unloaded"
    
    def test_plugin_dependencies(self):
        """Test plugin dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create dependency plugin
            dep_dir = Path(tmpdir) / "dep_plugin"
            dep_dir.mkdir()
            
            with open(dep_dir / "plugin.json", "w") as f:
                json.dump({
                    "plugin_id": "dep_plugin",
                    "name": "Dependency Plugin",
                    "version": "1.0.0",
                }, f)
            
            with open(dep_dir / "plugin.py", "w") as f:
                f.write("")
            
            # Create dependent plugin
            main_dir = Path(tmpdir) / "main_plugin"
            main_dir.mkdir()
            
            with open(main_dir / "plugin.json", "w") as f:
                json.dump({
                    "plugin_id": "main_plugin",
                    "name": "Main Plugin",
                    "version": "1.0.0",
                    "dependencies": ["dep_plugin"],
                }, f)
            
            with open(main_dir / "plugin.py", "w") as f:
                f.write("")
            
            engine = create_plugin_engine(plugin_dirs=[tmpdir])
            engine.discover_plugins()
            
            # Enable dependency first
            engine.enable_plugin("dep_plugin")
            
            # Now main plugin should load
            result = engine.enable_plugin("main_plugin")
            
            assert result is True
    
    def test_plugin_missing_dependency(self):
        """Test plugin with missing dependency."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "main_plugin"
            plugin_dir.mkdir()
            
            with open(plugin_dir / "plugin.json", "w") as f:
                json.dump({
                    "plugin_id": "main_plugin",
                    "name": "Main Plugin",
                    "version": "1.0.0",
                    "dependencies": ["missing_plugin"],
                }, f)
            
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("")
            
            engine = create_plugin_engine(plugin_dirs=[tmpdir])
            engine.discover_plugins()
            
            result = engine.enable_plugin("main_plugin")
            
            assert result is False
            
            plugin = engine.get_plugin("main_plugin")
            assert plugin["status"] == "error"
            assert "Missing dependency" in plugin["error_message"]
    
    def test_trigger_hook(self):
        """Test triggering hooks."""
        engine = create_plugin_engine()
        
        results = []
        
        def handler1(*args, **kwargs):
            results.append(1)
            return "result1"
        
        def handler2(*args, **kwargs):
            results.append(2)
            return "result2"
        
        # Register hooks manually
        hook1 = HookRegistration(
            hook_id="test:hook1",
            hook_type=PluginHook.ON_EVENT,
            plugin_id="test_plugin",
            handler=handler1,
            priority=10,
        )
        
        hook2 = HookRegistration(
            hook_id="test:hook2",
            hook_type=PluginHook.ON_EVENT,
            plugin_id="test_plugin",
            handler=handler2,
            priority=5,
        )
        
        engine._hooks["on_event"] = [hook1, hook2]
        
        hook_results = engine.trigger_hook("on_event", "arg1", key="value")
        
        assert len(hook_results) == 2
        assert "result1" in hook_results
        assert "result2" in hook_results
        # Higher priority should be called first
        assert results == [1, 2]
    
    def test_trigger_hook_with_exception(self):
        """Test triggering hook with exception."""
        engine = create_plugin_engine()
        
        def failing_handler(*args, **kwargs):
            raise Exception("Handler failed")
        
        def working_handler(*args, **kwargs):
            return "success"
        
        hook1 = HookRegistration(
            hook_id="test:fail",
            hook_type=PluginHook.ON_EVENT,
            plugin_id="test_plugin",
            handler=failing_handler,
        )
        
        hook2 = HookRegistration(
            hook_id="test:work",
            hook_type=PluginHook.ON_EVENT,
            plugin_id="test_plugin",
            handler=working_handler,
        )
        
        engine._hooks["on_event"] = [hook1, hook2]
        
        # Should not raise, should collect working result
        results = engine.trigger_hook("on_event")
        
        assert "success" in results
    
    def test_get_plugin(self):
        """Test getting plugin info."""
        engine = create_plugin_engine()
        
        engine.register_plugin(
            "test_plugin",
            {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
            },
        )
        
        plugin = engine.get_plugin("test_plugin")
        
        assert plugin is not None
        assert plugin["plugin_id"] == "test_plugin"
        assert plugin["manifest"]["name"] == "Test Plugin"
    
    def test_get_unknown_plugin(self):
        """Test getting unknown plugin."""
        engine = create_plugin_engine()
        
        plugin = engine.get_plugin("unknown_plugin")
        
        assert plugin is None
    
    def test_get_all_plugins(self):
        """Test getting all plugins."""
        engine = create_plugin_engine()
        
        engine.register_plugin("plugin1", {"plugin_id": "plugin1", "name": "Plugin 1", "version": "1.0.0"})
        engine.register_plugin("plugin2", {"plugin_id": "plugin2", "name": "Plugin 2", "version": "1.0.0"})
        engine.register_plugin("plugin3", {"plugin_id": "plugin3", "name": "Plugin 3", "version": "1.0.0"})
        
        plugins = engine.get_all_plugins()
        
        assert len(plugins) == 3
    
    def test_get_all_plugins_filtered_by_status(self):
        """Test getting plugins filtered by status."""
        engine = create_plugin_engine()
        
        engine.register_plugin("plugin1", {"plugin_id": "plugin1", "name": "Plugin 1", "version": "1.0.0"})
        engine.register_plugin("plugin2", {"plugin_id": "plugin2", "name": "Plugin 2", "version": "1.0.0"})
        
        # Manually set status
        engine._plugins["plugin1"].status = PluginStatus.ENABLED
        engine._plugins["plugin2"].status = PluginStatus.DISABLED
        
        enabled = engine.get_all_plugins(status=PluginStatus.ENABLED)
        disabled = engine.get_all_plugins(status=PluginStatus.DISABLED)
        
        assert len(enabled) == 1
        assert len(disabled) == 1
    
    def test_get_enabled_plugins(self):
        """Test getting enabled plugins."""
        engine = create_plugin_engine()
        
        engine.register_plugin("plugin1", {"plugin_id": "plugin1", "name": "Plugin 1", "version": "1.0.0"})
        engine.register_plugin("plugin2", {"plugin_id": "plugin2", "name": "Plugin 2", "version": "1.0.0"})
        
        engine._plugins["plugin1"].status = PluginStatus.ENABLED
        
        enabled = engine.get_enabled_plugins()
        
        assert len(enabled) == 1
        assert enabled[0]["plugin_id"] == "plugin1"
    
    def test_register_plugin_programmatically(self):
        """Test registering plugin programmatically."""
        engine = create_plugin_engine()
        
        result = engine.register_plugin(
            "test_plugin",
            {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
                "description": "A test plugin",
            },
        )
        
        assert result is True
        
        plugin = engine.get_plugin("test_plugin")
        assert plugin is not None
    
    def test_register_duplicate_plugin(self):
        """Test registering duplicate plugin."""
        engine = create_plugin_engine()
        
        engine.register_plugin("test_plugin", {"plugin_id": "test_plugin", "name": "Test", "version": "1.0.0"})
        
        result = engine.register_plugin("test_plugin", {"plugin_id": "test_plugin", "name": "Test", "version": "1.0.0"})
        
        assert result is False
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = create_plugin_engine()
        
        engine.register_plugin("plugin1", {"plugin_id": "plugin1", "name": "Plugin 1", "version": "1.0.0"})
        engine.register_plugin("plugin2", {"plugin_id": "plugin2", "name": "Plugin 2", "version": "1.0.0"})
        
        engine._plugins["plugin1"].status = PluginStatus.ENABLED
        engine._plugins["plugin2"].status = PluginStatus.DISABLED
        
        stats = engine.get_statistics()
        
        assert stats["total_discovered"] == 2
        assert "by_status" in stats
        assert stats["by_status"]["enabled"] == 1
        assert stats["by_status"]["disabled"] == 1
    
    def test_get_hooks(self):
        """Test getting registered hooks."""
        engine = create_plugin_engine()
        
        hook = HookRegistration(
            hook_id="test:hook",
            hook_type=PluginHook.ON_EVENT,
            plugin_id="test_plugin",
            handler=lambda: None,
            priority=5,
        )
        
        engine._hooks["on_event"] = [hook]
        
        hooks = engine.get_hooks()
        
        assert len(hooks) == 1
        assert hooks[0]["hook_id"] == "test:hook"
    
    def test_get_hooks_filtered_by_type(self):
        """Test getting hooks filtered by type."""
        engine = create_plugin_engine()
        
        hook1 = HookRegistration(
            hook_id="test:hook1",
            hook_type=PluginHook.ON_EVENT,
            plugin_id="test_plugin",
            handler=lambda: None,
        )
        
        hook2 = HookRegistration(
            hook_id="test:hook2",
            hook_type=PluginHook.ON_STARTUP,
            plugin_id="test_plugin",
            handler=lambda: None,
        )
        
        engine._hooks["on_event"] = [hook1]
        engine._hooks["on_startup"] = [hook2]
        
        event_hooks = engine.get_hooks(hook_type="on_event")
        
        assert len(event_hooks) == 1
        assert event_hooks[0]["hook_type"] == "on_event"
    
    def test_validate_plugin_dependencies_valid(self):
        """Test validating valid plugin dependencies."""
        engine = create_plugin_engine()
        
        engine.register_plugin("dep_plugin", {"plugin_id": "dep_plugin", "name": "Dep", "version": "1.0.0"})
        engine.register_plugin("main_plugin", {
            "plugin_id": "main_plugin",
            "name": "Main",
            "version": "1.0.0",
            "dependencies": ["dep_plugin"],
        })
        
        engine._plugins["dep_plugin"].status = PluginStatus.ENABLED
        
        result = engine.validate_plugin_dependencies("main_plugin")
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
    
    def test_validate_plugin_dependencies_missing(self):
        """Test validating missing plugin dependencies."""
        engine = create_plugin_engine()
        
        engine.register_plugin("main_plugin", {
            "plugin_id": "main_plugin",
            "name": "Main",
            "version": "1.0.0",
            "dependencies": ["missing_plugin"],
        })
        
        result = engine.validate_plugin_dependencies("main_plugin")
        
        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert "Missing dependency" in result["errors"][0]
    
    def test_validate_unknown_plugin(self):
        """Test validating unknown plugin."""
        engine = create_plugin_engine()
        
        result = engine.validate_plugin_dependencies("unknown_plugin")
        
        assert result["valid"] is False
        assert "Plugin not found" in result["errors"]
    
    def test_register_lifecycle_callback(self):
        """Test registering lifecycle callback."""
        engine = create_plugin_engine()
        
        callbacks_called = []
        
        def on_load_callback(plugin):
            callbacks_called.append(("on_load", plugin.plugin_id))
        
        result = engine.register_lifecycle_callback("on_load", on_load_callback)
        
        assert result is True
        
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            with open(plugin_dir / "plugin.json", "w") as f:
                json.dump({"plugin_id": "test_plugin", "name": "Test", "version": "1.0.0"}, f)
            
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("")
            
            engine._plugin_dirs = [tmpdir]
            engine.discover_plugins()
            engine.load_plugin("test_plugin")
        
        assert len(callbacks_called) == 1
        assert callbacks_called[0] == ("on_load", "test_plugin")
    
    def test_register_invalid_lifecycle_callback(self):
        """Test registering invalid lifecycle callback type."""
        engine = create_plugin_engine()
        
        result = engine.register_lifecycle_callback("invalid_type", lambda p: None)
        
        assert result is False
    
    def test_plugin_manifest_to_dict(self):
        """Test plugin manifest serialization."""
        manifest = PluginManifest(
            plugin_id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            dependencies=["dep1", "dep2"],
        )
        
        d = manifest.to_dict()
        
        assert d["plugin_id"] == "test_plugin"
        assert d["name"] == "Test Plugin"
        assert d["dependencies"] == ["dep1", "dep2"]
    
    def test_plugin_to_dict(self):
        """Test plugin serialization."""
        manifest = PluginManifest(
            plugin_id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
        )
        
        plugin = Plugin(
            plugin_id="test_plugin",
            manifest=manifest,
            status=PluginStatus.ENABLED,
            config={"key": "value"},
        )
        
        d = plugin.to_dict()
        
        assert d["plugin_id"] == "test_plugin"
        assert d["status"] == "enabled"
        assert d["config"]["key"] == "value"
    
    def test_hook_registration_to_dict(self):
        """Test hook registration serialization."""
        hook = HookRegistration(
            hook_id="test:hook",
            hook_type=PluginHook.ON_EVENT,
            plugin_id="test_plugin",
            handler=lambda: None,
            priority=10,
        )
        
        d = hook.to_dict()
        
        assert d["hook_id"] == "test:hook"
        assert d["hook_type"] == "on_event"
        assert d["priority"] == 10
    
    def test_plugin_status_enum_values(self):
        """Test plugin status enum values."""
        assert PluginStatus.DISCOVERED.value == "discovered"
        assert PluginStatus.LOADED.value == "loaded"
        assert PluginStatus.ENABLED.value == "enabled"
        assert PluginStatus.DISABLED.value == "disabled"
        assert PluginStatus.ERROR.value == "error"
        assert PluginStatus.UNLOADED.value == "unloaded"
    
    def test_plugin_hook_enum_values(self):
        """Test plugin hook enum values."""
        assert PluginHook.ON_STARTUP.value == "on_startup"
        assert PluginHook.ON_SHUTDOWN.value == "on_shutdown"
        assert PluginHook.ON_CONFIG_LOAD.value == "on_config_load"
        assert PluginHook.ON_EVENT.value == "on_event"
        assert PluginHook.ON_REQUEST.value == "on_request"
        assert PluginHook.ON_RESPONSE.value == "on_response"
        assert PluginHook.ON_ERROR.value == "on_error"
        assert PluginHook.CUSTOM.value == "custom"
    
    def test_trigger_hook_no_registered_hooks(self):
        """Test triggering hook with no registered hooks."""
        engine = create_plugin_engine()
        
        results = engine.trigger_hook("nonexistent_hook")
        
        assert results == []
    
    def test_plugin_loaded_at_tracked(self):
        """Test that plugin loaded_at is tracked."""
        engine = create_plugin_engine()
        
        engine.register_plugin(
            "test_plugin",
            {"plugin_id": "test_plugin", "name": "Test", "version": "1.0.0"},
            module="mock_module",
        )
        
        plugin = engine.get_plugin("test_plugin")
        
        assert plugin["loaded_at"] is not None
    
    def test_plugin_enabled_at_tracked(self):
        """Test that plugin enabled_at is tracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            with open(plugin_dir / "plugin.json", "w") as f:
                json.dump({"plugin_id": "test_plugin", "name": "Test", "version": "1.0.0"}, f)
            
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("def on_enable(config): pass\n")
            
            engine = create_plugin_engine(plugin_dirs=[tmpdir])
            engine.discover_plugins()
            engine.enable_plugin("test_plugin")
            
            plugin = engine.get_plugin("test_plugin")
            
            assert plugin["enabled_at"] is not None
    
    def test_plugin_error_message_tracked(self):
        """Test that plugin error message is tracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            with open(plugin_dir / "plugin.json", "w") as f:
                json.dump({
                    "plugin_id": "test_plugin",
                    "name": "Test",
                    "version": "1.0.0",
                    "dependencies": ["missing"],
                }, f)
            
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("")
            
            engine = create_plugin_engine(plugin_dirs=[tmpdir])
            engine.discover_plugins()
            engine.enable_plugin("test_plugin")
            
            plugin = engine.get_plugin("test_plugin")
            
            assert plugin["error_message"] is not None
    
    def test_hooks_registered_tracked(self):
        """Test that registered hooks are tracked."""
        engine = create_plugin_engine()
        
        def on_event_handler(event):
            pass
        
        # Simulate plugin with hooks
        plugin = Plugin(
            plugin_id="test_plugin",
            manifest=PluginManifest("test_plugin", "Test", "1.0.0"),
            status=PluginStatus.ENABLED,
        )
        
        plugin.hooks_registered["on_event"] = [on_event_handler]
        engine._plugins["test_plugin"] = plugin
        
        plugin_dict = engine.get_plugin("test_plugin")
        
        assert "on_event" in plugin_dict["hooks_registered"]
    
    def test_statistics_total_hooks(self):
        """Test that statistics include total hooks count."""
        engine = create_plugin_engine()
        
        for i in range(5):
            hook = HookRegistration(
                hook_id=f"test:hook{i}",
                hook_type=PluginHook.ON_EVENT,
                plugin_id="test_plugin",
                handler=lambda: None,
            )
            engine._hooks.setdefault("on_event", []).append(hook)
        
        stats = engine.get_statistics()
        
        assert stats["total_hooks"] == 5
    
    def test_statistics_hook_types(self):
        """Test that statistics include hook types count."""
        engine = create_plugin_engine()
        
        engine._hooks["on_event"] = []
        engine._hooks["on_startup"] = []
        engine._hooks["on_shutdown"] = []
        
        stats = engine.get_statistics()
        
        assert stats["hook_types"] == 3
    
    def test_discover_plugins_nonexistent_dir(self):
        """Test discovering plugins in nonexistent directory."""
        engine = create_plugin_engine(plugin_dirs=["/nonexistent/path"])
        
        count = engine.discover_plugins()
        
        assert count == 0
    
    def test_load_plugin_already_loaded(self):
        """Test loading already loaded plugin."""
        engine = create_plugin_engine()
        
        engine.register_plugin(
            "test_plugin",
            {"plugin_id": "test_plugin", "name": "Test", "version": "1.0.0"},
            module="mock_module",
        )
        
        result = engine.load_plugin("test_plugin")
        
        assert result is False
    
    def test_disable_plugin_not_enabled(self):
        """Test disabling plugin that is not enabled."""
        engine = create_plugin_engine()
        
        engine.register_plugin(
            "test_plugin",
            {"plugin_id": "test_plugin", "name": "Test", "version": "1.0.0"},
        )
        
        result = engine.disable_plugin("test_plugin")
        
        assert result is False
    
    def test_unload_plugin_not_loaded(self):
        """Test unloading plugin that is not loaded."""
        engine = create_plugin_engine()
        
        engine.register_plugin(
            "test_plugin",
            {"plugin_id": "test_plugin", "name": "Test", "version": "1.0.0"},
        )
        
        result = engine.unload_plugin("test_plugin")
        
        assert result is False
    
    def test_trigger_hook_priority_ordering(self):
        """Test that hooks are triggered in priority order."""
        engine = create_plugin_engine()
        
        call_order = []
        
        def handler1(*args, **kwargs):
            call_order.append(1)
        
        def handler2(*args, **kwargs):
            call_order.append(2)
        
        def handler3(*args, **kwargs):
            call_order.append(3)
        
        engine._hooks["on_event"] = [
            HookRegistration("h1", PluginHook.ON_EVENT, "p1", handler1, priority=5),
            HookRegistration("h2", PluginHook.ON_EVENT, "p2", handler2, priority=15),
            HookRegistration("h3", PluginHook.ON_EVENT, "p3", handler3, priority=10),
        ]
        
        engine.trigger_hook("on_event")
        
        # Should be called in priority order (highest first)
        assert call_order == [2, 3, 1]
    
    def test_plugin_manifest_min_core_version(self):
        """Test plugin manifest min_core_version."""
        manifest = PluginManifest(
            plugin_id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            min_core_version="15.2.0",
        )
        
        d = manifest.to_dict()
        
        assert d["min_core_version"] == "15.2.0"
    
    def test_plugin_manifest_hooks_list(self):
        """Test plugin manifest hooks list."""
        manifest = PluginManifest(
            plugin_id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            hooks=["on_startup", "on_shutdown", "on_event"],
        )
        
        d = manifest.to_dict()
        
        assert d["hooks"] == ["on_startup", "on_shutdown", "on_event"]
    
    def test_plugin_manifest_config_schema(self):
        """Test plugin manifest config schema."""
        manifest = PluginManifest(
            plugin_id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            config_schema={
                "api_key": {"type": "string", "required": True},
                "timeout": {"type": "number", "default": 30},
            },
        )
        
        d = manifest.to_dict()
        
        assert "api_key" in d["config_schema"]
        assert d["config_schema"]["api_key"]["required"] is True
    
    def test_register_plugin_with_module(self):
        """Test registering plugin with module."""
        engine = create_plugin_engine()
        
        class MockModule:
            def on_enable(self, config):
                pass
        
        engine.register_plugin(
            "test_plugin",
            {"plugin_id": "test_plugin", "name": "Test", "version": "1.0.0"},
            module=MockModule(),
        )
        
        plugin = engine.get_plugin("test_plugin")
        
        assert plugin["status"] == "loaded"
        assert plugin["loaded_at"] is not None
    
    def test_get_enabled_plugins_empty(self):
        """Test getting enabled plugins when none enabled."""
        engine = create_plugin_engine()
        
        enabled = engine.get_enabled_plugins()
        
        assert enabled == []
    
    def test_discover_plugins_multiple_dirs(self):
        """Test discovering plugins in multiple directories."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                # Create plugin in first dir
                plugin1_dir = Path(tmpdir1) / "plugin1"
                plugin1_dir.mkdir()
                
                with open(plugin1_dir / "plugin.json", "w") as f:
                    json.dump({"plugin_id": "plugin1", "name": "Plugin 1", "version": "1.0.0"}, f)
                
                with open(plugin1_dir / "plugin.py", "w") as f:
                    f.write("")
                
                # Create plugin in second dir
                plugin2_dir = Path(tmpdir2) / "plugin2"
                plugin2_dir.mkdir()
                
                with open(plugin2_dir / "plugin.json", "w") as f:
                    json.dump({"plugin_id": "plugin2", "name": "Plugin 2", "version": "1.0.0"}, f)
                
                with open(plugin2_dir / "plugin.py", "w") as f:
                    f.write("")
                
                engine = create_plugin_engine(plugin_dirs=[tmpdir1, tmpdir2])
                
                count = engine.discover_plugins()
                
                assert count == 2
