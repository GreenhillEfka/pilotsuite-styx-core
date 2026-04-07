# copilot_core/plugins/__init__.py
# Plugins module — PilotSuite plugin system for third-party extensibility.

from .API import HookContext, PluginAPI, emit_config_load, emit_error, emit_event, emit_request, emit_response, emit_shutdown, emit_startup, hook, register_decorated_hooks
from .engine import (
    DiscoveryResult,
    HookRegistration,
    Plugin,
    PluginEngine,
    PluginHook,
    PluginManifest,
    PluginStatus,
    create_plugin_engine,
)
from .loader import PluginLoadError, PluginLoader
from .plugin_base import PluginBase, PluginManager
from .plugin_manager import PluginManager as PluginLifecycleManager
from .sandbox import PluginSandbox, SandboxConfig, get_sandbox, register_sandbox, unregister_sandbox
from .store import PluginRecord, PluginStore

# Optional plugins — loaded lazily to avoid breaking the core when
# their third-party dependencies (requests, bs4, etc.) are absent.
_LLMPlugin = _ReactBackendPlugin = _SearXNGClient = _SearchPlugin = None

try:
    from .llm_plugin import LLMPlugin as _LLMPlugin
except ModuleNotFoundError:
    pass

try:
    from .react_backend import ReactBackendPlugin as _ReactBackendPlugin
except ModuleNotFoundError:
    pass

try:
    from .search.searxng_client import SearXNGClient as _SearXNGClient
    from .search_plugin import SearchPlugin as _SearchPlugin
except ModuleNotFoundError:
    pass

LLMPlugin = _LLMPlugin
ReactBackendPlugin = _ReactBackendPlugin
SearXNGClient = _SearXNGClient
SearchPlugin = _SearchPlugin

__all__ = [
    # Core engine
    "PluginEngine",
    "PluginStatus",
    "PluginHook",
    "PluginManifest",
    "Plugin",
    "HookRegistration",
    "DiscoveryResult",
    "create_plugin_engine",
    # High-level manager
    "PluginManager",
    "PluginLifecycleManager",
    # Base interface (legacy)
    "PluginBase",
    # Persistence
    "PluginStore",
    "PluginRecord",
    # Loader
    "PluginLoader",
    "PluginLoadError",
    # Sandboxing
    "PluginSandbox",
    "SandboxConfig",
    "get_sandbox",
    "register_sandbox",
    "unregister_sandbox",
    # API helpers
    "PluginAPI",
    "HookContext",
    "emit_startup",
    "emit_shutdown",
    "emit_config_load",
    "emit_event",
    "emit_request",
    "emit_response",
    "emit_error",
    "hook",
    "register_decorated_hooks",
    # Optional plugins (may be None if deps not installed)
    "LLMPlugin",
    "ReactBackendPlugin",
    "SearXNGClient",
    "SearchPlugin",
]
