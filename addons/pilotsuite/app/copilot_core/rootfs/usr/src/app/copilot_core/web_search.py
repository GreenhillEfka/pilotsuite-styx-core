"""
Web Search + News + Regional Warning Service for PilotSuite

Provides the LLM assistant (Styx) with live internet access:
  - Web search via DuckDuckGo HTML (no API key)
  - German news aggregation from Tagesschau + Spiegel RSS
  - Regional civil protection warnings via NINA API
  - DWD weather warnings

All results are returned as plain dicts ready for JSON serialization
and/or injection into LLM system prompts.

Design:
  - Thread-safe singleton (double-checked locking)
  - TTL-based in-memory caching (news 15min, warnings 5min)
  - Only stdlib + requests -- no BeautifulSoup, no new deps
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import xml.etree.ElementTree as ET
from html import unescape
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REQUEST_TIMEOUT = 10  # seconds

# DuckDuckGo HTML search endpoint (no API key required)
_DDG_URL = "https://html.duckduckgo.com/html/"

# Default German news RSS feeds
_DEFAULT_NEWS_FEEDS: List[Dict[str, str]] = [
    {
        "name": "Tagesschau",
        "url": "https://www.tagesschau.de/xml/rss2/",
    },
    {
        "name": "Spiegel",
        "url": "https://www.spiegel.de/schlagzeilen/index.rss",
    },
]

# NINA API -- German civil protection warnings
_NINA_WARNINGS_URL = "https://nina.api.proxy.bund.de/api31/warnings/mapData.json"

# DWD weather warnings (returns JSONP, not pure JSON)
_DWD_WARNINGS_URL = (
    "https://www.dwd.de/DWD/warnungen/warnapp/json/warnings.json"
)

# Cache TTLs (seconds)
_NEWS_CACHE_TTL = 15 * 60   # 15 minutes
_WARNINGS_CACHE_TTL = 5 * 60  # 5 minutes

# Regex for stripping HTML tags from snippets
_TAG_RE = re.compile(r"<[^>]+>")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = _TAG_RE.sub("", text)
    return unescape(text).strip()


def _now() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# WebSearchService
# ---------------------------------------------------------------------------

class WebSearchService:
    """Thread-safe singleton providing web search, news and warning access.

    Usage::

        svc = WebSearchService.get_instance(ags_code="091620000000")
        results = svc.search("Home Assistant smart home tips")
        news    = svc.get_news()
        warns   = svc.get_regional_warnings()
        summary = svc.get_warning_summary()
    """

    _instance: Optional["WebSearchService"] = None
    _lock = threading.Lock()

    # -- Singleton -----------------------------------------------------------

    def __init__(
        self,
        ags_code: Optional[str] = None,
        news_feeds: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        self._ags_code = ags_code
        self._news_feeds = news_feeds or list(_DEFAULT_NEWS_FEEDS)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; PilotSuite/1.0; "
                "+https://github.com/pilotsuite)"
            ),
        })

        # Cache storage: (timestamp, data)
        self._news_cache: Optional[tuple[float, dict]] = None
        self._warnings_cache: Optional[tuple[float, dict]] = None
        self._cache_lock = threading.Lock()

        logger.info(
            "WebSearchService initialised  ags=%s  feeds=%d",
            self._ags_code or "(none)",
            len(self._news_feeds),
        )

    @classmethod
    def get_instance(
        cls,
        ags_code: Optional[str] = None,
        news_feeds: Optional[List[Dict[str, str]]] = None,
    ) -> "WebSearchService":
        """Return (or create) the singleton instance.

        On the first call the provided parameters are used for construction.
        Subsequent calls return the existing instance regardless of args.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(
                        ags_code=ags_code,
                        news_feeds=news_feeds,
                    )
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Destroy the singleton (for testing / reconfiguration)."""
        with cls._lock:
            cls._instance = None

    # -- Configuration -------------------------------------------------------

    def set_ags_code(self, ags_code: Optional[str]) -> None:
        """Update the regional code at runtime."""
        self._ags_code = ags_code
        # Invalidate warnings cache so next fetch uses the new code
        with self._cache_lock:
            self._warnings_cache = None
        logger.info("AGS code updated to %s", ags_code or "(none)")

    # -- Web Search ----------------------------------------------------------

    def search(self, query: str, max_results: int = 5) -> dict:
        """Search the web via DuckDuckGo HTML.

        Returns::

            {
                "query": "...",
                "results": [
                    {"title": "...", "url": "...", "snippet": "..."},
                    ...
                ],
                "error": null
            }
        """
        logger.debug("Web search: %r  (max %d)", query, max_results)

        try:
            resp = self._session.post(
                _DDG_URL,
                data={"q": query, "b": ""},
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("DuckDuckGo request failed: %s", exc)
            return {"query": query, "results": [], "error": str(exc)}

        results = self._parse_ddg_html(resp.text, max_results)
        return {"query": query, "results": results, "error": None}

    @staticmethod
    def _parse_ddg_html(html: str, max_results: int) -> List[Dict[str, str]]:
        """Extract search results from DuckDuckGo HTML response.

        The HTML contains result blocks with class ``result__a`` for links
        and ``result__snippet`` for the description text.  We use regex
        rather than a DOM parser to avoid a BeautifulSoup dependency.
        """
        results: List[Dict[str, str]] = []

        # Each result lives inside a <div class="result ..."> block.
        # We split by these blocks and process each one.
        result_blocks = re.split(
            r'<div[^>]*class="[^"]*result\b[^"]*"[^>]*>', html
        )

        for block in result_blocks[1:]:  # skip preamble before first result
            if len(results) >= max_results:
                break

            # Title + URL -- <a class="result__a" href="...">title</a>
            link_match = re.search(
                r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                block,
                re.DOTALL,
            )
            if not link_match:
                continue

            raw_url = link_match.group(1)
            title = _strip_html(link_match.group(2))

            # DuckDuckGo wraps URLs through a redirect; extract the real URL
            # from the uddg= parameter if present.
            uddg_match = re.search(r"uddg=([^&]+)", raw_url)
            if uddg_match:
                url = unquote(uddg_match.group(1))
            else:
                url = raw_url

            # Snippet -- <a class="result__snippet" ...>text</a>
            snippet_match = re.search(
                r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                block,
                re.DOTALL,
            )
            snippet = (
                _strip_html(snippet_match.group(1)) if snippet_match else ""
            )

            if title and url:
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                })

        return results

    # -- News ----------------------------------------------------------------

    def get_news(self, max_items: int = 10) -> dict:
        """Fetch and aggregate news from configured RSS feeds.

        Returns::

            {
                "items": [
                    {
                        "source": "Tagesschau",
                        "title": "...",
                        "link": "...",
                        "description": "...",
                        "pub_date": "..."
                    },
                    ...
                ],
                "fetched_at": 1700000000.0,
                "error": null
            }
        """
        # Check cache
        with self._cache_lock:
            if (
                self._news_cache is not None
                and (_now() - self._news_cache[0]) < _NEWS_CACHE_TTL
            ):
                logger.debug("Returning cached news (%d items)", len(self._news_cache[1]["items"]))
                cached = self._news_cache[1].copy()
                # Apply max_items limit on cached data too
                cached["items"] = cached["items"][:max_items]
                return cached

        logger.debug("Fetching fresh news from %d feeds", len(self._news_feeds))
        all_items: List[Dict[str, str]] = []
        errors: List[str] = []

        for feed in self._news_feeds:
            try:
                resp = self._session.get(
                    feed["url"], timeout=_REQUEST_TIMEOUT
                )
                resp.raise_for_status()
                items = self._parse_rss(resp.text, source_name=feed["name"])
                all_items.extend(items)
            except requests.RequestException as exc:
                msg = f"{feed['name']}: {exc}"
                logger.warning("RSS fetch failed -- %s", msg)
                errors.append(msg)

        # Sort newest first (simple string sort on pubDate is usually OK for
        # RSS date formats, but we try to be robust).
        all_items.sort(key=lambda x: x.get("pub_date", ""), reverse=True)

        result: dict = {
            "items": all_items,
            "fetched_at": _now(),
            "error": "; ".join(errors) if errors else None,
        }

        # Store full result in cache (before applying max_items limit)
        with self._cache_lock:
            self._news_cache = (_now(), result.copy())

        result["items"] = result["items"][:max_items]
        return result

    @staticmethod
    def _parse_rss(xml_text: str, source_name: str) -> List[Dict[str, str]]:
        """Parse an RSS 2.0 feed and return a list of item dicts."""
        items: List[Dict[str, str]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("RSS XML parse error (%s): %s", source_name, exc)
            return items

        # RSS 2.0: <rss><channel><item>...</item></channel></rss>
        # Also handle Atom-style namespaces gracefully.
        for item_elem in root.iter("item"):
            title = (item_elem.findtext("title") or "").strip()
            link = (item_elem.findtext("link") or "").strip()
            description = _strip_html(
                item_elem.findtext("description") or ""
            )
            pub_date = (item_elem.findtext("pubDate") or "").strip()

            items.append({
                "source": source_name,
                "title": title,
                "link": link,
                "description": description,
                "pub_date": pub_date,
            })

        return items

    # -- Regional Warnings ---------------------------------------------------

    def get_regional_warnings(self) -> dict:
        """Fetch NINA + DWD warnings, optionally filtered by AGS region.

        Returns::

            {
                "nina_warnings": [...],
                "dwd_warnings": [...],
                "ags_code": "091620000000" | null,
                "fetched_at": 1700000000.0,
                "error": null
            }
        """
        # Check cache
        with self._cache_lock:
            if (
                self._warnings_cache is not None
                and (_now() - self._warnings_cache[0]) < _WARNINGS_CACHE_TTL
            ):
                logger.debug("Returning cached warnings")
                return self._warnings_cache[1]

        logger.debug("Fetching fresh warnings  ags=%s", self._ags_code or "(none)")
        errors: List[str] = []

        nina = self._fetch_nina_warnings(errors)
        dwd = self._fetch_dwd_warnings(errors)

        result: dict = {
            "nina_warnings": nina,
            "dwd_warnings": dwd,
            "ags_code": self._ags_code,
            "fetched_at": _now(),
            "error": "; ".join(errors) if errors else None,
        }

        with self._cache_lock:
            self._warnings_cache = (_now(), result)

        return result

    def _fetch_nina_warnings(self, errors: List[str]) -> List[dict]:
        """Fetch and filter NINA civil protection warnings."""
        try:
            resp = self._session.get(_NINA_WARNINGS_URL, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            msg = f"NINA request failed: {exc}"
            logger.warning(msg)
            errors.append(msg)
            return []
        except (json.JSONDecodeError, ValueError) as exc:
            msg = f"NINA JSON decode error: {exc}"
            logger.warning(msg)
            errors.append(msg)
            return []

        if not isinstance(data, list):
            logger.warning("NINA response is not a list (type=%s)", type(data).__name__)
            return []

        warnings: List[dict] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue

            # Each entry has an "id", optional "i18nTitle", "severity", etc.
            # and an "areas" list with AGS codes.
            warning = {
                "id": entry.get("id", ""),
                "version": entry.get("version", 0),
                "type": entry.get("type", ""),
                "title": entry.get("i18nTitle", {}).get("de", "")
                    if isinstance(entry.get("i18nTitle"), dict)
                    else str(entry.get("i18nTitle", "")),
                "severity": entry.get("severity", ""),
                "sent": entry.get("sent", ""),
            }

            # Filter by AGS code if configured
            if self._ags_code:
                areas = entry.get("areas", [])
                if not isinstance(areas, list):
                    areas = []
                # Check if any area's AGS matches our configured region
                # AGS matching: our code might be a prefix of the warning's code
                # or vice versa (different granularity levels).
                area_match = False
                for area in areas:
                    if not isinstance(area, dict):
                        continue
                    area_ags = str(area.get("geocode", {}).get("ags", ""))
                    if not area_ags:
                        continue
                    # Prefix matching: either code is a prefix of the other
                    if (
                        area_ags.startswith(self._ags_code[:5])
                        or self._ags_code.startswith(area_ags[:5])
                    ):
                        area_match = True
                        break
                if not area_match:
                    continue

            warnings.append(warning)

        logger.debug(
            "NINA: %d warnings total, %d after filtering",
            len(data),
            len(warnings),
        )
        return warnings

    def _fetch_dwd_warnings(self, errors: List[str]) -> List[dict]:
        """Fetch DWD weather warnings.

        The DWD endpoint returns JSONP wrapped in a callback function::

            warnWetter.loadWarnings({...});

        We strip the wrapper to get pure JSON.
        """
        try:
            resp = self._session.get(_DWD_WARNINGS_URL, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            raw = resp.text.strip()
        except requests.RequestException as exc:
            msg = f"DWD request failed: {exc}"
            logger.warning(msg)
            errors.append(msg)
            return []

        # Strip JSONP callback wrapper
        # Format: warnWetter.loadWarnings(<json>);
        prefix = "warnWetter.loadWarnings("
        suffix = ");"
        if raw.startswith(prefix) and raw.endswith(suffix):
            raw = raw[len(prefix) : -len(suffix)]
        elif raw.startswith(prefix) and raw.endswith(")"):
            # Sometimes the trailing semicolon is missing
            raw = raw[len(prefix) : -1]

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            msg = f"DWD JSON decode error: {exc}"
            logger.warning(msg)
            errors.append(msg)
            return []

        if not isinstance(data, dict):
            logger.warning("DWD response is not a dict (type=%s)", type(data).__name__)
            return []

        # DWD structure: {"time": ..., "warnings": {"<region_key>": [...]}, ...}
        all_warnings_map = data.get("warnings", {})
        if not isinstance(all_warnings_map, dict):
            return []

        warnings: List[dict] = []
        for region_key, region_warnings in all_warnings_map.items():
            if not isinstance(region_warnings, list):
                continue

            # Filter by AGS code if configured:
            # DWD region keys often start with the first digits of the AGS.
            if self._ags_code and not region_key.startswith(self._ags_code[:5]):
                continue

            for w in region_warnings:
                if not isinstance(w, dict):
                    continue
                warnings.append({
                    "region_key": region_key,
                    "region_name": w.get("regionName", ""),
                    "level": w.get("level", 0),
                    "type": w.get("type", 0),
                    "headline": w.get("headline", ""),
                    "description": w.get("description", ""),
                    "event": w.get("event", ""),
                    "start": w.get("start"),
                    "end": w.get("end"),
                    "state": w.get("state", ""),
                    "state_short": w.get("stateShort", ""),
                })

        logger.debug(
            "DWD: %d region groups total, %d warnings after filtering",
            len(all_warnings_map),
            len(warnings),
        )
        return warnings

    # -- Warning Summary (for LLM context) -----------------------------------

    def get_warning_summary(self) -> str:
        """Return a human-readable warning summary suitable for LLM context.

        This is injected into the system prompt so Styx can proactively
        inform the user about active warnings without being asked.

        Returns an empty string if there are no active warnings.
        """
        data = self.get_regional_warnings()

        lines: List[str] = []

        # NINA warnings
        for w in data.get("nina_warnings", []):
            title = w.get("title", "Unbekannte Warnung")
            severity = w.get("severity", "")
            severity_str = f" [{severity}]" if severity else ""
            lines.append(f"- NINA{severity_str}: {title}")

        # DWD weather warnings
        for w in data.get("dwd_warnings", []):
            headline = w.get("headline", "")
            region = w.get("region_name", "")
            level = w.get("level", 0)
            event = w.get("event", "")
            desc = headline or event or "Wetterwarnung"
            region_str = f" ({region})" if region else ""
            lines.append(f"- DWD Stufe {level}{region_str}: {desc}")

        if not lines:
            return ""

        region_label = (
            f" fuer Region {self._ags_code}" if self._ags_code else ""
        )
        header = f"Aktive Warnungen{region_label}:"
        return header + "\n" + "\n".join(lines)
