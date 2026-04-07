"""Cache Engine — Slice 35.

Multi-layer caching for PilotSuite Core.

Features:
- In-memory caching with TTL
- LRU eviction
- Cache invalidation patterns
- Cache warming
- Hit/miss statistics
- Namespace support
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import uuid
import threading

logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Cache eviction strategy."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live only


@dataclass
class CacheEntry:
    """Cache entry."""
    key: str
    value: Any
    namespace: str
    created_at: str
    expires_at: Optional[str]
    last_accessed: str
    access_count: int = 0
    size_bytes: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "namespace": self.namespace,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "size_bytes": self.size_bytes,
        }


@dataclass
class CacheStats:
    """Cache statistics."""
    namespace: str
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    sets: int = 0
    deletes: int = 0
    
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "namespace": self.namespace,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "sets": self.sets,
            "deletes": self.deletes,
            "hit_rate": round(self.hit_rate(), 4),
        }


class CacheEngine:
    """Multi-layer cache engine."""
    
    def __init__(self, max_size: int = 10000, 
                 default_ttl_seconds: int = 3600,
                 strategy: CacheStrategy = CacheStrategy.LRU):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._default_ttl = timedelta(seconds=default_ttl_seconds)
        self._strategy = strategy
        self._lock = threading.RLock()
        
        # Statistics per namespace
        self._stats: Dict[str, CacheStats] = {}
        
        # Access order for LRU (key -> timestamp)
        self._access_order: Dict[str, float] = {}
        
        # Frequency count for LFU (key -> count)
        self._frequency: Dict[str, int] = {}
        
        # Insertion order for FIFO (key -> sequence)
        self._insertion_order: Dict[str, int] = {}
        self._insertion_sequence: int = 0
    
    def get(self, key: str, namespace: str = "default",
            default: Any = None) -> Any:
        """Get value from cache."""
        with self._lock:
            full_key = f"{namespace}:{key}"
            
            # Ensure stats exist
            self._ensure_stats(namespace)
            
            if full_key not in self._cache:
                self._stats[namespace].misses += 1
                return default
            
            entry = self._cache[full_key]
            
            # Check expiration
            if entry.expires_at:
                expires = datetime.fromisoformat(entry.expires_at)
                if datetime.now(timezone.utc) > expires:
                    self._remove_entry(full_key, namespace)
                    self._stats[namespace].misses += 1
                    self._stats[namespace].expirations += 1
                    return default
            
            # Update access metadata
            entry.last_accessed = datetime.now(timezone.utc).isoformat()
            entry.access_count += 1
            
            # Update strategy-specific metadata
            self._update_access_metadata(full_key)
            
            self._stats[namespace].hits += 1
            
            return entry.value
    
    def set(self, key: str, value: Any, namespace: str = "default",
            ttl_seconds: Optional[int] = None,
            size_bytes: int = 0) -> None:
        """Set value in cache."""
        with self._lock:
            full_key = f"{namespace}:{key}"
            
            # Ensure stats exist
            self._ensure_stats(namespace)
            
            # Calculate expiration
            now = datetime.now(timezone.utc)
            ttl = timedelta(seconds=ttl_seconds) if ttl_seconds else self._default_ttl
            expires_at = (now + ttl).isoformat()
            
            # Check if we need to evict
            if full_key not in self._cache and len(self._cache) >= self._max_size:
                self._evict_one(namespace)
            
            # Create or update entry
            entry = CacheEntry(
                key=key,
                value=value,
                namespace=namespace,
                created_at=now.isoformat(),
                expires_at=expires_at,
                last_accessed=now.isoformat(),
                size_bytes=size_bytes,
            )
            
            self._cache[full_key] = entry
            
            # Update strategy-specific metadata
            self._update_insertion_metadata(full_key)
            
            self._stats[namespace].sets += 1
    
    def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete entry from cache."""
        with self._lock:
            full_key = f"{namespace}:{key}"
            
            self._ensure_stats(namespace)
            
            if full_key not in self._cache:
                return False
            
            self._remove_entry(full_key, namespace)
            self._stats[namespace].deletes += 1
            
            return True
    
    def _remove_entry(self, full_key: str, namespace: str) -> None:
        """Remove entry and clean up metadata."""
        if full_key in self._cache:
            del self._cache[full_key]
        
        if full_key in self._access_order:
            del self._access_order[full_key]
        
        if full_key in self._frequency:
            del self._frequency[full_key]
        
        if full_key in self._insertion_order:
            del self._insertion_order[full_key]
        
        self._stats[namespace].evictions += 1
    
    def _evict_one(self, namespace: str) -> None:
        """Evict one entry based on strategy."""
        if not self._cache:
            return
        
        candidates = [
            (k, e) for k, e in self._cache.items()
            if e.namespace == namespace or namespace == "default"
        ]
        
        if not candidates:
            # Evict from any namespace
            candidates = list(self._cache.items())
        
        if not candidates:
            return
        
        key_to_evict = None
        
        if self._strategy == CacheStrategy.LRU:
            # Least recently used
            key_to_evict = min(candidates, key=lambda x: self._access_order.get(x[0], float('inf')))[0]
        
        elif self._strategy == CacheStrategy.LFU:
            # Least frequently used
            key_to_evict = min(candidates, key=lambda x: self._frequency.get(x[0], 0))[0]
        
        elif self._strategy == CacheStrategy.FIFO:
            # First in first out
            key_to_evict = min(candidates, key=lambda x: self._insertion_order.get(x[0], float('inf')))[0]
        
        elif self._strategy == CacheStrategy.TTL:
            # Earliest expiration
            key_to_evict = min(
                candidates,
                key=lambda x: datetime.fromisoformat(x[1].expires_at) if x[1].expires_at else datetime.max.replace(tzinfo=timezone.utc)
            )[0]
        
        if key_to_evict:
            entry = self._cache[key_to_evict]
            self._remove_entry(key_to_evict, entry.namespace)
    
    def _update_access_metadata(self, key: str) -> None:
        """Update access metadata for eviction strategies."""
        now = datetime.now(timezone.utc).timestamp()
        
        if self._strategy in (CacheStrategy.LRU, CacheStrategy.TTL):
            self._access_order[key] = now
        
        if self._strategy == CacheStrategy.LFU:
            self._frequency[key] = self._frequency.get(key, 0) + 1
    
    def _update_insertion_metadata(self, key: str) -> None:
        """Update insertion metadata."""
        self._insertion_order[key] = self._insertion_sequence
        self._insertion_sequence += 1

        # Also update access order for new entries
        self._update_access_metadata(key)
    
    def _ensure_stats(self, namespace: str) -> None:
        """Ensure stats exist for namespace."""
        if namespace not in self._stats:
            self._stats[namespace] = CacheStats(namespace=namespace)
    
    def clear(self, namespace: Optional[str] = None) -> int:
        """Clear cache (optionally by namespace)."""
        with self._lock:
            if namespace is None:
                count = len(self._cache)
                self._cache.clear()
                self._access_order.clear()
                self._frequency.clear()
                self._insertion_order.clear()
                self._insertion_sequence = 0
                self._stats.clear()
                return count
            
            # Clear specific namespace
            keys_to_remove = [k for k, e in self._cache.items() if e.namespace == namespace]
            for key in keys_to_remove:
                self._remove_entry(key, namespace)
            
            return len(keys_to_remove)
    
    def invalidate_pattern(self, pattern: str, namespace: str = "default") -> int:
        """Invalidate entries matching pattern."""
        with self._lock:
            import fnmatch
            
            keys_to_remove = [
                k for k, e in self._cache.items()
                if e.namespace == namespace and fnmatch.fnmatch(e.key, pattern)
            ]
            
            for key in keys_to_remove:
                self._remove_entry(key, namespace)
            
            return len(keys_to_remove)
    
    def get_stats(self, namespace: str = "default") -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            self._ensure_stats(namespace)
            return self._stats[namespace].to_dict()
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all namespaces."""
        with self._lock:
            total_hits = sum(s.hits for s in self._stats.values())
            total_misses = sum(s.misses for s in self._stats.values())
            total_evictions = sum(s.evictions for s in self._stats.values())
            
            return {
                "total_entries": len(self._cache),
                "max_size": self._max_size,
                "strategy": self._strategy.value,
                "namespaces": {ns: s.to_dict() for ns, s in self._stats.items()},
                "totals": {
                    "hits": total_hits,
                    "misses": total_misses,
                    "evictions": total_evictions,
                    "hit_rate": round(total_hits / (total_hits + total_misses), 4) if (total_hits + total_misses) > 0 else 0.0,
                },
            }
    
    def get_entry(self, key: str, namespace: str = "default") -> Optional[Dict[str, Any]]:
        """Get cache entry details."""
        with self._lock:
            full_key = f"{namespace}:{key}"
            
            if full_key not in self._cache:
                return None
            
            return self._cache[full_key].to_dict()
    
    def get_all_entries(self, namespace: Optional[str] = None,
                       limit: int = 100) -> List[Dict[str, Any]]:
        """Get all cache entries."""
        with self._lock:
            entries = list(self._cache.values())
            
            if namespace:
                entries = [e for e in entries if e.namespace == namespace]
            
            # Sort by last_accessed (newest first)
            entries.sort(key=lambda e: e.last_accessed, reverse=True)
            
            return [e.to_dict() for e in entries[:limit]]
    
    def warm_cache(self, key: str, loader: Callable[[], Any],
                  namespace: str = "default",
                  ttl_seconds: Optional[int] = None) -> Any:
        """Get value, loading from loader if not cached."""
        value = self.get(key, namespace)
        
        if value is None:
            value = loader()
            self.set(key, value, namespace, ttl_seconds)
        
        return value
    
    def get_or_set(self, key: str, default: Any,
                  namespace: str = "default",
                  ttl_seconds: Optional[int] = None) -> Any:
        """Get value or set default."""
        value = self.get(key, namespace)
        
        if value is None:
            self.set(key, default, namespace, ttl_seconds)
            return default
        
        return value
    
    def touch(self, key: str, namespace: str = "default") -> bool:
        """Touch entry (update last accessed time)."""
        with self._lock:
            full_key = f"{namespace}:{key}"
            
            if full_key not in self._cache:
                return False
            
            entry = self._cache[full_key]
            entry.last_accessed = datetime.now(timezone.utc).isoformat()
            entry.access_count += 1
            
            self._update_access_metadata(full_key)
            
            return True
    
    def exists(self, key: str, namespace: str = "default") -> bool:
        """Check if key exists and is not expired."""
        with self._lock:
            full_key = f"{namespace}:{key}"
            
            if full_key not in self._cache:
                return False
            
            entry = self._cache[full_key]
            
            # Check expiration
            if entry.expires_at:
                expires = datetime.fromisoformat(entry.expires_at)
                if datetime.now(timezone.utc) > expires:
                    self._remove_entry(full_key, entry.namespace)
                    return False
            
            return True
    
    def get_size(self, namespace: Optional[str] = None) -> int:
        """Get cache size (entry count)."""
        with self._lock:
            if namespace:
                return len([e for e in self._cache.values() if e.namespace == namespace])
            return len(self._cache)
    
    def get_memory_usage(self, namespace: Optional[str] = None) -> int:
        """Get approximate memory usage in bytes."""
        with self._lock:
            entries = self._cache.values()
            
            if namespace:
                entries = [e for e in entries if e.namespace == namespace]
            
            return sum(e.size_bytes for e in entries if e.size_bytes > 0)
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        with self._lock:
            now = datetime.now(timezone.utc)
            
            keys_to_remove = []
            for key, entry in self._cache.items():
                if entry.expires_at:
                    expires = datetime.fromisoformat(entry.expires_at)
                    if now > expires:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                entry = self._cache[key]
                self._remove_entry(key, entry.namespace)
                self._stats[entry.namespace].expirations += 1
            
            return len(keys_to_remove)


def create_cache_engine(max_size: int = 10000,
                       default_ttl_seconds: int = 3600,
                       strategy: str = "lru") -> CacheEngine:
    """Factory function to create cache engine."""
    return CacheEngine(
        max_size=max_size,
        default_ttl_seconds=default_ttl_seconds,
        strategy=CacheStrategy(strategy),
    )
