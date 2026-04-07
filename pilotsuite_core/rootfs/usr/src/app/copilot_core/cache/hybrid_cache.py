"""Hybrid Cache Manager with Redis + Local LRU.

Two-tier caching architecture for high-performance caching:
- Local LRU Cache: Ultra-fast in-memory cache for hot data
- Redis Cache: Shared, persistent cache for distributed systems

Optimized for:
- Sensor data (high-frequency reads, moderate writes)
- RAG search results (expensive to compute, frequently accessed)
- API responses (reduce redundant computations)

Target: >80% cache hit rate
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Generic, TypeVar, Callable

_LOGGER = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with value, timestamp, and access tracking."""
    
    value: T
    created_at: float
    expires_at: float
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    total_requests: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests
    
    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.misses / self.total_requests
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "total_requests": self.total_requests,
            "hit_rate": round(self.hit_rate, 4),
            "miss_rate": round(self.miss_rate, 4),
        }


@dataclass
class HybridCacheConfig:
    """Configuration for hybrid cache manager."""
    
    cache_enabled: bool = True
    default_ttl: int = 300  # 5 minutes
    max_size: int = 1000
    cleanup_interval: int = 60  # seconds
    # Tiered TTL by data type
    ttl_sensor: int = 60       # High-frequency sensor data
    ttl_rag: int = 600         # RAG search results
    ttl_api: int = 300         # API responses
    ttl_config: int = 3600     # Config/metadata
    # Hybrid cache settings
    redis_enabled: bool = True
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: Optional[str] = None
    redis_db: int = 0
    local_cache_size: int = 1000  # Local LRU cache size (increased for hot data)
    write_through: bool = True  # Write to both Redis and local cache
    read_through_local_first: bool = True  # Check local cache before Redis


class HybridCacheManager:
    """Hybrid cache with Redis + Local LRU for high-performance caching.
    
    Architecture:
    - **Local LRU Cache**: Ultra-fast in-memory cache for hot data
    - **Redis Cache**: Shared, persistent cache for distributed systems
    - **Smart Write Policy**: Write-through to both layers
    - **Smart Read Policy**: Check local first, fallback to Redis
    
    Optimized for:
    - Sensor data (high-frequency reads, moderate writes)
    - RAG search results (expensive to compute, frequently accessed)
    - API responses (reduce redundant computations)
    
    Features:
    - Two-tier caching with automatic synchronization
    - Local LRU eviction (configurable size)
    - Redis TTL-based expiration
    - Cache warming on startup
    - Hit/miss metrics per layer
    - Graceful degradation if Redis unavailable
    
    Usage:
        cache = HybridCacheManager(redis_host="localhost", local_cache_size=500)
        await cache.start()
        await cache.set("sensor:temp:1", {"value": 23.5}, ttl=300)
        value = await cache.get("sensor:temp:1")
        await cache.stop()
    """
    
    def __init__(
        self,
        cache_enabled: bool = True,
        default_ttl: int = 300,
        max_size: int = 1000,
        cleanup_interval: int = 60,
        ttl_sensor: int = 60,
        ttl_rag: int = 600,
        ttl_api: int = 300,
        ttl_config: int = 3600,
        redis_enabled: bool = True,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: Optional[str] = None,
        redis_db: int = 0,
        local_cache_size: int = 1000,
        write_through: bool = True,
        read_through_local_first: bool = True,
    ):
        self._config = HybridCacheConfig(
            cache_enabled=cache_enabled,
            default_ttl=default_ttl,
            max_size=max_size,
            cleanup_interval=cleanup_interval,
            ttl_sensor=ttl_sensor,
            ttl_rag=ttl_rag,
            ttl_api=ttl_api,
            ttl_config=ttl_config,
            redis_enabled=redis_enabled,
            redis_host=redis_host,
            redis_port=redis_port,
            redis_password=redis_password,
            redis_db=redis_db,
            local_cache_size=local_cache_size,
            write_through=write_through,
            read_through_local_first=read_through_local_first,
        )
        
        # Local LRU cache
        self._local_cache: OrderedDict[str, CacheEntry[Any]] = OrderedDict()
        self._lock = asyncio.Lock()
        
        # Redis client (lazy initialization)
        self._redis_client: Optional[Any] = None
        self._redis_connected = False
        
        # Metrics (separate for local and redis)
        self._local_metrics = CacheMetrics()
        self._redis_metrics = CacheMetrics()
        self._hybrid_metrics = CacheMetrics()
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._redis_sync_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Key prefix for Redis namespacing
        self._redis_prefix = "pilotsuite:hybrid:"
        
        _LOGGER.info(
            "HybridCacheManager initialized: local_size=%d, redis=%s:%d, ttl=%ds (sensor=%ds, rag=%ds, api=%ds, config=%ds)",
            local_cache_size, redis_host, redis_port, default_ttl, ttl_sensor, ttl_rag, ttl_api, ttl_config
        )
    
    async def _init_redis(self) -> bool:
        """Initialize Redis connection."""
        if not self._config.redis_enabled:
            _LOGGER.debug("Redis disabled in config")
            return False
        
        try:
            # Try to import redis.asyncio
            import redis.asyncio as redis
            
            self._redis_client = redis.Redis(
                host=self._config.redis_host,
                port=self._config.redis_port,
                db=self._config.redis_db,
                password=self._config.redis_password,
                decode_responses=True,
            )
            
            # Test connection
            await self._redis_client.ping()
            self._redis_connected = True
            _LOGGER.info(
                "Redis connected at %s:%d",
                self._config.redis_host, self._config.redis_port
            )
            return True
            
        except ImportError:
            _LOGGER.warning("redis.asyncio not installed, using local cache only")
            self._redis_connected = False
            return False
        except Exception as e:
            _LOGGER.warning("Redis connection failed: %s, using local cache only", e)
            self._redis_connected = False
            return False
    
    async def start(self) -> None:
        """Start hybrid cache with Redis connection and background tasks."""
        if not self._config.cache_enabled:
            return
        
        self._running = True
        
        # Initialize Redis (non-blocking)
        if self._config.redis_enabled:
            await self._init_redis()
        
        # Start background tasks
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        if self._redis_connected:
            self._redis_sync_task = asyncio.create_task(self._redis_sync_loop())
        
        _LOGGER.info(
            "HybridCacheManager started: redis_connected=%s",
            self._redis_connected
        )
    
    async def stop(self) -> None:
        """Stop hybrid cache and cleanup resources."""
        self._running = False
        
        # Cancel background tasks
        for task in [self._cleanup_task, self._redis_sync_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Close Redis connection
        if self._redis_client and self._redis_connected:
            try:
                await self._redis_client.close()
            except Exception:
                pass
        
        self._redis_connected = False
        _LOGGER.info("HybridCacheManager stopped")
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired entries."""
        while self._running:
            try:
                await asyncio.sleep(self._config.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error("Cache cleanup error: %s", e)
    
    async def _cleanup_expired(self) -> int:
        """Remove expired entries from local cache. Returns count of removed entries."""
        now = time.time()
        expired_keys = []
        
        async with self._lock:
            for key, entry in self._local_cache.items():
                if now > entry.expires_at:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._local_cache[key]
                self._local_metrics.expirations += 1
        
        if expired_keys:
            _LOGGER.debug("Cleaned up %d expired cache entries", len(expired_keys))
        
        return len(expired_keys)
    
    async def _redis_sync_loop(self) -> None:
        """Background task to sync local cache stats to Redis."""
        while self._running and self._redis_connected:
            try:
                await asyncio.sleep(self._config.cleanup_interval * 2)
                # Could sync metrics or warm cache here
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error("Redis sync error: %s", e)
    
    async def _evict_local_if_needed(self) -> None:
        """Evict oldest entries from local cache if it exceeds max_size."""
        while len(self._local_cache) >= self._config.local_cache_size:
            oldest_key = next(iter(self._local_cache))
            del self._local_cache[oldest_key]
            self._local_metrics.evictions += 1
            _LOGGER.debug("Evicted local cache entry: %s", oldest_key)
    
    async def _get_from_redis(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        if not self._redis_connected or not self._redis_client:
            return None
        
        try:
            full_key = f"{self._redis_prefix}{key}"
            data = await self._redis_client.get(full_key)
            
            if data:
                self._redis_metrics.hits += 1
                self._redis_metrics.total_requests += 1
                return json.loads(data)
            else:
                self._redis_metrics.misses += 1
                self._redis_metrics.total_requests += 1
                return None
                
        except Exception as e:
            _LOGGER.debug("Redis get error for %s: %s", key, e)
            self._redis_metrics.misses += 1
            self._redis_metrics.total_requests += 1
            return None
    
    async def _set_to_redis(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Set value in Redis."""
        if not self._redis_connected or not self._redis_client:
            return False
        
        try:
            full_key = f"{self._redis_prefix}{key}"
            serialized = json.dumps(value)
            effective_ttl = ttl if ttl is not None else self._config.default_ttl
            
            await self._redis_client.set(full_key, serialized, ex=effective_ttl)
            _LOGGER.debug("Redis set: %s (ttl=%ds)", key, effective_ttl)
            return True
            
        except Exception as e:
            _LOGGER.debug("Redis set error for %s: %s", key, e)
            return False
    
    async def get(self, key: str, default: Any = None) -> Optional[Any]:
        """Get value from hybrid cache (local first, then Redis).
        
        Args:
            key: Cache key
            default: Default value if key not found or expired
            
        Returns:
            Cached value or default
        """
        if not self._config.cache_enabled:
            self._hybrid_metrics.misses += 1
            self._hybrid_metrics.total_requests += 1
            return default
        
        now = time.time()
        
        # Check local cache first (fast path)
        async with self._lock:
            if key in self._local_cache:
                entry = self._local_cache[key]
                
                # Check expiration
                if now > entry.expires_at:
                    del self._local_cache[key]
                    self._local_metrics.expirations += 1
                    self._local_metrics.misses += 1
                    self._local_metrics.total_requests += 1
                else:
                    # Cache hit - update LRU
                    entry.last_accessed = now
                    entry.access_count += 1
                    self._local_cache.move_to_end(key)
                    
                    self._local_metrics.hits += 1
                    self._local_metrics.total_requests += 1
                    self._hybrid_metrics.hits += 1
                    self._hybrid_metrics.total_requests += 1
                    
                    _LOGGER.debug(
                        "Local cache hit: %s (access_count=%d)",
                        key, entry.access_count
                    )
                    return entry.value
        
        # Local miss - check Redis
        if self._redis_connected:
            value = await self._get_from_redis(key)
            
            if value is not None:
                # Populate local cache from Redis (write-back)
                await self._set_local(key, value, ttl=self._config.default_ttl)
                self._hybrid_metrics.hits += 1
                self._hybrid_metrics.total_requests += 1
                return value
        
        # Complete miss
        self._hybrid_metrics.misses += 1
        self._hybrid_metrics.total_requests += 1
        return default
    
    def _get_tier_ttl(self, tier: str) -> int:
        """Get TTL for a specific tier.
        
        Args:
            tier: Cache tier (sensor, rag, api, config)
            
        Returns:
            TTL in seconds for the tier
        """
        tier_map = {
            "sensor": self._config.ttl_sensor,
            "rag": self._config.ttl_rag,
            "api": self._config.ttl_api,
            "config": self._config.ttl_config,
        }
        return tier_map.get(tier.lower(), self._config.default_ttl)
    
    async def _set_local(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tier: Optional[str] = None,
    ) -> None:
        """Set value in local cache only.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Explicit TTL (overrides tier)
            tier: Cache tier for tiered TTL (sensor, rag, api, config)
        """
        now = time.time()
        
        # Determine effective TTL: explicit > tier > default
        if ttl is None and tier is not None:
            ttl = self._get_tier_ttl(tier)
        effective_ttl = ttl if ttl is not None else self._config.default_ttl
        expires_at = now + effective_ttl
        
        async with self._lock:
            # If key exists, remove it first (will re-add at end)
            if key in self._local_cache:
                del self._local_cache[key]
            
            # Evict if needed before adding
            await self._evict_local_if_needed()
            
            entry = CacheEntry(
                value=value,
                created_at=now,
                expires_at=expires_at,
                last_accessed=now,
                access_count=0,
            )
            self._local_cache[key] = entry
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tier: Optional[str] = None,
    ) -> None:
        """Set value in hybrid cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (overrides tier/default)
            tier: Cache tier for tiered TTL (sensor, rag, api, config)
        """
        if not self._config.cache_enabled:
            return
        
        # Write to local cache (always)
        await self._set_local(key, value, ttl, tier)
        
        # Write to Redis (if enabled and write_through)
        if self._config.write_through and self._redis_connected:
            await self._set_to_redis(key, value, ttl)
        
        _LOGGER.debug("Hybrid cache set: %s", key)
    
    async def delete(self, key: str) -> bool:
        """Delete key from hybrid cache.
        
        Returns:
            True if key was deleted, False if not found
        """
        deleted = False
        
        async with self._lock:
            if key in self._local_cache:
                del self._local_cache[key]
                deleted = True
        
        # Delete from Redis too
        if self._redis_connected:
            try:
                full_key = f"{self._redis_prefix}{key}"
                await self._redis_client.delete(full_key)
            except Exception:
                pass
        
        if deleted:
            _LOGGER.debug("Hybrid cache delete: %s", key)
        
        return deleted
    
    async def clear(self) -> None:
        """Clear all cache entries (local and Redis)."""
        async with self._lock:
            self._local_cache.clear()
        
        if self._redis_connected:
            try:
                # Delete all keys with our prefix
                keys = await self._redis_client.keys(f"{self._redis_prefix}*")
                if keys:
                    await self._redis_client.delete(*keys)
            except Exception as e:
                _LOGGER.error("Error clearing Redis cache: %s", e)
        
        _LOGGER.info("Hybrid cache cleared")

    async def clear_by_prefix(self, prefix: str) -> int:
        """Clear cache entries whose keys start with the given prefix.

        Args:
            prefix: Key prefix to match (e.g. "rag:ha_docs:")

        Returns:
            Number of entries deleted
        """
        deleted_count = 0

        # Delete from local cache
        async with self._lock:
            keys_to_delete = [k for k in self._local_cache if k.startswith(prefix)]
            for key in keys_to_delete:
                del self._local_cache[key]
                deleted_count += 1

        # Delete from Redis
        if self._redis_connected:
            try:
                pattern = f"{self._redis_prefix}{prefix}*"
                keys = await self._redis_client.keys(pattern)
                if keys:
                    await self._redis_client.delete(*keys)
                    deleted_count = max(deleted_count, len(keys))
            except Exception as e:
                _LOGGER.error("Error clearing Redis cache by prefix '%s': %s", prefix, e)

        if deleted_count:
            _LOGGER.info("Hybrid cache cleared %d entries with prefix '%s'", deleted_count, prefix)

        return deleted_count

    async def clear_by_pattern(self, pattern: str) -> int:
        """Clear cache entries whose keys contain the given pattern.

        Args:
            pattern: Substring pattern to match anywhere in key

        Returns:
            Number of entries deleted
        """
        import fnmatch

        deleted_count = 0

        # Delete from local cache
        async with self._lock:
            keys_to_delete = [k for k in self._local_cache if fnmatch.fnmatch(k, pattern)]
            for key in keys_to_delete:
                del self._local_cache[key]
                deleted_count += 1

        # Delete from Redis using SCAN + pattern
        if self._redis_connected:
            try:
                redis_pattern = f"{self._redis_prefix}{pattern}"
                keys = await self._redis_client.keys(redis_pattern)
                if keys:
                    await self._redis_client.delete(*keys)
                    deleted_count = max(deleted_count, len(keys))
            except Exception as e:
                _LOGGER.error("Error clearing Redis cache by pattern '%s': %s", pattern, e)

        if deleted_count:
            _LOGGER.info("Hybrid cache cleared %d entries matching '%s'", deleted_count, pattern)

        return deleted_count

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        if not self._config.cache_enabled:
            return False
        
        now = time.time()
        
        # Check local first
        async with self._lock:
            if key in self._local_cache:
                entry = self._local_cache[key]
                if now <= entry.expires_at:
                    return True
        
        # Check Redis
        if self._redis_connected:
            try:
                full_key = f"{self._redis_prefix}{key}"
                ttl = await self._redis_client.ttl(full_key)
                return ttl > 0
            except Exception:
                return False
        
        return False
    
    async def get_or_set(
        self,
        key: str,
        factory: Any,
        ttl: Optional[int] = None,
    ) -> Any:
        """Get value from cache or compute and cache it.
        
        Args:
            key: Cache key
            factory: Async callable to compute value if not cached
            ttl: Time-to-live in seconds
            
        Returns:
            Cached or computed value
        """
        value = await self.get(key)
        if value is not None:
            return value
        
        # Compute value
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()
        
        # Cache it
        await self.set(key, value, ttl=ttl)
        return value
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive cache metrics."""
        async with self._lock:
            return {
                "local": {
                    "size": len(self._local_cache),
                    "max_size": self._config.local_cache_size,
                    "metrics": self._local_metrics.to_dict(),
                },
                "redis": {
                    "connected": self._redis_connected,
                    "host": self._config.redis_host,
                    "port": self._config.redis_port,
                    "metrics": self._redis_metrics.to_dict(),
                },
                "hybrid": {
                    "enabled": self._config.cache_enabled,
                    "write_through": self._config.write_through,
                    "default_ttl": self._config.default_ttl,
                    "metrics": self._hybrid_metrics.to_dict(),
                },
            }
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics (alias for get_metrics)."""
        return await self.get_metrics()
    
    async def warm_cache(
        self,
        keys: list[str],
        loader: Callable[[str], Any],
    ) -> Dict[str, Any]:
        """Warm cache with pre-computed values.
        
        Args:
            keys: List of keys to warm
            loader: Async callable to load value for each key
            
        Returns:
            Dict with warming statistics
        """
        warmed = 0
        failed = 0
        
        for key in keys:
            try:
                if asyncio.iscoroutinefunction(loader):
                    value = await loader(key)
                else:
                    value = loader(key)
                
                await self.set(key, value)
                warmed += 1
            except Exception as e:
                _LOGGER.debug("Failed to warm cache for %s: %s", key, e)
                failed += 1
        
        _LOGGER.info(
            "Cache warming complete: warmed=%d, failed=%d",
            warmed, failed
        )
        
        return {"warmed": warmed, "failed": failed}


# Global cache instances for different use cases (Hybrid)
_sensor_cache: Optional[HybridCacheManager] = None
_habitus_cache: Optional[HybridCacheManager] = None
_rag_cache: Optional[HybridCacheManager] = None


def get_sensor_cache() -> HybridCacheManager:
    """Get or create sensor cache with hybrid Redis + Local LRU (5 min TTL).
    
    Optimized for high-frequency sensor data reads.
    Local cache size: 500 entries
    Target hit rate: >85%
    """
    global _sensor_cache
    if _sensor_cache is None:
        _sensor_cache = HybridCacheManager(
            cache_enabled=True,
            default_ttl=300,  # 5 minutes
            local_cache_size=500,
            cleanup_interval=30,
            redis_enabled=True,
            write_through=True,
        )
    return _sensor_cache


def get_habitus_cache() -> HybridCacheManager:
    """Get or create habitus cache with hybrid Redis + Local LRU (15 min TTL).
    
    Optimized for habitus zone data (moderate frequency).
    Local cache size: 200 entries
    Target hit rate: >80%
    """
    global _habitus_cache
    if _habitus_cache is None:
        _habitus_cache = HybridCacheManager(
            cache_enabled=True,
            default_ttl=900,  # 15 minutes
            local_cache_size=200,
            cleanup_interval=60,
            redis_enabled=True,
            write_through=True,
        )
    return _habitus_cache


def get_rag_cache() -> HybridCacheManager:
    """Get or create RAG cache with hybrid Redis + Local LRU (10 min TTL).
    
    Optimized for RAG search results (expensive to compute).
    Local cache size: 1000 entries
    Target hit rate: >90%
    """
    global _rag_cache
    if _rag_cache is None:
        _rag_cache = HybridCacheManager(
            cache_enabled=True,
            default_ttl=600,  # 10 minutes
            local_cache_size=1000,
            cleanup_interval=45,
            redis_enabled=True,
            write_through=True,
        )
    return _rag_cache


def get_rag_bm25_cache() -> HybridCacheManager:
    """Alias for get_rag_cache() - for BM25 search result caching."""
    return get_rag_cache()


async def init_all_caches() -> None:
    """Initialize and start all hybrid cache managers."""
    for cache in [get_sensor_cache(), get_habitus_cache(), get_rag_cache()]:
        await cache.start()


async def shutdown_all_caches() -> None:
    """Stop all hybrid cache managers."""
    for cache in [get_sensor_cache(), get_habitus_cache(), get_rag_cache()]:
        await cache.stop()
