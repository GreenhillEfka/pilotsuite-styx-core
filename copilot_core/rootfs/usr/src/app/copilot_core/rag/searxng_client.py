"""SearXNG Client for Web Search.

Async client for SearXNG meta-search engine integration.
Uses connection pooling for efficient HTTP requests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiohttp
from copilot_core.connection_pool import get_ollama_session

_LOGGER = logging.getLogger(__name__)

# Default SearXNG categories
DEFAULT_CATEGORIES = ["general", "news", "weather", "science", "it"]


@dataclass(frozen=True)
class SearXNGResult:
    """Search result from SearXNG."""
    
    title: str
    url: str
    content: str
    score: float
    category: Optional[str] = None
    engine: Optional[str] = None
    publishedDate: Optional[str] = None


@dataclass
class SearXNGClient:
    """Async client for SearXNG meta-search engine.
    
    SearXNG is a privacy-respecting meta-search engine that aggregates
    results from multiple search engines (Google, Bing, DuckDuckGo, etc.).
    
    Args:
        base_url: SearXNG instance URL (default: http://localhost:8080)
        timeout: Request timeout in seconds (default: 10)
        categories: Default categories to search
    
    Example:
        ```python
        client = SearXNGClient(base_url="http://localhost:8080")
        results = await client.search("Wetter heute", categories=["weather"])
        for result in results:
            print(f"{result.title}: {result.url}")
        ```
    """
    
    base_url: str = "http://localhost:8080"
    timeout: int = 10
    categories: List[str] = field(default_factory=lambda: DEFAULT_CATEGORIES.copy())
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.base_url:
            raise ValueError("base_url must be provided")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
    
    async def search(
        self,
        query: str,
        categories: Optional[List[str]] = None,
        top_k: int = 10,
        language: str = "de",
    ) -> List[SearXNGResult]:
        """Search SearXNG for a query.
        
        Args:
            query: Search query string
            categories: List of categories to search (e.g., ['general', 'news', 'weather'])
            top_k: Maximum number of results to return
            language: Language code for results (default: 'de')
        
        Returns:
            List of SearXNGResult objects sorted by score
        
        Raises:
            aiohttp.ClientError: If request fails
            TimeoutError: If request times out
        """
        if not query or not query.strip():
            return []
        
        cats = categories if categories is not None else self.categories
        
        # Build SearXNG API URL
        # SearXNG API: /search?q=<query>&format=json&categories=<cat1,cat2>&language=<lang>
        url = f"{self.base_url.rstrip('/')}/search"
        
        params: Dict[str, str] = {
            "q": query.strip(),
            "format": "json",
            "language": language,
        }
        
        if cats:
            params["categories"] = ",".join(cats)
        
        try:
            # Use pooled session for efficient connection reuse
            async with get_ollama_session() as session:
                async with session.get(url, params=params, timeout=self.timeout) as response:
                    if response.status != 200:
                        _LOGGER.warning(
                            "SearXNG search failed with status %d for query: %s",
                            response.status,
                            query,
                        )
                        return []
                    
                    data = await response.json()
                    return self._parse_results(data, top_k)
        
        except aiohttp.ClientError as e:
            _LOGGER.warning("SearXNG client error for query '%s': %s", query, e)
            return []
        except TimeoutError:
            _LOGGER.warning("SearXNG search timed out for query: %s", query)
            return []
        except Exception as e:
            _LOGGER.exception("SearXNG search failed for query: %s", query)
            return []
    
    def _parse_results(
        self,
        data: Dict[str, Any],
        top_k: int,
    ) -> List[SearXNGResult]:
        """Parse SearXNG JSON response into result objects.
        
        Args:
            data: JSON response from SearXNG
            top_k: Maximum number of results to return
        
        Returns:
            List of parsed SearXNGResult objects
        """
        results: List[SearXNGResult] = []
        
        if not data or "results" not in data:
            return results
        
        raw_results = data.get("results", [])
        
        for i, item in enumerate(raw_results[:top_k]):
            if not isinstance(item, dict):
                continue
            
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            content = str(item.get("content", "")).strip()
            
            # Skip results without essential fields
            if not title or not url:
                continue
            
            # Score from SearXNG (higher is better)
            score = float(item.get("score", 0.0))
            
            # If no score provided, use rank-based score
            if score == 0.0:
                score = 1.0 / (i + 1)
            
            results.append(
                SearXNGResult(
                    title=title,
                    url=url,
                    content=content,
                    score=score,
                    category=item.get("category"),
                    engine=item.get("engine"),
                    publishedDate=item.get("publishedDate"),
                )
            )
        
        # Sort by score (descending)
        results.sort(key=lambda r: -r.score)
        
        return results
    
    async def health_check(self) -> bool:
        """Check if SearXNG instance is available.
        
        Returns:
            True if SearXNG is reachable and responding
        """
        try:
            async with get_ollama_session() as session:
                # Try to access the SearXNG instance
                async with session.get(
                    f"{self.base_url.rstrip('/')}/search",
                    params={"q": "test", "format": "json"},
                    timeout=5,
                ) as response:
                    return response.status == 200
        except Exception:
            return False


# Global client instance (lazy initialization)
_searxng_client: Optional[SearXNGClient] = None


def get_searxng_client(
    base_url: Optional[str] = None,
    timeout: int = 10,
) -> SearXNGClient:
    """Get or create global SearXNG client instance.
    
    Args:
        base_url: SearXNG instance URL (optional, uses default if not provided)
        timeout: Request timeout in seconds
    
    Returns:
        SearXNGClient instance
    """
    global _searxng_client
    
    if _searxng_client is None:
        url = base_url or "http://localhost:8080"
        _searxng_client = SearXNGClient(base_url=url, timeout=timeout)
    
    return _searxng_client
