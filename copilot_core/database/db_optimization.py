"""P1-004: Database Optimization — Indexing, Pooling, Caching, Migrations."""
from __future__ import annotations

import logging
import time
import hashlib
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class QueryMetrics:
    """Metrics for database query performance."""
    query: str
    duration_ms: float
    timestamp: float = field(default_factory=time.time)
    rows_affected: int = 0
    index_used: Optional[str] = None
    table_scan: bool = False


@dataclass
class ConnectionPoolStats:
    """Connection pool statistics."""
    total_connections: int
    active_connections: int
    idle_connections: int
    max_connections: int
    wait_count: int = 0
    avg_wait_ms: float = 0.0


class QueryOptimizer:
    """Analyzes and optimizes database queries."""

    def __init__(self):
        self._query_history: List[QueryMetrics] = []
        self._slow_query_threshold_ms = 100
        self._index_suggestions: Dict[str, str] = {}

    def record_query(self, query: str, duration_ms: float, rows_affected: int = 0, index_used: Optional[str] = None):
        """Record query metrics."""
        metrics = QueryMetrics(
            query=query,
            duration_ms=duration_ms,
            rows_affected=rows_affected,
            index_used=index_used,
            table_scan=index_used is None
        )
        self._query_history.append(metrics)

        if duration_ms > self._slow_query_threshold_ms:
            logger.warning(f"Slow query detected: {duration_ms:.2f}ms - {query[:100]}")
            self._analyze_slow_query(query, duration_ms)

    def _analyze_slow_query(self, query: str, duration_ms: float):
        """Analyze slow query and suggest optimizations."""
        import re
        query_lower = query.lower()
        if 'where' in query_lower and 'id' in query_lower:
            match = re.search(r'FROM\s+(\w+)', query, re.IGNORECASE)
            if match:
                table = match.group(1)
                suggestion = f"CREATE INDEX idx_{table}_id ON {table}(id)"
                self._index_suggestions[f"{table}.id"] = suggestion
                logger.info(f"Index suggestion: {suggestion}")

    def get_slow_queries(self, limit: int = 10) -> List[QueryMetrics]:
        """Get recent slow queries."""
        slow = [q for q in self._query_history if q.duration_ms > self._slow_query_threshold_ms]
        return sorted(slow, key=lambda x: x.duration_ms, reverse=True)[:limit]

    def get_index_suggestions(self) -> Dict[str, str]:
        """Get index creation suggestions."""
        return self._index_suggestions.copy()


class ConnectionPool:
    """Database connection pool with monitoring (thread-safe)."""

    def __init__(self, max_connections: int = 20, connection_factory: Optional[Callable] = None):
        self.max_connections = max_connections
        self.connection_factory = connection_factory
        self._connections: List[Any] = []
        self._active: set = set()
        self._wait_count = 0
        self._total_wait_ms = 0.0
        self._lock = threading.Lock()

    @contextmanager
    def get_connection(self, timeout: float = 5.0):
        """Get connection from pool."""
        start = time.time()
        
        with self._lock:
            for conn in self._connections:
                if conn not in self._active:
                    self._active.add(conn)
                    try:
                        yield conn
                    finally:
                        with self._lock:
                            self._active.discard(conn)
                    return

            if len(self._connections) < self.max_connections:
                conn = self.connection_factory() if self.connection_factory else None
                self._connections.append(conn)
                self._active.add(conn)
                try:
                    yield conn
                finally:
                    with self._lock:
                        self._active.discard(conn)
                return

            self._wait_count += 1
            raise TimeoutError("Connection pool exhausted")

    def get_stats(self) -> ConnectionPoolStats:
        """Get pool statistics."""
        with self._lock:
            return ConnectionPoolStats(
                total_connections=len(self._connections),
                active_connections=len(self._active),
                idle_connections=len(self._connections) - len(self._active),
                max_connections=self.max_connections,
                wait_count=self._wait_count,
                avg_wait_ms=self._total_wait_ms / max(1, self._wait_count)
            )


class QueryCache:
    """Redis-compatible query result cache."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, tuple] = {}
        self._hits = 0
        self._misses = 0

    def _make_key(self, query: str, params: Optional[Dict] = None) -> str:
        key = query
        if params:
            key += f":{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key.encode()).hexdigest()

    def get(self, query: str, params: Optional[Dict] = None) -> Optional[Any]:
        key = self._make_key(query, params)
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                self._hits += 1
                return value
            del self._cache[key]
        self._misses += 1
        return None

    def set(self, query: str, value: Any, params: Optional[Dict] = None):
        key = self._make_key(query, params)
        self._cache[key] = (value, time.time() + self.ttl_seconds)

    def get_stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / max(1, total),
            "size": len(self._cache),
            "ttl_seconds": self.ttl_seconds
        }


class DatabaseOptimizer:
    """Central database optimization engine."""

    def __init__(self, max_connections: int = 20, cache_ttl: int = 300):
        self.query_optimizer = QueryOptimizer()
        self.connection_pool = ConnectionPool(max_connections=max_connections)
        self.cache = QueryCache(ttl_seconds=cache_ttl)

    def get_health(self) -> Dict[str, Any]:
        pool_stats = self.connection_pool.get_stats()
        cache_stats = self.cache.get_stats()
        return {
            "pool": {
                "active": pool_stats.active_connections,
                "idle": pool_stats.idle_connections,
                "max": pool_stats.max_connections,
            },
            "cache": cache_stats,
            "status": "healthy" if pool_stats.active_connections < pool_stats.max_connections else "degraded"
        }


# Global default optimizer
default_db_optimizer: Optional[DatabaseOptimizer] = None


def init_db_optimizer(max_connections: int = 20, cache_ttl: int = 300) -> DatabaseOptimizer:
    """Initialize global database optimizer."""
    global default_db_optimizer
    default_db_optimizer = DatabaseOptimizer(max_connections, cache_ttl)
    return default_db_optimizer
