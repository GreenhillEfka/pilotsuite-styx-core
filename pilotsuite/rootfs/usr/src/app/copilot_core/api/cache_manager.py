"""Caching system for API endpoints.

Provides:
- Redis-based caching for frequently accessed endpoints
- Query optimization hints
- Lazy loading support for large responses
- Automatic cache invalidation
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

from flask import request, jsonify

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

_LOGGER = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached entry."""
    data: Any
    timestamp: float
    ttl: int
    hit_count: int = 0
    last_access: float = 0


class CacheManager:
    """Manages API response caching with multiple storage backends."""
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: int = 300,
        max_size: int = 10000
    ):
        """Initialize cache manager.
        
        Args:
            redis_url: Redis connection URL (optional)
            default_ttl: Default time-to-live in seconds
            max_size: Maximum number of cached entries
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._local_cache: Dict[str, CacheEntry] = {}
        self._redis_client = None
        self._redis_key_prefix = "pilotsuite_cache:"
        
        if REDIS_AVAILABLE and redis_url:
            try:
                self._redis_client = redis.from_url(redis_url)
                self._redis_client.ping()
                _LOGGER.info("Redis cache connected successfully")
            except Exception as e:
                _LOGGER.warning(f"Failed to connect to Redis: {e}. Using local cache only.")
    
    def _generate_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate cache key from endpoint and parameters.
        
        Args:
            endpoint: API endpoint path
            params: Request parameters
            
        Returns:
            Hashed cache key string
        """
        key_data = {
            "endpoint": endpoint,
            "params": dict(sorted(params.items()))
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def _compress_data(self, data: Any) -> bytes:
        """Compress data for storage.
        
        Args:
            data: Data to compress
            
        Returns:
            Compressed bytes
        """
        return pickle.dumps(data)
    
    def _decompress_data(self, data: bytes) -> Any:
        """Decompress stored data.
        
        Args:
            data: Compressed bytes
            
        Returns:
            Decompressed data
        """
        return pickle.loads(data)
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value by key.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None if not found/expired
        """
        full_key = f"{self._redis_key_prefix}{key}"
        
        # Try Redis first
        if self._redis_client:
            try:
                cached = self._redis_client.get(full_key)
                if cached:
                    entry = self._decompress_data(cached)
                    entry.hit_count += 1
                    entry.last_access = time.time()
                    return entry.data
            except Exception as e:
                _LOGGER.warning(f"Redis GET error: {e}")
        
        # Fall back to local cache
        if key in self._local_cache:
            entry = self._local_cache[key]
            if time.time() - entry.timestamp < entry.ttl:
                entry.hit_count += 1
                entry.last_access = time.time()
                return entry.data
            else:
                del self._local_cache[key]
        
        return None
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """Store data in cache.
        
        Args:
            key: Cache key
            data: Data to cache
            ttl: Time-to-live in seconds (default from constructor)
            
        Returns:
            True if successful
        """
        ttl = ttl or self.default_ttl
        full_key = f"{self._redis_key_prefix}{key}"
        entry = CacheEntry(data=data, timestamp=time.time(), ttl=ttl)
        
        # Try Redis first
        if self._redis_client:
            try:
                compressed = self._compress_data(entry)
                self._redis_client.setex(full_key, ttl, compressed)
                _LOGGER.debug(f"Cached to Redis: {key}")
                return True
            except Exception as e:
                _LOGGER.warning(f"Redis SET error: {e}")
        
        # Use local cache
        if len(self._local_cache) >= self.max_size:
            self._evict_oldest()
        
        self._local_cache[key] = entry
        _LOGGER.debug(f"Cached locally: {key}")
        return True
    
    def delete(self, key: str) -> bool:
        """Delete entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted
        """
        full_key = f"{self._redis_key_prefix}{key}"
        
        if self._redis_client:
            try:
                self._redis_client.delete(full_key)
            except Exception as e:
                _LOGGER.warning(f"Redis DELETE error: {e}")
        
        if key in self._local_cache:
            del self._local_cache[key]
        
        return True
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all cache entries matching pattern.
        
        Args:
            pattern: Pattern to match (supports * wildcard)
            
        Returns:
            Number of entries invalidated
        """
        count = 0
        
        # Invalidate Redis
        if self._redis_client:
            try:
                full_pattern = f"{self._redis_key_prefix}{pattern}"
                keys = self._redis_client.keys(full_pattern)
                if keys:
                    count += self._redis_client.delete(*keys)
            except Exception as e:
                _LOGGER.warning(f"Redis INVALIDATE error: {e}")
        
        # Invalidate local cache
        import fnmatch
        keys_to_delete = [k for k in self._local_cache if fnmatch.fnmatch(k, pattern)]
        for key in keys_to_delete:
            del self._local_cache[key]
            count += 1
        
        return count
    
    def _evict_oldest(self) -> None:
        """Remove oldest cache entries."""
        if not self._local_cache:
            return
        
        oldest_key = min(
            self._local_cache.keys(),
            key=lambda k: self._local_cache[k].last_access or self._local_cache[k].timestamp
        )
        del self._local_cache[oldest_key]
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        stats = {
            "local_size": len(self._local_cache),
            "local_hits": sum(e.hit_count for e in self._local_cache.values()),
        }
        
        if self._redis_client:
            try:
                keys = self._redis_client.keys(f"{self._redis_key_prefix}*")
                stats["redis_size"] = len(keys)
            except Exception:
                _LOGGER.debug("Failed to get Redis cache stats", exc_info=True)
        
        return stats


def cached(
    ttl: Optional[int] = None,
    key_prefix: str = "",
    skip_if: Optional[Callable[[Dict[str, Any]], bool]] = None
) -> Callable:
    """Decorator for caching API endpoint responses.
    
    Args:
        ttl: Time-to-live in seconds (default from CacheManager)
        key_prefix: Prefix for cache keys
        skip_if: Function that returns True if caching should be skipped
        
    Returns:
        Decorated function
    """
    cache_manager: Optional[CacheManager] = None
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal cache_manager
            
            # Initialize cache manager on first use
            if cache_manager is None:
                try:
                    from copilot_core.app import get_app
                    app = get_app()
                    cache_manager = getattr(app, '_cache_manager', None)
                    if cache_manager is None:
                        cache_manager = CacheManager()
                except Exception:
                    cache_manager = CacheManager()
            
            # Check if caching should be skipped
            if skip_if and skip_if(kwargs):
                return func(*args, **kwargs)
            
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{hashlib.md5(str(kwargs).encode()).hexdigest()}"
            
            # Try to get from cache
            cached_data = cache_manager.get(cache_key)
            if cached_data is not None:
                _LOGGER.debug(f"Cache hit: {cache_key}")
                return cached_data
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            _LOGGER.debug(f"Cache miss, stored: {cache_key}")
            
            return result
        
        wrapper.__cache_manager = cache_manager  # type: ignore
        return wrapper
    
    return decorator


def lazy_load(data: List[Any], page: int = 1, page_size: int = 100) -> Dict[str, Any]:
    """Implement lazy loading for large datasets.
    
    Args:
        data: Full dataset
        page: Page number (1-indexed)
        page_size: Number of items per page
        
    Returns:
        Dictionary with paginated data and metadata
    """
    total_items = len(data)
    total_pages = (total_items + page_size - 1) // page_size
    
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)
    
    return {
        "data": data[start_idx:end_idx],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_previous": page > 1,
            "has_next": page < total_pages,
        }
    }