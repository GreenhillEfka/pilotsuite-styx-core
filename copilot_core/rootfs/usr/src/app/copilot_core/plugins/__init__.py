# copilot_core/plugins/__init__.py
# Plugins module — Plugin system for PilotSuite

from .plugin_base import PluginBase, PluginManager
from .search.searxng_client import SearXNGClient
from .search_plugin import SearchPlugin
from .llm_plugin import LLMPlugin
from .react_backend import ReactBackendPlugin

__all__ = [
    "PluginBase",
    "PluginManager",
    "SearXNGClient",
    "SearchPlugin",
    "LLMPlugin",
    "ReactBackendPlugin",
]
