"""Tests for Cache Manager with LRU Eviction."""

import pytest
import time
from copilot_core.api.cache_manager import CacheManager, CacheEntry


class TestCacheManager:
    """Test cache manager functionality."""
    
    @pytest.fixture
    def cache(self):
        """Create a cache instance for testing."""
        return CacheManager(
            default_ttl=300,
            max_size=100,
        )
    
    @pytest.fixture
    def small_cache(self):
        """Create a small cache for LRU testing."""
        return CacheManager(
            default_ttl=300,
            max_size=5,  # Very small for testing eviction
        )
    
    def test_set_and_get(self, cache):
        """Test basic set and get operations."""
        cache.set("key1", "value1")
        result = cache.get("key1")
        assert result == "value1"
    
    def test_get_nonexistent_key(self, cache):
        """Test getting a key that doesn't exist."""
        result = cache.get("nonexistent")
        assert result is None
    
    def test_ttl_expiration(self):
        """Test that entries expire after TTL."""
        cache = CacheManager(default_ttl=1)  # 1 second TTL
        
        cache.set("key1", "value1")
        result = cache.get("key1")
        assert result == "value1"
        
        # Wait for expiration
        time.sleep(1.1)
        
        result = cache.get("key1")
        assert result is None
    
    def test_custom_ttl(self, cache):
        """Test setting custom TTL per key."""
        cache.set("key1", "value1", ttl=1)  # 1 second
        cache.set("key2", "value2", ttl=10)  # 10 seconds
        
        # Both should exist
        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        
        # Wait for first to expire
        time.sleep(1.1)
        
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
    
    def test_lru_eviction(self, small_cache):
        """Test LRU eviction when cache exceeds max_size."""
        # Fill cache beyond max_size (5)
        for i in range(7):
            small_cache.set(f"key{i}", f"value{i}")
        
        # First two keys should be evicted (oldest)
        assert small_cache.get("key0") is None
        assert small_cache.get("key1") is None
        
        # Last five should exist
        assert small_cache.get("key2") == "value2"
        assert small_cache.get("key3") == "value3"
        assert small_cache.get("key4") == "value4"
        assert small_cache.get("key5") == "value5"
        assert small_cache.get("key6") == "value6"
    
    def test_delete(self, cache):
        """Test deleting a key."""
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        result = cache.delete("key1")
        assert result is True
        assert cache.get("key1") is None
    
    def test_invalidate_pattern(self, cache):
        """Test invalidating cache entries by pattern."""
        cache.set("user:1", "data1")
        cache.set("user:2", "data2")
        cache.set("product:1", "prod1")
        
        # Invalidate all user entries
        count = cache.invalidate_pattern("user:*")
        assert count >= 2
        
        # User entries should be gone
        assert cache.get("user:1") is None
        assert cache.get("user:2") is None
        # Product entry should remain
        assert cache.get("product:1") == "prod1"
    
    def test_stats(self, cache):
        """Test getting cache statistics."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        stats = cache.stats()
        
        assert stats["local_size"] == 2
        assert stats["local_hits"] == 0
        
        # Access keys to generate hits
        cache.get("key1")
        cache.get("key1")
        
        stats = cache.stats()
        assert stats["local_hits"] == 2


class TestCacheEntry:
    """Test cache entry dataclass."""
    
    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        entry = CacheEntry(
            data={"test": "data"},
            timestamp=time.time(),
            ttl=300
        )
        
        assert entry.data == {"test": "data"}
        assert entry.ttl == 300
        assert entry.hit_count == 0
    
    def test_cache_entry_with_defaults(self):
        """Test cache entry with default values."""
        entry = CacheEntry(
            data="simple_value",
            timestamp=time.time(),
            ttl=60
        )
        
        assert entry.hit_count == 0
        assert entry.last_access == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
