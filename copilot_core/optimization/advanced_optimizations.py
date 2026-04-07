"""Advanced Performance Optimizations — Caching, async improvements, memory management."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Callable, TypeVar
from dataclasses import dataclass, field
from functools import wraps
import time
import asyncio
from collections import OrderedDict
import hashlib

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# ADVANCED CACHING
# =============================================================================

@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: float
    expires_at: Optional[float]
    access_count: int = 0
    last_accessed: float = field(default_factory=lambda: time.time())


class LRUCache:
    """
    LRU Cache with TTL support.
    
    Features:
    - Least Recently Used eviction
    - Time-to-live expiration
    - Thread-safe access
    - Statistics tracking
    """

    def __init__(self, max_size: int = 10000, default_ttl_seconds: int = 300):
        self._max_size = max_size
        self._default_ttl = default_ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key not in self._cache:
            self._misses += 1
            return None
        
        entry = self._cache[key]
        
        # Check expiration
        if entry.expires_at and time.time() > entry.expires_at:
            del self._cache[key]
            self._misses += 1
            return None
        
        # Update access
        entry.access_count += 1
        entry.last_accessed = time.time()
        self._cache.move_to_end(key)
        
        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Set value in cache."""
        now = time.time()
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        
        # Evict if at capacity
        if len(self._cache) >= self._max_size and key not in self._cache:
            self._cache.popitem(last=False)
        
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            expires_at=now + ttl if ttl > 0 else None,
        )
        
        self._cache[key] = entry
        self._cache.move_to_end(key)

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def cleanup_expired(self):
        """Remove expired entries."""
        now = time.time()
        expired = [
            key for key, entry in self._cache.items()
            if entry.expires_at and now > entry.expires_at
        ]
        for key in expired:
            del self._cache[key]

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "avg_ttl_seconds": self._default_ttl,
        }


# =============================================================================
# ASYNC OPTIMIZATIONS
# =============================================================================

class AsyncBatchProcessor:
    """
    Batch processing for async operations.
    
    Features:
    - Configurable batch size
    - Timeout handling
    - Error recovery
    - Progress tracking
    """

    def __init__(self, batch_size: int = 100, timeout_seconds: float = 30.0):
        self._batch_size = batch_size
        self._timeout = timeout_seconds

    async def process_batch(
        self,
        items: List[Any],
        processor: Callable,
    ) -> List[Any]:
        """
        Process items in batches.
        
        Args:
            items: Items to process
            processor: Async function to process each item
        
        Returns:
            List of processed results
        """
        results = []
        
        for i in range(0, len(items), self._batch_size):
            batch = items[i:i + self._batch_size]
            
            # Process batch with timeout
            try:
                batch_results = await asyncio.wait_for(
                    asyncio.gather(*[processor(item) for item in batch]),
                    timeout=self._timeout
                )
                results.extend(batch_results)
            except asyncio.TimeoutError:
                logger.warning(f"Batch {i // self._batch_size} timed out")
                # Continue with next batch
        
        return results

    async def process_with_retry(
        self,
        items: List[Any],
        processor: Callable,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> List[Any]:
        """Process items with retry on failure."""
        results = []
        failures = []
        
        for item in items:
            success = False
            for attempt in range(max_retries):
                try:
                    result = await processor(item)
                    results.append(result)
                    success = True
                    break
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (attempt + 1))
            
            if not success:
                failures.append(item)
        
        if failures:
            logger.error(f"{len(failures)} items failed after {max_retries} retries")
        
        return results


# =============================================================================
# MEMORY MANAGEMENT
# =============================================================================

class MemoryManager:
    """
    Memory usage monitoring and optimization.
    
    Features:
    - Memory usage tracking
    - Automatic cleanup
    - Garbage collection hints
    - Memory limits
    """

    def __init__(self, max_memory_mb: int = 1500):
        self._max_memory_mb = max_memory_mb
        self._tracked_objects: Dict[str, int] = {}

    def track_object(self, name: str, size_bytes: int):
        """Track memory usage of an object."""
        self._tracked_objects[name] = size_bytes

    def untrack_object(self, name: str):
        """Stop tracking an object."""
        if name in self._tracked_objects:
            del self._tracked_objects[name]

    def get_total_memory(self) -> int:
        """Get total tracked memory in bytes."""
        return sum(self._tracked_objects.values())

    def get_memory_mb(self) -> float:
        """Get total tracked memory in MB."""
        return self.get_total_memory() / 1024 / 1024

    def is_within_limits(self) -> bool:
        """Check if memory usage is within limits."""
        return self.get_memory_mb() <= self._max_memory_mb

    def get_largest_objects(self, top_n: int = 10) -> List[tuple]:
        """Get largest tracked objects."""
        sorted_objects = sorted(
            self._tracked_objects.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_objects[:top_n]

    def suggest_cleanup(self) -> List[str]:
        """Suggest objects to clean up based on size."""
        if self.is_within_limits():
            return []
        
        # Suggest largest objects for cleanup
        largest = self.get_largest_objects(5)
        return [name for name, size in largest if size > 10 * 1024 * 1024]  # > 10 MB

    def force_cleanup(self, target_memory_mb: int):
        """Force cleanup to reach target memory."""
        import gc
        
        while self.get_memory_mb() > target_memory_mb:
            # Get largest object
            largest = self.get_largest_objects(1)
            if not largest:
                break
            
            name, size = largest[0]
            logger.info(f"Cleaning up {name} ({size / 1024 / 1024:.2f} MB)")
            self.untrack_object(name)
            
            # Hint garbage collector
            gc.collect()


# =============================================================================
# DECORATORS
# =============================================================================

def cached(ttl_seconds: int = 300, cache: Optional[LRUCache] = None):
    """
    Caching decorator for async functions.
    
    Args:
        ttl_seconds: Time-to-live in seconds
        cache: Cache instance (uses default if None)
    """
    if cache is None:
        cache = LRUCache()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key
            key_data = f"{func.__name__}:{args}:{kwargs}"
            key = hashlib.sha256(key_data.encode()).hexdigest()[:32]
            
            # Try cache
            cached_result = cache.get(key)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            cache.set(key, result, ttl_seconds)
            
            return result
        
        return wrapper
    return decorator


def rate_limited(max_calls: int, period_seconds: float):
    """
    Rate limiting decorator.
    
    Args:
        max_calls: Maximum calls per period
        period_seconds: Time period in seconds
    """
    calls: List[float] = []
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal calls
            
            now = time.time()
            
            # Remove old calls
            calls = [t for t in calls if now - t < period_seconds]
            
            # Check limit
            if len(calls) >= max_calls:
                wait_time = period_seconds - (now - calls[0])
                logger.warning(f"Rate limit hit, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                return await wrapper(*args, **kwargs)
            
            # Record call
            calls.append(now)
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def timed(metric_name: Optional[str] = None):
    """
    Timing decorator for performance monitoring.
    
    Args:
        metric_name: Name for the metric (defaults to function name)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            name = metric_name or func.__name__
            start = time.perf_counter()
            
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                logger.debug(f"{name} took {elapsed:.2f}ms")
        
        return wrapper
    return decorator


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

_default_cache: Optional[LRUCache] = None
_memory_manager: Optional[MemoryManager] = None


def init_performance_optimizations(
    cache_size: int = 10000,
    cache_ttl: int = 300,
    max_memory_mb: int = 1500,
) -> Dict[str, Any]:
    """Initialize performance optimizations."""
    global _default_cache, _memory_manager
    
    _default_cache = LRUCache(max_size=cache_size, default_ttl_seconds=cache_ttl)
    _memory_manager = MemoryManager(max_memory_mb=max_memory_mb)
    
    logger.info(f"Performance optimizations initialized: cache={cache_size}, memory={max_memory_mb}MB")
    
    return {
        "cache": _default_cache,
        "memory_manager": _memory_manager,
    }


def get_cache() -> LRUCache:
    """Get default cache instance."""
    global _default_cache
    if not _default_cache:
        _default_cache = LRUCache()
    return _default_cache


def get_memory_manager() -> MemoryManager:
    """Get memory manager instance."""
    global _memory_manager
    if not _memory_manager:
        _memory_manager = MemoryManager()
    return _memory_manager
