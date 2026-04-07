"""Async Redis Client with In-Memory Fallback.

Provides async Redis connection with automatic fallback to in-memory storage
when Redis is unavailable.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis.asyncio not available, using in-memory fallback")


class InMemoryStore:
    """Simple in-memory key-value store with TTL support."""
    
    def __init__(self):
        self._store: dict[str, Any] = {}
        self._expiry: dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key, returns None if expired or missing."""
        async with self._lock:
            if key in self._expiry:
                if datetime.now().timestamp() > self._expiry[key]:
                    del self._store[key]
                    del self._expiry[key]
                    return None
            return self._store.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value with optional TTL in seconds."""
        async with self._lock:
            self._store[key] = value
            if ttl:
                self._expiry[key] = datetime.now().timestamp() + ttl
            return True
    
    async def delete(self, key: str) -> bool:
        """Delete key from store."""
        async with self._lock:
            if key in self._store:
                del self._store[key]
            if key in self._expiry:
                del self._expiry[key]
            return True
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern (supports * wildcard)."""
        async with self._lock:
            import fnmatch
            keys_to_delete = [k for k in self._store.keys() if fnmatch.fnmatch(k, pattern)]
            for key in keys_to_delete:
                del self._store[key]
                if key in self._expiry:
                    del self._expiry[key]
            return len(keys_to_delete)
    
    async def keys(self, pattern: str = "*") -> list[str]:
        """Get keys matching pattern."""
        async with self._lock:
            import fnmatch
            if pattern == "*":
                return list(self._store.keys())
            return [k for k in self._store.keys() if fnmatch.fnmatch(k, pattern)]
    
    async def flush(self) -> bool:
        """Clear all keys."""
        async with self._lock:
            self._store.clear()
            self._expiry.clear()
            return True
    
    async def ping(self) -> bool:
        """Always returns True for in-memory store."""
        return True


class RedisClient:
    """Async Redis client with in-memory fallback.
    
    Features:
    - Automatic fallback to in-memory when Redis unavailable
    - Connection health checking
    - TTL-based expiration
    - Pattern-based key deletion
    """
    
    DEFAULT_TTL_ENTITY = 300  # 5 minutes for entity data
    DEFAULT_TTL_STATE = 60    # 1 minute for states
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        key_prefix: str = "pilotsuite:"
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.key_prefix = key_prefix
        self._redis: Optional[redis.Redis] = None
        self._fallback = InMemoryStore()
        self._connected = False
        self._lock = asyncio.Lock()
    
    def _full_key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self.key_prefix}{key}"
    
    async def connect(self) -> bool:
        """Establish Redis connection."""
        if not REDIS_AVAILABLE:
            logger.info("Redis not available, using in-memory fallback")
            self._connected = False
            return False
        
        try:
            self._redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True
            )
            await self._redis.ping()
            self._connected = True
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, using in-memory fallback")
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis and self._connected:
            await self._redis.close()
            self._connected = False
            logger.info("Disconnected from Redis")
    
    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._connected
    
    async def _get_store(self):
        """Get Redis or fallback store."""
        if self._connected and self._redis:
            try:
                await self._redis.ping()
                return self._redis
            except Exception:
                logger.warning("Redis ping failed, switching to fallback")
                self._connected = False
        return self._fallback
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        store = await self._get_store()
        full_key = self._full_key(key)
        
        try:
            if isinstance(store, InMemoryStore):
                return await store.get(full_key)
            else:
                return await store.get(full_key)
        except Exception as e:
            logger.error(f"Error getting key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value with optional TTL in seconds."""
        store = await self._get_store()
        full_key = self._full_key(key)
        
        try:
            if isinstance(store, InMemoryStore):
                return await store.set(full_key, value, ttl)
            else:
                if ttl:
                    return await store.set(full_key, value, ex=ttl)
                else:
                    return await store.set(full_key, value)
        except Exception as e:
            logger.error(f"Error setting key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key."""
        store = await self._get_store()
        full_key = self._full_key(key)
        
        try:
            if isinstance(store, InMemoryStore):
                return await store.delete(full_key)
            else:
                return await store.delete(full_key) > 0
        except Exception as e:
            logger.error(f"Error deleting key {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        store = await self._get_store()
        full_pattern = self._full_key(pattern)
        
        try:
            if isinstance(store, InMemoryStore):
                return await store.delete_pattern(full_pattern)
            else:
                keys = await store.keys(full_pattern)
                if keys:
                    return await store.delete(*keys)
                return 0
        except Exception as e:
            logger.error(f"Error deleting pattern {pattern}: {e}")
            return 0
    
    async def flush(self) -> bool:
        """Clear all keys with our prefix."""
        store = await self._get_store()
        
        try:
            if isinstance(store, InMemoryStore):
                return await store.flush()
            else:
                keys = await store.keys(f"{self.key_prefix}*")
                if keys:
                    await store.delete(*keys)
                return True
        except Exception as e:
            logger.error(f"Error flushing cache: {e}")
            return False
    
    async def ping(self) -> bool:
        """Check connection health."""
        if self._connected and self._redis:
            try:
                await self._redis.ping()
                return True
            except Exception:
                self._connected = False
        return False
    
    async def get_stats(self) -> dict:
        """Get connection stats."""
        return {
            "connected": self._connected,
            "host": self.host,
            "port": self.port,
            "using_fallback": not self._connected
        }


# Global instance
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """Get or create Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


async def init_redis_client(
    host: str = "localhost",
    port: int = 6379,
    password: Optional[str] = None
) -> RedisClient:
    """Initialize Redis client with connection."""
    global _redis_client
    _redis_client = RedisClient(host=host, port=port, password=password)
    await _redis_client.connect()
    return _redis_client
