# copilot_core/plugins/__init__.py
# Plugins module — Plugin system for PilotSuite

from .plugin_base import PluginBase, PluginManager
from .llm_plugin import LLMPlugin
from .react_backend import ReactBackendPlugin

try:  # Optional dependency chain: bs4 is not required for engine-only tests.
    from .search.searxng_client import SearXNGClient
    from .search_plugin import SearchPlugin
except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
    if exc.name != "bs4":
        raise
    SearXNGClient = None
    SearchPlugin = None

__all__ = [
    "PluginBase",
    "PluginManager",
    "SearXNGClient",
    "SearchPlugin",
    "LLMPlugin",
    "ReactBackendPlugin",
]
