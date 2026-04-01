"""API Response Caching Layer.

Provides caching for HomeAssistant API responses with configurable TTL,
cache invalidation, and hit/miss metrics.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Optional, Callable
from datetime import datetime
from functools import wraps

from .redis_client import get_redis_client, RedisClient

logger = logging.getLogger(__name__)


class CacheMetrics:
    """Track cache hit/miss metrics."""
    
    def __init__(self):
        self._hits = 0
        self._misses = 0
        self._locks = asyncio.Lock()
    
    async def record_hit(self):
        """Record cache hit."""
        async with self._locks:
            self._hits += 1
    
    async def record_miss(self):
        """Record cache miss."""
        async with self._locks:
            self._misses += 1
    
    async def get_stats(self) -> dict:
        """Get hit/miss statistics."""
        async with self._locks:
            total = self._hits + self._misses
            ratio = self._hits / total if total > 0 else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "total": total,
                "hit_ratio": round(ratio, 3)
            }
    
    async def reset(self):
        """Reset metrics."""
        async with self._locks:
            self._hits = 0
            self._misses = 0


class APICache:
    """Cache layer for API responses.
    
    Features:
    - TTL-based expiration (5 min entities, 1 min states)
    - Automatic cache invalidation
    - Hit/miss metrics
    - JSON serialization
    """
    
    TTL_ENTITY = 300  # 5 minutes
    TTL_STATE = 60    # 1 minute
    TTL_DEFAULT = 120 # 2 minutes
    
    def __init__(self, redis_client: Optional[RedisClient] = None):
        self.redis = redis_client or get_redis_client()
        self.metrics = CacheMetrics()
        self._invalidation_listeners: list[Callable] = []
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Create cache key from arguments."""
        key_parts = [prefix] + [str(a) for a in args]
        if kwargs:
            key_parts.append(json.dumps(kwargs, sort_keys=True))
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        data = await self.redis.get(key)
        if data:
            await self.metrics.record_hit()
            try:
                return json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return data
        else:
            await self.metrics.record_miss()
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Cache value with TTL."""
        try:
            serialized = json.dumps(value)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize value for key {key}: {e}")
            return False
        
        return await self.redis.set(key, serialized, ttl)
    
    async def get_or_set(
        self,
        key: str,
        factory: Callable,
        ttl: Optional[int] = None
    ) -> Any:
        """Get from cache or compute and cache."""
        cached = await self.get(key)
        if cached is not None:
            logger.debug(f"Cache hit for key: {key}")
            return cached
        
        logger.debug(f"Cache miss for key: {key}")
        value = factory() if asyncio.iscoroutinefunction(factory) else factory()
        
        if asyncio.iscoroutine(value):
            value = await value
        
        await self.set(key, value, ttl)
        return value
    
    async def invalidate(self, key: str) -> bool:
        """Invalidate cached key."""
        success = await self.redis.delete(key)
        if success:
            logger.debug(f"Invalidated cache key: {key}")
            await self._notify_invalidation(key)
        return success
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate keys matching pattern."""
        count = await self.redis.delete_pattern(pattern)
        if count > 0:
            logger.info(f"Invalidated {count} keys matching pattern: {pattern}")
        return count
    
    async def invalidate_all(self) -> bool:
        """Clear all cached data."""
        return await self.redis.flush()
    
    async def get_stats(self) -> dict:
        """Get cache statistics."""
        metrics = await self.metrics.get_stats()
        connection = await self.redis.get_stats()
        return {
            **metrics,
            "connection": connection
        }
    
    def register_invalidation_listener(self, callback: Callable):
        """Register callback for cache invalidation events."""
        self._invalidation_listeners.append(callback)
    
    async def _notify_invalidation(self, key: str):
        """Notify listeners of cache invalidation."""
        for callback in self._invalidation_listeners:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(key)
                else:
                    callback(key)
            except Exception as e:
                logger.error(f"Invalidation listener error: {e}")
    
    # Convenience methods for common caching patterns
    
    async def cache_entity_data(
        self,
        entity_id: str,
        data: Any
    ) -> bool:
        """Cache entity data with 5-minute TTL."""
        key = f"entity:{entity_id}"
        return await self.set(key, data, self.TTL_ENTITY)
    
    async def get_entity_data(self, entity_id: str) -> Optional[Any]:
        """Get cached entity data."""
        key = f"entity:{entity_id}"
        return await self.get(key)
    
    async def cache_state(self, entity_id: str, state: Any) -> bool:
        """Cache state with 1-minute TTL."""
        key = f"state:{entity_id}"
        return await self.set(key, state, self.TTL_STATE)
    
    async def get_state(self, entity_id: str) -> Optional[Any]:
        """Get cached state."""
        key = f"state:{entity_id}"
        return await self.get(key)
    
    async def invalidate_entity(self, entity_id: str) -> bool:
        """Invalidate entity cache."""
        return await self.invalidate(f"entity:{entity_id}")
    
    async def invalidate_state(self, entity_id: str) -> bool:
        """Invalidate state cache."""
        return await self.invalidate(f"state:{entity_id}")
    
    async def invalidate_entities(self, pattern: str = "*") -> int:
        """Invalidate all entity caches matching pattern."""
        return await self.invalidate_pattern("entity:*")
    
    async def invalidate_states(self, pattern: str = "*") -> int:
        """Invalidate all state caches matching pattern."""
        return await self.invalidate_pattern("state:*")


# Global instance
_api_cache: Optional[APICache] = None


def get_api_cache() -> APICache:
    """Get or create API cache instance."""
    global _api_cache
    if _api_cache is None:
        _api_cache = APICache()
    return _api_cache


def cached(ttl: Optional[int] = None, key_prefix: str = "api"):
    """Decorator for caching function results.
    
    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache key
    
    Usage:
        @cached(ttl=300, key_prefix="entities")
        async def get_entities():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_api_cache()
            key = cache._make_key(key_prefix, func.__name__, *args, **kwargs)
            
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value
            
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            await cache.set(key, result, ttl)
            return result
        
        return wrapper
    return decorator


async def setup_cache_invalidation(websocket_handler):
    """Setup cache invalidation on WebSocket events.
    
    Args:
        websocket_handler: Handler that can register event listeners
    """
    cache = get_api_cache()
    
    async def on_state_changed(event: dict):
        """Invalidate cache when state changes."""
        entity_id = event.get("entity_id") or event.get("data", {}).get("entity_id")
        if entity_id:
            await cache.invalidate_entity(entity_id)
            await cache.invalidate_state(entity_id)
    
    async def on_entity_added(event: dict):
        """Invalidate entity list cache."""
        await cache.invalidate_pattern("entity:*")
    
    # Register listeners if handler supports it
    if hasattr(websocket_handler, 'register_listener'):
        websocket_handler.register_listener("state_changed", on_state_changed)
        websocket_handler.register_listener("entity_added", on_entity_added)
    
    logger.info("Cache invalidation listeners registered")


async def get_cache_stats() -> dict:
    """Get comprehensive cache statistics.
    
    Returns:
        dict with cache statistics including:
        - total_keys: Number of cached items
        - hits: Cache hit count
        - misses: Cache miss count
        - hit_rate_pct: Cache hit percentage
        - connection: Redis connection status
    """
    cache = get_api_cache()
    
    # Get metrics from cache
    metrics = await cache.metrics.get_stats()
    
    # Get connection stats
    connection = await cache.redis.get_stats()
    
    # Try to get key count from Redis or the fallback store
    total_keys = 0
    try:
        if getattr(cache.redis, "is_connected", True) is False:
            fallback_store = getattr(getattr(cache.redis, "_fallback", None), "_store", None)
            total_keys = len(fallback_store) if isinstance(fallback_store, dict) else metrics.get("total", 0)
        elif getattr(cache.redis, "_redis", None):
            keys = await cache.redis._redis.keys(f"{cache.redis.key_prefix}*")
            total_keys = len(keys)
        else:
            total_keys = metrics.get("total", 0)
    except Exception as e:
        logger.debug(f"Could not get key count: {e}")
        fallback_store = getattr(getattr(cache.redis, "_fallback", None), "_store", None)
        total_keys = len(fallback_store) if isinstance(fallback_store, dict) else metrics.get("total", 0)
    
    return {
        "total_keys": total_keys,
        "hits": metrics["hits"],
        "misses": metrics["misses"],
        "total": metrics["total"],
        "hit_rate_pct": round(metrics["hit_ratio"] * 100, 2),
        "hit_ratio": metrics["hit_ratio"],
        "connection": connection,
        "healthy": connection.get("connected", False) or connection.get("using_fallback", False),
    }
