"""Cache module for PilotSuite Styx Core.

Provides Redis-based caching with in-memory fallback for API responses.
"""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path


__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

_pkg_dir = Path(__file__).resolve().parent
_runtime_pkg_dir = (
    _pkg_dir.parent / "rootfs" / "usr" / "src" / "app" / "copilot_core" / "cache"
)
_runtime_pkg_path = str(_runtime_pkg_dir)

if _runtime_pkg_dir.is_dir() and _runtime_pkg_path not in __path__:
    __path__.append(_runtime_pkg_path)

from .redis_client import RedisClient, get_redis_client, init_redis_client
from .api_cache import APICache, get_api_cache, cached, CacheMetrics
from .engine import CacheEngine, CacheEntry, CacheStats, CacheStrategy, create_cache_engine

__all__ = [
    "RedisClient",
    "get_redis_client",
    "init_redis_client",
    "APICache",
    "get_api_cache",
    "cached",
    "CacheMetrics",
    "CacheEngine",
    "CacheEntry",
    "CacheStats",
    "CacheStrategy",
    "create_cache_engine",
]
