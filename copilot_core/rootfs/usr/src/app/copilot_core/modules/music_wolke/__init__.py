"""Musikwolke Module — Smart Audio Follow through Habitus Zones.

Exports:
- MusicWolkeEngine (singleton)
- PlaybackSession, ZoneMediaState (dataclasses)
- ZoneFavoritesStore
"""

from .engine import MusicWolkeEngine, PlaybackSession, ZoneMediaState, MediaTransfer

try:
    from .sonos_adapter import SonosAdapter
except (ImportError, OSError):
    SonosAdapter = None  # type: ignore

try:
    from .zone_favorites import ZoneFavoritesStore
except (ImportError, OSError):
    ZoneFavoritesStore = None  # type: ignore

__all__ = [
    "MusicWolkeEngine",
    "PlaybackSession",
    "ZoneMediaState",
    "MediaTransfer",
    "SonosAdapter",
    "ZoneFavoritesStore",
]
