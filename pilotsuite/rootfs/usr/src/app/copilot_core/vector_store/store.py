"""Vector Store for Preference Learning & Knowledge Graph.

Provides efficient storage and similarity search for:
- Entity embeddings
- User preference vectors
- Pattern embeddings

Uses SQLite for persistence with in-memory cache for performance.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .embeddings import EmbeddingEngine, EmbeddingResult, get_embedding_engine

_LOGGER = logging.getLogger(__name__)

# Default storage path
DEFAULT_DB_PATH = "/data/vector_store.db"


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(vec1) != len(vec2):
        raise ValueError(f"Vector dimensions don't match: {len(vec1)} vs {len(vec2)}")
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
        
    return dot_product / (magnitude1 * magnitude2)


@dataclass
class VectorEntry:
    """A stored vector entry."""
    
    id: str
    vector: list[float]
    entry_type: str  # "entity", "user_preference", "pattern"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    

@dataclass
class SearchResult:
    """Result of a similarity search."""
    
    id: str
    similarity: float
    entry_type: str
    metadata: dict[str, Any]


@dataclass
class VectorStoreConfig:
    """Configuration for vector store."""
    
    db_path: str = DEFAULT_DB_PATH
    persist: bool = True
    cache_size: int = 500
    similarity_threshold: float = 0.7
    

class VectorStore:
    """Vector storage with similarity search.
    
    Features:
    - SQLite persistence
    - In-memory cache for performance
    - Cosine similarity search
    - Type-filtered search
    - Metadata filtering
    """
    
    def __init__(self, config: VectorStoreConfig | None = None) -> None:
        """Initialize the vector store."""
        self.config = config or VectorStoreConfig()
        self._cache: dict[str, VectorEntry] = {}
        self._cache_order: list[str] = []
        self._lock = threading.RLock()
        self._db: sqlite3.Connection | None = None
        self._embedding_engine: EmbeddingEngine | None = None
        
        if self.config.persist:
            self._init_db()

    def _resolve_writable_db_path(self, configured_path: Path) -> Path:
        """Resolve writable DB path with fallback outside add-on runtime."""
        try:
            configured_path.parent.mkdir(parents=True, exist_ok=True)
            return configured_path
        except OSError:
            fallback_dir = Path(os.environ.get("COPILOT_VECTOR_DB_DIR", "/tmp"))
            fallback_dir.mkdir(parents=True, exist_ok=True)
            fallback_path = fallback_dir / configured_path.name
            _LOGGER.warning(
                "Vector DB path %s is not writable, using fallback %s",
                configured_path,
                fallback_path,
            )
            return fallback_path
            
    def _init_db(self) -> None:
        """Initialize SQLite database."""
        db_path = self._resolve_writable_db_path(Path(self.config.db_path))
        self.config.db_path = str(db_path)
        
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        
        # Create tables
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS vectors (
                id TEXT PRIMARY KEY,
                entry_type TEXT NOT NULL,
                vector BLOB NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_vectors_type ON vectors(entry_type);
            CREATE INDEX IF NOT EXISTS idx_vectors_created ON vectors(created_at);
        """)
        self._db.commit()
        _LOGGER.info("Vector store initialized: %s", self.config.db_path)
        
    def set_embedding_engine(self, engine: EmbeddingEngine) -> None:
        """Set the embedding engine for auto-embedding."""
        self._embedding_engine = engine
        
    # ==================== CRUD Operations ====================
    
    async def upsert(
        self,
        entry_id: str,
        vector: list[float],
        entry_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> VectorEntry:
        """Insert or update a vector entry.
        
        Args:
            entry_id: Unique identifier
            vector: Embedding vector
            entry_type: Type of entry (entity, user_preference, pattern)
            metadata: Optional metadata dict
            
        Returns:
            The stored VectorEntry
        """
        now = datetime.now(timezone.utc).isoformat()
        entry = VectorEntry(
            id=entry_id,
            vector=vector,
            entry_type=entry_type,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        
        with self._lock:
            # Update cache
            if entry_id in self._cache:
                entry.created_at = self._cache[entry_id].created_at
            self._cache[entry_id] = entry
            self._prune_cache()
            
            # Persist to DB
            if self.config.persist and self._db:
                vector_blob = json.dumps(vector).encode("utf-8")
                metadata_json = json.dumps(entry.metadata)
                
                self._db.execute(
                    """
                    INSERT OR REPLACE INTO vectors 
                    (id, entry_type, vector, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (entry_id, entry_type, vector_blob, metadata_json, entry.created_at, entry.updated_at),
                )
                self._db.commit()
                
        _LOGGER.debug("Upserted vector: %s (type=%s)", entry_id, entry_type)
        return entry
        
    async def get(self, entry_id: str) -> VectorEntry | None:
        """Get a vector entry by ID.
        
        Args:
            entry_id: Entry identifier
            
        Returns:
            VectorEntry or None if not found
        """
        with self._lock:
            # Check cache first
            if entry_id in self._cache:
                return self._cache[entry_id]
                
            # Load from DB
            if self.config.persist and self._db:
                row = self._db.execute(
                    "SELECT * FROM vectors WHERE id = ?",
                    (entry_id,),
                ).fetchone()
                
                if row:
                    entry = VectorEntry(
                        id=row["id"],
                        vector=json.loads(row["vector"]),
                        entry_type=row["entry_type"],
                        metadata=json.loads(row["metadata"]),
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                    self._cache[entry_id] = entry
                    return entry
                    
        return None
        
    async def delete(self, entry_id: str) -> bool:
        """Delete a vector entry.
        
        Args:
            entry_id: Entry identifier
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            # Remove from cache
            if entry_id in self._cache:
                del self._cache[entry_id]
                
            # Remove from DB
            if self.config.persist and self._db:
                cursor = self._db.execute(
                    "DELETE FROM vectors WHERE id = ?",
                    (entry_id,),
                )
                self._db.commit()
                return cursor.rowcount > 0
                
        return False
        
    async def get_by_type(self, entry_type: str, limit: int = 100) -> list[VectorEntry]:
        """Get all entries of a specific type.
        
        Args:
            entry_type: Type of entries to get
            limit: Maximum number of entries
            
        Returns:
            List of VectorEntry objects
        """
        entries: list[VectorEntry] = []
        
        with self._lock:
            # Check cache
            for entry in self._cache.values():
                if entry.entry_type == entry_type:
                    entries.append(entry)
                    
            # Load from DB if needed
            if self.config.persist and self._db and len(entries) < limit:
                rows = self._db.execute(
                    "SELECT * FROM vectors WHERE entry_type = ? ORDER BY created_at DESC LIMIT ?",
                    (entry_type, limit),
                ).fetchall()
                
                for row in rows:
                    if row["id"] not in self._cache:
                        entry = VectorEntry(
                            id=row["id"],
                            vector=json.loads(row["vector"]),
                            entry_type=row["entry_type"],
                            metadata=json.loads(row["metadata"]),
                            created_at=row["created_at"],
                            updated_at=row["updated_at"],
                        )
                        entries.append(entry)
                        
        return entries[:limit]
        
    # ==================== Similarity Search ====================
    
    async def search_similar(
        self,
        query_vector: list[float],
        entry_type: str | None = None,
        limit: int = 10,
        threshold: float | None = None,
        exclude_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors.
        
        Args:
            query_vector: Vector to search for
            entry_type: Filter by entry type (optional)
            limit: Maximum number of results
            threshold: Minimum similarity threshold (default from config)
            exclude_ids: IDs to exclude from results
            
        Returns:
            List of SearchResult objects, sorted by similarity (descending)
        """
        threshold = threshold if threshold is not None else self.config.similarity_threshold
        exclude_ids = exclude_ids or []
        
        # Calculate similarities
        results: list[SearchResult] = []
        
        with self._lock:
            # Search in cache
            entries_to_search = list(self._cache.values())
            
            # Load from DB if persist enabled
            if self.config.persist and self._db:
                if entry_type:
                    rows = self._db.execute(
                        "SELECT * FROM vectors WHERE entry_type = ?",
                        (entry_type,),
                    ).fetchall()
                else:
                    rows = self._db.execute("SELECT * FROM vectors").fetchall()
                    
                for row in rows:
                    if row["id"] not in self._cache:
                        entry = VectorEntry(
                            id=row["id"],
                            vector=json.loads(row["vector"]),
                            entry_type=row["entry_type"],
                            metadata=json.loads(row["metadata"]),
                            created_at=row["created_at"],
                            updated_at=row["updated_at"],
                        )
                        entries_to_search.append(entry)
                        
            # Calculate similarities
            for entry in entries_to_search:
                # Apply filters
                if entry.id in exclude_ids:
                    continue
                if entry_type and entry.entry_type != entry_type:
                    continue
                    
                # Calculate similarity
                similarity = _cosine_similarity(query_vector, entry.vector)
                
                if similarity >= threshold:
                    results.append(SearchResult(
                        id=entry.id,
                        similarity=similarity,
                        entry_type=entry.entry_type,
                        metadata=entry.metadata,
                    ))
                    
        # Sort by similarity (descending) and limit
        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:limit]
        
    async def find_similar_entities(
        self,
        entity_id: str,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[SearchResult]:
        """Find entities similar to a given entity.
        
        Args:
            entity_id: Entity to find similar entities for
            limit: Maximum number of results
            threshold: Minimum similarity threshold
            
        Returns:
            List of similar entities
        """
        entry = await self.get(entity_id)
        if not entry:
            return []
            
        return await self.search_similar(
            query_vector=entry.vector,
            entry_type="entity",
            limit=limit,
            threshold=threshold,
            exclude_ids=[entity_id],
        )
        
    async def find_similar_users(
        self,
        user_id: str,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[SearchResult]:
        """Find users with similar preferences.
        
        Args:
            user_id: User to find similar users for
            limit: Maximum number of results
            threshold: Minimum similarity threshold
            
        Returns:
            List of similar users
        """
        entry = await self.get(f"user_pref:{user_id}")
        if not entry:
            return []
            
        return await self.search_similar(
            query_vector=entry.vector,
            entry_type="user_preference",
            limit=limit,
            threshold=threshold,
            exclude_ids=[f"user_pref:{user_id}"],
        )
        
    # ==================== Entity Embeddings ====================
    
    async def store_entity_embedding(
        self,
        entity_id: str,
        domain: str | None = None,
        area: str | None = None,
        capabilities: list[str] | None = None,
        tags: list[str] | None = None,
        state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> VectorEntry:
        """Store an embedding for an entity.
        
        Args:
            entity_id: Home Assistant entity ID
            domain: Entity domain
            area: Area/zone
            capabilities: Entity capabilities
            tags: Entity tags
            state: Current state
            metadata: Additional metadata
            
        Returns:
            The stored VectorEntry
        """
        if not self._embedding_engine:
            self._embedding_engine = get_embedding_engine()
            
        result = await self._embedding_engine.embed_entity(
            entity_id=entity_id,
            domain=domain,
            area=area,
            capabilities=capabilities,
            tags=tags,
            state=state,
        )
        
        # Build metadata
        meta = {
            "entity_id": entity_id,
            "domain": domain,
            "area": area,
            "capabilities": capabilities or [],
            "tags": tags or [],
            **(metadata or {}),
        }
        
        return await self.upsert(
            entry_id=f"entity:{entity_id}",
            vector=result.vector,
            entry_type="entity",
            metadata=meta,
        )
        
    # ==================== User Preference Embeddings ====================
    
    async def store_user_preference_embedding(
        self,
        user_id: str,
        preferences: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> VectorEntry:
        """Store an embedding for user preferences.
        
        Args:
            user_id: User identifier
            preferences: User preference dict
            metadata: Additional metadata
            
        Returns:
            The stored VectorEntry
        """
        if not self._embedding_engine:
            self._embedding_engine = get_embedding_engine()
            
        result = await self._embedding_engine.embed_user_preferences(
            user_id=user_id,
            preferences=preferences,
        )
        
        meta = {
            "user_id": user_id,
            **(metadata or {}),
        }
        
        return await self.upsert(
            entry_id=f"user_pref:{user_id}",
            vector=result.vector,
            entry_type="user_preference",
            metadata=meta,
        )
        
    # ==================== Pattern Embeddings ====================
    
    async def store_pattern_embedding(
        self,
        pattern_id: str,
        pattern_type: str,
        entities: list[str],
        conditions: dict[str, Any] | None = None,
        confidence: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> VectorEntry:
        """Store an embedding for a pattern.
        
        Args:
            pattern_id: Pattern identifier
            pattern_type: Type of pattern
            entities: Entities involved in pattern
            conditions: Pattern conditions
            confidence: Pattern confidence
            metadata: Additional metadata
            
        Returns:
            The stored VectorEntry
        """
        if not self._embedding_engine:
            self._embedding_engine = get_embedding_engine()
            
        result = await self._embedding_engine.embed_pattern(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            entities=entities,
            conditions=conditions,
            confidence=confidence,
        )
        
        meta = {
            "pattern_id": pattern_id,
            "pattern_type": pattern_type,
            "entities": entities,
            "conditions": conditions or {},
            "confidence": confidence,
            **(metadata or {}),
        }
        
        return await self.upsert(
            entry_id=f"pattern:{pattern_id}",
            vector=result.vector,
            entry_type="pattern",
            metadata=meta,
        )
        
    # ==================== Synchronous helpers (Flask / non-async) ===========

    def upsert_sync(
        self,
        entry_id: str,
        vector: list[float],
        entry_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> VectorEntry:
        """Synchronous variant of :meth:`upsert` for Flask (non-async) code."""
        now = datetime.now(timezone.utc).isoformat()
        entry = VectorEntry(
            id=entry_id,
            vector=vector,
            entry_type=entry_type,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            if entry_id in self._cache:
                entry.created_at = self._cache[entry_id].created_at
            self._cache[entry_id] = entry
            self._prune_cache()

            if self.config.persist and self._db:
                vector_blob = json.dumps(vector).encode("utf-8")
                metadata_json = json.dumps(entry.metadata)
                self._db.execute(
                    """INSERT OR REPLACE INTO vectors
                    (id, entry_type, vector, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (entry_id, entry_type, vector_blob, metadata_json,
                     entry.created_at, entry.updated_at),
                )
                self._db.commit()

        return entry

    def search_similar_sync(
        self,
        query_vector: list[float],
        entry_type: str | None = None,
        limit: int = 10,
        threshold: float | None = None,
        exclude_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        """Synchronous variant of :meth:`search_similar` for Flask code."""
        threshold = threshold if threshold is not None else self.config.similarity_threshold
        exclude_ids = exclude_ids or []
        results: list[SearchResult] = []

        with self._lock:
            entries_to_search = list(self._cache.values())

            if self.config.persist and self._db:
                if entry_type:
                    rows = self._db.execute(
                        "SELECT * FROM vectors WHERE entry_type = ?",
                        (entry_type,),
                    ).fetchall()
                else:
                    rows = self._db.execute("SELECT * FROM vectors").fetchall()

                for row in rows:
                    if row["id"] not in self._cache:
                        entry = VectorEntry(
                            id=row["id"],
                            vector=json.loads(row["vector"]),
                            entry_type=row["entry_type"],
                            metadata=json.loads(row["metadata"]),
                            created_at=row["created_at"],
                            updated_at=row["updated_at"],
                        )
                        entries_to_search.append(entry)

            for entry in entries_to_search:
                if entry.id in exclude_ids:
                    continue
                if entry_type and entry.entry_type != entry_type:
                    continue
                similarity = _cosine_similarity(query_vector, entry.vector)
                if similarity >= threshold:
                    results.append(SearchResult(
                        id=entry.id,
                        similarity=similarity,
                        entry_type=entry.entry_type,
                        metadata=entry.metadata,
                    ))

        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:limit]

    # ==================== Stats & Maintenance ====================
    
    async def stats(self) -> dict[str, Any]:
        """Get vector store statistics.
        
        Returns:
            Stats dict with counts and info
        """
        stats = {
            "cache_size": len(self._cache),
            "persist": self.config.persist,
            "db_path": self.config.db_path if self.config.persist else None,
            "by_type": {},
        }
        
        with self._lock:
            # Count by type in cache
            for entry in self._cache.values():
                stats["by_type"][entry.entry_type] = stats["by_type"].get(entry.entry_type, 0) + 1
                
            # Count in DB
            if self.config.persist and self._db:
                rows = self._db.execute(
                    "SELECT entry_type, COUNT(*) as cnt FROM vectors GROUP BY entry_type"
                ).fetchall()
                for row in rows:
                    stats["by_type"][row["entry_type"]] = max(
                        stats["by_type"].get(row["entry_type"], 0),
                        row["cnt"],
                    )
                    
                # Total count
                total = self._db.execute("SELECT COUNT(*) as cnt FROM vectors").fetchone()
                stats["total_entries"] = total["cnt"]
                
        return stats
        
    async def clear(self, entry_type: str | None = None) -> int:
        """Clear entries from the store.
        
        Args:
            entry_type: Only clear entries of this type (optional)
            
        Returns:
            Number of entries cleared
        """
        count = 0
        
        with self._lock:
            if entry_type:
                # Clear specific type
                ids_to_remove = [
                    entry_id for entry_id, entry in self._cache.items()
                    if entry.entry_type == entry_type
                ]
                for entry_id in ids_to_remove:
                    del self._cache[entry_id]
                    count += 1
                    
                if self.config.persist and self._db:
                    cursor = self._db.execute(
                        "DELETE FROM vectors WHERE entry_type = ?",
                        (entry_type,),
                    )
                    self._db.commit()
                    count = max(count, cursor.rowcount)
            else:
                # Clear all
                count = len(self._cache)
                self._cache.clear()
                
                if self.config.persist and self._db:
                    cursor = self._db.execute("DELETE FROM vectors")
                    self._db.commit()
                    count = max(count, cursor.rowcount)
                    
        _LOGGER.info("Cleared %d vector entries (type=%s)", count, entry_type or "all")
        return count
        
    def _prune_cache(self) -> None:
        """Prune cache if it exceeds max size."""
        while len(self._cache) > self.config.cache_size:
            # Remove oldest entry
            if self._cache_order:
                oldest_id = self._cache_order.pop(0)
                if oldest_id in self._cache:
                    del self._cache[oldest_id]
            else:
                # Fallback: remove any entry
                self._cache.popitem()
                
    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._db:
                self._db.close()
                self._db = None
                _LOGGER.info("Vector store closed")


# Singleton instance
_VECTOR_STORE: VectorStore | None = None


def get_vector_store(config: VectorStoreConfig | None = None) -> VectorStore:
    """Get the vector store singleton."""
    global _VECTOR_STORE
    if _VECTOR_STORE is None:
        # Build config from environment
        if config is None:
            config = VectorStoreConfig(
                db_path=os.environ.get("COPILOT_VECTOR_DB_PATH", DEFAULT_DB_PATH),
                persist=os.environ.get("COPILOT_VECTOR_PERSIST", "true").lower() == "true",
            )
        _VECTOR_STORE = VectorStore(config)
    return _VECTOR_STORE


def reset_vector_store() -> None:
    """Reset the vector store singleton (for testing)."""
    global _VECTOR_STORE
    if _VECTOR_STORE:
        _VECTOR_STORE.close()
    _VECTOR_STORE = None
