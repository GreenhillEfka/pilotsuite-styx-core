"""Tests for Plugin System — Slice 27."""
import pytest
import json
import tempfile
from pathlib import Path
from copilot_core.plugins.engine import (
    PluginEngine,
    PluginStatus,
    PluginHook,
    create_plugin_engine,
)


class TestPluginEngine:
    """Test plugin engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_plugin_engine()
        assert engine is not None
    
    def test_create_engine_with_custom_dir(self):
        """Test engine creation with custom plugins directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = create_plugin_engine(plugins_dir=tmpdir)
            assert engine._plugins_dir == Path(tmpdir)
    
    def test_discover_plugins_empty(self):
        """Test discovering plugins in empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = create_plugin_engine(plugins_dir=tmpdir)
            
            discovered = engine.discover_plugins()
            
            assert len(discovered) == 0
    
    def test_discover_plugin_with_manifest(self):
        """Test discovering plugin with manifest."""
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
                "author": "Test Author",
                "license": "MIT",
                "min_core_version": "15.0.0",
            }
            
            with open(plugin_dir / "manifest.json", "w") as f:
                json.dump(manifest, f)
            
            engine = create_plugin_engine(plugins_dir=tmpdir)
            
            discovered = engine.discover_plugins()
            
            assert len(discovered) == 1
            assert "test_plugin" in discovered
    
    def test_discover_plugin_without_manifest(self):
        """Test that plugin without manifest is ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create plugin directory without manifest
            plugin_dir = Path(tmpdir) / "no_manifest_plugin"
            plugin_dir.mkdir()
            
            engine = create_plugin_engine(plugins_dir=tmpdir)
            
            discovered = engine.discover_plugins()
            
            assert len(discovered) == 0
    
    def test_load_plugin_success(self):
        """Test loading plugin successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create plugin
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
                "description": "Test",
                "author": "Test",
                "license": "MIT",
                "min_core_version": "15.0.0",
            }
            
            with open(plugin_dir / "manifest.json", "w") as f:
                json.dump(manifest, f)
            
            # Create plugin module
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("# Test plugin module\n")
            
            engine = create_plugin_engine(plugins_dir=tmpdir)
            engine.discover_plugins()
            
            result = engine.load_plugin("test_plugin")
            
            assert result is True
            assert engine._plugins["test_plugin"].status == PluginStatus.LOADED
    
    def test_load_unknown_plugin(self):
        """Test loading unknown plugin."""
        engine = create_plugin_engine()
        
        result = engine.load_plugin("unknown_plugin")
        
        assert result is False
    
    def test_load_plugin_version_incompatible(self):
        """Test loading plugin with incompatible core version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "old_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "old_plugin",
                "name": "Old Plugin",
                "version": "1.0.0",
                "description": "Test",
                "author": "Test",
                "license": "MIT",
                "min_core_version": "99.0.0",  # Requires future version
            }
            
            with open(plugin_dir / "manifest.json", "w") as f:
                json.dump(manifest, f)
            
            engine = create_plugin_engine(plugins_dir=tmpdir)
            engine.discover_plugins()
            
            result = engine.load_plugin("old_plugin")
            
            assert result is False
            assert engine._plugins["old_plugin"].status == PluginStatus.ERROR
    
    def test_enable_plugin(self):
        """Test enabling plugin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
                "description": "Test",
                "author": "Test",
                "license": "MIT",
                "min_core_version": "15.0.0",
            }
            
            with open(plugin_dir / "manifest.json", "w") as f:
                json.dump(manifest, f)
            
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("# Test plugin\n")
            
            engine = create_plugin_engine(plugins_dir=tmpdir)
            engine.discover_plugins()
            
            result = engine.enable_plugin("test_plugin")
            
            assert result is True
            assert engine._plugins["test_plugin"].status == PluginStatus.ACTIVE
    
    def test_disable_plugin(self):
        """Test disabling plugin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
                "description": "Test",
                "author": "Test",
                "license": "MIT",
                "min_core_version": "15.0.0",
            }
            
            with open(plugin_dir / "manifest.json", "w") as f:
                json.dump(manifest, f)
            
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("# Test plugin\n")
            
            engine = create_plugin_engine(plugins_dir=tmpdir)
            engine.discover_plugins()
            engine.enable_plugin("test_plugin")
            
            result = engine.disable_plugin("test_plugin")
            
            assert result is True
            assert engine._plugins["test_plugin"].status == PluginStatus.DISABLED
    
    def test_unload_plugin(self):
        """Test unloading plugin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
                "description": "Test",
                "author": "Test",
                "license": "MIT",
                "min_core_version": "15.0.0",
            }
            
            with open(plugin_dir / "manifest.json", "w") as f:
                json.dump(manifest, f)
            
            with open(plugin_dir / "plugin.py", "w") as f:
                f.write("# Test plugin\n")
            
            engine = create_plugin_engine(plugins_dir=tmpdir)
            engine.discover_plugins()
            engine.enable_plugin("test_plugin")
            
            result = engine.unload_plugin("test_plugin")
            
            assert result is True
            assert engine._plugins["test_plugin"].status == PluginStatus.UNLOADED
    
    def test_register_hook(self):
        """Test registering hook callback."""
        engine = create_plugin_engine()
        
        def test_callback(**kwargs):
            return "test_result"
        
        hook_id = engine.register_hook(PluginHook.ON_STARTUP, test_callback)
        
        assert hook_id.startswith("hook_")
        assert len(engine._hooks[PluginHook.ON_STARTUP]) == 1
    
    def test_unregister_hook(self):
        """Test unregistering hook callback."""
        engine = create_plugin_engine()
        
        def test_callback(**kwargs):
            pass
        
        hook_id = engine.register_hook(PluginHook.ON_STARTUP, test_callback)
        
        result = engine.unregister_hook(hook_id)
        
        assert result is True
        assert len(engine._hooks[PluginHook.ON_STARTUP]) == 0
    
    def test_unregister_unknown_hook(self):
        """Test unregistering unknown hook."""
        engine = create_plugin_engine()
        
        result = engine.unregister_hook("unknown_hook")
        
        assert result is False
    
    def test_trigger_hook(self):
        """Test triggering hook."""
        engine = create_plugin_engine()
        
        results_collected = []
        
        def callback1(**kwargs):
            results_collected.append("callback1")
            return "result1"
        
        def callback2(**kwargs):
            results_collected.append("callback2")
            return "result2"
        
        engine.register_hook(PluginHook.ON_HEALTH_CHECK, callback1)
        engine.register_hook(PluginHook.ON_HEALTH_CHECK, callback2)
        
        results = engine.trigger_hook(PluginHook.ON_HEALTH_CHECK)
        
        assert len(results) == 2
        assert "result1" in results
        assert "result2" in results
    
    def test_trigger_hook_with_priority(self):
        """Test triggering hook with priority."""
        engine = create_plugin_engine()
        
        def callback_low(**kwargs):
            return "low"
        
        def callback_high(**kwargs):
            return "high"
        
        engine.register_hook(PluginHook.ON_HEALTH_CHECK, callback_low, priority=1)
        engine.register_hook(PluginHook.ON_HEALTH_CHECK, callback_high, priority=10)
        
        # Higher priority should be first
        results = engine.trigger_hook(PluginHook.ON_HEALTH_CHECK)
        
        assert results[0] == "high"
        assert results[1] == "low"
    
    def test_get_plugin(self):
        """Test getting plugin details."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
                "description": "Test description",
                "author": "Test Author",
                "license": "MIT",
                "min_core_version": "15.0.0",
            }
            
            with open(plugin_dir / "manifest.json", "w") as f:
                json.dump(manifest, f)
            
            engine = create_plugin_engine(plugins_dir=tmpdir)
            engine.discover_plugins()
            
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
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two plugins
            for i in range(2):
                plugin_dir = Path(tmpdir) / f"plugin_{i}"
                plugin_dir.mkdir()
                
                manifest = {
                    "plugin_id": f"plugin_{i}",
                    "name": f"Plugin {i}",
                    "version": "1.0.0",
                    "description": "Test",
                    "author": "Test",
                    "license": "MIT",
                    "min_core_version": "15.0.0",
                }
                
                with open(plugin_dir / "manifest.json", "w") as f:
                    json.dump(manifest, f)
            
            engine = create_plugin_engine(plugins_dir=tmpdir)
            engine.discover_plugins()
            
            plugins = engine.get_all_plugins()
            
            assert len(plugins) == 2
    
    def test_get_plugin_config(self):
        """Test getting plugin config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
                "description": "Test",
                "author": "Test",
                "license": "MIT",
                "min_core_version": "15.0.0",
            }
            
            with open(plugin_dir / "manifest.json", "w") as f:
                json.dump(manifest, f)
            
            engine = create_plugin_engine(plugins_dir=tmpdir)
            engine.discover_plugins()
            
            config = engine.get_plugin_config("test_plugin")
            
            assert config == {}  # Empty initially
    
    def test_update_plugin_config(self):
        """Test updating plugin config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            manifest = {
                "plugin_id": "test_plugin",
                "name": "Test Plugin",
                "version": "1.0.0",
                "description": "Test",
                "author": "Test",
                "license": "MIT",
                "min_core_version": "15.0.0",
            }
            
            with open(plugin_dir / "manifest.json", "w") as f:
                json.dump(manifest, f)
            
            engine = create_plugin_engine(plugins_dir=tmpdir)
            engine.discover_plugins()
            
            result = engine.update_plugin_config("test_plugin", {"setting": "value"})
            
            assert result is True
            assert engine._plugins["test_plugin"].config["setting"] == "value"
    
    def test_get_plugin_summary(self):
        """Test plugin summary."""
        engine = create_plugin_engine()
        
        summary = engine.get_plugin_summary()
        
        assert "total_plugins" in summary
        assert "active_plugins" in summary
        assert "plugins_dir" in summary
        assert "core_version" in summary
    
    def test_plugin_status_enum(self):
        """Test plugin status enum values."""
        assert PluginStatus.DISCOVERED.value == "discovered"
        assert PluginStatus.LOADED.value == "loaded"
        assert PluginStatus.ACTIVE.value == "active"
        assert PluginStatus.DISABLED.value == "disabled"
        assert PluginStatus.ERROR.value == "error"
    
    def test_plugin_hook_enum(self):
        """Test plugin hook enum values."""
        assert PluginHook.ON_STARTUP.value == "on_startup"
        assert PluginHook.ON_SHUTDOWN.value == "on_shutdown"
        assert PluginHook.ON_EVENT_RECEIVED.value == "on_event_received"
        assert PluginHook.ON_ZONE_CREATED.value == "on_zone_created"
    
    def test_plugin_manifest_to_dict(self):
        """Test plugin manifest serialization."""
        from copilot_core.plugins.engine import PluginManifest
        
        manifest = PluginManifest(
            plugin_id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            description="Test description",
            author="Test Author",
            homepage="https://example.com",
            license="MIT",
            min_core_version="15.0.0",
        )
        
        d = manifest.to_dict()
        
        assert d["plugin_id"] == "test_plugin"
        assert d["name"] == "Test Plugin"
        assert d["version"] == "1.0.0"
    
    def test_plugin_to_dict(self):
        """Test plugin serialization."""
        from copilot_core.plugins.engine import Plugin, PluginManifest
        
        manifest = PluginManifest(
            plugin_id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            description="Test",
            author="Test",
            homepage=None,
            license="MIT",
            min_core_version="15.0.0",
        )
        
        plugin = Plugin(
            plugin_id="test_plugin",
            manifest=manifest,
            status=PluginStatus.ACTIVE,
            path="/plugins/test_plugin",
        )
        
        d = plugin.to_dict()
        
        assert d["plugin_id"] == "test_plugin"
        assert d["status"] == "active"
        assert d["path"] == "/plugins/test_plugin"
    
    def test_version_compatibility_check(self):
        """Test version compatibility check."""
        engine = create_plugin_engine(core_version="15.2.36")
        
        # Compatible version
        assert engine._check_version_compatibility("15.0.0") is True
        assert engine._check_version_compatibility("15.2.0") is True
        assert engine._check_version_compatibility("15.2.36") is True
        
        # Incompatible version
        assert engine._check_version_compatibility("16.0.0") is False
        assert engine._check_version_compatibility("99.0.0") is False
    
    def test_dependency_check_missing(self):
        """Test dependency check with missing dependencies."""
        engine = create_plugin_engine()
        
        missing = engine._check_dependencies(["plugin_a", "plugin_b"])
        
        assert "plugin_a" in missing
        assert "plugin_b" in missing
    
    def test_dependency_check_satisfied(self):
        """Test dependency check with satisfied dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create dependency plugin
            dep_dir = Path(tmpdir) / "dep_plugin"
            dep_dir.mkdir()
            
            manifest = {
                "plugin_id": "dep_plugin",
                "name": "Dep Plugin",
                "version": "1.0.0",
                "description": "Test",
                "author": "Test",
                "license": "MIT",
                "min_core_version": "15.0.0",
            }
            
            with open(dep_dir / "manifest.json", "w") as f:
                json.dump(manifest, f)
            
            with open(dep_dir / "plugin.py", "w") as f:
                f.write("# Dep plugin\n")
            
            engine = create_plugin_engine(plugins_dir=tmpdir)
            engine.discover_plugins()
            engine.enable_plugin("dep_plugin")
            
            missing = engine._check_dependencies(["dep_plugin"])
            
            assert len(missing) == 0
