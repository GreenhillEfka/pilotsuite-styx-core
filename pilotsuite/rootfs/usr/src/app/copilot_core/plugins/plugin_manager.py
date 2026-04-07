"""Plugin Manager — high-level facade tying together engine, store, and loader."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from .API import PluginAPI, emit_config_load, emit_error, emit_event, emit_request, emit_response, emit_shutdown, emit_startup
from .engine import PluginEngine, PluginHook, PluginManifest, PluginStatus
from .loader import PluginLoader
from .sandbox import PluginSandbox, SandboxConfig, register_sandbox, unregister_sandbox
from .store import PluginRecord, PluginStore

logger = logging.getLogger(__name__)


class PluginManager:
    """High-level plugin lifecycle manager.

    Coordinates three sub-systems:
    - **PluginEngine**: discovery, loading, hook dispatch
    - **PluginStore**: persistent registry (enabled state, config, order)
    - **PluginLoader**: dynamic Python module import

    The ``PluginManager`` is the primary interface for the rest of the
    application. It also creates and manages per-plugin ``PluginSandbox``
    instances.
    """

    def __init__(
        self,
        plugin_dirs: list[str | Path] | None = None,
        store_path: str | Path | None = None,
        core_version: str = "1.0.0",
    ) -> None:
        self._engine = PluginEngine(
            plugin_dirs=[str(d) for d in (plugin_dirs or ["plugins", "~/.pilotclaw/plugins"])],
            core_version=core_version,
        )
        self._store = PluginStore(store_path=store_path)
        self._loader = PluginLoader()
        self._core_version = core_version
        self._initialized = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def engine(self) -> PluginEngine:
        """The underlying plugin engine."""
        return self._engine

    @property
    def store(self) -> PluginStore:
        """The persistent plugin store."""
        return self._store

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        """Discover plugins, load the store, and restore enabled state.

        This is the main entry point for the application — call it once at
        startup before handling any requests.
        """
        if self._initialized:
            return

        self._store.load()
        self._engine.discover_plugins()

        # Restore enabled state from store
        for plugin_id in self._store.get_enabled_ids():
            plugin = self._engine._plugins.get(plugin_id)
            if plugin is None:
                continue
            # Restore config from store
            stored = self._store.get(plugin_id)
            if stored:
                plugin.config = dict(stored.config)

        self._initialized = True
        emit_startup(self._engine)
        logger.info("PluginManager initialised")

    def shutdown(self) -> None:
        """Disable all enabled plugins and persist state."""
        emit_shutdown(self._engine)

        for plugin_id in list(self._engine._plugins.keys()):
            if self._engine._is_enabled_status(self._engine._plugins[plugin_id].status):
                self.disable_plugin(plugin_id)

        self._store.save()
        self._initialized = False
        logger.info("PluginManager shut down")

    # ------------------------------------------------------------------
    # Individual plugin lifecycle
    # ------------------------------------------------------------------
    def discover_plugin(self, plugin_dir: str | Path) -> bool:
        """Discover a single plugin in a directory (no file-system scan).

        Returns True if a manifest was found and the plugin was added.
        """
        result = self._engine.discover_plugins()
        return str(plugin_dir) in (p.path for p in self._engine._plugins.values())

    def load_plugin(self, plugin_id: str) -> bool:
        """Load a plugin's Python module into memory."""
        return self._engine.load_plugin(plugin_id)

    def enable_plugin(self, plugin_id: str, config: Optional[dict[str, Any]] = None) -> bool:
        """Enable a plugin (load + register hooks + persist enabled state)."""
        plugin = self._engine._plugins.get(plugin_id)
        if plugin is None:
            logger.error("enable_plugin: unknown plugin %s", plugin_id)
            return False

        # Merge store config with runtime config
        stored_config: dict[str, Any] = {}
        stored = self._store.get(plugin_id)
        if stored:
            stored_config = dict(stored.config)
        if config:
            stored_config.update(config)

        # Create sandbox
        sandbox_config = SandboxConfig(
            plugin_id=plugin_id,
            plugin_dir=plugin.path,
        )
        sandbox = PluginSandbox(sandbox_config)
        sandbox.activate()
        register_sandbox(plugin_id, sandbox)

        # Delegate to engine (engine calls on_enable, registers hooks)
        ok = self._engine.enable_plugin(plugin_id, stored_config)

        if ok:
            self._store.register(
                PluginRecord(
                    plugin_id=plugin_id,
                    name=plugin.manifest.name,
                    version=plugin.manifest.version,
                    enabled=True,
                    config=stored_config,
                    enabled_at=plugin.enabled_at,
                )
            )
            self._store.save()
        else:
            unregister_sandbox(plugin_id)

        return ok

    def disable_plugin(self, plugin_id: str) -> bool:
        """Disable a plugin (unregister hooks + persist disabled state)."""
        ok = self._engine.disable_plugin(plugin_id)
        if ok:
            self._store.set_enabled(plugin_id, False)
            self._store.save()
            sandbox = self._engine._plugins.get(plugin_id)
            if sandbox:
                unregister_sandbox(plugin_id)
        return ok

    def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a plugin and remove it from the registry."""
        self._loader.unload_module(plugin_id)
        unregister_sandbox(plugin_id)
        return self._engine.unload_plugin(plugin_id)

    def remove_plugin(self, plugin_id: str) -> None:
        """Fully remove a plugin (disable + unload + unregister)."""
        self.disable_plugin(plugin_id)
        self.unload_plugin(plugin_id)
        self._engine._plugins.pop(plugin_id, None)
        self._store.unregister(plugin_id)
        self._store.save()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get_plugin(self, plugin_id: str) -> Optional[dict[str, Any]]:
        """Return the full dictionary representation of a plugin."""
        return self._engine.get_plugin(plugin_id)

    def get_all_plugins(self, status: Optional[PluginStatus] = None) -> list[dict[str, Any]]:
        """Return all plugins, optionally filtered by status."""
        return self._engine.get_all_plugins(status=status)

    def get_enabled_plugins(self) -> list[dict[str, Any]]:
        """Return all currently enabled plugins."""
        return self._engine.get_enabled_plugins()

    def get_plugin_config(self, plugin_id: str) -> Optional[dict[str, Any]]:
        """Return the stored configuration for a plugin."""
        return self._engine.get_plugin_config(plugin_id)

    def update_plugin_config(self, plugin_id: str, config: dict[str, Any]) -> bool:
        """Update a plugin's runtime and persisted config."""
        self._store.update_config(plugin_id, config)
        self._store.save()
        return self._engine.update_plugin_config(plugin_id, config)

    def get_plugin_summary(self) -> dict[str, Any]:
        """Return a summary of the plugin system's state."""
        return self._engine.get_plugin_summary()

    def get_statistics(self) -> dict[str, Any]:
        """Return detailed plugin statistics."""
        return self._engine.get_statistics()

    def validate_dependencies(self, plugin_id: str) -> dict[str, Any]:
        """Validate a plugin's dependencies."""
        return self._engine.validate_plugin_dependencies(plugin_id)

    def reload_plugin(self, plugin_id: str) -> bool:
        """Force-reload a plugin's Python module."""
        plugin = self._engine._plugins.get(plugin_id)
        if plugin is None:
            return False
        self._loader.reload_module(plugin_id, plugin.path)
        return True

    # ------------------------------------------------------------------
    # Hook dispatch helpers (delegate to API helpers)
    # ------------------------------------------------------------------
    def on_startup(self) -> list[Any]:
        return emit_startup(self._engine)

    def on_shutdown(self) -> list[Any]:
        return emit_shutdown(self._engine)

    def on_config_load(self, config: dict[str, Any]) -> list[Any]:
        return emit_config_load(self._engine, config)

    def on_event(self, event: dict[str, Any]) -> list[Any]:
        return emit_event(self._engine, event)

    def on_request(self, request: dict[str, Any]) -> list[Any]:
        return emit_request(self._engine, request)

    def on_response(self, response: dict[str, Any], request: Optional[dict[str, Any]] = None) -> list[Any]:
        return emit_response(self._engine, response, request)

    def on_error(self, error: Exception, context: Optional[dict[str, Any]] = None) -> list[Any]:
        return emit_error(self._engine, error, context)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _create_plugin_api(self, plugin_id: str) -> PluginAPI:
        """Create a PluginAPI instance for the given plugin."""
        return PluginAPI(self._engine, plugin_id)
