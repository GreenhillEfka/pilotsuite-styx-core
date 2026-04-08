"""
React Backend Plugin — Controls plugin state via web interface.

Provides REST endpoints to enable/disable plugins dynamically.
"""

from typing import Dict, Any, List
from .plugin_base import PluginManager


class ReactBackendPlugin:
    """Web UI plugin controller — REST API for React frontend."""

    def __init__(self, plugin_manager: PluginManager):
        self.manager = plugin_manager

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Return all plugins with status."""
        return self.manager.get_status()

    def enable_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Enable a plugin by ID."""
        if self.manager.enable(plugin_id):
            return {"success": True, "plugin_id": plugin_id, "status": "enabled"}
        return {"success": False, "plugin_id": plugin_id, "error": "Plugin not found"}

    def disable_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Disable a plugin by ID."""
        if self.manager.disable(plugin_id):
            return {"success": True, "plugin_id": plugin_id, "status": "disabled"}
        return {"success": False, "plugin_id": plugin_id, "error": "Plugin not found"}

    def update_config(self, plugin_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Update plugin configuration (placeholder for future implementation)."""
        if plugin_id not in self.manager.plugins:
            return {"success": False, "plugin_id": plugin_id, "error": "Plugin not found"}

        # Merge config (future: persist to config.yaml)
        self.manager.plugins[plugin_id].config.update(config)
        return {"success": True, "plugin_id": plugin_id, "config": config}

    def execute_plugin(self, plugin_id: str, *args, **kwargs) -> Dict[str, Any]:
        """Execute a plugin and return result."""
        result = self.manager.execute(plugin_id, *args, **kwargs)
        if result is None:
            return {"success": False, "plugin_id": plugin_id, "error": "Plugin disabled or not found"}
        return {"success": True, "plugin_id": plugin_id, "result": result}
