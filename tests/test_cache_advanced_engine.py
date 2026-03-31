"""Tests for Cache Advanced Engine — Slice 54."""
import pytest
from copilot_core.cache_advanced.engine import (
    CacheEngine,
    CacheTier,
    EvictionStrategy,
    InvalidationStrategy,
    CacheEntry,
    create_cache_engine,
)
from datetime import datetime, timezone, timedelta
import time


class TestCacheEngine:
    """Test cache advanced engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_cache_engine()
        assert engine is not None
    
    def test_create_engine_with_max_size(self):
        """Test engine creation with max size."""
        engine = create_cache_engine(max_size=5000)
        assert engine._max_size == 5000
    
    def test_create_engine_with_eviction(self):
        """Test engine creation with eviction strategy."""
        engine = create_cache_engine(eviction_strategy="lfu")
        assert engine._eviction_strategy == EvictionStrategy.LFU
    
    def test_create_engine_with_ttl(self):
        """Test engine creation with default TTL."""
        engine = create_cache_engine(default_ttl_seconds=1800)
        assert engine._default_ttl == 1800
    
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
        """Test getting with default value."""
        engine = CacheEngine()
        
        result = engine.get("nonexistent", default="default_value")
        
        assert result == "default_value"
    
    def test_set_with_ttl(self):
        """Test setting with TTL."""
        engine = CacheEngine()
        
        engine.set("temp_key", "temp_value", ttl_seconds=2)
        
        # Should exist immediately
        assert engine.get("temp_key") == "temp_value"
        
        # Wait for expiry
        time.sleep(2.1)
        
        # Should be expired
        assert engine.get("temp_key") is None
    
    def test_set_with_tags(self):
        """Test setting with tags."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", tags=["users", "active"])
        engine.set("key2", "value2", tags=["users", "inactive"])
        engine.set("key3", "value3", tags=["posts"])
        
        users = engine.get_by_tag("users")
        
        assert len(users) == 2
        assert "value1" in users
        assert "value2" in users
    
    def test_set_calculates_size(self):
        """Test that set calculates size automatically."""
        engine = CacheEngine()
        
        engine.set("key1", "a" * 100)
        
        entry = engine.get_entry("key1")
        
        assert entry.size_bytes > 0
        assert entry.size_bytes >= 100
    
    def test_set_with_custom_size(self):
        """Test setting with custom size."""
        engine = CacheEngine()
        
        engine.set("key1", "small", size_bytes=1000)
        
        entry = engine.get_entry("key1")
        
        assert entry.size_bytes == 1000
    
    def test_delete(self):
        """Test deleting key."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        result = engine.delete("key1")
        
        assert result is True
        assert engine.get("key1") is None
    
    def test_delete_nonexistent(self):
        """Test deleting nonexistent key."""
        engine = CacheEngine()
        
        result = engine.delete("nonexistent")
        
        assert result is False
    
    def test_exists(self):
        """Test checking if key exists."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        assert engine.exists("key1") is True
        assert engine.exists("nonexistent") is False
    
    def test_exists_expired(self):
        """Test that exists returns False for expired keys."""
        engine = CacheEngine()
        
        engine.set("temp", "value", ttl_seconds=1)
        
        time.sleep(1.1)
        
        assert engine.exists("temp") is False
    
    def test_clear(self):
        """Test clearing all entries."""
        engine = CacheEngine()
        
        for i in range(10):
            engine.set(f"key{i}", f"value{i}")
        
        count = engine.clear()
        
        assert count == 10
        assert len(engine.get_keys()) == 0
    
    def test_invalidate_by_tag(self):
        """Test invalidating by tag."""
        engine = CacheEngine()
        
        engine.set("user:1", "u1", tags=["users"])
        engine.set("user:2", "u2", tags=["users"])
        engine.set("post:1", "p1", tags=["posts"])
        
        count = engine.invalidate_by_tag("users")
        
        assert count == 2
        assert engine.exists("user:1") is False
        assert engine.exists("user:2") is False
        assert engine.exists("post:1") is True
    
    def test_invalidate_by_tag_nonexistent(self):
        """Test invalidating nonexistent tag."""
        engine = CacheEngine()
        
        count = engine.invalidate_by_tag("nonexistent")
        
        assert count == 0
    
    def test_invalidate_by_pattern(self):
        """Test invalidating by pattern."""
        engine = CacheEngine()
        
        engine.set("user:1", "u1")
        engine.set("user:2", "u2")
        engine.set("user:3", "u3")
        engine.set("post:1", "p1")
        
        count = engine.invalidate_by_pattern("user:")
        
        assert count == 3
        assert engine.exists("user:1") is False
        assert engine.exists("post:1") is True
    
    def test_get_many(self):
        """Test getting multiple values."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        engine.set("key3", "value3")
        
        results = engine.get_many(["key1", "key2", "key4"])
        
        assert len(results) == 2
        assert results["key1"] == "value1"
        assert results["key2"] == "value2"
    
    def test_set_many(self):
        """Test setting multiple values."""
        engine = CacheEngine()
        
        items = {"key1": "value1", "key2": "value2", "key3": "value3"}
        
        count = engine.set_many(items)
        
        assert count == 3
        assert engine.get("key1") == "value1"
        assert engine.get("key2") == "value2"
    
    def test_set_many_with_ttl(self):
        """Test setting multiple values with TTL."""
        engine = CacheEngine()
        
        items = {"key1": "value1", "key2": "value2"}
        
        engine.set_many(items, ttl_seconds=2)
        
        assert engine.get("key1") == "value1"
        
        time.sleep(2.1)
        
        assert engine.get("key1") is None
    
    def test_set_many_with_tags(self):
        """Test setting multiple values with tags."""
        engine = CacheEngine()
        
        items = {"key1": "value1", "key2": "value2"}
        
        engine.set_many(items, tags=["batch"])
        
        values = engine.get_by_tag("batch")
        
        assert len(values) == 2
    
    def test_delete_many(self):
        """Test deleting multiple keys."""
        engine = CacheEngine()
        
        for i in range(5):
            engine.set(f"key{i}", f"value{i}")
        
        count = engine.delete_many(["key0", "key1", "key99"])
        
        assert count == 2
        assert not engine.exists("key0")
        assert not engine.exists("key1")
        assert engine.exists("key2")
    
    def test_get_or_set_cache_hit(self):
        """Test get_or_set with cache hit."""
        engine = CacheEngine()
        
        call_count = [0]
        
        def factory():
            call_count[0] += 1
            return "computed_value"
        
        engine.set("key1", "cached_value")
        
        result = engine.get_or_set("key1", factory)
        
        assert result == "cached_value"
        assert call_count[0] == 0  # Factory not called
    
    def test_get_or_set_cache_miss(self):
        """Test get_or_set with cache miss."""
        engine = CacheEngine()
        
        call_count = [0]
        
        def factory():
            call_count[0] += 1
            return "computed_value"
        
        result = engine.get_or_set("key1", factory)
        
        assert result == "computed_value"
        assert call_count[0] == 1  # Factory called once
        
        # Second call should use cache
        result2 = engine.get_or_set("key1", factory)
        
        assert result2 == "computed_value"
        assert call_count[0] == 1  # Factory not called again
    
    def test_touch(self):
        """Test refreshing TTL."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", ttl_seconds=2)
        
        time.sleep(1.5)
        
        # Refresh TTL
        result = engine.touch("key1", ttl_seconds=5)
        
        assert result is True
        
        # Should still exist after original TTL
        time.sleep(2)
        
        assert engine.exists("key1") is True
    
    def test_touch_nonexistent(self):
        """Test touching nonexistent key."""
        engine = CacheEngine()
        
        result = engine.touch("nonexistent")
        
        assert result is False
    
    def test_touch_expired(self):
        """Test touching expired key."""
        engine = CacheEngine()
        
        engine.set("temp", "value", ttl_seconds=1)
        
        time.sleep(1.1)
        
        result = engine.touch("temp")
        
        assert result is False
    
    def test_increment(self):
        """Test incrementing numeric value."""
        engine = CacheEngine()
        
        engine.set("counter", 10)
        
        result = engine.increment("counter", delta=5)
        
        assert result == 15
        assert engine.get("counter") == 15
    
    def test_increment_nonexistent(self):
        """Test incrementing nonexistent key."""
        engine = CacheEngine()
        
        result = engine.increment("counter", delta=5, default=10)
        
        assert result == 15
        assert engine.get("counter") == 15
    
    def test_decrement(self):
        """Test decrementing numeric value."""
        engine = CacheEngine()
        
        engine.set("counter", 20)
        
        result = engine.decrement("counter", delta=5)
        
        assert result == 15
        assert engine.get("counter") == 15
    
    def test_append_to_list(self):
        """Test appending to list value."""
        engine = CacheEngine()
        
        engine.set("items", ["a", "b"])
        
        result = engine.append("items", "c")
        
        assert result == ["a", "b", "c"]
        assert engine.get("items") == ["a", "b", "c"]
    
    def test_append_to_nonexistent(self):
        """Test appending to nonexistent key."""
        engine = CacheEngine()
        
        result = engine.append("items", "first", default=["init"])
        
        assert result == ["init", "first"]
    
    def test_append_creates_list(self):
        """Test that append creates list if value doesn't exist."""
        engine = CacheEngine()
        
        result = engine.append("items", "first")
        
        assert result == ["first"]
    
    def test_get_keys(self):
        """Test getting all keys."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        engine.set("key3", "value3")
        
        keys = engine.get_keys()
        
        assert len(keys) == 3
        assert "key1" in keys
    
    def test_get_keys_with_pattern(self):
        """Test getting keys with pattern."""
        engine = CacheEngine()
        
        engine.set("user:1", "u1")
        engine.set("user:2", "u2")
        engine.set("post:1", "p1")
        
        keys = engine.get_keys(pattern="user:")
        
        assert len(keys) == 2
        assert "user:1" in keys
        assert "user:2" in keys
    
    def test_get_by_tag(self):
        """Test getting values by tag."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", tags=["tag1"])
        engine.set("key2", "value2", tags=["tag1", "tag2"])
        engine.set("key3", "value3", tags=["tag2"])
        
        tag1_values = engine.get_by_tag("tag1")
        tag2_values = engine.get_by_tag("tag2")
        
        assert len(tag1_values) == 2
        assert len(tag2_values) == 2
    
    def test_get_by_tag_nonexistent(self):
        """Test getting values by nonexistent tag."""
        engine = CacheEngine()
        
        values = engine.get_by_tag("nonexistent")
        
        assert values == []
    
    def test_get_entry(self):
        """Test getting full cache entry."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", ttl_seconds=60, tags=["test"])
        
        entry = engine.get_entry("key1")
        
        assert entry is not None
        assert entry.key == "key1"
        assert entry.value == "value1"
        assert entry.tags == ["test"]
    
    def test_get_entry_nonexistent(self):
        """Test getting nonexistent entry."""
        engine = CacheEngine()
        
        entry = engine.get_entry("nonexistent")
        
        assert entry is None
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        
        engine.get("key1")
        engine.get("key1")
        engine.get("key2")
        engine.get("nonexistent")
        
        stats = engine.get_statistics()
        
        assert stats["total_sets"] == 2
        assert stats["total_hits"] == 3
        assert stats["total_misses"] == 1
        assert stats["total_entries"] == 2
    
    def test_statistics_hit_rate(self):
        """Test hit rate calculation."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        # 3 hits, 1 miss
        engine.get("key1")
        engine.get("key1")
        engine.get("key1")
        engine.get("nonexistent")
        
        stats = engine.get_statistics()
        
        assert stats["hit_rate"] == 0.75
    
    def test_statistics_utilization(self):
        """Test utilization calculation."""
        engine = CacheEngine(max_size=100)
        
        for i in range(50):
            engine.set(f"key{i}", f"value{i}")
        
        stats = engine.get_statistics()
        
        assert stats["utilization"] == 0.5
    
    def test_eviction_lru(self):
        """Test LRU eviction."""
        engine = CacheEngine(max_size=3, eviction_strategy="lru")
        
        engine.set("key1", "value1")
        time.sleep(0.01)
        engine.set("key2", "value2")
        time.sleep(0.01)
        engine.set("key3", "value3")
        
        # Access key1 and key3 to make key2 the LRU
        engine.get("key1")
        engine.get("key3")
        
        # Add new key - should evict key2
        engine.set("key4", "value4")
        
        assert engine.exists("key1") is True
        assert engine.exists("key2") is False
        assert engine.exists("key3") is True
        assert engine.exists("key4") is True
    
    def test_eviction_lfu(self):
        """Test LFU eviction."""
        engine = CacheEngine(max_size=3, eviction_strategy="lfu")
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        engine.set("key3", "value3")
        
        # Access key1 and key3 more frequently
        for i in range(5):
            engine.get("key1")
            engine.get("key3")
        
        # Add new key - should evict key2 (least frequently used)
        engine.set("key4", "value4")
        
        assert engine.exists("key2") is False
    
    def test_eviction_fifo(self):
        """Test FIFO eviction."""
        engine = CacheEngine(max_size=3, eviction_strategy="fifo")
        
        engine.set("key1", "value1")
        time.sleep(0.01)
        engine.set("key2", "value2")
        time.sleep(0.01)
        engine.set("key3", "value3")
        
        # Add new key - should evict key1 (first in)
        engine.set("key4", "value4")
        
        assert engine.exists("key1") is False
        assert engine.exists("key2") is True
        assert engine.exists("key3") is True
        assert engine.exists("key4") is True
    
    def test_eviction_updates_stats(self):
        """Test that eviction updates statistics."""
        engine = CacheEngine(max_size=2, eviction_strategy="lru")
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        engine.set("key3", "value3")  # Should evict key1
        
        stats = engine.get_statistics()
        
        assert stats["total_evictions"] == 1
    
    def test_flush_expired(self):
        """Test flushing expired entries."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", ttl_seconds=1)
        engine.set("key2", "value2", ttl_seconds=1)
        engine.set("key3", "value3", ttl_seconds=60)
        
        time.sleep(1.1)
        
        count = engine.flush_expired()
        
        assert count == 2
        assert engine.exists("key3") is True
    
    def test_flush_empty(self):
        """Test flushing when nothing expired."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", ttl_seconds=60)
        
        count = engine.flush_expired()
        
        assert count == 0
    
    def test_warm_cache(self):
        """Test warming cache."""
        engine = CacheEngine()
        
        items = {
            "config:db": {"host": "localhost", "port": 5432},
            "config:cache": {"host": "localhost", "port": 6379},
        }
        
        count = engine.warm(items, ttl_seconds=3600, tags=["config"])
        
        assert count == 2
        assert engine.get("config:db")["host"] == "localhost"
        
        config_values = engine.get_by_tag("config")
        assert len(config_values) == 2
    
    def test_memory_usage(self):
        """Test memory usage breakdown."""
        engine = CacheEngine()
        
        engine.set("key1", "a" * 100)
        engine.set("key2", "b" * 200)
        
        usage = engine.get_memory_usage()
        
        assert usage["total_entries"] == 2
        assert usage["total_size_bytes"] >= 300
        assert "by_tier" in usage
    
    def test_cache_entry_is_expired(self):
        """Test cache entry expiry check."""
        past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        expired_entry = CacheEntry(
            key="test",
            value="value",
            created_at=past,
            expires_at=past,
            last_accessed=past,
        )
        
        valid_entry = CacheEntry(
            key="test",
            value="value",
            created_at=past,
            expires_at=future,
            last_accessed=past,
        )
        
        no_expiry_entry = CacheEntry(
            key="test",
            value="value",
            created_at=past,
            expires_at=None,
            last_accessed=past,
        )
        
        assert expired_entry.is_expired() is True
        assert valid_entry.is_expired() is False
        assert no_expiry_entry.is_expired() is False
    
    def test_cache_entry_to_dict(self):
        """Test cache entry serialization."""
        entry = CacheEntry(
            key="test_key",
            value={"data": "value"},
            created_at="2025-01-01T00:00:00Z",
            expires_at="2025-01-02T00:00:00Z",
            last_accessed="2025-01-01T12:00:00Z",
            access_count=5,
            tier=CacheTier.L1,
            size_bytes=100,
            tags=["tag1", "tag2"],
        )
        
        d = entry.to_dict()
        
        assert d["key"] == "test_key"
        assert d["access_count"] == 5
        assert d["tier"] == "l1"
        assert d["tags"] == ["tag1", "tag2"]
    
    def test_cache_tier_enum_values(self):
        """Test cache tier enum values."""
        assert CacheTier.L1.value == "l1"
        assert CacheTier.L2.value == "l2"
    
    def test_eviction_strategy_enum_values(self):
        """Test eviction strategy enum values."""
        assert EvictionStrategy.LRU.value == "lru"
        assert EvictionStrategy.LFU.value == "lfu"
        assert EvictionStrategy.FIFO.value == "fifo"
        assert EvictionStrategy.TTL.value == "ttl"
    
    def test_entry_access_count_updated(self):
        """Test that access count is updated on get."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        for i in range(10):
            engine.get("key1")
        
        entry = engine.get_entry("key1")
        
        assert entry.access_count == 10
    
    def test_entry_last_accessed_updated(self):
        """Test that last_accessed is updated on get."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        time.sleep(0.01)
        
        engine.get("key1")
        
        entry = engine.get_entry("key1")
        
        assert entry.last_accessed > entry.created_at
    
    def test_statistics_by_key_prefix(self):
        """Test statistics by key prefix."""
        engine = CacheEngine()
        
        engine.set("user:1", "u1")
        engine.set("user:2", "u2")
        engine.set("post:1", "p1")
        
        engine.get("user:1")
        engine.get("user:2")
        engine.get("post:1")
        
        stats = engine.get_statistics()
        
        assert stats["by_key_prefix"]["user"] == 2
        assert stats["by_key_prefix"]["post"] == 1
    
    def test_tag_index_updated_on_delete(self):
        """Test that tag index is updated on delete."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", tags=["test"])
        engine.set("key2", "value2", tags=["test"])
        
        engine.delete("key1")
        
        values = engine.get_by_tag("test")
        
        assert len(values) == 1
        assert values[0] == "value2"
    
    def test_set_overwrites_existing(self):
        """Test that set overwrites existing value."""
        engine = CacheEngine()
        
        engine.set("key1", "old_value")
        engine.set("key1", "new_value")
        
        result = engine.get("key1")
        
        assert result == "new_value"
    
    def test_set_preserves_tags_on_overwrite(self):
        """Test that set updates tags on overwrite."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", tags=["old_tag"])
        engine.set("key1", "value2", tags=["new_tag"])
        
        old_values = engine.get_by_tag("old_tag")
        new_values = engine.get_by_tag("new_tag")
        
        assert len(old_values) == 0
        assert len(new_values) == 1
    
    def test_increment_negative_delta(self):
        """Test incrementing with negative delta."""
        engine = CacheEngine()
        
        engine.set("counter", 10)
        
        result = engine.increment("counter", delta=-5)
        
        assert result == 5
    
    def test_decrement_negative_delta(self):
        """Test decrementing with negative delta (adds)."""
        engine = CacheEngine()
        
        engine.set("counter", 10)
        
        result = engine.decrement("counter", delta=-5)
        
        assert result == 15
    
    def test_append_to_non_list_value(self):
        """Test appending to non-list value converts to list."""
        engine = CacheEngine()
        
        engine.set("key1", "string_value")
        
        result = engine.append("key1", "new_item")
        
        assert result == ["string_value", "new_item"]
    
    def test_get_keys_empty_cache(self):
        """Test getting keys from empty cache."""
        engine = CacheEngine()
        
        keys = engine.get_keys()
        
        assert keys == []
    
    def test_get_many_empty_list(self):
        """Test get_many with empty list."""
        engine = CacheEngine()
        
        results = engine.get_many([])
        
        assert results == {}
    
    def test_set_many_empty_dict(self):
        """Test set_many with empty dict."""
        engine = CacheEngine()
        
        count = engine.set_many({})
        
        assert count == 0
    
    def test_delete_many_empty_list(self):
        """Test delete_many with empty list."""
        engine = CacheEngine()
        
        count = engine.delete_many([])
        
        assert count == 0
    
    def test_invalidate_by_pattern_no_match(self):
        """Test invalidating pattern with no matches."""
        engine = CacheEngine()
        
        engine.set("user:1", "u1")
        engine.set("user:2", "u2")
        
        count = engine.invalidate_by_pattern("post:")
        
        assert count == 0
    
    def test_touch_preserves_value(self):
        """Test that touch preserves value."""
        engine = CacheEngine()
        
        engine.set("key1", {"complex": "value"}, ttl_seconds=1)
        
        time.sleep(0.5)
        
        engine.touch("key1", ttl_seconds=60)
        
        assert engine.get("key1") == {"complex": "value"}
    
    def test_get_or_set_with_ttl(self):
        """Test get_or_set with TTL."""
        engine = CacheEngine()
        
        def factory():
            return "computed"
        
        engine.get_or_set("key1", factory, ttl_seconds=2)
        
        assert engine.get("key1") == "computed"
        
        time.sleep(2.1)
        
        assert engine.get("key1") is None
    
    def test_statistics_total_deletes(self):
        """Test that statistics track total deletes."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        
        engine.delete("key1")
        engine.delete("key2")
        engine.delete("nonexistent")
        
        stats = engine.get_statistics()
        
        assert stats["total_deletes"] == 2
    
    def test_statistics_total_expirations(self):
        """Test that statistics track total expirations."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", ttl_seconds=1)
        
        time.sleep(1.1)
        
        engine.get("key1")  # Should trigger expiration
        
        stats = engine.get_statistics()
        
        assert stats["total_expirations"] >= 1
    
    def test_max_size_one(self):
        """Test cache with max_size=1."""
        engine = CacheEngine(max_size=1, eviction_strategy="lru")
        
        engine.set("key1", "value1")
        engine.set("key2", "value2")
        engine.set("key3", "value3")
        
        # Only key3 should remain
        assert engine.exists("key1") is False
        assert engine.exists("key2") is False
        assert engine.exists("key3") is True
    
    def test_ttl_zero_means_no_expiry(self):
        """Test that TTL=0 means no expiry."""
        engine = CacheEngine(default_ttl_seconds=0)
        
        engine.set("key1", "value1")
        
        # Should not expire
        time.sleep(0.1)
        
        assert engine.exists("key1") is True
    
    def test_entry_created_at_set(self):
        """Test that entry created_at is set."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        entry = engine.get_entry("key1")
        
        assert entry.created_at is not None
    
    def test_entry_expires_at_set(self):
        """Test that entry expires_at is set."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", ttl_seconds=60)
        
        entry = engine.get_entry("key1")
        
        assert entry.expires_at is not None
    
    def test_entry_last_accessed_initial(self):
        """Test that entry last_accessed is set initially."""
        engine = CacheEngine()
        
        engine.set("key1", "value1")
        
        entry = engine.get_entry("key1")
        
        assert entry.last_accessed is not None
        assert entry.last_accessed == entry.created_at
    
    def test_multiple_tags_per_entry(self):
        """Test entry with multiple tags."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", tags=["tag1", "tag2", "tag3"])
        
        tag1 = engine.get_by_tag("tag1")
        tag2 = engine.get_by_tag("tag2")
        tag3 = engine.get_by_tag("tag3")
        
        assert len(tag1) == 1
        assert len(tag2) == 1
        assert len(tag3) == 1
        assert tag1[0] == tag2[0] == tag3[0] == "value1"
    
    def test_eviction_ttl_strategy(self):
        """Test TTL eviction strategy."""
        engine = CacheEngine(max_size=3, eviction_strategy="ttl")
        
        # key1 expires soonest
        engine.set("key1", "value1", ttl_seconds=1)
        time.sleep(0.01)
        engine.set("key2", "value2", ttl_seconds=60)
        time.sleep(0.01)
        engine.set("key3", "value3", ttl_seconds=60)
        
        # Add new key - should evict key1 (soonest to expire)
        engine.set("key4", "value4")
        
        assert engine.exists("key1") is False
    
    def test_write_behind_callback(self):
        """Test write-behind callback."""
        engine = CacheEngine()
        
        called = []
        
        def callback(key, value):
            called.append((key, value))
        
        engine.set_write_behind_callback(callback)
        
        # Note: Current implementation doesn't auto-trigger write-behind
        # This is for future extension
        
        assert engine._write_behind_callback == callback
    
    def test_get_keys_pattern_empty_result(self):
        """Test get_keys with pattern returning empty result."""
        engine = CacheEngine()
        
        engine.set("user:1", "u1")
        engine.set("user:2", "u2")
        
        keys = engine.get_keys(pattern="post:")
        
        assert keys == []
    
    def test_clear_empty_cache(self):
        """Test clearing empty cache."""
        engine = CacheEngine()
        
        count = engine.clear()
        
        assert count == 0
    
    def test_increment_large_delta(self):
        """Test incrementing with large delta."""
        engine = CacheEngine()
        
        engine.set("counter", 0)
        
        result = engine.increment("counter", delta=1000000)
        
        assert result == 1000000
    
    def test_decrement_below_zero(self):
        """Test decrementing below zero."""
        engine = CacheEngine()
        
        engine.set("counter", 5)
        
        result = engine.decrement("counter", delta=10)
        
        assert result == -5
    
    def test_get_or_set_factory_exception(self):
        """Test get_or_set when factory raises exception."""
        engine = CacheEngine()
        
        def failing_factory():
            raise ValueError("Factory failed")
        
        with pytest.raises(ValueError):
            engine.get_or_set("key1", failing_factory)
        
        # Key should not be in cache
        assert not engine.exists("key1")
    
    def test_statistics_max_size(self):
        """Test that statistics include max_size."""
        engine = CacheEngine(max_size=5000)
        
        stats = engine.get_statistics()
        
        assert stats["max_size"] == 5000
    
    def test_statistics_eviction_strategy(self):
        """Test that statistics include eviction strategy."""
        engine = CacheEngine(eviction_strategy="lfu")
        
        stats = engine.get_statistics()
        
        assert stats["eviction_strategy"] == "lfu"
    
    def test_statistics_total_tags(self):
        """Test that statistics include total tags."""
        engine = CacheEngine()
        
        engine.set("key1", "value1", tags=["tag1"])
        engine.set("key2", "value2", tags=["tag2"])
        engine.set("key3", "value3", tags=["tag1", "tag3"])
        
        stats = engine.get_statistics()
        
        assert stats["total_tags"] == 3  # tag1, tag2, tag3
    
    def test_concurrent_access_thread_safety(self):
        """Test thread safety with concurrent access."""
        import threading
        
        engine = CacheEngine(max_size=1000)
        errors = []
        
        def writer():
            try:
                for i in range(100):
                    engine.set(f"key_{threading.current_thread().name}_{i}", i)
            except Exception as e:
                errors.append(e)
        
        def reader():
            try:
                for i in range(100):
                    engine.get(f"key_{threading.current_thread().name}_{i}")
            except Exception as e:
                errors.append(e)
        
        threads = []
        for i in range(5):
            t1 = threading.Thread(target=writer, name=f"writer_{i}")
            t2 = threading.Thread(target=reader, name=f"reader_{i}")
            threads.extend([t1, t2])
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(errors) == 0
