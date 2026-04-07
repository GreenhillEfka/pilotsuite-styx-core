"""
Search Plugin for PilotSuite — SearXNG integration.

Provides web search via local SearXNG instance.
"""

from typing import List, Dict, Any
from .plugin_base import PluginBase


class SearchPlugin(PluginBase):
    """Search plugin using SearXNG local instance."""

    PLUGIN_ID = "search"
    PLUGIN_NAME = "SearXNG Search"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "Privacy-respecting web search via local SearXNG"
    PLUGIN_CONFIG_SCHEMA = {
        "enabled": "bool",
        "base_url": "str",
        "timeout": "int",
        "max_results": "int",
        "safesearch": "list(0|1|2)",
        "default_language": "str",
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        from .search.searxng_client import SearXNGClient

        self.client = SearXNGClient(
            base_url=config.get("base_url", "http://192.168.30.18:4041")
        )
        self.timeout = config.get("timeout", 10)
        self.max_results = config.get("max_results", 10)
        self.safesearch = config.get("safesearch", 0)
        self.language = config.get("default_language", "auto")

    def execute(
        self,
        query: str,
        language: str = None,
        safesearch: int = None,
        categories: List[str] = None,
    ) -> List[Dict]:
        """Execute search via SearXNG."""
        if not self.enabled:
            return [{"error": "Search plugin disabled"}]

        return self.client.search(
            query=query,
            language=language or self.language,
            safesearch=safesearch if safesearch is not None else self.safesearch,
            categories=categories,
        )

    def search_simple(self, query: str) -> str:
        """Get simple string result for LLM prompts."""
        if not self.enabled:
            return f"Search plugin disabled — enable in config to search for: {query}"

        return self.client.search_simple(query)

    def get_status(self) -> Dict[str, Any]:
        """Return enhanced plugin status."""
        status = super().get_status()
        status.update({
            "base_url": self.client.base_url,
            "timeout": self.timeout,
            "max_results": self.max_results,
            "safesearch": self.safesearch,
            "language": self.language,
        })
        return status
