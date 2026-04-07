"""
Plugin Base Interface for PilotSuite.

Every plugin must implement these methods to be compatible with the PluginManager.
"""

from typing import Dict, Any, List, Optional


class PluginBase:
    """Base interface for all PilotSuite plugins."""

    PLUGIN_ID: str = "base"
    PLUGIN_NAME: str = "Base Plugin"
    PLUGIN_VERSION: str = "1.0.0"
    PLUGIN_DESCRIPTION: str = "Base plugin interface"
    PLUGIN_CONFIG_SCHEMA: Dict[str, str] = {}

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", False)

    def execute(self, *args, **kwargs) -> Any:
        """Execute plugin logic. Must be overridden by subclasses."""
        raise NotImplementedError

    def get_status(self) -> Dict[str, Any]:
        """Return plugin status."""
        return {
            "id": self.PLUGIN_ID,
            "name": self.PLUGIN_NAME,
            "version": self.PLUGIN_VERSION,
            "enabled": self.enabled,
        }

    def toggle(self, enabled: bool) -> None:
        """Toggle plugin state."""
        self.enabled = enabled


class PluginManager:
    """Manages all plugins — load, enable, disable, execute."""

    def __init__(self):
        self.plugins: Dict[str, PluginBase] = {}

    def register(self, plugin: PluginBase) -> None:
        """Register a plugin instance."""
        self.plugins[plugin.PLUGIN_ID] = plugin

    def unregister(self, plugin_id: str) -> bool:
        """Unregister a plugin by ID."""
        if plugin_id in self.plugins:
            del self.plugins[plugin_id]
            return True
        return False

    def enable(self, plugin_id: str) -> bool:
        """Enable a plugin by ID."""
        if plugin_id in self.plugins:
            self.plugins[plugin_id].toggle(True)
            return True
        return False

    def disable(self, plugin_id: str) -> bool:
        """Disable a plugin by ID."""
        if plugin_id in self.plugins:
            self.plugins[plugin_id].toggle(False)
            return True
        return False

    def execute(self, plugin_id: str, *args, **kwargs) -> Optional[Any]:
        """Execute a plugin by ID."""
        if plugin_id in self.plugins and self.plugins[plugin_id].enabled:
            return self.plugins[plugin_id].execute(*args, **kwargs)
        return None

    def get_status(self) -> List[Dict[str, Any]]:
        """Return status of all plugins."""
        return [p.get_status() for p in self.plugins.values()]

    def get_config_schema(self, plugin_id: str) -> Optional[Dict[str, str]]:
        """Return config schema for a plugin."""
        if plugin_id in self.plugins:
            return self.plugins[plugin_id].PLUGIN_CONFIG_SCHEMA
        return None
