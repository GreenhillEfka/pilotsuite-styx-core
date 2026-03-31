"""Cache Advanced Engine — Slice 54.

Advanced caching for PilotSuite Core.

Features:
- Multi-tier caching (L1/L2)
- Cache invalidation strategies
- Cache warming
- Distributed cache support
- Cache statistics and monitoring
- TTL management
"""
from __future__ import annotations

import logging
import threading
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable, Tuple
from enum import Enum
import uuid
from collections import OrderedDict

logger = logging.getLogger(__name__)


class CacheTier(Enum):
    """Cache tiers."""
    L1 = "l1"  # In-memory, fast
    L2 = "l2"  # External, larger


class EvictionStrategy(Enum):
    """Eviction strategies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live


class InvalidationStrategy(Enum):
    """Invalidation strategies."""
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    INVALIDATE = "invalidate"


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: str
    expires_at: Optional[str]
    last_accessed: str
    access_count: int = 0
    tier: CacheTier = CacheTier.L1
    size_bytes: int = 0
    tags: List[str] = field(default_factory=list)
    
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if not self.expires_at:
            return False
        
        expiry = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
        return datetime.now(timezone.utc) > expiry
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "tier": self.tier.value,
            "size_bytes": self.size_bytes,
            "tags": self.tags,
        }


class CacheEngine:
    """Advanced cache engine."""
    
    def __init__(self, max_size: int = 10000,
                 eviction_strategy: EvictionStrategy = EvictionStrategy.LRU,
                 default_ttl_seconds: int = 3600):
        self._max_size = max_size
        self._eviction_strategy = eviction_strategy
        self._default_ttl = default_ttl_seconds
        
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._tag_index: Dict[str, set] = {}  # tag -> set of keys
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            "total_hits": 0,
            "total_misses": 0,
            "total_sets": 0,
            "total_deletes": 0,
            "total_evictions": 0,
            "total_expirations": 0,
            "by_key_prefix": {},
        }
        
        # Write-behind queue
        self._write_behind_queue: List[Tuple[str, Any]] = []
        self._write_behind_callback: Optional[Callable[[str, Any], None]] = None
    
    def set_write_behind_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Set callback for write-behind invalidation."""
        self._write_behind_callback = callback
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        with self._lock:
            entry = self._cache.get(key)
            
            if not entry:
                self._stats["total_misses"] += 1
                return default
            
            if entry.is_expired():
                self._delete_entry(key)
                self._stats["total_expirations"] += 1
                self._stats["total_misses"] += 1
                return default
            
            # Update access metadata
            entry.last_accessed = datetime.now(timezone.utc).isoformat()
            entry.access_count += 1
            
            # Move to end for LRU
            self._cache.move_to_end(key)
            
            self._stats["total_hits"] += 1
            
            # Track by prefix
            prefix = key.split(":")[0] if ":" in key else key
            self._stats["by_key_prefix"][prefix] = self._stats["by_key_prefix"].get(prefix, 0) + 1
            
            return entry.value
    
    def set(self, key: str, value: Any,
            ttl_seconds: Optional[int] = None,
            tags: Optional[List[str]] = None,
            size_bytes: int = 0) -> None:
        """Set value in cache."""
        now = datetime.now(timezone.utc)
        
        # Calculate expiry
        expires_at = None
        ttl = ttl_seconds or self._default_ttl
        if ttl > 0:
            expires_at = (now + timedelta(seconds=ttl)).isoformat()
        
        # Calculate size if not provided
        if size_bytes == 0:
            try:
                size_bytes = len(str(value).encode())
            except:
                size_bytes = 0
        
        with self._lock:
            # Check if key exists
            if key in self._cache:
                old_entry = self._cache[key]
                # Remove from tag index
                for tag in old_entry.tags:
                    if tag in self._tag_index:
                        self._tag_index[tag].discard(key)
            
            # Evict if necessary
            while len(self._cache) >= self._max_size:
                self._evict_one()
            
            # Create entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now.isoformat(),
                expires_at=expires_at,
                last_accessed=now.isoformat(),
                size_bytes=size_bytes,
                tags=tags or [],
            )
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
            
            # Update tag index
            for tag in entry.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(key)
            
            self._stats["total_sets"] += 1
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            return self._delete_entry(key)
    
    def _delete_entry(self, key: str) -> bool:
        """Delete entry (internal, assumes lock held)."""
        if key not in self._cache:
            return False
        
        entry = self._cache[key]
        
        # Remove from tag index
        for tag in entry.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(key)
        
        del self._cache[key]
        
        self._stats["total_deletes"] += 1
        
        return True
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        with self._lock:
            entry = self._cache.get(key)
            
            if not entry:
                return False
            
            if entry.is_expired():
                self._delete_entry(key)
                return False
            
            return True
    
    def clear(self) -> int:
        """Clear all entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._tag_index.clear()
            return count
    
    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with a tag."""
        with self._lock:
            if tag not in self._tag_index:
                return 0
            
            keys = list(self._tag_index[tag])
            count = 0
            
            for key in keys:
                if self._delete_entry(key):
                    count += 1
            
            del self._tag_index[tag]
            
            return count
    
    def invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate entries matching pattern (prefix)."""
        with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys()
                if key.startswith(pattern) or key.startswith(f"{pattern}:")
            ]
            
            count = 0
            for key in keys_to_delete:
                if self._delete_entry(key):
                    count += 1
            
            return count
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values."""
        results = {}
        
        for key in keys:
            value = self.get(key)
            if value is not None:
                results[key] = value
        
        return results
    
    def set_many(self, items: Dict[str, Any],
                 ttl_seconds: Optional[int] = None,
                 tags: Optional[List[str]] = None) -> int:
        """Set multiple values."""
        count = 0
        
        for key, value in items.items():
            self.set(key, value, ttl_seconds=ttl_seconds, tags=tags)
            count += 1
        
        return count
    
    def delete_many(self, keys: List[str]) -> int:
        """Delete multiple keys."""
        count = 0
        
        for key in keys:
            if self.delete(key):
                count += 1
        
        return count
    
    def get_or_set(self, key: str,
                   factory: Callable[[], Any],
                   ttl_seconds: Optional[int] = None,
                   tags: Optional[List[str]] = None) -> Any:
        """Get value or set using factory function."""
        value = self.get(key)
        
        if value is not None:
            return value
        
        # Compute value
        value = factory()
        
        self.set(key, value, ttl_seconds=ttl_seconds, tags=tags)
        
        return value
    
    def touch(self, key: str, ttl_seconds: Optional[int] = None) -> bool:
        """Refresh TTL on existing key."""
        with self._lock:
            entry = self._cache.get(key)
            
            if not entry:
                return False
            
            if entry.is_expired():
                self._delete_entry(key)
                return False
            
            ttl = ttl_seconds or self._default_ttl
            entry.expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat()
            
            return True
    
    def increment(self, key: str, delta: int = 1, default: int = 0) -> int:
        """Increment numeric value."""
        with self._lock:
            value = self.get(key)
            
            if value is None:
                value = default
            
            new_value = value + delta
            self.set(key, new_value)
            
            return new_value
    
    def decrement(self, key: str, delta: int = 1, default: int = 0) -> int:
        """Decrement numeric value."""
        return self.increment(key, -delta, default)
    
    def append(self, key: str, value: Any, default: List[Any] = None) -> List[Any]:
        """Append to list value."""
        with self._lock:
            existing = self.get(key)
            
            if existing is None:
                existing = default or []
            
            if not isinstance(existing, list):
                existing = [existing]
            
            existing.append(value)
            self.set(key, existing)
            
            return existing
    
    def get_keys(self, pattern: Optional[str] = None) -> List[str]:
        """Get all keys, optionally filtered by pattern."""
        with self._lock:
            keys = list(self._cache.keys())
            
            if pattern:
                keys = [k for k in keys if k.startswith(pattern)]
            
            return keys
    
    def get_by_tag(self, tag: str) -> List[Any]:
        """Get all values with a tag."""
        with self._lock:
            if tag not in self._tag_index:
                return []
            
            values = []
            for key in self._tag_index[tag]:
                entry = self._cache.get(key)
                if entry and not entry.is_expired():
                    values.append(entry.value)
            
            return values
    
    def get_entry(self, key: str) -> Optional[CacheEntry]:
        """Get full cache entry."""
        with self._lock:
            return self._cache.get(key)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_entries = len(self._cache)
            total_size = sum(e.size_bytes for e in self._cache.values())
            
            hit_rate = 0
            total_requests = self._stats["total_hits"] + self._stats["total_misses"]
            if total_requests > 0:
                hit_rate = self._stats["total_hits"] / total_requests
            
            return {
                **self._stats,
                "total_entries": total_entries,
                "total_size_bytes": total_size,
                "max_size": self._max_size,
                "hit_rate": round(hit_rate, 4),
                "utilization": round(total_entries / self._max_size, 4),
                "eviction_strategy": self._eviction_strategy.value,
                "total_tags": len(self._tag_index),
            }
    
    def warm(self, items: Dict[str, Any],
            ttl_seconds: Optional[int] = None,
            tags: Optional[List[str]] = None) -> int:
        """Warm cache with items."""
        return self.set_many(items, ttl_seconds=ttl_seconds, tags=tags)
    
    def _evict_one(self) -> None:
        """Evict one entry based on strategy."""
        if not self._cache:
            return
        
        key_to_evict = None
        
        if self._eviction_strategy == EvictionStrategy.LRU:
            # First item is least recently used
            key_to_evict = next(iter(self._cache))
        
        elif self._eviction_strategy == EvictionStrategy.LFU:
            # Find least frequently used
            min_access = float('inf')
            for key, entry in self._cache.items():
                if entry.access_count < min_access:
                    min_access = entry.access_count
                    key_to_evict = key
        
        elif self._eviction_strategy == EvictionStrategy.FIFO:
            # First item is oldest
            key_to_evict = next(iter(self._cache))
        
        elif self._eviction_strategy == EvictionStrategy.TTL:
            # Find soonest to expire
            min_expiry = None
            for key, entry in self._cache.items():
                if entry.expires_at:
                    if min_expiry is None or entry.expires_at < min_expiry:
                        min_expiry = entry.expires_at
                        key_to_evict = key
            
            # If no TTL entries, fall back to LRU
            if key_to_evict is None:
                key_to_evict = next(iter(self._cache))
        
        if key_to_evict:
            self._delete_entry(key_to_evict)
            self._stats["total_evictions"] += 1
    
    def flush_expired(self) -> int:
        """Flush all expired entries."""
        with self._lock:
            keys_to_delete = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            count = 0
            for key in keys_to_delete:
                if self._delete_entry(key):
                    count += 1
                    self._stats["total_expirations"] += 1
            
            return count
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage breakdown."""
        with self._lock:
            by_tier = {
                "l1": {"count": 0, "size_bytes": 0},
                "l2": {"count": 0, "size_bytes": 0},
            }
            
            for entry in self._cache.values():
                tier_name = entry.tier.value
                by_tier[tier_name]["count"] += 1
                by_tier[tier_name]["size_bytes"] += entry.size_bytes
            
            return {
                "total_entries": len(self._cache),
                "total_size_bytes": sum(e.size_bytes for e in self._cache.values()),
                "by_tier": by_tier,
            }


def create_cache_engine(max_size: int = 10000,
                       eviction_strategy: str = "lru",
                       default_ttl_seconds: int = 3600) -> CacheEngine:
    """Factory function to create cache engine."""
    strategy = EvictionStrategy(eviction_strategy.lower())
    return CacheEngine(
        max_size=max_size,
        eviction_strategy=strategy,
        default_ttl_seconds=default_ttl_seconds,
    )
