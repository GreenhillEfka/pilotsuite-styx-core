"""
Performance Optimization Module - Core Add-on Performance Enhancements.

Implements:
- Query Caching (Redis/Memory)
- Lazy Loading (ML Models)
- Connection Pooling (Database/API)
- Async Optimization (Parallel Execution)
"""

import time
import threading
import functools
from typing import Dict, Any, Optional, Callable, List
from collections import OrderedDict
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import hashlib
import json


# =============================================================================
# 1. QUERY CACHING
# =============================================================================

@dataclass
class CacheEntry:
    """Cache entry with TTL support."""
    value: Any
    expires_at: float
    hit_count: int = 0
    created_at: float = field(default_factory=time.time)


class QueryCache:
    """Memory-based query cache with TTL and LRU eviction."""
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300.0,  # 5 minutes default
        enabled: bool = True,
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.enabled = enabled
        
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "clears": 0,
        }
    
    def _compute_key(self, *args, **kwargs) -> str:
        """Compute cache key from function arguments."""
        content = json.dumps((args, sorted(kwargs.items())), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if not self.enabled:
            return None
            
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return None
            
            if time.time() > entry.expires_at:
                del self._cache[key]
                self._stats["misses"] += 1
                return None
            
            entry.hit_count += 1
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in cache with optional TTL."""
        if not self.enabled:
            return
            
        with self._lock:
            # Remove if exists to update position
            if key in self._cache:
                del self._cache[key]
            
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1
            
            ttl = ttl or self.default_ttl
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=time.time() + ttl,
            )
    
    def delete(self, key: str) -> bool:
        """Delete key from cache. Returns True if key existed."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._stats["clears"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                **self._stats,
                "size": len(self._cache),
                "max_size": self.max_size,
                "hit_rate": (
                    self._stats["hits"] / (self._stats["hits"] + self._stats["misses"])
                    if (self._stats["hits"] + self._stats["misses"]) > 0 else 0.0
                ),
            }
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        with self._lock:
            now = time.time()
            expired_keys = [
                k for k, entry in self._cache.items()
                if now > entry.expires_at
            ]
            for key in expired_keys:
                del self._cache[key]
            self._stats["evictions"] += len(expired_keys)
            return len(expired_keys)

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern. Returns count invalidated."""
        with self._lock:
            keys_to_delete = [k for k in self._cache if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)


# Global cache instances
brain_graph_cache = QueryCache(max_size=100, default_ttl=60.0)
ml_cache = QueryCache(max_size=200, default_ttl=120.0)
api_response_cache = QueryCache(max_size=1000, default_ttl=30.0)


def get_performance_stats() -> Dict[str, Any]:
    """Get all performance statistics."""
    return {
        "cache": {
            "brain_graph": brain_graph_cache.get_stats(),
            "ml_models": ml_cache.get_stats(),
            "api_response": api_response_cache.get_stats(),
        },
        "connection_pool": sql_pool.get_stats(),
        "async_executor": async_executor.get_stats(),
    }


def reset_performance_stats() -> None:
    """Reset all performance statistics."""
    brain_graph_cache.clear()
    ml_cache.clear()
    api_response_cache.clear()


def cached(ttl: Optional[float] = None, cache: Optional[QueryCache] = None):
    """Decorator for caching function results."""
    def decorator(func: Callable) -> Callable:
        cache_instance = cache or QueryCache()
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = cache_instance._compute_key(func.__name__, *args, **kwargs)
            
            # Try cache
            cached_value = cache_instance.get(key)
            if cached_value is not None:
                return cached_value
            
            # Call function and cache result
            result = func(*args, **kwargs)
            cache_instance.set(key, result, ttl)
            return result
        
        wrapper._cache = cache_instance
        return wrapper
    
    return decorator


# =============================================================================
# 2. LAZY LOADING (ML Models)
# =============================================================================

class LazyModelLoader:
    """Lazy-loaded ML model manager with on-demand loading."""
    
    def __init__(
        self,
        model_path: str = "/tmp/ml_models",
        load_timeout: float = 10.0,
        max_concurrent: int = 4,
    ):
        self.model_path = model_path
        self.load_timeout = load_timeout
        self.max_concurrent = max_concurrent
        
        self._models: Dict[str, Any] = {}
        self._model_configs: Dict[str, Dict] = {}
        self._loading_locks: Dict[str, threading.Lock] = {}
        self._stats = {
            "loads": 0,
            "hits": 0,
            "misses": 0,
        }
        self._lock = threading.RLock()
    
    def register_model(
        self,
        name: str,
        model_class: Any,
        **kwargs,
    ) -> None:
        """Register a model for lazy loading."""
        with self._lock:
            self._model_configs[name] = {
                "class": model_class,
                "kwargs": kwargs,
                "loaded": False,
                "load_time": None,
            }
            self._loading_locks[name] = threading.Lock()
    
    def get_model(self, name: str) -> Optional[Any]:
        """Get model, loading it on-demand if needed."""
        with self._lock:
            # Check if already loaded
            if name in self._models:
                self._stats["hits"] += 1
                return self._models[name]
            
            # Check if registered
            if name not in self._model_configs:
                self._stats["misses"] += 1
                return None
            
            config = self._model_configs[name]
            
        # Use lock for loading
        with self._loading_locks[name]:
            # Double-check after acquiring lock
            if name in self._models:
                self._stats["hits"] += 1
                return self._models[name]
            
            try:
                # Load model
                start_time = time.time()
                model = config["class"](**config["kwargs"])
                model.load(self.model_path) if hasattr(model, "load") else None
                
                load_time = time.time() - start_time
                
                with self._lock:
                    self._models[name] = model
                    config["loaded"] = True
                    config["load_time"] = load_time
                    self._stats["loads"] += 1
                
                return model
                
            except Exception as e:
                self._stats["misses"] += 1
                raise RuntimeError(f"Failed to load model '{name}': {e}")
    
    def unload_model(self, name: str) -> bool:
        """Unload a model. Returns True if model was loaded."""
        with self._lock:
            if name in self._models:
                del self._models[name]
                if name in self._model_configs:
                    self._model_configs[name]["loaded"] = False
                return True
            return False
    
    def unload_all(self) -> int:
        """Unload all models. Returns count unloaded."""
        with self._lock:
            count = len(self._models)
            self._models.clear()
            for config in self._model_configs.values():
                config["loaded"] = False
            return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get loader statistics."""
        with self._lock:
            return {
                **self._stats,
                "loaded_models": list(self._models.keys()),
                "loaded_count": len(self._models),
                "registered_count": len(self._model_configs),
            }


# Global lazy loader instance
ml_model_loader = LazyModelLoader()


# =============================================================================
# 3. CONNECTION POOLING (Database/API)
# =============================================================================

class ConnectionPool:
    """Thread-safe connection pool with health checks."""
    
    def __init__(
        self,
        max_connections: int = 10,
        min_connections: int = 2,
        connection_timeout: float = 5.0,
        max_idle_time: float = 300.0,  # 5 minutes
    ):
        self.max_connections = max_connections
        self.min_connections = min_connections
        self.connection_timeout = connection_timeout
        self.max_idle_time = max_idle_time
        
        self._pool: List[Any] = []
        self._active: Dict[int, float] = {}  # id -> acquire_time
        self._lock = threading.RLock()
        self._next_id = 0
        self._stats = {
            "acquired": 0,
            "released": 0,
            "created": 0,
            "destroyed": 0,
            "timeouts": 0,
        }
    
    def _create_connection(self) -> Any:
        """Create a new connection (override in subclasses)."""
        raise NotImplementedError
    
    def _validate_connection(self, conn: Any) -> bool:
        """Validate connection is still usable (override in subclasses)."""
        return True
    
    def _close_connection(self, conn: Any) -> None:
        """Close a connection (override in subclasses)."""
        pass
    
    def acquire(self, timeout: Optional[float] = None) -> Any:
        """Acquire a connection from the pool."""
        timeout = timeout or self.connection_timeout
        start_time = time.time()
        
        while True:
            with self._lock:
                # Try to get idle connection
                while self._pool:
                    conn = self._pool.pop(0)
                    if self._validate_connection(conn):
                        conn_id = id(conn)
                        self._active[conn_id] = time.time()
                        self._stats["acquired"] += 1
                        return conn
                    else:
                        self._close_connection(conn)
                        self._stats["destroyed"] += 1
                
                # Create new connection if under limit
                total_connections = len(self._pool) + len(self._active)
                if total_connections < self.max_connections:
                    conn = self._create_connection()
                    conn_id = id(conn)
                    self._active[conn_id] = time.time()
                    self._stats["created"] += 1
                    self._stats["acquired"] += 1
                    return conn
            
            # Wait and retry
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                self._stats["timeouts"] += 1
                raise TimeoutError("Connection pool timeout")
            
            time.sleep(0.01)  # Small delay before retry
    
    def release(self, conn: Any) -> bool:
        """Release a connection back to the pool."""
        conn_id = id(conn)
        
        with self._lock:
            if conn_id in self._active:
                del self._active[conn_id]
                
                # Return to pool if valid
                if self._validate_connection(conn) and len(self._pool) < self.max_connections:
                    self._pool.append(conn)
                else:
                    self._close_connection(conn)
                    self._stats["destroyed"] += 1
                
                self._stats["released"] += 1
                return True
        
        return False
    
    def cleanup_idle(self) -> int:
        """Remove idle connections. Returns count removed."""
        with self._lock:
            now = time.time()
            removed = 0
            
            # Clean idle pool connections
            while self._pool:
                conn = self._pool[0]
                # Check if idle too long (need last_use timestamp)
                # For now, just keep min_connections
                if len(self._pool) > self.min_connections:
                    self._pool.pop(0)
                    self._close_connection(conn)
                    removed += 1
                else:
                    break
            
            self._stats["destroyed"] += removed
            return removed
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            return {
                **self._stats,
                "pool_size": len(self._pool),
                "active_count": len(self._active),
                "max_connections": self.max_connections,
            }


class SQLiteConnectionPool(ConnectionPool):
    """SQLite-specific connection pool."""
    
    def __init__(self, db_path: str = "/data/brain_graph.db", **kwargs):
        super().__init__(**kwargs)
        self.db_path = db_path
        import sqlite3
        self.sqlite3 = sqlite3
    
    def _create_connection(self) -> Any:
        return self.sqlite3.connect(self.db_path, timeout=self.connection_timeout)
    
    def _validate_connection(self, conn: Any) -> bool:
        try:
            conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False
    
    def _close_connection(self, conn: Any) -> None:
        try:
            conn.close()
        except Exception:
            pass


# Global SQLite connection pool
sql_pool = SQLiteConnectionPool(
    db_path="/data/brain_graph.db",
    max_connections=10,
    min_connections=1,
    connection_timeout=5.0,
    max_idle_time=300.0,
)


# =============================================================================
# 4. ASYNC OPTIMIZATION (Parallel Execution)
# =============================================================================

class AsyncExecutor:
    """Optimized async executor with parallelization and batching."""
    
    def __init__(
        self,
        max_workers: int = 4,
        batch_size: int = 10,
        timeout: float = 30.0,
    ):
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.timeout = timeout
        
        self._executor: Optional[ThreadPoolExecutor] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "batches_processed": 0,
        }
        self._lock = threading.RLock()
    
    def _ensure_executor(self) -> ThreadPoolExecutor:
        """Ensure executor exists, create if needed."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="async_exec_",
            )
        return self._executor
    
    async def submit(self, func: Callable, *args, **kwargs) -> Any:
        """Submit async task for execution."""
        loop = asyncio.get_event_loop()
        executor = self._ensure_executor()
        
        with self._lock:
            self._stats["tasks_submitted"] += 1
        
        try:
            result = await loop.run_in_executor(
                executor,
                functools.partial(func, *args, **kwargs),
            )
            
            with self._lock:
                self._stats["tasks_completed"] += 1
            
            return result
            
        except Exception as e:
            with self._lock:
                self._stats["tasks_failed"] += 1
            raise
    
    async def submit_batch(self, tasks: List[tuple]) -> List[Any]:
        """Submit batch of tasks for parallel execution.
        
        Args:
            tasks: List of (func, args, kwargs) tuples
        
        Returns:
            List of results in same order as input
        """
        if not tasks:
            return []
        
        # Split into batches
        batches = [
            tasks[i:i + self.batch_size]
            for i in range(0, len(tasks), self.batch_size)
        ]
        
        results = []
        executor = self._ensure_executor()
        loop = asyncio.get_event_loop()
        
        for batch in batches:
            with self._lock:
                self._stats["batches_processed"] += 1
            
            # Submit batch in parallel
            futures = []
            for func, args, kwargs in batch:
                future = loop.run_in_executor(
                    executor,
                    functools.partial(func, *args, **kwargs),
                )
                futures.append(future)
            
            # Wait for batch with timeout
            try:
                batch_results = await asyncio.wait_for(
                    asyncio.gather(*futures, return_exceptions=True),
                    timeout=self.timeout,
                )
                
                # Handle exceptions
                for i, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        with self._lock:
                            self._stats["tasks_failed"] += 1
                        batch_results[i] = None
                    else:
                        with self._lock:
                            self._stats["tasks_completed"] += 1
                
                results.extend(batch_results)
                
            except asyncio.TimeoutError:
                # Cancel remaining tasks
                for future in futures:
                    if not future.done():
                        future.cancel()
                
                # Return partial results
                results.extend([None] * len(batch))
        
        return results
    
    async def map_async(self, func: Callable, items: List[Any]) -> List[Any]:
        """Map function over items with parallel execution."""
        tasks = [(func, (item,), {}) for item in items]
        return await self.submit_batch(tasks)
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown executor."""
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        with self._lock:
            return {
                **self._stats,
                "max_workers": self.max_workers,
                "batch_size": self.batch_size,
            }


# Global async executor
async_executor = AsyncExecutor(
    max_workers=4,
    batch_size=10,
    timeout=30.0,
)


# =============================================================================
# PERFORMANCE MONITOR
# =============================================================================

class PerformanceMonitor:
    """Performance monitoring and metrics collection."""
    
    def __init__(self):
        self._metrics: Dict[str, List[float]] = {}
        self._start_time = time.time()
        self._lock = threading.RLock()
    
    def record(self, name: str, value: float) -> None:
        """Record a metric value."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = []
            self._metrics[name].append(value)
            
            # Keep only last 1000 values per metric
            if len(self._metrics[name]) > 1000:
                self._metrics[name] = self._metrics[name][-1000:]
    
    def get_stats(self, name: str) -> Dict[str, float]:
        """Get statistics for a metric."""
        with self._lock:
            values = self._metrics.get(name, [])
            
            if not values:
                return {
                    "count": 0,
                    "min": 0.0,
                    "max": 0.0,
                    "avg": 0.0,
                    "p50": 0.0,
                    "p95": 0.0,
                    "p99": 0.0,
                }
            
            sorted_values = sorted(values)
            n = len(sorted_values)
            
            return {
                "count": n,
                "min": sorted_values[0],
                "max": sorted_values[-1],
                "avg": sum(sorted_values) / n,
                "p50": sorted_values[int(n * 0.5)],
                "p95": sorted_values[int(n * 0.95)],
                "p99": sorted_values[int(n * 0.99)],
            }
    
    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all metrics."""
        with self._lock:
            return {
                name: self.get_stats(name)
                for name in self._metrics
            }
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._metrics.clear()
            self._start_time = time.time()


# Global performance monitor
perf_monitor = PerformanceMonitor()


def measure_performance(func: Callable) -> Callable:
    """Decorator to measure function performance."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed = time.time() - start_time
            perf_monitor.record(func.__name__, elapsed)
    
    return wrapper
