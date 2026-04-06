"""Musikwolke Module — Smart Audio Follow through Habitus Zones.

Consolidated module for:
- Media playback following users between zones
- Zone-specific favorite sources
- Sonos HTTP API integration
- Time-based volume profiles
- Preset management
"""

from .engine import MusicWolkeEngine, PlaybackSession, ZoneMediaState
from .zone_favorites import ZoneFavoritesStore
from .sonos_adapter import SonosAdapter
from .api import init_music_wolke_api

__all__ = [
    "MusicWolkeEngine",
    "PlaybackSession",
    "ZoneMediaState",
    "ZoneFavoritesStore",
    "SonosAdapter",
    "init_music_wolke_api",
]
