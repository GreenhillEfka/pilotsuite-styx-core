"""Dynamic Plugin Loader — safely imports and instantiates plugin modules."""
from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PluginLoadError(Exception):
    """Raised when a plugin module fails to load."""


class PluginLoader:
    """Dynamically loads plugin Python modules from disk.

    This loader handles:
    - Importing plugin.py files with ``importlib``
    - Caching loaded modules to avoid repeated imports
    - Clean teardown of loaded modules
    """

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Module loading
    # ------------------------------------------------------------------
    def load_module(self, plugin_id: str, plugin_path: str | Path) -> Any:
        """Load a plugin module from its ``plugin.py`` file.

        The module is cached under ``plugin_{plugin_id}`` in ``sys.modules``.
        Subsequent calls return the cached module.

        Args:
            plugin_id: Unique identifier for this plugin.
            plugin_path: Directory containing the plugin's ``plugin.py`` file.

        Returns:
            The loaded Python module.

        Raises:
            PluginLoadError: If the module cannot be imported.
        """
        module_name = f"plugin_{plugin_id}"

        # Return cached module if already loaded
        if module_name in sys.modules:
            return sys.modules[module_name]

        plugin_path = Path(plugin_path)
        module_file = plugin_path / "plugin.py"

        if not module_file.exists():
            raise PluginLoadError(f"plugin.py not found: {module_file}")

        spec = importlib.util.spec_from_file_location(module_name, module_file)
        if spec is None or spec.loader is None:
            raise PluginLoadError(f"unable to create import spec for {module_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            # Clean up sys.modules on failure
            if module_name in sys.modules:
                del sys.modules[module_name]
            raise PluginLoadError(str(exc)) from exc

        self._cache[module_name] = module
        logger.debug("Plugin module loaded: %s from %s", plugin_id, module_file)
        return module

    def reload_module(self, plugin_id: str, plugin_path: str | Path) -> Any:
        """Force-reload a plugin module, bypassing the cache."""
        module_name = f"plugin_{plugin_id}"

        # Remove cached entry
        if module_name in sys.modules:
            del sys.modules[module_name]
        if module_name in self._cache:
            del self._cache[module_name]

        return self.load_module(plugin_id, plugin_path)

    def unload_module(self, plugin_id: str) -> bool:
        """Remove a plugin module from sys.modules.

        Returns:
            True if the module was present and removed, False otherwise.
        """
        module_name = f"plugin_{plugin_id}"

        if module_name in sys.modules:
            del sys.modules[module_name]

        if module_name in self._cache:
            del self._cache[module_name]

        logger.debug("Plugin module unloaded: %s", plugin_id)
        return True

    def is_loaded(self, plugin_id: str) -> bool:
        """Check whether a plugin module is currently loaded."""
        return f"plugin_{plugin_id}" in sys.modules

    def get_loaded_plugin_ids(self) -> list[str]:
        """Return list of plugin IDs that are currently loaded."""
        return [
            key.replace("plugin_", "")
            for key in sys.modules
            if key.startswith("plugin_")
        ]

    # ------------------------------------------------------------------
    # Manifest discovery helpers
    # ------------------------------------------------------------------
    @staticmethod
    def find_plugin_dirs(search_paths: list[str | Path]) -> list[Path]:
        """Find all directories that look like plugins (contain plugin.py or manifest).

        Args:
            search_paths: List of root directories to scan.

        Returns:
            List of plugin directory paths.
        """
        results: list[Path] = []

        for search_path in search_paths:
            root = Path(search_path).expanduser()
            if not root.exists() or not root.is_dir():
                continue

            for item in root.iterdir():
                if not item.is_dir():
                    continue
                if (item / "plugin.py").exists() or (item / "plugin.json").exists() or (item / "manifest.json").exists():
                    results.append(item)

        return results
