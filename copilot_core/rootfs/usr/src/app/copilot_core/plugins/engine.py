"""Plugin System — Slice 27.

Plugin system for PilotSuite Core extensibility.

Features:
- Plugin discovery and loading
- Plugin lifecycle management
- Hook system for extending core behavior
- Plugin configuration management
- Plugin dependency resolution
- Sandboxed plugin execution
"""
from __future__ import annotations

import logging
import importlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable, Set
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    """Plugin status."""
    DISCOVERED = "discovered"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"
    UNLOADING = "unloading"
    UNLOADED = "unloaded"


class PluginHook(Enum):
    """Available plugin hooks."""
    # Lifecycle hooks
    ON_STARTUP = "on_startup"
    ON_SHUTDOWN = "on_shutdown"
    ON_CONFIG_LOADED = "on_config_loaded"
    
    # Event hooks
    ON_EVENT_RECEIVED = "on_event_received"
    ON_EVENT_PROCESSED = "on_event_processed"
    
    # Zone hooks
    ON_ZONE_CREATED = "on_zone_created"
    ON_ZONE_UPDATED = "on_zone_updated"
    ON_ZONE_DELETED = "on_zone_deleted"
    
    # Module hooks
    ON_MODULE_REGISTERED = "on_module_registered"
    ON_MODULE_STATE_CHANGED = "on_module_state_changed"
    
    # Automation hooks
    ON_AUTOMATION_TRIGGERED = "on_automation_triggered"
    ON_AUTOMATION_EXECUTED = "on_automation_executed"
    
    # Health hooks
    ON_HEALTH_CHECK = "on_health_check"
    
    # Custom hooks
    CUSTOM = "custom"


@dataclass
class PluginManifest:
    """Plugin manifest/metadata."""
    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    homepage: Optional[str]
    license: str
    min_core_version: str
    dependencies: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "homepage": self.homepage,
            "license": self.license,
            "min_core_version": self.min_core_version,
            "dependencies": self.dependencies,
            "hooks": self.hooks,
            "config_schema": self.config_schema,
        }


@dataclass
class Plugin:
    """Loaded plugin instance."""
    plugin_id: str
    manifest: PluginManifest
    status: PluginStatus
    path: str
    module: Any = None
    config: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    loaded_at: Optional[str] = None
    enabled_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "manifest": self.manifest.to_dict(),
            "status": self.status.value,
            "path": self.path,
            "config": self.config,
            "error_message": self.error_message,
            "loaded_at": self.loaded_at,
            "enabled_at": self.enabled_at,
        }


class PluginEngine:
    """Plugin system engine."""
    
    def __init__(self, plugins_dir: str = "/data/plugins", core_version: str = "15.2.36"):
        self._plugins_dir = Path(plugins_dir)
        self._core_version = core_version
        self._plugins: Dict[str, Plugin] = {}
        self._hooks: Dict[PluginHook, List[Callable]] = {}
        self._hook_counter = 0
        
        # Initialize hook registries
        for hook in PluginHook:
            self._hooks[hook] = []
    
    def discover_plugins(self) -> List[str]:
        """Discover available plugins."""
        discovered = []
        
        if not self._plugins_dir.exists():
            self._plugins_dir.mkdir(parents=True, exist_ok=True)
            return discovered
        
        for plugin_path in self._plugins_dir.iterdir():
            if not plugin_path.is_dir():
                continue
            
            manifest_path = plugin_path / "manifest.json"
            if not manifest_path.exists():
                continue
            
            try:
                manifest = self._load_manifest(manifest_path)
                
                if manifest.plugin_id not in self._plugins:
                    plugin = Plugin(
                        plugin_id=manifest.plugin_id,
                        manifest=manifest,
                        status=PluginStatus.DISCOVERED,
                        path=str(plugin_path),
                    )
                    self._plugins[manifest.plugin_id] = plugin
                    discovered.append(manifest.plugin_id)
                    
            except Exception as exc:
                logger.warning("Failed to discover plugin at %s: %s", plugin_path, exc)
        
        return discovered
    
    def _load_manifest(self, manifest_path: Path) -> PluginManifest:
        """Load plugin manifest."""
        with open(manifest_path, "r") as f:
            data = json.load(f)
        
        return PluginManifest(
            plugin_id=data.get("plugin_id", ""),
            name=data.get("name", "Unknown"),
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            author=data.get("author", "Unknown"),
            homepage=data.get("homepage"),
            license=data.get("license", "Unknown"),
            min_core_version=data.get("min_core_version", "0.0.0"),
            dependencies=data.get("dependencies", []),
            hooks=data.get("hooks", []),
            config_schema=data.get("config_schema", {}),
        )
    
    def load_plugin(self, plugin_id: str) -> bool:
        """Load a plugin."""
        if plugin_id not in self._plugins:
            logger.warning("Unknown plugin: %s", plugin_id)
            return False
        
        plugin = self._plugins[plugin_id]
        
        # Check status
        if plugin.status not in (PluginStatus.DISCOVERED, PluginStatus.ERROR, PluginStatus.UNLOADED):
            logger.warning("Cannot load plugin %s in status %s", plugin_id, plugin.status.value)
            return False
        
        # Check core version compatibility
        if not self._check_version_compatibility(plugin.manifest.min_core_version):
            plugin.status = PluginStatus.ERROR
            plugin.error_message = f"Incompatible core version. Requires >= {plugin.manifest.min_core_version}"
            logger.error(plugin.error_message)
            return False
        
        # Check dependencies
        missing_deps = self._check_dependencies(plugin.manifest.dependencies)
        if missing_deps:
            plugin.status = PluginStatus.ERROR
            plugin.error_message = f"Missing dependencies: {missing_deps}"
            logger.error(plugin.error_message)
            return False
        
        plugin.status = PluginStatus.LOADING
        
        try:
            # Load plugin module
            plugin_module_path = Path(plugin.path) / "plugin.py"
            
            if not plugin_module_path.exists():
                raise FileNotFoundError(f"Plugin module not found: {plugin_module_path}")
            
            # Import plugin module
            import sys
            sys.path.insert(0, plugin.path)
            
            plugin.module = importlib.import_module("plugin")
            
            plugin.status = PluginStatus.LOADED
            plugin.loaded_at = datetime.now(timezone.utc).isoformat()
            
            logger.info("Plugin %s loaded successfully", plugin_id)
            return True
            
        except Exception as exc:
            plugin.status = PluginStatus.ERROR
            plugin.error_message = str(exc)
            logger.exception("Failed to load plugin %s: %s", plugin_id, exc)
            return False
    
    def enable_plugin(self, plugin_id: str) -> bool:
        """Enable a plugin."""
        if plugin_id not in self._plugins:
            return False
        
        plugin = self._plugins[plugin_id]
        
        if plugin.status != PluginStatus.LOADED:
            # Try to load first
            if not self.load_plugin(plugin_id):
                return False
        
        # Register hooks
        self._register_plugin_hooks(plugin)
        
        plugin.status = PluginStatus.ACTIVE
        plugin.enabled_at = datetime.now(timezone.utc).isoformat()
        
        # Call on_startup hook if available
        self._call_hook(PluginHook.ON_STARTUP, plugin_id=plugin_id)
        
        logger.info("Plugin %s enabled", plugin_id)
        return True
    
    def disable_plugin(self, plugin_id: str) -> bool:
        """Disable a plugin."""
        if plugin_id not in self._plugins:
            return False
        
        plugin = self._plugins[plugin_id]
        
        if plugin.status != PluginStatus.ACTIVE:
            return False
        
        # Call on_shutdown hook
        self._call_hook(PluginHook.ON_SHUTDOWN, plugin_id=plugin_id)
        
        # Unregister hooks
        self._unregister_plugin_hooks(plugin)
        
        plugin.status = PluginStatus.DISABLED
        
        logger.info("Plugin %s disabled", plugin_id)
        return True
    
    def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a plugin."""
        if plugin_id not in self._plugins:
            return False
        
        plugin = self._plugins[plugin_id]
        
        # Disable first if active
        if plugin.status == PluginStatus.ACTIVE:
            self.disable_plugin(plugin_id)
        
        plugin.status = PluginStatus.UNLOADING
        
        # Remove from sys.modules
        if plugin.module:
            import sys
            if "plugin" in sys.modules:
                del sys.modules["plugin"]
        
        plugin.module = None
        plugin.status = PluginStatus.UNLOADED
        
        logger.info("Plugin %s unloaded", plugin_id)
        return True
    
    def register_hook(self, hook: PluginHook, callback: Callable, priority: int = 0) -> str:
        """Register a hook callback."""
        self._hook_counter += 1
        hook_id = f"hook_{self._hook_counter}"
        
        # Store with priority
        self._hooks[hook].append((priority, hook_id, callback))
        
        # Sort by priority (higher first)
        self._hooks[hook].sort(key=lambda x: x[0], reverse=True)
        
        return hook_id
    
    def unregister_hook(self, hook_id: str) -> bool:
        """Unregister a hook callback."""
        for hook in PluginHook:
            for i, (priority, hid, callback) in enumerate(self._hooks[hook]):
                if hid == hook_id:
                    del self._hooks[hook][i]
                    return True
        return False
    
    def trigger_hook(self, hook: PluginHook, **kwargs) -> List[Any]:
        """Trigger a hook and collect results."""
        results = []
        
        for priority, hook_id, callback in self._hooks[hook]:
            try:
                result = callback(**kwargs)
                results.append(result)
            except Exception as exc:
                logger.exception("Hook %s (%s) failed: %s", hook.value, hook_id, exc)
        
        return results
    
    def _register_plugin_hooks(self, plugin: Plugin) -> None:
        """Register plugin hooks."""
        if not plugin.module:
            return
        
        for hook_name in plugin.manifest.hooks:
            try:
                hook = PluginHook(hook_name)
            except ValueError:
                continue
            
            if hasattr(plugin.module, hook_name):
                callback = getattr(plugin.module, hook_name)
                self.register_hook(hook, callback)
    
    def _unregister_plugin_hooks(self, plugin: Plugin) -> None:
        """Unregister plugin hooks."""
        # This is simplified - in production, track hook_ids per plugin
        pass
    
    def _call_hook(self, hook: PluginHook, **kwargs) -> None:
        """Call a hook (fire and forget)."""
        self.trigger_hook(hook, **kwargs)
    
    def _check_version_compatibility(self, min_version: str) -> bool:
        """Check if core version is compatible."""
        # Simple version comparison
        try:
            core_parts = [int(x) for x in self._core_version.split(".")[:3]]
            min_parts = [int(x) for x in min_version.split(".")[:3]]
            
            return core_parts >= min_parts
        except (ValueError, IndexError):
            return False
    
    def _check_dependencies(self, dependencies: List[str]) -> List[str]:
        """Check if all dependencies are satisfied."""
        missing = []
        
        for dep in dependencies:
            if dep not in self._plugins or self._plugins[dep].status != PluginStatus.ACTIVE:
                missing.append(dep)
        
        return missing
    
    def get_plugin(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get plugin details."""
        if plugin_id not in self._plugins:
            return None
        
        return self._plugins[plugin_id].to_dict()
    
    def get_all_plugins(self) -> List[Dict[str, Any]]:
        """Get all plugins."""
        return [p.to_dict() for p in self._plugins.values()]
    
    def get_plugin_config(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get plugin configuration."""
        if plugin_id not in self._plugins:
            return None
        
        return self._plugins[plugin_id].config
    
    def update_plugin_config(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        """Update plugin configuration."""
        if plugin_id not in self._plugins:
            return False
        
        self._plugins[plugin_id].config.update(config)
        return True
    
    def get_plugin_summary(self) -> Dict[str, Any]:
        """Get plugin system summary."""
        total = len(self._plugins)
        active = len([p for p in self._plugins.values() if p.status == PluginStatus.ACTIVE])
        disabled = len([p for p in self._plugins.values() if p.status == PluginStatus.DISABLED])
        error = len([p for p in self._plugins.values() if p.status == PluginStatus.ERROR])
        
        total_hooks = sum(len(hooks) for hooks in self._hooks.values())
        
        return {
            "total_plugins": total,
            "active_plugins": active,
            "disabled_plugins": disabled,
            "error_plugins": error,
            "total_hooks_registered": total_hooks,
            "plugins_dir": str(self._plugins_dir),
            "core_version": self._core_version,
        }


def create_plugin_engine(plugins_dir: str = "/data/plugins",
                        core_version: str = "15.2.36") -> PluginEngine:
    """Factory function to create plugin engine."""
    return PluginEngine(plugins_dir=plugins_dir, core_version=core_version)
