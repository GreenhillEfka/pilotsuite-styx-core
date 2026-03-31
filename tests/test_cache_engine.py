"""Tests for Cache Engine — Slice 35."""
import pytest
from copilot_core.cache.engine import (
    CacheEngine,
    CacheStrategy,
    CacheEntry,
    CacheStats,
    create_cache_engine,
)
from datetime import datetime, timezone, timedelta
import time


class TestCacheEngine:
    """Test cache engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_cache_engine()
        assert engine is not None
    
    def test_set_and_get(self):
        """Test basic set and get."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        result = engine.get("key1")
        
        assert result == "value1"
    
    def test_get_nonexistent_key(self):
        """Test getting nonexistent key."""
        engine = CacheEngine()
        
        result = engine.get("nonexistent")
        
        assert result is None
    
    def test_get_with_default(self):
        """Test get with default value."""
        engine = CacheEngine()
        
        result = engine.get("nonexistent", default="default_value")
        
        assert result == "default_value"
    
    def test_set_with_namespace(self):
        """Test set with namespace."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", namespace="ns1")
        engine.set("key1", "value2", namespace="ns2")
        
        assert engine.get("key1", namespace="ns1") == "value1"
        assert engine.get("key1", namespace="ns2") == "value2"
    
    def test_delete_key(self):
        """Test deleting key."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        result = engine.delete("key1")
        
        assert result is True
        assert engine.get("key1") is None
    
    def test_delete_nonexistent_key(self):
        """Test deleting nonexistent key."""
        engine = CacheEngine()
        
        result = engine.delete("nonexistent")
        
        assert result is False
    
    def test_ttl_expiration(self):
        """Test TTL expiration."""
        engine = CacheEngine(default_ttl_seconds=1)
        
        engine.set("key1", "value1")
        
        # Should exist immediately
        assert engine.get("key1") == "value1"
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired
        result = engine.get("key1")
        assert result is None
    
    def test_custom_ttl(self):
        """Test custom TTL per entry."""
        engine = CacheEngine(default_ttl_seconds=3600)
        
        engine.set("key1", "value1", ttl_seconds=1)
        
        assert engine.get("key1") == "value1"
        
        time.sleep(1.1)
        
        assert engine.get("key1") is None
    
    def test_lru_eviction(self):
        """Test LRU eviction."""
        engine = CacheEngine(max_size=3, strategy=CacheStrategy.LRU)
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        engine.set("key3", "value3")
        
        # Access key1 to make it recently used
        engine.get("key1")
        
        # Add new key, should evict key2 (least recently used)
        engine.set("key4", "value4")
        
        assert engine.get("key1") == "value1"
        assert engine.get("key2") is None  # Evicted
        assert engine.get("key3") == "value3"
        assert engine.get("key4") == "value4"
    
    def test_lfu_eviction(self):
        """Test LFU eviction."""
        engine = CacheEngine(max_size=3, strategy=CacheStrategy.LFU)
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        engine.set("key3", "value3")
        
        # Access key1 and key3 multiple times
        engine.get("key1")
        engine.get("key1")
        engine.get("key3")
        
        # Add new key, should evict key2 (least frequently used)
        engine.set("key4", "value4")
        
        assert engine.get("key1") == "value1"
        assert engine.get("key2") is None  # Evicted
        assert engine.get("key3") == "value3"
        assert engine.get("key4") == "value4"
    
    def test_fifo_eviction(self):
        """Test FIFO eviction."""
        engine = CacheEngine(max_size=3, strategy=CacheStrategy.FIFO)
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        engine.set("key3", "value3")
        
        # Access key1 (shouldn't matter for FIFO)
        engine.get("key1")
        
        # Add new key, should evict key1 (first in)
        engine.set("key4", "value4")
        
        assert engine.get("key1") is None  # Evicted (first in)
        assert engine.get("key2") == "value2"
        assert engine.get("key3") == "value3"
        assert engine.get("key4") == "value4"
    
    def test_ttl_eviction(self):
        """Test TTL-based eviction."""
        engine = CacheEngine(max_size=3, strategy=CacheStrategy.TTL)
        
        engine.set("key1", "value1", ttl_seconds=1)
        engine.set("key2", "value2", ttl_seconds=3600)
        engine.set("key3", "value3", ttl_seconds=3600)
        
        time.sleep(1.1)
        
        # Add new key, should evict key1 (earliest expiration)
        engine.set("key4", "value4")
        
        assert engine.get("key1") is None  # Evicted (expired first)
        assert engine.get("key2") == "value2"
        assert engine.get("key3") == "value3"
        assert engine.get("key4") == "value4"
    
    def test_clear_all(self):
        """Test clearing all cache."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        engine.set("key3", "value3")
        
        count = engine.clear()
        
        assert count == 3
        assert engine.get_size() == 0
    
    def test_clear_namespace(self):
        """Test clearing specific namespace."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", namespace="ns1")
        engine.set("key2", "value2", namespace="ns2")
        engine.set("key3", "value3", namespace="ns1")
        
        count = engine.clear(namespace="ns1")
        
        assert count == 2
        assert engine.get("key1", namespace="ns1") is None
        assert engine.get("key2", namespace="ns2") == "value2"
        assert engine.get("key3", namespace="ns1") is None
    
    def test_invalidate_pattern(self):
        """Test invalidating by pattern."""
        engine = CacheEngine()
        
        engine.set("user:1", "value1")
        engine.set("user:2", "value2")
        engine.set("user:3", "value3")
        engine.set("post:1", "value4")
        
        count = engine.invalidate_pattern("user:*")
        
        assert count == 3
        assert engine.get("user:1") is None
        assert engine.get("user:2") is None
        assert engine.get("user:3") is None
        assert engine.get("post:1") == "value4"
    
    def test_get_stats(self):
        """Test getting cache statistics."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        engine.get("key1")  # Hit
        engine.get("key1")  # Hit
        engine.get("nonexistent")  # Miss
        
        stats = engine.get_stats()
        
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["sets"] == 1
    
    def test_get_all_stats(self):
        """Test getting all statistics."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", namespace="ns1")
        engine.set("key2", "value2", namespace="ns2")
        
        engine.get("key1", namespace="ns1")
        engine.get("key2", namespace="ns2")
        engine.get("nonexistent", namespace="ns1")
        
        all_stats = engine.get_all_stats()
        
        assert all_stats["total_entries"] == 2
        assert "ns1" in all_stats["namespaces"]
        assert "ns2" in all_stats["namespaces"]
        assert "totals" in all_stats
    
    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        # 2 hits, 1 miss
        engine.get("key1")
        engine.get("key1")
        engine.get("nonexistent")
        
        stats = engine.get_stats()
        
        assert stats["hit_rate"] == pytest.approx(0.6667, rel=0.01)
    
    def test_get_entry(self):
        """Test getting cache entry details."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", namespace="test")
        
        entry = engine.get_entry("key1", namespace="test")
        
        assert entry is not None
        assert entry["key"] == "key1"
        assert entry["value"] == "value1"
        assert entry["namespace"] == "test"
    
    def test_get_nonexistent_entry(self):
        """Test getting nonexistent entry."""
        engine = CacheEngine()
        
        entry = engine.get_entry("nonexistent")
        
        assert entry is None
    
    def test_get_all_entries(self):
        """Test getting all entries."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        engine.set("key3", "value3")
        
        entries = engine.get_all_entries(limit=10)
        
        assert len(entries) == 3
    
    def test_get_all_entries_filtered_by_namespace(self):
        """Test getting entries filtered by namespace."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", namespace="ns1")
        engine.set("key2", "value2", namespace="ns2")
        engine.set("key3", "value3", namespace="ns1")
        
        entries = engine.get_all_entries(namespace="ns1")
        
        assert len(entries) == 2
        assert all(e["namespace"] == "ns1" for e in entries)
    
    def test_get_all_entries_limit(self):
        """Test getting entries with limit."""
        engine = CacheEngine()
        
        for i in range(10):
            engine.set(f"key{i}", f"value{i}")
        
        entries = engine.get_all_entries(limit=5)
        
        assert len(entries) == 5
    
    def test_warm_cache(self):
        """Test cache warming."""
        engine = CacheEngine()
        
        call_count = [0]
        
        def loader():
            call_count[0] += 1
            return "loaded_value"
        
        # First call should load
        result1 = engine.warm_cache("key1", loader)
        assert result1 == "loaded_value"
        assert call_count[0] == 1
        
        # Second call should use cache
        result2 = engine.warm_cache("key1", loader)
        assert result2 == "loaded_value"
        assert call_count[0] == 1  # Not called again
    
    def test_get_or_set(self):
        """Test get or set."""
        engine = CacheEngine()
        
        result1 = engine.get_or_set("key1", "default_value")
        assert result1 == "default_value"
        
        result2 = engine.get_or_set("key1", "other_default")
        assert result2 == "default_value"  # Cached value returned
    
    def test_touch(self):
        """Test touching entry."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        result = engine.touch("key1")
        
        assert result is True
        
        entry = engine.get_entry("key1")
        assert entry["access_count"] >= 1
    
    def test_touch_nonexistent(self):
        """Test touching nonexistent entry."""
        engine = CacheEngine()
        
        result = engine.touch("nonexistent")
        
        assert result is False
    
    def test_exists(self):
        """Test exists check."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        assert engine.exists("key1") is True
        assert engine.exists("nonexistent") is False
    
    def test_exists_expired(self):
        """Test exists with expired entry."""
        engine = CacheEngine(default_ttl_seconds=1)
        
        engine.set("key1", "value1")
        
        assert engine.exists("key1") is True
        
        time.sleep(1.1)
        
        assert engine.exists("key1") is False
    
    def test_get_size(self):
        """Test getting cache size."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        engine.set("key3", "value3", namespace="ns1")
        
        assert engine.get_size() == 3
        assert engine.get_size(namespace="ns1") == 1
    
    def test_get_memory_usage(self):
        """Test getting memory usage."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", size_bytes=100)
        engine.set("key2", "value2", size_bytes=200)
        
        usage = engine.get_memory_usage()
        
        assert usage == 300
    
    def test_cleanup_expired(self):
        """Test cleaning up expired entries."""
        engine = CacheEngine(default_ttl_seconds=1)
        
        engine.set("key1", "value1")
        engine.set("key2", "value2", ttl_seconds=3600)
        
        time.sleep(1.1)
        
        count = engine.cleanup_expired()
        
        assert count == 1
        assert engine.get("key1") is None
        assert engine.get("key2") == "value2"
    
    def test_entries_sorted_by_last_accessed(self):
        """Test that entries are sorted by last_accessed."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        time.sleep(0.01)
        engine.set("key2", "value2")
        time.sleep(0.01)
        engine.set("key3", "value3")
        
        # Access key1 to make it most recent
        engine.get("key1")
        
        entries = engine.get_all_entries(limit=10)
        
        # key1 should be first (most recently accessed)
        assert entries[0]["key"] == "key1"
    
    def test_cache_entry_to_dict(self):
        """Test cache entry serialization."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            namespace="test",
            created_at="2026-03-31T12:00:00Z",
            expires_at="2026-03-31T13:00:00Z",
            last_accessed="2026-03-31T12:30:00Z",
            access_count=5,
            size_bytes=100,
        )
        
        d = entry.to_dict()
        
        assert d["key"] == "test_key"
        assert d["value"] == "test_value"
        assert d["access_count"] == 5
    
    def test_cache_stats_to_dict(self):
        """Test cache stats serialization."""
        stats = CacheStats(
            namespace="test",
            hits=100,
            misses=50,
            evictions=10,
            expirations=5,
            sets=150,
            deletes=5,
        )
        
        d = stats.to_dict()
        
        assert d["namespace"] == "test"
        assert d["hits"] == 100
        assert d["hit_rate"] == pytest.approx(0.6667, rel=0.01)
    
    def test_cache_strategy_enum_values(self):
        """Test cache strategy enum values."""
        assert CacheStrategy.LRU.value == "lru"
        assert CacheStrategy.LFU.value == "lfu"
        assert CacheStrategy.FIFO.value == "fifo"
        assert CacheStrategy.TTL.value == "ttl"
    
    def test_stats_track_evictions(self):
        """Test that stats track evictions."""
        engine = CacheEngine(max_size=2, strategy=CacheStrategy.LRU)
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        engine.set("key3", "value3")  # Should evict key1
        
        stats = engine.get_stats()
        
        assert stats["evictions"] >= 1
    
    def test_stats_track_expirations(self):
        """Test that stats track expirations."""
        engine = CacheEngine(default_ttl_seconds=1)
        
        engine.set("key1", "value1")
        
        time.sleep(1.1)
        
        engine.get("key1")  # Should trigger expiration
        
        stats = engine.get_stats()
        
        assert stats["expirations"] >= 1
    
    def test_stats_track_deletes(self):
        """Test that stats track deletes."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        engine.delete("key1")
        
        stats = engine.get_stats()
        
        assert stats["deletes"] == 1
    
    def test_multiple_namespaces_isolated(self):
        """Test that namespaces are isolated."""
        engine = CacheEngine()
        
        engine.set("key1", "ns1_value", namespace="ns1")
        engine.set("key1", "ns2_value", namespace="ns2")
        engine.set("key1", "default_value", namespace="default")
        
        assert engine.get("key1", namespace="ns1") == "ns1_value"
        assert engine.get("key1", namespace="ns2") == "ns2_value"
        assert engine.get("key1", namespace="default") == "default_value"
    
    def test_warm_cache_with_ttl(self):
        """Test cache warming with TTL."""
        engine = CacheEngine()
        
        def loader():
            return "loaded"
        
        engine.warm_cache("key1", loader, ttl_seconds=1)
        
        assert engine.get("key1") == "loaded"
        
        time.sleep(1.1)
        
        assert engine.get("key1") is None
    
    def test_get_size_empty_cache(self):
        """Test getting size of empty cache."""
        engine = CacheEngine()
        
        assert engine.get_size() == 0
    
    def test_get_memory_usage_no_size_info(self):
        """Test memory usage when size_bytes not set."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")  # No size_bytes
        
        usage = engine.get_memory_usage()
        
        assert usage == 0  # Entries without size_bytes don't count
    
    def test_clear_empty_cache(self):
        """Test clearing empty cache."""
        engine = CacheEngine()
        
        count = engine.clear()
        
        assert count == 0
    
    def test_invalidate_pattern_no_matches(self):
        """Test invalidating pattern with no matches."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        
        count = engine.invalidate_pattern("nonexistent*")
        
        assert count == 0
    
    def test_hit_rate_zero_when_no_accesses(self):
        """Test hit rate is zero when no accesses."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        stats = engine.get_stats()
        
        assert stats["hit_rate"] == 0.0
    
    def test_all_stats_empty_cache(self):
        """Test all stats with empty cache."""
        engine = CacheEngine()
        
        all_stats = engine.get_all_stats()
        
        assert all_stats["total_entries"] == 0
        assert all_stats["totals"]["hits"] == 0
        assert all_stats["totals"]["misses"] == 0
    
    def test_set_overwrites_existing_key(self):
        """Test that set overwrites existing key."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        engine.set("key1", "value2")
        
        result = engine.get("key1")
        
        assert result == "value2"
    
    def test_access_count_increments(self):
        """Test that access count increments."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        engine.get("key1")
        engine.get("key1")
        engine.get("key1")
        
        entry = engine.get_entry("key1")
        
        assert entry["access_count"] == 3
    
    def test_default_ttl_applied(self):
        """Test that default TTL is applied."""
        engine = CacheEngine(default_ttl_seconds=60)
        
        engine.set("key1", "value1")
        
        entry = engine.get_entry("key1")
        
        # Should have expiration ~60 seconds from now
        created = datetime.fromisoformat(entry["created_at"])
        expires = datetime.fromisoformat(entry["expires_at"])
        
        diff = (expires - created).total_seconds()
        
        assert diff == pytest.approx(60, rel=0.01)
    
    def test_eviction_stats_namespace(self):
        """Test eviction stats per namespace."""
        engine = CacheEngine(max_size=2, strategy=CacheStrategy.LRU)
        
        engine.set("key1", "value1", namespace="ns1")
        engine.set("key2", "value2", namespace="ns1")
        engine.set("key3", "value3", namespace="ns1")  # Eviction
        
        stats_ns1 = engine.get_stats("ns1")
        
        assert stats_ns1["evictions"] >= 1
    
    def test_get_entry_includes_all_metadata(self):
        """Test that get entry includes all metadata."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", namespace="test", size_bytes=100)
        
        entry = engine.get_entry("key1", namespace="test")
        
        assert "key" in entry
        assert "value" in entry
        assert "namespace" in entry
        assert "created_at" in entry
        assert "expires_at" in entry
        assert "last_accessed" in entry
        assert "access_count" in entry
        assert "size_bytes" in entry
