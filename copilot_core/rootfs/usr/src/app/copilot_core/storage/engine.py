"""Storage Engine — Slice 49.

Unified storage abstraction for PilotSuite Core.

Features:
- Multiple storage backends (memory, file, S3-compatible)
- Key-value operations
- Batch operations
- TTL/expiry support
- Storage queries and filtering
- Storage statistics
"""
from __future__ import annotations

import json
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable, Iterator
from enum import Enum
import uuid
import os

logger = logging.getLogger(__name__)


class StorageBackend(Enum):
    """Storage backend types."""
    MEMORY = "memory"
    FILE = "file"
    S3 = "s3"


class StorageClass(Enum):
    """Storage class for tiered storage."""
    STANDARD = "standard"
    INFREQUENT = "infrequent"
    ARCHIVE = "archive"


@dataclass
class StorageEntry:
    """Storage entry with metadata."""
    key: str
    value: Any
    created_at: str
    updated_at: str
    expires_at: Optional[str] = None
    version: int = 1
    size_bytes: int = 0
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    storage_class: StorageClass = StorageClass.STANDARD

    def __post_init__(self) -> None:
        """Hydrate derived metadata for direct test/manual construction."""
        if not self.size_bytes:
            self.size_bytes = self._calculate_size_bytes(self.value)
        if self.checksum is None:
            self.checksum = self._calculate_checksum(self.value)

    @staticmethod
    def _serialize_value(value: Any) -> str:
        try:
            return json.dumps(value, sort_keys=True, ensure_ascii=False)
        except TypeError:
            return str(value)

    @classmethod
    def _calculate_size_bytes(cls, value: Any) -> int:
        return len(cls._serialize_value(value).encode())

    @classmethod
    def _calculate_checksum(cls, value: Any) -> str:
        payload = cls._serialize_value(value).encode()
        return hashlib.sha256(payload).hexdigest()
    
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
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "version": self.version,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "metadata": self.metadata,
            "storage_class": self.storage_class.value,
        }


@dataclass
class StorageQuery:
    """Storage query for filtering."""
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    contains: Optional[str] = None
    metadata_filter: Optional[Dict[str, Any]] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    storage_class: Optional[StorageClass] = None
    limit: Optional[int] = None
    offset: int = 0
    
    def matches(self, entry: StorageEntry) -> bool:
        """Check if entry matches query."""
        if self.prefix and not entry.key.startswith(self.prefix):
            return False
        
        if self.suffix and not entry.key.endswith(self.suffix):
            return False
        
        if self.contains and self.contains not in entry.key:
            return False
        
        if self.metadata_filter:
            for key, value in self.metadata_filter.items():
                if entry.metadata.get(key) != value:
                    return False
        
        if self.min_size and entry.size_bytes < self.min_size:
            return False
        
        if self.max_size and entry.size_bytes > self.max_size:
            return False
        
        if self.storage_class and entry.storage_class != self.storage_class:
            return False
        
        return True


class StorageBackendInterface:
    """Interface for storage backends."""
    
    def get(self, key: str) -> Optional[StorageEntry]:
        raise NotImplementedError
    
    def put(self, entry: StorageEntry) -> bool:
        raise NotImplementedError
    
    def delete(self, key: str) -> bool:
        raise NotImplementedError
    
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        raise NotImplementedError
    
    def close(self) -> None:
        raise NotImplementedError


class MemoryStorageBackend(StorageBackendInterface):
    """In-memory storage backend."""
    
    def __init__(self):
        self._data: Dict[str, StorageEntry] = {}
    
    def get(self, key: str) -> Optional[StorageEntry]:
        return self._data.get(key)
    
    def put(self, entry: StorageEntry) -> bool:
        self._data[entry.key] = entry
        return True
    
    def delete(self, key: str) -> bool:
        if key in self._data:
            del self._data[key]
            return True
        return False
    
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        if prefix:
            return [k for k in self._data.keys() if k.startswith(prefix)]
        return list(self._data.keys())
    
    def close(self) -> None:
        self._data.clear()
    
    def count(self) -> int:
        return len(self._data)
    
    def get_all_entries(self) -> List[StorageEntry]:
        return list(self._data.values())


class FileStorageBackend(StorageBackendInterface):
    """File-based storage backend."""
    
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
        self._index: Dict[str, str] = {}  # key -> file_path
        
        # Load index
        self._load_index()
    
    def _get_file_path(self, key: str) -> str:
        """Get file path for key."""
        # Use hash to avoid filesystem issues with special chars
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.base_path, f"{key_hash}.json")
    
    def _load_index(self) -> None:
        """Load index from disk."""
        index_path = os.path.join(self.base_path, "_index.json")
        
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r') as f:
                    self._index = json.load(f)
            except Exception:
                self._index = {}
    
    def _save_index(self) -> None:
        """Save index to disk."""
        index_path = os.path.join(self.base_path, "_index.json")
        
        with open(index_path, 'w') as f:
            json.dump(self._index, f)
    
    def get(self, key: str) -> Optional[StorageEntry]:
        if key not in self._index:
            return None
        
        file_path = self._index[key]
        
        if not os.path.exists(file_path):
            del self._index[key]
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            return StorageEntry(
                key=data["key"],
                value=data["value"],
                created_at=data["created_at"],
                updated_at=data["updated_at"],
                expires_at=data.get("expires_at"),
                version=data.get("version", 1),
                size_bytes=data.get("size_bytes", 0),
                checksum=data.get("checksum"),
                metadata=data.get("metadata", {}),
                storage_class=StorageClass(data.get("storage_class", "standard")),
            )
        except Exception as e:
            logger.exception("Failed to read entry: %s", e)
            return None
    
    def put(self, entry: StorageEntry) -> bool:
        file_path = self._get_file_path(entry.key)
        
        try:
            data = entry.to_dict()
            
            with open(file_path, 'w') as f:
                json.dump(data, f)
            
            self._index[entry.key] = file_path
            self._save_index()
            
            return True
        except Exception as e:
            logger.exception("Failed to write entry: %s", e)
            return False
    
    def delete(self, key: str) -> bool:
        if key not in self._index:
            return False
        
        file_path = self._index[key]
        
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            
            del self._index[key]
            self._save_index()
            
            return True
        except Exception as e:
            logger.exception("Failed to delete entry: %s", e)
            return False
    
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        if prefix:
            return [k for k in self._index.keys() if k.startswith(prefix)]
        return list(self._index.keys())
    
    def close(self) -> None:
        self._save_index()


class StorageEngine:
    """Unified storage engine."""
    
    def __init__(self, backend: Optional[StorageBackendInterface] = None):
        self._backend = backend or MemoryStorageBackend()
        self._listeners: List[Callable[[str, str, StorageEntry], None]] = []
        
        # Statistics
        self._stats = {
            "total_reads": 0,
            "total_writes": 0,
            "total_deletes": 0,
            "total_expired": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "by_storage_class": {},
        }
    
    def set_backend(self, backend: StorageBackendInterface) -> None:
        """Set storage backend."""
        self._backend = backend
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key."""
        self._stats["total_reads"] += 1
        
        entry = self._backend.get(key)
        
        if entry is None:
            return default
        
        if entry.is_expired():
            self._stats["total_expired"] += 1
            self.delete(key)
            return default
        
        return entry.value
    
    def get_entry(self, key: str) -> Optional[StorageEntry]:
        """Get full entry by key."""
        self._stats["total_reads"] += 1
        
        entry = self._backend.get(key)
        
        if entry and entry.is_expired():
            self._stats["total_expired"] += 1
            self.delete(key)
            return None
        
        return entry
    
    def put(self, key: str, value: Any,
            ttl_seconds: Optional[int] = None,
            metadata: Optional[Dict[str, Any]] = None,
            storage_class: StorageClass = StorageClass.STANDARD) -> bool:
        """Put value with optional TTL."""
        now = datetime.now(timezone.utc)
        
        # Calculate expiry
        expires_at = None
        if ttl_seconds:
            expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
        
        # Calculate checksum
        value_str = json.dumps(value, sort_keys=True)
        checksum = hashlib.md5(value_str.encode()).hexdigest()
        
        # Get existing version
        existing = self._backend.get(key)
        version = (existing.version + 1) if existing else 1
        
        entry = StorageEntry(
            key=key,
            value=value,
            created_at=now.isoformat() if not existing else existing.created_at,
            updated_at=now.isoformat(),
            expires_at=expires_at,
            version=version,
            size_bytes=len(value_str.encode()),
            checksum=checksum,
            metadata=metadata or {},
            storage_class=storage_class,
        )
        
        result = self._backend.put(entry)
        
        if result:
            self._stats["total_writes"] += 1
            storage_class_name = storage_class.value
            self._stats["by_storage_class"][storage_class_name] = \
                self._stats["by_storage_class"].get(storage_class_name, 0) + 1
            
            self._notify("put", key, entry)
        
        return result
    
    def delete(self, key: str) -> bool:
        """Delete key."""
        result = self._backend.delete(key)
        
        if result:
            self._stats["total_deletes"] += 1
            self._notify("delete", key, None)
        
        return result
    
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        entry = self._backend.get(key)
        return entry is not None and not entry.is_expired()
    
    def keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys."""
        return self._backend.list_keys(prefix)
    
    def query(self, query: StorageQuery) -> List[StorageEntry]:
        """Query storage with filters."""
        results = []
        
        if isinstance(self._backend, MemoryStorageBackend):
            entries = self._backend.get_all_entries()
        else:
            # For other backends, fetch each entry
            entries = []
            for key in self._backend.list_keys():
                entry = self._backend.get(key)
                if entry:
                    entries.append(entry)
        
        for entry in entries:
            if entry.is_expired():
                continue
            
            if query.matches(entry):
                results.append(entry)
        
        # Apply pagination
        if query.limit:
            results = results[query.offset:query.offset + query.limit]
        
        return results
    
    def batch_get(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values."""
        results = {}
        
        for key in keys:
            value = self.get(key)
            if value is not None:
                results[key] = value
        
        return results
    
    def batch_put(self, items: Dict[str, Any],
                  ttl_seconds: Optional[int] = None) -> int:
        """Put multiple values."""
        count = 0
        
        for key, value in items.items():
            if self.put(key, value, ttl_seconds=ttl_seconds):
                count += 1
        
        return count
    
    def batch_delete(self, keys: List[str]) -> int:
        """Delete multiple keys."""
        count = 0
        
        for key in keys:
            if self.delete(key):
                count += 1
        
        return count
    
    def clear(self, prefix: Optional[str] = None) -> int:
        """Clear all entries or entries with prefix."""
        keys = self.keys(prefix)
        return self.batch_delete(keys)
    
    def add_listener(self, listener: Callable[[str, str, StorageEntry], None]) -> None:
        """Add storage event listener."""
        self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[str, str, StorageEntry], None]) -> bool:
        """Remove storage event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)
            return True
        return False
    
    def _notify(self, event: str, key: str, entry: Optional[StorageEntry]) -> None:
        """Notify listeners of storage event."""
        for listener in self._listeners:
            try:
                listener(event, key, entry)
            except Exception as e:
                logger.exception("Listener failed: %s", e)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get storage statistics."""
        if isinstance(self._backend, MemoryStorageBackend):
            self._stats["total_entries"] = self._backend.count()
        else:
            self._stats["total_entries"] = len(self._backend.list_keys())
        
        return self._stats
    
    def get_size(self, key: str) -> int:
        """Get entry size in bytes."""
        entry = self.get_entry(key)
        return entry.size_bytes if entry else 0
    
    def get_total_size(self) -> int:
        """Get total storage size in bytes."""
        total = 0
        
        if isinstance(self._backend, MemoryStorageBackend):
            for entry in self._backend.get_all_entries():
                if not entry.is_expired():
                    total += entry.size_bytes
        else:
            for key in self._backend.list_keys():
                entry = self._backend.get(key)
                if entry and not entry.is_expired():
                    total += entry.size_bytes
        
        return total
    
    def get_version(self, key: str) -> Optional[int]:
        """Get entry version."""
        entry = self.get_entry(key)
        return entry.version if entry else None
    
    def get_checksum(self, key: str) -> Optional[str]:
        """Get entry checksum."""
        entry = self.get_entry(key)
        return entry.checksum if entry else None
    
    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Get entry metadata."""
        entry = self.get_entry(key)
        return entry.metadata if entry else None
    
    def set_metadata(self, key: str, metadata: Dict[str, Any]) -> bool:
        """Update entry metadata."""
        entry = self.get_entry(key)
        
        if not entry:
            return False
        
        entry.metadata.update(metadata)
        entry.updated_at = datetime.now(timezone.utc).isoformat()
        
        return self._backend.put(entry)
    
    def get_expiry(self, key: str) -> Optional[str]:
        """Get entry expiry time."""
        entry = self.get_entry(key)
        return entry.expires_at if entry else None
    
    def refresh_ttl(self, key: str, ttl_seconds: int) -> bool:
        """Refresh TTL on entry."""
        entry = self.get_entry(key)
        
        if not entry:
            return False
        
        entry.expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
        entry.updated_at = datetime.now(timezone.utc).isoformat()
        
        return self._backend.put(entry)
    
    def close(self) -> None:
        """Close storage engine."""
        self._backend.close()


def create_storage_engine(backend_type: StorageBackend = StorageBackend.MEMORY,
                         base_path: Optional[str] = None) -> StorageEngine:
    """Factory function to create storage engine."""
    if backend_type == StorageBackend.FILE:
        if not base_path:
            raise ValueError("base_path required for FILE backend")
        backend = FileStorageBackend(base_path)
    else:
        backend = MemoryStorageBackend()
    
    return StorageEngine(backend)
