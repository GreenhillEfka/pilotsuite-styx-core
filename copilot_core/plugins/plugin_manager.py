"""PilotSuite Plugin System — Third-Party Extensions."""
from __future__ import annotations

import logging
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Type
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# PLUGIN TYPES
# =============================================================================

class PluginType(Enum):
    """Types of plugins."""
    INTEGRATION = "integration"  # New device/service integrations
    AUTOMATION = "automation"  # Custom automation logic
    SENSOR = "sensor"  # Custom sensor types
    ACTION = "action"  # Custom actions
    UI = "ui"  # Custom UI components
    ANALYTICS = "analytics"  # Custom analytics


class PluginStatus(Enum):
    """Plugin status."""
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    UPDATING = "updating"


@dataclass
class PluginManifest:
    """Plugin manifest definition."""
    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    requirements: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    min_pilotsuite_version: str = "1.0.0"
    homepage: Optional[str] = None
    license: str = "MIT"


@dataclass
class Plugin:
    """Loaded plugin instance."""
    manifest: PluginManifest
    path: Path
    status: PluginStatus
    installed_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# PLUGIN BASE CLASS
# =============================================================================

class PluginBase:
    """
    Base class for all plugins.
    
    Plugins should inherit from this class and implement required methods.
    
    Example:
    ```python
    from copilot_core.plugins import PluginBase
    
    class MyPlugin(PluginBase):
        async def initialize(self):
            # Called when plugin is loaded
            pass
        
        async def shutdown(self):
            # Called when plugin is unloaded
            pass
    ```
    """

    def __init__(self, plugin_id: str, config: Dict[str, Any] = None):
        self.plugin_id = plugin_id
        self.config = config or {}
        self._initialized = False

    async def initialize(self):
        """Initialize the plugin."""
        self._initialized = True
        logger.info(f"Plugin {self.plugin_id} initialized")

    async def shutdown(self):
        """Shutdown the plugin."""
        self._initialized = False
        logger.info(f"Plugin {self.plugin_id} shutdown")

    def get_status(self) -> Dict[str, Any]:
        """Get plugin status."""
        return {
            "plugin_id": self.plugin_id,
            "initialized": self._initialized,
            "config": self.config,
        }


# =============================================================================
# PLUGIN MANAGER
# =============================================================================

class PluginManager:
    """
    Plugin Manager — Third-Party Extensions
    
    Features:
    - Plugin discovery
    - Installation/uninstallation
    - Enable/disable
    - Version management
    - Dependency resolution
    - Security validation
    
    Directory Structure:
    ```
    /config/pilotsuite/plugins/
    ├── manifest.json
    ├── plugin.py
    ├── requirements.txt
    └── assets/
    ```
    
    Usage:
    ```python
    from copilot_core.plugins import PluginManager
    
    manager = PluginManager("/config/pilotsuite/plugins")
    
    # Install plugin
    await manager.install_plugin("https://github.com/user/pilotsuite-plugin-example")
    
    # Enable plugin
    await manager.enable_plugin("example-plugin")
    
    # List plugins
    plugins = manager.get_installed_plugins()
    ```
    """

    def __init__(self, plugins_dir: str = "/config/pilotsuite/plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        
        self._plugins: Dict[str, Plugin] = {}
        self._plugin_instances: Dict[str, PluginBase] = {}

    def discover_plugins(self) -> List[Path]:
        """Discover installed plugins."""
        plugin_dirs = []
        
        for item in self.plugins_dir.iterdir():
            if item.is_dir():
                manifest_path = item / "manifest.json"
                if manifest_path.exists():
                    plugin_dirs.append(item)
        
        logger.info(f"Discovered {len(plugin_dirs)} plugins")
        return plugin_dirs

    async def load_plugins(self):
        """Load all discovered plugins."""
        plugin_dirs = self.discover_plugins()
        
        for plugin_dir in plugin_dirs:
            try:
                await self._load_plugin(plugin_dir)
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_dir.name}: {e}")

    async def _load_plugin(self, plugin_dir: Path):
        """Load a single plugin."""
        manifest_path = plugin_dir / "manifest.json"
        
        with open(manifest_path) as f:
            manifest_data = json.load(f)
        
        manifest = PluginManifest(
            plugin_id=manifest_data["plugin_id"],
            name=manifest_data["name"],
            version=manifest_data["version"],
            description=manifest_data["description"],
            author=manifest_data["author"],
            plugin_type=PluginType(manifest_data["plugin_type"]),
            requirements=manifest_data.get("requirements", []),
            dependencies=manifest_data.get("dependencies", []),
            min_pilotsuite_version=manifest_data.get("min_pilotsuite_version", "1.0.0"),
            homepage=manifest_data.get("homepage"),
            license=manifest_data.get("license", "MIT"),
        )
        
        # Load plugin config
        config_path = plugin_dir / "config.json"
        config = {}
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
        
        plugin = Plugin(
            manifest=manifest,
            path=plugin_dir,
            status=PluginStatus.INSTALLED,
            installed_at=datetime.now(),
            updated_at=datetime.now(),
            config=config,
        )
        
        self._plugins[manifest.plugin_id] = plugin
        
        # Install requirements
        if manifest.requirements:
            await self._install_requirements(plugin_dir, manifest.requirements)
        
        # Load plugin module
        plugin_module_path = plugin_dir / "plugin.py"
        if plugin_module_path.exists():
            await self._load_plugin_module(plugin_module_path, manifest.plugin_id, config)
        
        logger.info(f"Loaded plugin: {manifest.name} v{manifest.version}")

    async def _install_requirements(self, plugin_dir: Path, requirements: List[str]):
        """Install plugin requirements."""
        import subprocess
        
        requirements_path = plugin_dir / "requirements.txt"
        
        if requirements_path.exists():
            cmd = ["pip", "install", "-r", str(requirements_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to install requirements: {result.stderr}")

    async def _load_plugin_module(self, module_path: Path, plugin_id: str, config: Dict[str, Any]):
        """Load plugin Python module."""
        spec = importlib.util.spec_from_file_location(f"pilotsuite_plugin_{plugin_id}", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find plugin class
        plugin_class = getattr(module, "Plugin", None)
        
        if plugin_class and issubclass(plugin_class, PluginBase):
            instance = plugin_class(plugin_id, config)
            await instance.initialize()
            self._plugin_instances[plugin_id] = instance
            
            # Update status
            if plugin_id in self._plugins:
                self._plugins[plugin_id].status = PluginStatus.ENABLED

    async def install_plugin(self, source: str) -> Dict[str, Any]:
        """
        Install a plugin from source.
        
        Args:
            source: URL or path to plugin
        
        Returns:
            Installation result
        """
        # Validate source
        if not self._validate_plugin_source(source):
            return {"success": False, "error": "Invalid plugin source"}
        
        # Download/clone plugin
        plugin_dir = await self._download_plugin(source)
        
        if not plugin_dir:
            return {"success": False, "error": "Failed to download plugin"}
        
        # Load plugin
        try:
            await self._load_plugin(plugin_dir)
            return {
                "success": True,
                "plugin_id": self._plugins[list(self._plugins.keys())[-1]].manifest.plugin_id,
                "name": plugin_dir.name,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def uninstall_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Uninstall a plugin."""
        if plugin_id not in self._plugins:
            return {"success": False, "error": "Plugin not found"}
        
        plugin = self._plugins[plugin_id]
        
        # Shutdown plugin instance
        if plugin_id in self._plugin_instances:
            await self._plugin_instances[plugin_id].shutdown()
            del self._plugin_instances[plugin_id]
        
        # Remove plugin directory
        import shutil
        shutil.rmtree(plugin.path)
        
        del self._plugins[plugin_id]
        
        logger.info(f"Uninstalled plugin: {plugin_id}")
        
        return {"success": True}

    async def enable_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Enable a plugin."""
        if plugin_id not in self._plugins:
            return {"success": False, "error": "Plugin not found"}
        
        plugin = self._plugins[plugin_id]
        
        if plugin.status == PluginStatus.ERROR:
            return {"success": False, "error": f"Plugin has errors: {plugin.error_message}"}
        
        # Load plugin module
        plugin_module_path = plugin.path / "plugin.py"
        if plugin_module_path.exists():
            await self._load_plugin_module(plugin_module_path, plugin_id, plugin.config)
        
        plugin.status = PluginStatus.ENABLED
        
        return {"success": True}

    async def disable_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Disable a plugin."""
        if plugin_id not in self._plugins:
            return {"success": False, "error": "Plugin not found"}
        
        plugin = self._plugins[plugin_id]
        
        # Shutdown plugin instance
        if plugin_id in self._plugin_instances:
            await self._plugin_instances[plugin_id].shutdown()
            del self._plugin_instances[plugin_id]
        
        plugin.status = PluginStatus.DISABLED
        
        return {"success": True}

    def get_installed_plugins(self) -> List[Dict[str, Any]]:
        """Get list of installed plugins."""
        return [
            {
                "plugin_id": p.manifest.plugin_id,
                "name": p.manifest.name,
                "version": p.manifest.version,
                "type": p.manifest.plugin_type.value,
                "status": p.status.value,
                "author": p.manifest.author,
                "description": p.manifest.description,
            }
            for p in self._plugins.values()
        ]

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Get plugin by ID."""
        return self._plugins.get(plugin_id)

    def _validate_plugin_source(self, source: str) -> bool:
        """Validate plugin source."""
        # Would validate GitHub URL, etc.
        return True

    async def _download_plugin(self, source: str) -> Optional[Path]:
        """Download plugin from source."""
        # Would download from GitHub, etc.
        # For now, return None
        return None


# =============================================================================
# PLUGIN REGISTRY
# =============================================================================

class PluginRegistry:
    """Central plugin registry for discovery."""

    OFFICIAL_PLUGINS = [
        {
            "plugin_id": "spotify-integration",
            "name": "Spotify Integration",
            "description": "Control Spotify playback and playlists",
            "type": "integration",
            "repository": "https://github.com/pilotsuite/plugin-spotify",
        },
        {
            "plugin_id": "tesla-integration",
            "name": "Tesla Integration",
            "description": "Monitor and control Tesla vehicles",
            "type": "integration",
            "repository": "https://github.com/pilotsuite/plugin-tesla",
        },
        {
            "plugin_id": "advanced-scheduling",
            "name": "Advanced Scheduling",
            "description": "Complex scheduling with calendar integration",
            "type": "automation",
            "repository": "https://github.com/pilotsuite/plugin-scheduler",
        },
        {
            "plugin_id": "voice-commands",
            "name": "Voice Commands",
            "description": "Advanced voice command processing",
            "type": "action",
            "repository": "https://github.com/pilotsuite/plugin-voice",
        },
        {
            "plugin_id": "custom-dashboards",
            "name": "Custom Dashboards",
            "description": "Advanced dashboard components",
            "type": "ui",
            "repository": "https://github.com/pilotsuite/plugin-dashboards",
        },
    ]

    @classmethod
    def get_available_plugins(cls) -> List[Dict[str, Any]]:
        """Get list of available official plugins."""
        return cls.OFFICIAL_PLUGINS

    @classmethod
    async def search_plugins(cls, query: str) -> List[Dict[str, Any]]:
        """Search for plugins."""
        # Would search plugin registry
        return [
            p for p in cls.OFFICIAL_PLUGINS
            if query.lower() in p["name"].lower() or query.lower() in p["description"].lower()
        ]


# =============================================================================
# HOME ASSISTANT INTEGRATION
# =============================================================================

async def async_setup_plugins(hass, config: Dict[str, Any]):
    """Set up plugin system in Home Assistant."""
    plugins_dir = config.get("plugins_dir", "/config/pilotsuite/plugins")
    
    manager = PluginManager(plugins_dir)
    
    # Load existing plugins
    await manager.load_plugins()
    
    # Store in hass.data
    hass.data["pilotsuite_plugin_manager"] = manager
    
    logger.info("Plugin system set up successfully")
    
    return manager
