"""Plugin Engine — Slice 44.

Plugin system for PilotSuite Core extensibility.

Features:
- Plugin discovery and loading
- Plugin lifecycle management
- Hook system for extensions
- Plugin dependencies
- Plugin configuration
- Hot reload support
"""
from __future__ import annotations

import logging
import importlib
import importlib.util
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Type
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    """Plugin status."""
    DISCOVERED = "discovered"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    UNLOADED = "unloaded"


class PluginHook(Enum):
    """Plugin hook types."""
    ON_STARTUP = "on_startup"
    ON_SHUTDOWN = "on_shutdown"
    ON_CONFIG_LOAD = "on_config_load"
    ON_EVENT = "on_event"
    ON_REQUEST = "on_request"
    ON_RESPONSE = "on_response"
    ON_ERROR = "on_error"
    CUSTOM = "custom"


@dataclass
class PluginManifest:
    """Plugin manifest definition."""
    plugin_id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    homepage: str = ""
    license: str = "MIT"
    min_core_version: str = "15.2.0"
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
    module: Any = None
    status: PluginStatus = PluginStatus.DISCOVERED
    config: Dict[str, Any] = field(default_factory=dict)
    path: Optional[str] = None
    loaded_at: Optional[str] = None
    enabled_at: Optional[str] = None
    error_message: Optional[str] = None
    hooks_registered: Dict[str, List[Callable]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "manifest": self.manifest.to_dict(),
            "status": self.status.value,
            "config": self.config,
            "path": self.path,
            "loaded_at": self.loaded_at,
            "enabled_at": self.enabled_at,
            "error_message": self.error_message,
            "hooks_registered": list(self.hooks_registered.keys()),
        }


@dataclass
class HookRegistration:
    """Registered hook."""
    hook_id: str
    hook_type: PluginHook
    plugin_id: str
    handler: Callable
    priority: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook_id": self.hook_id,
            "hook_type": self.hook_type.value,
            "plugin_id": self.plugin_id,
            "priority": self.priority,
        }


class PluginEngine:
    """Plugin management engine."""
    
    def __init__(self, plugin_dirs: Optional[List[str]] = None):
        self._plugins: Dict[str, Plugin] = {}
        self._hooks: Dict[str, List[HookRegistration]] = {}
        self._plugin_dirs = plugin_dirs or ["plugins", "~/.pilotclaw/plugins"]
        
        # Plugin lifecycle callbacks
        self._lifecycle_callbacks: Dict[str, List[Callable]] = {
            "on_load": [],
            "on_enable": [],
            "on_disable": [],
            "on_unload": [],
        }
        
        # Statistics
        self._stats = {
            "total_discovered": 0,
            "total_loaded": 0,
            "total_enabled": 0,
            "total_errors": 0,
        }
    
    def discover_plugins(self) -> int:
        """Discover plugins in configured directories."""
        discovered = 0
        
        for plugin_dir in self._plugin_dirs:
            plugin_path = Path(plugin_dir).expanduser()
            
            if not plugin_path.exists():
                continue
            
            # Look for plugin directories
            for item in plugin_path.iterdir():
                if not item.is_dir():
                    continue
                
                # Check for manifest
                manifest_path = item / "plugin.json"
                if not manifest_path.exists():
                    continue
                
                # Check for module
                module_path = item / "plugin.py"
                if not module_path.exists():
                    continue
                
                try:
                    manifest = self._load_manifest(manifest_path)
                    
                    plugin = Plugin(
                        plugin_id=manifest.plugin_id,
                        manifest=manifest,
                        path=str(item),
                        status=PluginStatus.DISCOVERED,
                    )
                    
                    self._plugins[manifest.plugin_id] = plugin
                    self._stats["total_discovered"] += 1
                    discovered += 1
                    
                    logger.info("Plugin discovered: %s (%s)", manifest.name, manifest.plugin_id)
                    
                except Exception as exc:
                    logger.error("Failed to discover plugin at %s: %s", item, exc)
                    self._stats["total_errors"] += 1
        
        logger.info("Discovered %d plugins", discovered)
        
        return discovered
    
    def _load_manifest(self, manifest_path: Path) -> PluginManifest:
        """Load plugin manifest from JSON file."""
        import json
        
        with open(manifest_path, "r") as f:
            data = json.load(f)
        
        return PluginManifest(
            plugin_id=data.get("plugin_id", data.get("id", "")),
            name=data.get("name", ""),
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            homepage=data.get("homepage", ""),
            license=data.get("license", "MIT"),
            min_core_version=data.get("min_core_version", "15.2.0"),
            dependencies=data.get("dependencies", []),
            hooks=data.get("hooks", []),
            config_schema=data.get("config_schema", {}),
        )
    
    def load_plugin(self, plugin_id: str) -> bool:
        """Load a plugin."""
        if plugin_id not in self._plugins:
            logger.error("Plugin not found: %s", plugin_id)
            return False
        
        plugin = self._plugins[plugin_id]
        
        if plugin.status not in (PluginStatus.DISCOVERED, PluginStatus.UNLOADED):
            logger.warning("Plugin %s cannot be loaded (status: %s)", plugin_id, plugin.status.value)
            return False
        
        # Check dependencies
        for dep in plugin.manifest.dependencies:
            if dep not in self._plugins or self._plugins[dep].status != PluginStatus.ENABLED:
                logger.error("Plugin %s missing dependency: %s", plugin_id, dep)
                plugin.status = PluginStatus.ERROR
                plugin.error_message = f"Missing dependency: {dep}"
                self._stats["total_errors"] += 1
                return False
        
        try:
            # Load module
            plugin_path = Path(plugin.path)
            module_path = plugin_path / "plugin.py"
            
            spec = importlib.util.spec_from_file_location(f"plugin_{plugin_id}", module_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"plugin_{plugin_id}"] = module
            spec.loader.exec_module(module)
            
            plugin.module = module
            plugin.status = PluginStatus.LOADED
            plugin.loaded_at = datetime.now(timezone.utc).isoformat()
            
            self._stats["total_loaded"] += 1
            
            # Call lifecycle callbacks
            self._call_lifecycle_callbacks("on_load", plugin)
            
            logger.info("Plugin loaded: %s", plugin_id)
            
            return True
            
        except Exception as exc:
            logger.exception("Failed to load plugin %s: %s", plugin_id, exc)
            plugin.status = PluginStatus.ERROR
            plugin.error_message = str(exc)
            self._stats["total_errors"] += 1
            return False
    
    def enable_plugin(self, plugin_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """Enable a plugin."""
        if plugin_id not in self._plugins:
            return False
        
        plugin = self._plugins[plugin_id]
        
        if plugin.status != PluginStatus.LOADED:
            if not self.load_plugin(plugin_id):
                return False
        
        try:
            # Set config
            plugin.config = config or {}
            
            # Call plugin enable hook if exists
            if hasattr(plugin.module, "on_enable"):
                plugin.module.on_enable(plugin.config)
            
            # Register hooks
            self._register_plugin_hooks(plugin)
            
            plugin.status = PluginStatus.ENABLED
            plugin.enabled_at = datetime.now(timezone.utc).isoformat()
            
            self._stats["total_enabled"] += 1
            
            # Call lifecycle callbacks
            self._call_lifecycle_callbacks("on_enable", plugin)
            
            logger.info("Plugin enabled: %s", plugin_id)
            
            return True
            
        except Exception as exc:
            logger.exception("Failed to enable plugin %s: %s", plugin_id, exc)
            plugin.status = PluginStatus.ERROR
            plugin.error_message = str(exc)
            self._stats["total_errors"] += 1
            return False
    
    def disable_plugin(self, plugin_id: str) -> bool:
        """Disable a plugin."""
        if plugin_id not in self._plugins:
            return False
        
        plugin = self._plugins[plugin_id]
        
        if plugin.status != PluginStatus.ENABLED:
            return False
        
        try:
            # Call plugin disable hook if exists
            if hasattr(plugin.module, "on_disable"):
                plugin.module.on_disable()
            
            # Unregister hooks
            self._unregister_plugin_hooks(plugin)
            
            plugin.status = PluginStatus.DISABLED
            plugin.enabled_at = None
            
            # Call lifecycle callbacks
            self._call_lifecycle_callbacks("on_disable", plugin)
            
            logger.info("Plugin disabled: %s", plugin_id)
            
            return True
            
        except Exception as exc:
            logger.exception("Failed to disable plugin %s: %s", plugin_id, exc)
            return False
    
    def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a plugin."""
        if plugin_id not in self._plugins:
            return False
        
        plugin = self._plugins[plugin_id]
        
        # Disable first if enabled
        if plugin.status == PluginStatus.ENABLED:
            self.disable_plugin(plugin_id)
        
        if plugin.status not in (PluginStatus.LOADED, PluginStatus.DISABLED, PluginStatus.ERROR):
            return False
        
        try:
            # Call plugin unload hook if exists
            if hasattr(plugin.module, "on_unload"):
                plugin.module.on_unload()
            
            # Remove from sys.modules
            module_name = f"plugin_{plugin_id}"
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            plugin.module = None
            plugin.status = PluginStatus.UNLOADED
            plugin.loaded_at = None
            
            # Call lifecycle callbacks
            self._call_lifecycle_callbacks("on_unload", plugin)
            
            logger.info("Plugin unloaded: %s", plugin_id)
            
            return True
            
        except Exception as exc:
            logger.exception("Failed to unload plugin %s: %s", plugin_id, exc)
            return False
    
    def _register_plugin_hooks(self, plugin: Plugin) -> None:
        """Register hooks from plugin."""
        module = plugin.module
        
        # Check for hook handlers
        hook_map = {
            "on_startup": PluginHook.ON_STARTUP,
            "on_shutdown": PluginHook.ON_SHUTDOWN,
            "on_config_load": PluginHook.ON_CONFIG_LOAD,
            "on_event": PluginHook.ON_EVENT,
            "on_request": PluginHook.ON_REQUEST,
            "on_response": PluginHook.ON_RESPONSE,
            "on_error": PluginHook.ON_ERROR,
        }
        
        for hook_name, hook_type in hook_map.items():
            if hasattr(module, hook_name):
                handler = getattr(module, hook_name)
                hook_id = f"{plugin.plugin_id}:{hook_name}"
                
                registration = HookRegistration(
                    hook_id=hook_id,
                    hook_type=hook_type,
                    plugin_id=plugin.plugin_id,
                    handler=handler,
                )
                
                hook_key = hook_type.value
                if hook_key not in self._hooks:
                    self._hooks[hook_key] = []
                self._hooks[hook_key].append(registration)
                
                plugin.hooks_registered[hook_key] = plugin.hooks_registered.get(hook_key, []) + [handler]
    
    def _unregister_plugin_hooks(self, plugin: Plugin) -> None:
        """Unregister hooks from plugin."""
        for hook_key, handlers in list(plugin.hooks_registered.items()):
            if hook_key in self._hooks:
                self._hooks[hook_key] = [
                    h for h in self._hooks[hook_key]
                    if h.plugin_id != plugin.plugin_id
                ]
        
        plugin.hooks_registered.clear()
    
    def _call_lifecycle_callbacks(self, callback_type: str, plugin: Plugin) -> None:
        """Call lifecycle callbacks."""
        for callback in self._lifecycle_callbacks.get(callback_type, []):
            try:
                callback(plugin)
            except Exception as exc:
                logger.exception("Lifecycle callback failed: %s", exc)
    
    def register_lifecycle_callback(self, callback_type: str,
                                   callback: Callable[[Plugin], None]) -> bool:
        """Register lifecycle callback."""
        if callback_type not in self._lifecycle_callbacks:
            return False
        
        self._lifecycle_callbacks[callback_type].append(callback)
        return True
    
    def trigger_hook(self, hook_type: str, *args, **kwargs) -> List[Any]:
        """Trigger a hook and collect results."""
        if hook_type not in self._hooks:
            return []
        
        results = []
        
        # Sort by priority (higher first)
        hooks = sorted(self._hooks[hook_type], key=lambda h: h.priority, reverse=True)
        
        for hook in hooks:
            try:
                result = hook.handler(*args, **kwargs)
                if result is not None:
                    results.append(result)
            except Exception as exc:
                logger.exception("Hook %s failed: %s", hook.hook_id, exc)
        
        return results
    
    def get_plugin(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get plugin info."""
        if plugin_id not in self._plugins:
            return None
        
        return self._plugins[plugin_id].to_dict()
    
    def get_all_plugins(self, status: Optional[PluginStatus] = None) -> List[Dict[str, Any]]:
        """Get all plugins."""
        plugins = list(self._plugins.values())
        
        if status:
            plugins = [p for p in plugins if p.status == status]
        
        return [p.to_dict() for p in plugins]
    
    def get_enabled_plugins(self) -> List[Dict[str, Any]]:
        """Get enabled plugins."""
        return self.get_all_plugins(PluginStatus.ENABLED)
    
    def register_plugin(self, plugin_id: str, manifest: Dict[str, Any],
                       module: Any = None) -> bool:
        """Register a plugin programmatically."""
        if plugin_id in self._plugins:
            return False
        
        plugin_manifest = PluginManifest(
            plugin_id=manifest.get("plugin_id", plugin_id),
            name=manifest.get("name", plugin_id),
            version=manifest.get("version", "0.0.0"),
            description=manifest.get("description", ""),
            dependencies=manifest.get("dependencies", []),
            hooks=manifest.get("hooks", []),
        )
        
        plugin = Plugin(
            plugin_id=plugin_id,
            manifest=plugin_manifest,
            module=module,
            status=PluginStatus.LOADED if module else PluginStatus.DISCOVERED,
            loaded_at=datetime.now(timezone.utc).isoformat() if module else None,
        )
        
        self._plugins[plugin_id] = plugin
        
        if module:
            self._stats["total_loaded"] += 1
        
        logger.info("Plugin registered: %s", plugin_id)
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get plugin statistics."""
        by_status = {}
        for plugin in self._plugins.values():
            status = plugin.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            **self._stats,
            "by_status": by_status,
            "total_hooks": sum(len(h) for h in self._hooks.values()),
            "hook_types": len(self._hooks),
        }
    
    def get_hooks(self, hook_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get registered hooks."""
        hooks = []
        
        for htype, hook_list in self._hooks.items():
            if hook_type and htype != hook_type:
                continue
            
            hooks.extend([h.to_dict() for h in hook_list])
        
        return hooks
    
    def validate_plugin_dependencies(self, plugin_id: str) -> Dict[str, Any]:
        """Validate plugin dependencies."""
        if plugin_id not in self._plugins:
            return {"valid": False, "errors": ["Plugin not found"]}
        
        plugin = self._plugins[plugin_id]
        errors = []
        missing = []
        
        for dep in plugin.manifest.dependencies:
            if dep not in self._plugins:
                missing.append(dep)
                errors.append(f"Missing dependency: {dep}")
            elif self._plugins[dep].status != PluginStatus.ENABLED:
                errors.append(f"Dependency not enabled: {dep}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "missing": missing,
        }


def create_plugin_engine(plugin_dirs: Optional[List[str]] = None) -> PluginEngine:
    """Factory function to create plugin engine."""
    return PluginEngine(plugin_dirs=plugin_dirs)
