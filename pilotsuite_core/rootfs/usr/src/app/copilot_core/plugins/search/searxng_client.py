"""
SearXNG Client for PilotSuite.

Local web search via SearXNG HTML interface (JSON disabled).
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional


class SearXNGClient:
    """SearXNG HTML client — privacy-respecting metasearch for PilotSuite."""

    def __init__(self, base_url: str = "http://192.168.30.18:4041"):
        self.base_url = base_url.rstrip("/")
        self.timeout = 10
        self.max_results = 10

    def search(
        self,
        query: str,
        language: str = "auto",
        safesearch: int = 0,
        categories: List[str] = None,
    ) -> List[Dict]:
        """Search via SearXNG HTML interface and return structured results."""
        if categories is None:
            categories = ["general"]

        url = f"{self.base_url}/search"
        params = {
            "q": query,
            "language": language,
            "safesearch": safesearch,
            "categories": ",".join(categories),
        }
        headers = {"User-Agent": "PilotSuite-Styx/7.9.1"}

        try:
            resp = requests.post(url, data=params, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
        except Exception as e:
            return [{"error": str(e)}]

        results = []
        soup = BeautifulSoup(resp.text, "html.parser")

        for article in soup.find_all("article", class_="result"):
            title_el = article.find("h3")
            link_el = article.find("a", class_="url_header")
            desc_el = article.find("p", class_="content")

            results.append({
                "title": title_el.get_text(strip=True) if title_el else "",
                "url": link_el.get("href", "") if link_el else "",
                "snippet": desc_el.get_text(strip=True) if desc_el else "",
            })

        return results[: self.max_results]

    def search_simple(self, query: str) -> str:
        """Einfache String-Antwort mit Top-Ergebnis für LLM-Prompts."""
        res = self.search(query)
        if not res or res[0].get("error"):
            return f"Keine Suchergebnisse für: {query}"

        top = res[0]
        snippet = top.get("snippet", "")[:200]
        return f"Titel: {top['title']}\nURL: {top['url']}\nSnippet: {snippet}..."
