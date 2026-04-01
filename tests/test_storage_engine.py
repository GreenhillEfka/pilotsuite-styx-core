"""Tests for Storage Engine — Slice 49."""
import pytest
from copilot_core.storage.engine import (
    StorageEngine,
    StorageBackend,
    StorageClass,
    StorageEntry,
    StorageQuery,
    MemoryStorageBackend,
    FileStorageBackend,
    create_storage_engine,
)
from datetime import datetime, timezone, timedelta
import tempfile
import os
import time


class TestStorageEngine:
    """Test storage engine."""
    
    def test_create_engine_memory(self):
        """Test creating engine with memory backend."""
        engine = create_storage_engine(StorageBackend.MEMORY)
        assert engine is not None
    
    def test_create_engine_file(self):
        """Test creating engine with file backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = create_storage_engine(StorageBackend.FILE, base_path=tmpdir)
            assert engine is not None
    
    def test_create_engine_file_without_path(self):
        """Test that file backend requires path."""
        with pytest.raises(ValueError):
            create_storage_engine(StorageBackend.FILE)
    
    def test_put_and_get(self):
        """Test basic put and get."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        
        result = engine.get("key1")
        
        assert result == "value1"
    
    def test_put_dict_value(self):
        """Test putting dict value."""
        engine = StorageEngine()
        
        engine.put("user:123", {"name": "Alice", "email": "alice@example.com"})
        
        result = engine.get("user:123")
        
        assert result["name"] == "Alice"
        assert result["email"] == "alice@example.com"
    
    def test_get_nonexistent_key(self):
        """Test getting nonexistent key."""
        engine = StorageEngine()
        
        result = engine.get("nonexistent")
        
        assert result is None
    
    def test_get_with_default(self):
        """Test getting with default value."""
        engine = StorageEngine()
        
        result = engine.get("nonexistent", default="default_value")
        
        assert result == "default_value"
    
    def test_exists(self):
        """Test checking if key exists."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        
        assert engine.exists("key1") is True
        assert engine.exists("nonexistent") is False
    
    def test_delete(self):
        """Test deleting key."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        
        result = engine.delete("key1")
        
        assert result is True
        assert engine.exists("key1") is False
    
    def test_delete_nonexistent(self):
        """Test deleting nonexistent key."""
        engine = StorageEngine()
        
        result = engine.delete("nonexistent")
        
        assert result is False
    
    def test_keys(self):
        """Test listing keys."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        engine.put("key2", "value2")
        engine.put("key3", "value3")
        
        keys = engine.keys()
        
        assert len(keys) == 3
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys
    
    def test_keys_with_prefix(self):
        """Test listing keys with prefix."""
        engine = StorageEngine()
        
        engine.put("user:1", "value1")
        engine.put("user:2", "value2")
        engine.put("post:1", "value3")
        
        keys = engine.keys(prefix="user:")
        
        assert len(keys) == 2
        assert "user:1" in keys
        assert "user:2" in keys
    
    def test_put_with_ttl(self):
        """Test putting with TTL."""
        engine = StorageEngine()
        
        engine.put("temp_key", "temp_value", ttl_seconds=1)
        
        # Should exist immediately
        assert engine.exists("temp_key") is True
        
        # Wait for expiry
        time.sleep(1.1)
        
        # Should be expired
        assert engine.exists("temp_key") is False
        assert engine.get("temp_key") is None
    
    def test_put_with_metadata(self):
        """Test putting with metadata."""
        engine = StorageEngine()
        
        engine.put(
            "key1",
            "value1",
            metadata={"content_type": "text/plain", "author": "test"},
        )
        
        metadata = engine.get_metadata("key1")
        
        assert metadata["content_type"] == "text/plain"
        assert metadata["author"] == "test"
    
    def test_put_with_storage_class(self):
        """Test putting with storage class."""
        engine = StorageEngine()
        
        engine.put("key1", "value1", storage_class=StorageClass.ARCHIVE)
        
        entry = engine.get_entry("key1")
        
        assert entry.storage_class == StorageClass.ARCHIVE
    
    def test_get_entry(self):
        """Test getting full entry."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        
        entry = engine.get_entry("key1")
        
        assert entry.key == "key1"
        assert entry.value == "value1"
        assert entry.version == 1
    
    def test_version_increment(self):
        """Test that version increments on update."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        engine.put("key1", "value2")
        engine.put("key1", "value3")
        
        version = engine.get_version("key1")
        
        assert version == 3
    
    def test_checksum_calculated(self):
        """Test that checksum is calculated."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        
        checksum = engine.get_checksum("key1")
        
        assert checksum is not None
        assert len(checksum) == 32  # MD5 hex
    
    def test_checksum_changes_with_value(self):
        """Test that checksum changes when value changes."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        checksum1 = engine.get_checksum("key1")
        
        engine.put("key1", "value2")
        checksum2 = engine.get_checksum("key1")
        
        assert checksum1 != checksum2
    
    def test_batch_get(self):
        """Test batch get."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        engine.put("key2", "value2")
        engine.put("key3", "value3")
        
        results = engine.batch_get(["key1", "key2", "key4"])
        
        assert len(results) == 2
        assert results["key1"] == "value1"
        assert results["key2"] == "value2"
    
    def test_batch_put(self):
        """Test batch put."""
        engine = StorageEngine()
        
        items = {"key1": "value1", "key2": "value2", "key3": "value3"}
        
        count = engine.batch_put(items)
        
        assert count == 3
        assert engine.get("key1") == "value1"
        assert engine.get("key2") == "value2"
    
    def test_batch_put_with_ttl(self):
        """Test batch put with TTL."""
        engine = StorageEngine()
        
        items = {"key1": "value1", "key2": "value2"}
        
        engine.batch_put(items, ttl_seconds=1)
        
        assert engine.exists("key1") is True
        
        time.sleep(1.1)
        
        assert engine.exists("key1") is False
    
    def test_batch_delete(self):
        """Test batch delete."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        engine.put("key2", "value2")
        engine.put("key3", "value3")
        
        count = engine.batch_delete(["key1", "key2", "key4"])
        
        assert count == 2
        assert not engine.exists("key1")
        assert not engine.exists("key2")
        assert engine.exists("key3")
    
    def test_clear_all(self):
        """Test clearing all entries."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        engine.put("key2", "value2")
        engine.put("key3", "value3")
        
        count = engine.clear()
        
        assert count == 3
        assert len(engine.keys()) == 0
    
    def test_clear_with_prefix(self):
        """Test clearing with prefix."""
        engine = StorageEngine()
        
        engine.put("user:1", "value1")
        engine.put("user:2", "value2")
        engine.put("post:1", "value3")
        
        count = engine.clear(prefix="user:")
        
        assert count == 2
        assert len(engine.keys()) == 1
        assert "post:1" in engine.keys()
    
    def test_query_by_prefix(self):
        """Test querying by prefix."""
        engine = StorageEngine()
        
        engine.put("user:alice", {"name": "Alice"})
        engine.put("user:bob", {"name": "Bob"})
        engine.put("post:1", {"title": "Post"})
        
        query = StorageQuery(prefix="user:")
        results = engine.query(query)
        
        assert len(results) == 2
    
    def test_query_by_suffix(self):
        """Test querying by suffix."""
        engine = StorageEngine()
        
        engine.put("config:dev", "dev_value")
        engine.put("config:prod", "prod_value")
        engine.put("data:dev", "data_value")
        
        query = StorageQuery(suffix=":dev")
        results = engine.query(query)
        
        assert len(results) == 2
    
    def test_query_by_contains(self):
        """Test querying by contains."""
        engine = StorageEngine()
        
        engine.put("user:123", "value1")
        engine.put("user:456", "value2")
        engine.put("post:123", "value3")
        
        query = StorageQuery(contains="user:")
        results = engine.query(query)
        
        assert len(results) == 2
    
    def test_query_by_metadata(self):
        """Test querying by metadata filter."""
        engine = StorageEngine()
        
        engine.put("key1", "value1", metadata={"type": "config", "env": "prod"})
        engine.put("key2", "value2", metadata={"type": "config", "env": "dev"})
        engine.put("key3", "value3", metadata={"type": "data"})
        
        query = StorageQuery(metadata_filter={"type": "config", "env": "prod"})
        results = engine.query(query)
        
        assert len(results) == 1
        assert results[0].key == "key1"
    
    def test_query_by_storage_class(self):
        """Test querying by storage class."""
        engine = StorageEngine()
        
        engine.put("key1", "value1", storage_class=StorageClass.STANDARD)
        engine.put("key2", "value2", storage_class=StorageClass.ARCHIVE)
        engine.put("key3", "value3", storage_class=StorageClass.STANDARD)
        
        query = StorageQuery(storage_class=StorageClass.ARCHIVE)
        results = engine.query(query)
        
        assert len(results) == 1
        assert results[0].key == "key2"
    
    def test_query_with_limit(self):
        """Test querying with limit."""
        engine = StorageEngine()
        
        for i in range(10):
            engine.put(f"key{i}", f"value{i}")
        
        query = StorageQuery(limit=5)
        results = engine.query(query)
        
        assert len(results) == 5
    
    def test_query_with_offset(self):
        """Test querying with offset."""
        engine = StorageEngine()
        
        for i in range(10):
            engine.put(f"key{i:02d}", f"value{i}")
        
        query1 = StorageQuery(limit=5, offset=0)
        query2 = StorageQuery(limit=5, offset=5)
        
        results1 = engine.query(query1)
        results2 = engine.query(query2)
        
        assert len(results1) == 5
        assert len(results2) == 5
        
        # Should be different keys
        keys1 = set(r.key for r in results1)
        keys2 = set(r.key for r in results2)
        
        assert keys1.isdisjoint(keys2)
    
    def test_add_listener(self):
        """Test adding storage listener."""
        engine = StorageEngine()
        
        events = []
        
        def listener(event, key, entry):
            events.append((event, key))
        
        engine.add_listener(listener)
        
        engine.put("key1", "value1")
        
        assert len(events) == 1
        assert events[0] == ("put", "key1")
    
    def test_remove_listener(self):
        """Test removing listener."""
        engine = StorageEngine()
        
        events = []
        
        def listener(event, key, entry):
            events.append((event, key))
        
        engine.add_listener(listener)
        engine.remove_listener(listener)
        
        engine.put("key1", "value1")
        
        assert len(events) == 0
    
    def test_listener_on_delete(self):
        """Test listener notified on delete."""
        engine = StorageEngine()
        
        events = []
        
        def listener(event, key, entry):
            events.append((event, key))
        
        engine.add_listener(listener)
        
        engine.put("key1", "value1")
        engine.delete("key1")
        
        assert len(events) == 2
        assert events[1] == ("delete", "key1")
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        engine.put("key2", "value2")
        engine.get("key1")
        engine.get("key1")
        engine.delete("key2")
        
        stats = engine.get_statistics()
        
        assert stats["total_writes"] == 2
        assert stats["total_reads"] == 2
        assert stats["total_deletes"] == 1
    
    def test_statistics_by_storage_class(self):
        """Test statistics by storage class."""
        engine = StorageEngine()
        
        engine.put("key1", "value1", storage_class=StorageClass.STANDARD)
        engine.put("key2", "value2", storage_class=StorageClass.ARCHIVE)
        engine.put("key3", "value3", storage_class=StorageClass.STANDARD)
        
        stats = engine.get_statistics()
        
        assert stats["by_storage_class"]["standard"] == 2
        assert stats["by_storage_class"]["archive"] == 1
    
    def test_get_size(self):
        """Test getting entry size."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        engine.put("key2", "a" * 1000)
        
        size1 = engine.get_size("key1")
        size2 = engine.get_size("key2")
        
        assert size1 < size2
        assert size2 > 1000
    
    def test_get_total_size(self):
        """Test getting total storage size."""
        engine = StorageEngine()
        
        engine.put("key1", "a" * 100)
        engine.put("key2", "b" * 200)
        
        total = engine.get_total_size()
        
        assert total > 300
    
    def test_set_metadata(self):
        """Test updating metadata."""
        engine = StorageEngine()
        
        engine.put("key1", "value1", metadata={"initial": "value"})
        
        result = engine.set_metadata("key1", {"updated": "true", "new_key": "new_value"})
        
        assert result is True
        
        metadata = engine.get_metadata("key1")
        
        assert metadata["initial"] == "value"
        assert metadata["updated"] == "true"
        assert metadata["new_key"] == "new_value"
    
    def test_set_metadata_nonexistent(self):
        """Test setting metadata on nonexistent key."""
        engine = StorageEngine()
        
        result = engine.set_metadata("nonexistent", {"key": "value"})
        
        assert result is False
    
    def test_get_expiry(self):
        """Test getting expiry time."""
        engine = StorageEngine()
        
        engine.put("key1", "value1", ttl_seconds=60)
        
        expiry = engine.get_expiry("key1")
        
        assert expiry is not None
    
    def test_get_expiry_no_ttl(self):
        """Test getting expiry when no TTL set."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        
        expiry = engine.get_expiry("key1")
        
        assert expiry is None
    
    def test_refresh_ttl(self):
        """Test refreshing TTL."""
        engine = StorageEngine()
        
        engine.put("key1", "value1", ttl_seconds=1)
        
        time.sleep(0.5)
        
        # Refresh TTL
        result = engine.refresh_ttl("key1", ttl_seconds=60)
        
        assert result is True
        
        # Should still exist after original TTL would have expired
        time.sleep(0.6)
        
        assert engine.exists("key1") is True
    
    def test_refresh_ttl_nonexistent(self):
        """Test refreshing TTL on nonexistent key."""
        engine = StorageEngine()
        
        result = engine.refresh_ttl("nonexistent", ttl_seconds=60)
        
        assert result is False
    
    def test_entry_is_expired(self):
        """Test entry expiry check."""
        entry = StorageEntry(
            key="test",
            value="value",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
            expires_at="2025-01-01T00:00:01Z",
        )
        
        assert entry.is_expired() is True
    
    def test_entry_not_expired(self):
        """Test entry not expired."""
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        entry = StorageEntry(
            key="test",
            value="value",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            expires_at=future,
        )
        
        assert entry.is_expired() is False
    
    def test_entry_no_expiry(self):
        """Test entry without expiry."""
        entry = StorageEntry(
            key="test",
            value="value",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        
        assert entry.is_expired() is False
    
    def test_entry_to_dict(self):
        """Test entry serialization."""
        entry = StorageEntry(
            key="test_key",
            value={"data": "value"},
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
            version=3,
            size_bytes=100,
            checksum="abc123",
            metadata={"type": "test"},
            storage_class=StorageClass.ARCHIVE,
        )
        
        d = entry.to_dict()
        
        assert d["key"] == "test_key"
        assert d["version"] == 3
        assert d["storage_class"] == "archive"
    
    def test_storage_class_enum_values(self):
        """Test storage class enum values."""
        assert StorageClass.STANDARD.value == "standard"
        assert StorageClass.INFREQUENT.value == "infrequent"
        assert StorageClass.ARCHIVE.value == "archive"
    
    def test_storage_backend_enum_values(self):
        """Test storage backend enum values."""
        assert StorageBackend.MEMORY.value == "memory"
        assert StorageBackend.FILE.value == "file"
        assert StorageBackend.S3.value == "s3"
    
    def test_memory_backend_count(self):
        """Test memory backend count."""
        backend = MemoryStorageBackend()
        
        backend.put(StorageEntry(
            key="key1",
            value="value1",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        ))
        backend.put(StorageEntry(
            key="key2",
            value="value2",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        ))
        
        assert backend.count() == 2
    
    def test_memory_backend_close(self):
        """Test memory backend close clears data."""
        backend = MemoryStorageBackend()
        
        backend.put(StorageEntry(
            key="key1",
            value="value1",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        ))
        
        backend.close()
        
        assert backend.count() == 0
    
    def test_file_backend_persistence(self):
        """Test file backend persistence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileStorageBackend(tmpdir)
            
            entry = StorageEntry(
                key="test_key",
                value={"data": "value"},
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
            )
            
            backend.put(entry)
            backend.close()
            
            # Create new backend instance
            backend2 = FileStorageBackend(tmpdir)
            
            retrieved = backend2.get("test_key")
            
            assert retrieved is not None
            assert retrieved.value == {"data": "value"}
            
            backend2.close()
    
    def test_file_backend_delete(self):
        """Test file backend delete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileStorageBackend(tmpdir)
            
            entry = StorageEntry(
                key="test_key",
                value="value",
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
            )
            
            backend.put(entry)
            
            result = backend.delete("test_key")
            
            assert result is True
            assert backend.get("test_key") is None
            
            backend.close()
    
    def test_file_backend_list_keys(self):
        """Test file backend list keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileStorageBackend(tmpdir)
            
            for i in range(5):
                entry = StorageEntry(
                    key=f"key{i}",
                    value=f"value{i}",
                    created_at="2025-01-01T00:00:00Z",
                    updated_at="2025-01-01T00:00:00Z",
                )
                backend.put(entry)
            
            keys = backend.list_keys()
            
            assert len(keys) == 5
            
            backend.close()
    
    def test_file_backend_list_keys_prefix(self):
        """Test file backend list keys with prefix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileStorageBackend(tmpdir)
            
            for i in range(3):
                entry = StorageEntry(
                    key=f"user:{i}",
                    value=f"value{i}",
                    created_at="2025-01-01T00:00:00Z",
                    updated_at="2025-01-01T00:00:00Z",
                )
                backend.put(entry)
            
            entry = StorageEntry(
                key="post:1",
                value="value",
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
            )
            backend.put(entry)
            
            keys = backend.list_keys(prefix="user:")
            
            assert len(keys) == 3
            
            backend.close()
    
    def test_query_matches_all_filters(self):
        """Test that query matches all filters."""
        query = StorageQuery(
            prefix="user:",
            suffix=":active",
            min_size=10,
        )
        
        # Matches all
        entry1 = StorageEntry(
            key="user:alice:active",
            value="a" * 20,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        
        # Wrong prefix
        entry2 = StorageEntry(
            key="post:alice:active",
            value="a" * 20,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        
        # Wrong suffix
        entry3 = StorageEntry(
            key="user:alice:inactive",
            value="a" * 20,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        
        # Too small
        entry4 = StorageEntry(
            key="user:bob:active",
            value="small",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        
        assert query.matches(entry1) is True
        assert query.matches(entry2) is False
        assert query.matches(entry3) is False
        assert query.matches(entry4) is False
    
    def test_set_backend(self):
        """Test changing backend."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        
        # Switch to new backend
        engine.set_backend(MemoryStorageBackend())
        
        # Old data should be gone
        assert engine.get("key1") is None
        
        # New writes should work
        engine.put("key2", "value2")
        assert engine.get("key2") == "value2"
    
    def test_expired_entry_deleted_on_get(self):
        """Test that expired entry is deleted on get."""
        engine = StorageEngine()
        
        engine.put("temp", "value", ttl_seconds=1)
        
        time.sleep(1.1)
        
        result = engine.get("temp")
        
        assert result is None
        assert not engine.exists("temp")
    
    def test_expired_entry_counted_in_stats(self):
        """Test that expired entries are counted."""
        engine = StorageEngine()
        
        engine.put("temp1", "value", ttl_seconds=1)
        engine.put("temp2", "value", ttl_seconds=1)
        
        time.sleep(1.1)
        
        engine.get("temp1")
        engine.get("temp2")
        
        stats = engine.get_statistics()
        
        assert stats["total_expired"] == 2
    
    def test_total_entries_in_stats(self):
        """Test that total entries is in stats."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        engine.put("key2", "value2")
        
        stats = engine.get_statistics()
        
        assert stats["total_entries"] == 2
    
    def test_updated_at_changes_on_put(self):
        """Test that updated_at changes on update."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        entry1 = engine.get_entry("key1")
        
        time.sleep(0.01)
        
        engine.put("key1", "value2")
        entry2 = engine.get_entry("key1")
        
        assert entry1.updated_at != entry2.updated_at
    
    def test_created_at_preserved_on_update(self):
        """Test that created_at is preserved on update."""
        engine = StorageEngine()
        
        engine.put("key1", "value1")
        entry1 = engine.get_entry("key1")
        
        time.sleep(0.01)
        
        engine.put("key1", "value2")
        entry2 = engine.get_entry("key1")
        
        assert entry1.created_at == entry2.created_at
    
    def test_storage_entry_size_calculated(self):
        """Test that storage entry size is calculated."""
        entry = StorageEntry(
            key="test",
            value={"large": "a" * 1000},
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        
        assert entry.size_bytes > 1000
    
    def test_query_excludes_expired(self):
        """Test that query excludes expired entries."""
        engine = StorageEngine()
        
        engine.put("valid", "value", ttl_seconds=60)
        engine.put("expired", "value", ttl_seconds=1)
        
        time.sleep(1.1)
        
        query = StorageQuery()
        results = engine.query(query)
        
        assert len(results) == 1
        assert results[0].key == "valid"
    
    def test_close_backend(self):
        """Test closing storage engine."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = StorageEngine(FileStorageBackend(tmpdir))
            
            engine.put("key1", "value1")
            
            engine.close()
            
            # Should have saved index
            assert os.path.exists(os.path.join(tmpdir, "_index.json"))
