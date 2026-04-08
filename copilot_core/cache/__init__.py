"""Cache module for PilotSuite Styx Core.

Provides Redis-based caching with in-memory fallback for API responses.
"""

from .redis_client import RedisClient, get_redis_client, init_redis_client
from .api_cache import APICache, get_api_cache, cached, CacheMetrics

__all__ = [
    "RedisClient",
    "get_redis_client",
    "init_redis_client",
    "APICache",
    "get_api_cache",
    "cached",
    "CacheMetrics",
]
