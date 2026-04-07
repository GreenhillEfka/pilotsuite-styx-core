"""Plugin API Hooks — the interface through which the core invokes plugin logic."""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from .engine import PluginEngine, PluginHook

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Hook registry (singleton, shared with the global engine)
# ------------------------------------------------------------------


class HookContext:
    """Carries contextual information through a hook chain."""

    def __init__(
        self,
        hook_type: str,
        source: str = "core",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self.hook_type = hook_type
        self.source = source
        self.metadata: dict[str, Any] = metadata or {}
        self._results: list[Any] = []

    def add_result(self, result: Any) -> None:
        self._results.append(result)

    @property
    def results(self) -> list[Any]:
        return list(self._results)


# ------------------------------------------------------------------
# Core-invoked hook emitters
# ------------------------------------------------------------------

def emit_startup(engine: PluginEngine) -> list[Any]:
    """Called once when PilotSuite core starts."""
    return engine.trigger_hook(PluginHook.ON_STARTUP)


def emit_shutdown(engine: PluginEngine) -> list[Any]:
    """Called once when PilotSuite core is shutting down."""
    return engine.trigger_hook(PluginHook.ON_SHUTDOWN)


def emit_config_load(engine: PluginEngine, config: dict[str, Any]) -> list[Any]:
    """Called whenever the core configuration is reloaded."""
    return engine.trigger_hook(PluginHook.ON_CONFIG_LOAD, config)


def emit_event(engine: PluginEngine, event: dict[str, Any]) -> list[Any]:
    """Called for every Home Assistant event ingested by the core."""
    return engine.trigger_hook(PluginHook.ON_EVENT, event)


def emit_request(engine: PluginEngine, request: dict[str, Any]) -> list[Any]:
    """Called before the core handles an incoming API request."""
    return engine.trigger_hook(PluginHook.ON_REQUEST, request)


def emit_response(
    engine: PluginEngine,
    response: dict[str, Any],
    request: Optional[dict[str, Any]] = None,
) -> list[Any]:
    """Called after the core produces an API response."""
    payload = {"response": response}
    if request is not None:
        payload["request"] = request
    return engine.trigger_hook(PluginHook.ON_RESPONSE, payload)


def emit_error(
    engine: PluginEngine,
    error: Exception,
    context: Optional[dict[str, Any]] = None,
) -> list[Any]:
    """Called when the core encounters an error."""
    return engine.trigger_hook(
        PluginHook.ON_ERROR,
        {"error": str(error), "type": type(error).__name__, "context": context or {}},
    )


# ------------------------------------------------------------------
# Decorator-based hook registration helpers
# ------------------------------------------------------------------

_HOOK_DECORATORS: dict[str, Callable[[Callable], Callable]] = {}


def hook(
    hook_type: str | PluginHook,
    *,
    priority: int = 0,
    plugin_id: str = "runtime",
) -> Callable[[Callable], Callable]:
    """Decorator that registers a function as a plugin hook handler.

    Usage::

        @hook(PluginHook.ON_STARTUP)
        def my_startup_handler():
            print("Core is starting!")

        @hook("on_event", priority=10)
        def high_priority_event_handler(event):
            return {"handled": True}
    """

    def decorator(func: Callable) -> Callable:
        func._pilot_hook_type = hook_type  # type: ignore[attr-defined]
        func._pilot_hook_priority = priority  # type: ignore[attr-defined]
        func._pilot_hook_plugin_id = plugin_id  # type: ignore[attr-defined]
        return func

    return decorator


def register_decorated_hooks(
    engine: PluginEngine,
    module: Any,
    plugin_id: str,
) -> None:
    """Scan a module for ``@hook``-decorated functions and register them."""
    for name in dir(module):
        if name.startswith("_"):
            continue
        attr = getattr(module, name)
        if not callable(attr):
            continue
        hook_type = getattr(attr, "_pilot_hook_type", None)
        if hook_type is None:
            continue

        priority = getattr(attr, "_pilot_hook_priority", 0)
        engine.register_hook(
            hook_type,
            attr,
            priority=priority,
            plugin_id=plugin_id,
        )
        logger.debug(
            "Registered decorated hook %s (%s) priority=%d for plugin %s",
            name,
            hook_type,
            priority,
            plugin_id,
        )


# ------------------------------------------------------------------
# Built-in plugin API surface (what plugins can import/use)
# ------------------------------------------------------------------

class PluginAPI:
    """The canonical API surface exposed to plugins.

    Plugins receive an instance of this class as the ``pilot`` argument
    in their ``on_enable(config)`` call.
    """

    def __init__(self, engine: PluginEngine, plugin_id: str) -> None:
        self._engine = engine
        self._plugin_id = plugin_id

    # --- Lifecycle ---------------------------------------------------------
    def get_config(self) -> dict[str, Any]:
        """Return this plugin's current configuration."""
        return self._engine.get_plugin_config(self._plugin_id) or {}

    def update_config(self, updates: dict[str, Any]) -> bool:
        """Merge updates into this plugin's runtime configuration."""
        return self._engine.update_plugin_config(self._plugin_id, updates)

    def get_status(self) -> str:
        """Return the current plugin status string."""
        plugin = self._engine.get_plugin(self._plugin_id)
        return plugin.get("status", "unknown") if plugin else "unknown"

    # --- Hooks --------------------------------------------------------------
    def emit_event(self, event: dict[str, Any]) -> list[Any]:
        """Emit a synthetic event through the core hook chain."""
        return self._engine.trigger_hook(PluginHook.ON_EVENT, event)

    def register_hook(
        self,
        hook_type: str | PluginHook,
        handler: Callable,
        *,
        priority: int = 0,
    ) -> str:
        """Register a hook handler for this plugin."""
        return self._engine.register_hook(
            hook_type,
            handler,
            priority=priority,
            plugin_id=self._plugin_id,
        )

    def unregister_hook(self, hook_id: str) -> bool:
        """Unregister a previously registered hook by its ID."""
        return self._engine.unregister_hook(hook_id)

    # --- Other plugins ------------------------------------------------------
    def is_plugin_enabled(self, other_plugin_id: str) -> bool:
        """Check whether another plugin is currently enabled."""
        other = self._engine.get_plugin(other_plugin_id)
        if other is None:
            return False
        return other.get("status") in ("active", "enabled")

    def get_enabled_plugins(self) -> list[dict[str, Any]]:
        """Return list of all currently enabled plugins."""
        return self._engine.get_enabled_plugins()
