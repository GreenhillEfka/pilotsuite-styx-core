"""Plugin System — Extensible Architecture, Plugin Marketplace, Lifecycle."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type
from enum import Enum
from pathlib import Path
import importlib
import json

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    """Plugin lifecycle status."""
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    UPDATING = "updating"


class PluginType(Enum):
    """Plugin types."""
    INTEGRATION = "integration"
    AUTOMATION = "automation"
    UI_WIDGET = "ui_widget"
    VOICE_COMMAND = "voice_command"
    ML_MODEL = "ml_model"
    DATA_SOURCE = "data_source"


@dataclass
class PluginManifest:
    """Plugin manifest definition."""
    id: str
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    requirements: List[str] = field(default_factory=list)
    entry_point: str = "main"
    config_schema: Dict[str, Any] = field(default_factory=dict)
    homepage: str = ""
    license: str = "MIT"


@dataclass
class Plugin:
    """Loaded plugin instance."""
    manifest: PluginManifest
    status: PluginStatus
    config: Dict[str, Any] = field(default_factory=dict)
    instance: Optional[Any] = None
    error_message: Optional[str] = None


class PluginSystem:
    """Extensible plugin system for PilotSuite."""

    def __init__(self, plugins_dir: str = "/config/plugins"):
        self._plugins_dir = Path(plugins_dir)
        self._plugins_dir.mkdir(parents=True, exist_ok=True)
        
        self._plugins: Dict[str, Plugin] = {}
        self._hooks: Dict[str, List[Callable]] = {}
        self._plugin_registry: Dict[str, PluginManifest] = {}
        self._marketplace_plugins: List[Dict] = []

    def register_plugin(self, manifest: PluginManifest) -> str:
        """Register a plugin manifest."""
        self._plugin_registry[manifest.id] = manifest
        
        plugin = Plugin(
            manifest=manifest,
            status=PluginStatus.INSTALLED,
        )
        self._plugins[manifest.id] = plugin
        
        logger.info(f"Plugin registered: {manifest.name} v{manifest.version}")
        return manifest.id

    def install_plugin(self, plugin_id: str, config: Optional[Dict] = None) -> bool:
        """Install a plugin."""
        if plugin_id not in self._plugin_registry:
            logger.error(f"Plugin not found: {plugin_id}")
            return False
        
        manifest = self._plugin_registry[plugin_id]
        
        # Create plugin directory
        plugin_dir = self._plugins_dir / plugin_id
        plugin_dir.mkdir(parents=True, exist_ok=True)
        
        # Save manifest
        manifest_path = plugin_dir / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump({
                "id": manifest.id,
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "plugin_type": manifest.plugin_type.value,
            }, f, indent=2)
        
        # Save config
        if config:
            config_path = plugin_dir / "config.json"
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
        
        if plugin_id in self._plugins:
            self._plugins[plugin_id].status = PluginStatus.INSTALLED
            self._plugins[plugin_id].config = config or {}
        
        logger.info(f"Plugin installed: {plugin_id}")
        return True

    def enable_plugin(self, plugin_id: str) -> bool:
        """Enable a plugin."""
        if plugin_id not in self._plugins:
            return False
        
        plugin = self._plugins[plugin_id]
        
        try:
            # Load plugin module
            plugin_dir = self._plugins_dir / plugin_id
            main_path = plugin_dir / f"{plugin.manifest.entry_point}.py"
            
            if main_path.exists():
                # Simulated loading
                # In production, would use importlib
                plugin.instance = {"loaded": True, "path": str(main_path)}
                plugin.status = PluginStatus.ENABLED
                
                # Call on_enable hook
                self._trigger_hook("on_plugin_enable", plugin_id)
                
                logger.info(f"Plugin enabled: {plugin_id}")
                return True
            else:
                plugin.status = PluginStatus.ERROR
                plugin.error_message = "Entry point not found"
                return False
                
        except Exception as e:
            plugin.status = PluginStatus.ERROR
            plugin.error_message = str(e)
            logger.error(f"Failed to enable plugin {plugin_id}: {e}")
            return False

    def disable_plugin(self, plugin_id: str) -> bool:
        """Disable a plugin."""
        if plugin_id not in self._plugins:
            return False
        
        plugin = self._plugins[plugin_id]
        
        try:
            # Call on_disable hook
            self._trigger_hook("on_plugin_disable", plugin_id)
            
            plugin.status = PluginStatus.DISABLED
            plugin.instance = None
            
            logger.info(f"Plugin disabled: {plugin_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disable plugin {plugin_id}: {e}")
            return False

    def uninstall_plugin(self, plugin_id: str) -> bool:
        """Uninstall a plugin."""
        if plugin_id not in self._plugins:
            return False
        
        # Disable first
        self.disable_plugin(plugin_id)
        
        # Remove directory
        plugin_dir = self._plugins_dir / plugin_id
        if plugin_dir.exists():
            import shutil
            shutil.rmtree(plugin_dir)
        
        del self._plugins[plugin_id]
        if plugin_id in self._plugin_registry:
            del self._plugin_registry[plugin_id]
        
        logger.info(f"Plugin uninstalled: {plugin_id}")
        return True

    def register_hook(self, hook_name: str, callback: Callable):
        """Register a hook callback."""
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append(callback)
        logger.info(f"Hook registered: {hook_name}")

    def _trigger_hook(self, hook_name: str, *args, **kwargs):
        """Trigger a hook."""
        if hook_name not in self._hooks:
            return
        
        for callback in self._hooks[hook_name]:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook {hook_name} callback failed: {e}")

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Get plugin by ID."""
        return self._plugins.get(plugin_id)

    def list_plugins(self, status: Optional[PluginStatus] = None) -> List[Dict]:
        """List installed plugins."""
        plugins = self._plugins.values()
        if status:
            plugins = [p for p in plugins if p.status == status]
        
        return [
            {
                "id": p.manifest.id,
                "name": p.manifest.name,
                "version": p.manifest.version,
                "type": p.manifest.plugin_type.value,
                "status": p.status.value,
                "error": p.error_message,
            }
            for p in plugins
        ]

    def search_marketplace(self, query: str) -> List[Dict]:
        """Search plugin marketplace."""
        # Simulated marketplace
        marketplace = [
            {"id": "hue_integration", "name": "Philips Hue Integration", "type": "integration", "rating": 4.8},
            {"id": "spotify_voice", "name": "Spotify Voice Commands", "type": "voice_command", "rating": 4.5},
            {"id": "weather_widget", "name": "Weather Dashboard Widget", "type": "ui_widget", "rating": 4.7},
            {"id": "energy_forecast", "name": "Energy Forecast ML", "type": "ml_model", "rating": 4.6},
            {"id": "telegram_notify", "name": "Telegram Notifications", "type": "integration", "rating": 4.9},
        ]
        
        if query:
            marketplace = [
                p for p in marketplace
                if query.lower() in p["name"].lower() or query.lower() in p["id"].lower()
            ]
        
        return marketplace

    def update_plugin(self, plugin_id: str, new_version: str) -> bool:
        """Update a plugin to a new version."""
        if plugin_id not in self._plugins:
            return False
        
        plugin = self._plugins[plugin_id]
        plugin.status = PluginStatus.UPDATING
        
        # Simulated update
        plugin.manifest.version = new_version
        plugin.status = PluginStatus.ENABLED
        
        logger.info(f"Plugin updated: {plugin_id} to v{new_version}")
        return True

    def get_plugin_config(self, plugin_id: str) -> Optional[Dict]:
        """Get plugin configuration."""
        if plugin_id not in self._plugins:
            return None
        
        config_path = self._plugins_dir / plugin_id / "config.json"
        if not config_path.exists():
            return None
        
        with open(config_path, 'r') as f:
            return json.load(f)

    def save_plugin_config(self, plugin_id: str, config: Dict) -> bool:
        """Save plugin configuration."""
        if plugin_id not in self._plugins:
            return False
        
        config_path = self._plugins_dir / plugin_id / "config.json"
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        self._plugins[plugin_id].config = config
        logger.info(f"Plugin config saved: {plugin_id}")
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get plugin system statistics."""
        by_status = {}
        for p in self._plugins.values():
            status = p.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total_plugins": len(self._plugins),
            "by_status": by_status,
            "hooks_registered": len(self._hooks),
            "plugins_dir": str(self._plugins_dir),
        }


# Global default plugin system
default_plugin_system: Optional[PluginSystem] = None


def init_plugin_system(plugins_dir: str = "/config/plugins") -> PluginSystem:
    """Initialize global plugin system."""
    global default_plugin_system
    default_plugin_system = PluginSystem(plugins_dir)
    return default_plugin_system
