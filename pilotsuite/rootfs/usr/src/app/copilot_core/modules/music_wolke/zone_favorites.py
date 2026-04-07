"""Zone Favorites Store — Per-zone music source preferences."""

from __future__ import annotations
import json
import logging
import os
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)
_FAVORITES_FILE = "/data/music_wolke_favorites.json"


class ZoneFavoritesStore:
    """Persistent storage for zone-specific music favorites."""

    def __init__(self, filepath: str = _FAVORITES_FILE):
        self._filepath = filepath
        self._favorites: Dict[str, Dict[str, Any]] = {}
        self._lock = __import__("threading").Lock()
        os.makedirs(os.path.dirname(filepath), exist_ok=True) if filepath != _FAVORITES_FILE else None
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath, "r") as f:
                    self._favorites = json.load(f)
                _LOGGER.debug("Loaded %d zone favorites", len(self._favorites))
            except Exception as e:
                _LOGGER.warning("Failed to load favorites: %s", e)
                self._favorites = {}

    def _save(self) -> None:
        try:
            with open(self._filepath, "w") as f:
                json.dump(self._favorites, f, indent=2)
        except Exception as e:
            _LOGGER.warning("Failed to save favorites: %s", e)

    def get_favorites(self, zone_id: str) -> List[str]:
        with self._lock:
            return list(self._favorites.get(zone_id, {}).get("sources", []))

    def set_favorites(self, zone_id: str, sources: List[str]) -> bool:
        with self._lock:
            if zone_id not in self._favorites:
                self._favorites[zone_id] = {}
            self._favorites[zone_id]["sources"] = sources
            self._save()
            return True

    def get_primary_source(self, zone_id: str) -> Optional[str]:
        with self._lock:
            sources = self._favorites.get(zone_id, {}).get("sources", [])
            return sources[0] if sources else None

    def set_primary_source(self, zone_id: str, source: str) -> bool:
        with self._lock:
            if zone_id not in self._favorites:
                self._favorites[zone_id] = {"sources": []}
            sources = self._favorites[zone_id].get("sources", [])
            if source in sources:
                sources.remove(source)
            sources.insert(0, source)
            self._favorites[zone_id]["sources"] = sources
            self._save()
            return True

    def add_favorite(self, zone_id: str, source: str) -> bool:
        with self._lock:
            if zone_id not in self._favorites:
                self._favorites[zone_id] = {"sources": []}
            sources = self._favorites[zone_id].get("sources", [])
            if source not in sources:
                sources.append(source)
                self._favorites[zone_id]["sources"] = sources
                self._save()
            return True

    def remove_favorite(self, zone_id: str, source: str) -> bool:
        with self._lock:
            if zone_id not in self._favorites:
                return False
            sources = self._favorites[zone_id].get("sources", [])
            if source in sources:
                sources.remove(source)
                self._favorites[zone_id]["sources"] = sources
                self._save()
                return True
            return False

    def get_all_zones(self) -> Dict[str, List[str]]:
        with self._lock:
            return {zid: data.get("sources", []) for zid, data in self._favorites.items()}
