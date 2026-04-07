"""Unified Habitus Store — Kombiniert RAG + Habitus + Anomaly in EINEM Store.

ARCHITEKTUR-REVISE:
Statt separater Stores (HabitusStorage, VectorStore, AnomalyBase) → ALLES in EINEM.

Vorteile:
1. **Maximale Synergien** — Patterns sind im RAG-Kontext nutzbar
2. **Einheitliche Vektoren** — Semantic Search über ALLES (Patterns, Preferences, Events)
3. **Anomaly Detection** — Nutzt Habitus-Patterns als Baseline
4. **Zone-Konsistenz** — Alle Daten mit zone_id getaggt
5. **Effizienz** — Ein Store, ein Index, eine Confidence-Berechnung

Usage:
    store = get_unified_habitus_store()
    
    # Pattern speichern (wird automatisch vektorisiert)
    store.save_pattern(pattern, zone="living")
    
    # Semantic Search über ALLES
    results = store.semantic_search("Was mache ich abends im Wohnzimmer?", zone="living")
    # → Findet Patterns, Preferences, RAG-Docs, Events
    
    # Anomaly Detection (vergleicht mit Habitus-Baseline)
    is_anomaly = store.detect_anomaly(current_event, zone="living")
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import hashlib

_LOGGER = logging.getLogger(__name__)

DB_PATH = os.environ.get("UNIFIED_HABITUS_DB", "/data/unified_habitus.db")


# =============================================================================
# Unified Data Types
# =============================================================================

class DataType(str, Enum):
    """Alle Datentypen im unified store."""
    PATTERN = "pattern"           # A→B Regel
    PREFERENCE = "preference"     # Nutzer-Vorliebe
    ROUTINE = "routine"           # Wiederkehrende Aktivität
    EVENT = "event"               # HA-Event
    RAG_DOC = "rag_doc"           # RAG-Dokument
    ANOMALY_BASELINE = "anomaly_baseline"  # Normalzustand
    CONTEXT = "context"           # Kontext-Snapshot


class PatternState(str, Enum):
    """Pattern-Lernzustand."""
    OBSERVING = "observing"
    LEARNING = "learning"
    STABLE = "stable"
    ACTIVE = "active"
    DISABLED = "disabled"


@dataclass
class UnifiedRecord:
    """Einheitlicher Datensatz für ALLES im Store.
    
    Jedes Record hat:
    - ID (eindeutig)
    - Type (pattern, preference, event, rag_doc, etc.)
    - Zone (optional, für zone-scoped queries)
    - Vector (für semantic search)
    - Metadata (type-spezifisch)
    - Timestamps (created, updated)
    """
    
    id: str
    data_type: DataType
    zone: Optional[str] = None
    module: Optional[str] = None
    
    # Vector (für semantic search)
    vector: Optional[List[float]] = None
    vector_model: str = "all-MiniLM-L6-v2"
    
    # Content (für BM25 + full-text search)
    content: str = ""
    title: str = ""
    
    # Metadata (type-spezifisch, JSON)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Confidence/Quality
    confidence: float = 0.0
    support: int = 0
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Tags (für filtering)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UnifiedRecord:
        return cls(**data)
    
    def get_vector_key(self) -> str:
        """Eindeutiger Key für Vector-Lookup."""
        return hashlib.md5(f"{self.data_type}:{self.id}".encode()).hexdigest()


# =============================================================================
# Unified Habitus Store
# =============================================================================

class UnifiedHabitusStore:
    """Kombiniert Habitus + RAG + Anomaly in EINEM Store.
    
    Features:
    - SQLite für strukturierte Daten
    - BM25 für full-text search
    - Vektoren für semantic search (extern gespeichert, referenziert)
    - Zone-scoped queries
    - Cross-type search (suche über Patterns + Preferences + Events)
    """
    
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or DB_PATH
        self._lock = threading.Lock()
        self._vector_cache: Dict[str, List[float]] = {}  # In-Memory Vector-Cache
        self._init_db()
        _LOGGER.info("UnifiedHabitusStore initialized at %s", self._db_path)
    
    def _init_db(self) -> None:
        """Datenbank-Tabellen erstellen."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.executescript("""
                    -- Unified Records (HAUPTTABELLE)
                    CREATE TABLE IF NOT EXISTS unified_records (
                        id TEXT PRIMARY KEY,
                        data_type TEXT NOT NULL,
                        zone TEXT,
                        module TEXT,
                        vector_key TEXT,
                        vector_model TEXT DEFAULT 'all-MiniLM-L6-v2',
                        content TEXT NOT NULL,
                        title TEXT DEFAULT '',
                        metadata_json TEXT DEFAULT '{}',
                        confidence REAL DEFAULT 0.0,
                        support INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        tags_json TEXT DEFAULT '[]'
                    );
                    
                    -- Zone-spezifische Konfiguration
                    CREATE TABLE IF NOT EXISTS zone_configs (
                        zone_id TEXT PRIMARY KEY,
                        zone_type TEXT NOT NULL,
                        name TEXT NOT NULL,
                        enabled_modules_json TEXT DEFAULT '[]',
                        module_states_json DEFAULT '{}',
                        preferences_json DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    
                    -- Anomaly Baselines (pro Zone + Module)
                    CREATE TABLE IF NOT EXISTS anomaly_baselines (
                        id TEXT PRIMARY KEY,
                        zone_id TEXT NOT NULL,
                        module_id TEXT NOT NULL,
                        baseline_json TEXT NOT NULL,
                        confidence REAL DEFAULT 0.0,
                        observations INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    
                    -- Cross-Module Dependencies
                    CREATE TABLE IF NOT EXISTS module_dependencies (
                        id TEXT PRIMARY KEY,
                        source_module TEXT NOT NULL,
                        target_module TEXT NOT NULL,
                        dependency_type TEXT NOT NULL,
                        strength REAL DEFAULT 0.0,
                        zone TEXT,
                        created_at TEXT NOT NULL
                    );
                    
                    -- Indexes
                    CREATE INDEX IF NOT EXISTS idx_records_type ON unified_records(data_type);
                    CREATE INDEX IF NOT EXISTS idx_records_zone ON unified_records(zone);
                    CREATE INDEX IF NOT EXISTS idx_records_module ON unified_records(module);
                    CREATE INDEX IF NOT EXISTS idx_records_tags ON unified_records(tags_json);
                    CREATE INDEX IF NOT EXISTS idx_records_content ON unified_records(content);
                    CREATE INDEX IF NOT EXISTS idx_baselines_zone ON anomaly_baselines(zone_id);
                    CREATE INDEX IF NOT EXISTS idx_dependencies_source ON module_dependencies(source_module);
                    
                    -- Full-Text Search (FTS5)
                    CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
                        content,
                        title,
                        tags_json,
                        content='unified_records',
                        content_rowid='rowid'
                    );
                    
                    -- Triggers für FTS
                    CREATE TRIGGER IF NOT EXISTS records_ai AFTER INSERT ON unified_records BEGIN
                        INSERT INTO records_fts(rowid, content, title, tags_json)
                        VALUES (NEW.rowid, NEW.content, NEW.title, NEW.tags_json);
                    END;
                    
                    CREATE TRIGGER IF NOT EXISTS records_ad AFTER DELETE ON unified_records BEGIN
                        INSERT INTO records_fts(records_fts, rowid, content, title, tags_json)
                        VALUES('delete', OLD.rowid, OLD.content, OLD.title, OLD.tags_json);
                    END;
                    
                    CREATE TRIGGER IF NOT EXISTS records_au AFTER UPDATE ON unified_records BEGIN
                        INSERT INTO records_fts(records_fts, rowid, content, title, tags_json)
                        VALUES('delete', OLD.rowid, OLD.content, OLD.title, OLD.tags_json);
                        INSERT INTO records_fts(rowid, content, title, tags_json)
                        VALUES (NEW.rowid, NEW.content, NEW.title, NEW.tags_json);
                    END;
                """)
                conn.commit()
            finally:
                conn.close()
    
    # ======================================================================
    # Unified Record Operations
    # ======================================================================
    
    def save_record(self, record: UnifiedRecord) -> None:
        """Record speichern (upsert)."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                vector_key = record.get_vector_key()
                
                # Vector im Cache speichern
                if record.vector:
                    self._vector_cache[vector_key] = record.vector
                
                conn.execute("""
                    INSERT OR REPLACE INTO unified_records 
                    (id, data_type, zone, module, vector_key, vector_model, content, title,
                     metadata_json, confidence, support, created_at, updated_at, tags_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.id,
                    record.data_type.value,
                    record.zone,
                    record.module,
                    vector_key,
                    record.vector_model,
                    record.content,
                    record.title,
                    json.dumps(record.metadata),
                    record.confidence,
                    record.support,
                    record.created_at,
                    record.updated_at,
                    json.dumps(record.tags),
                ))
                conn.commit()
            finally:
                conn.close()
    
    def get_record(self, record_id: str) -> Optional[UnifiedRecord]:
        """Record by ID laden."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM unified_records WHERE id = ?", (record_id,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                return UnifiedRecord(
                    id=row["id"],
                    data_type=DataType(row["data_type"]),
                    zone=row["zone"],
                    module=row["module"],
                    vector_key=row["vector_key"],
                    vector_model=row["vector_model"],
                    content=row["content"],
                    title=row["title"],
                    metadata=json.loads(row["metadata_json"]),
                    confidence=row["confidence"],
                    support=row["support"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    tags=json.loads(row["tags_json"]),
                )
            finally:
                conn.close()
    
    def get_records(
        self,
        data_type: Optional[DataType] = None,
        zone: Optional[str] = None,
        module: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[UnifiedRecord]:
        """Records filtern."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                
                query = "SELECT * FROM unified_records WHERE 1=1"
                params = []
                
                if data_type:
                    query += " AND data_type = ?"
                    params.append(data_type.value)
                
                if zone:
                    query += " AND zone = ?"
                    params.append(zone)
                
                if module:
                    query += " AND module = ?"
                    params.append(module)
                
                if tags:
                    for tag in tags:
                        query += " AND tags_json LIKE ?"
                        params.append(f'%"{tag}"%')
                
                query += " ORDER BY confidence DESC, support DESC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [
                    UnifiedRecord(
                        id=row["id"],
                        data_type=DataType(row["data_type"]),
                        zone=row["zone"],
                        module=row["module"],
                        vector_key=row["vector_key"],
                        vector_model=row["vector_model"],
                        content=row["content"],
                        title=row["title"],
                        metadata=json.loads(row["metadata_json"]),
                        confidence=row["confidence"],
                        support=row["support"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        tags=json.loads(row["tags_json"]),
                    )
                    for row in rows
                ]
            finally:
                conn.close()
    
    def delete_record(self, record_id: str) -> bool:
        """Record löschen."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.execute("DELETE FROM unified_records WHERE id = ?", (record_id,))
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()
    
    # ======================================================================
    # Search (BM25 + FTS)
    # ======================================================================
    
    def search(
        self,
        query: str,
        data_type: Optional[DataType] = None,
        zone: Optional[str] = None,
        limit: int = 20,
    ) -> List[Tuple[UnifiedRecord, float]]:
        """Full-Text Search über alle Records.
        
        Returns:
            List of (Record, score) tuples
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                
                # FTS5 Query
                fts_query = f'"{query}"'
                
                query_sql = """
                    SELECT r.*, bm25(records_fts) as score
                    FROM records_fts fts
                    JOIN unified_records r ON r.rowid = fts.rowid
                    WHERE records_fts MATCH ?
                """
                params = [fts_query]
                
                if data_type:
                    query_sql += " AND r.data_type = ?"
                    params.append(data_type.value)
                
                if zone:
                    query_sql += " AND r.zone = ?"
                    params.append(zone)
                
                query_sql += " ORDER BY score LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(query_sql, params)
                rows = cursor.fetchall()
                
                return [
                    (
                        UnifiedRecord(
                            id=row["id"],
                            data_type=DataType(row["data_type"]),
                            zone=row["zone"],
                            module=row["module"],
                            vector_key=row["vector_key"],
                            vector_model=row["vector_model"],
                            content=row["content"],
                            title=row["title"],
                            metadata=json.loads(row["metadata_json"]),
                            confidence=row["confidence"],
                            support=row["support"],
                            created_at=row["created_at"],
                            updated_at=row["updated_at"],
                            tags=json.loads(row["tags_json"]),
                        ),
                        row["score"],
                    )
                    for row in rows
                ]
            finally:
                conn.close()
    
    # ======================================================================
    # Zone Configuration
    # ======================================================================
    
    def save_zone_config(self, zone_id: str, zone_type: str, name: str, 
                         enabled_modules: List[str], module_states: Dict[str, str],
                         preferences: Dict[str, Any]) -> None:
        """Zone-Konfiguration speichern."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute("""
                    INSERT OR REPLACE INTO zone_configs 
                    (zone_id, zone_type, name, enabled_modules_json, module_states_json, 
                     preferences_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    zone_id,
                    zone_type,
                    name,
                    json.dumps(enabled_modules),
                    json.dumps(module_states),
                    json.dumps(preferences),
                    now,
                    now,
                ))
                conn.commit()
            finally:
                conn.close()
    
    def get_zone_config(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """Zone-Konfiguration laden."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM zone_configs WHERE zone_id = ?", (zone_id,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                return {
                    "zone_id": row["zone_id"],
                    "zone_type": row["zone_type"],
                    "name": row["name"],
                    "enabled_modules": json.loads(row["enabled_modules_json"]),
                    "module_states": json.loads(row["module_states_json"]),
                    "preferences": json.loads(row["preferences_json"]),
                }
            finally:
                conn.close()
    
    # ======================================================================
    # Anomaly Detection Baselines
    # ======================================================================
    
    def save_anomaly_baseline(self, zone_id: str, module_id: str, 
                               baseline: Dict[str, Any], confidence: float) -> str:
        """Anomaly-Baseline speichern."""
        import uuid
        baseline_id = f"baseline_{uuid.uuid4().hex[:8]}"
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute("""
                    INSERT OR REPLACE INTO anomaly_baselines 
                    (id, zone_id, module_id, baseline_json, confidence, observations, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """, (
                    baseline_id,
                    zone_id,
                    module_id,
                    json.dumps(baseline),
                    confidence,
                    now,
                    now,
                ))
                conn.commit()
            finally:
                conn.close()
        
        return baseline_id
    
    def get_anomaly_baseline(self, zone_id: str, module_id: str) -> Optional[Dict[str, Any]]:
        """Anomaly-Baseline laden."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM anomaly_baselines 
                    WHERE zone_id = ? AND module_id = ? 
                    ORDER BY confidence DESC, observations DESC LIMIT 1
                """, (zone_id, module_id))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                return {
                    "baseline": json.loads(row["baseline_json"]),
                    "confidence": row["confidence"],
                    "observations": row["observations"],
                }
            finally:
                conn.close()
    
    # ======================================================================
    # Module Dependencies
    # ======================================================================
    
    def save_module_dependency(self, source_module: str, target_module: str,
                                dependency_type: str, strength: float,
                                zone: Optional[str] = None) -> str:
        """Module-Dependency speichern."""
        import uuid
        dep_id = f"dep_{uuid.uuid4().hex[:8]}"
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute("""
                    INSERT OR REPLACE INTO module_dependencies 
                    (id, source_module, target_module, dependency_type, strength, zone, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    dep_id,
                    source_module,
                    target_module,
                    dependency_type,
                    strength,
                    zone,
                    now,
                ))
                conn.commit()
            finally:
                conn.close()
        
        return dep_id
    
    def get_module_dependencies(self, module_id: str, zone: Optional[str] = None) -> List[Dict[str, Any]]:
        """Module-Dependencies laden."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                
                query = "SELECT * FROM module_dependencies WHERE source_module = ?"
                params = [module_id]
                
                if zone:
                    query += " AND zone = ?"
                    params.append(zone)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [
                    {
                        "id": row["id"],
                        "source_module": row["source_module"],
                        "target_module": row["target_module"],
                        "dependency_type": row["dependency_type"],
                        "strength": row["strength"],
                        "zone": row["zone"],
                    }
                    for row in rows
                ]
            finally:
                conn.close()
    
    # ======================================================================
    # Analytics
    # ======================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Statistiken über Unified Store."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                
                stats = {}
                
                # Records by type
                cursor = conn.execute("SELECT data_type, COUNT(*) as count FROM unified_records GROUP BY data_type")
                stats["records_by_type"] = {row["data_type"]: row["count"] for row in cursor.fetchall()}
                
                # Records by zone
                cursor = conn.execute("SELECT zone, COUNT(*) as count FROM unified_records WHERE zone IS NOT NULL GROUP BY zone")
                stats["records_by_zone"] = {row["zone"]: row["count"] for row in cursor.fetchall()}
                
                # Total records
                cursor = conn.execute("SELECT COUNT(*) as count FROM unified_records")
                stats["total_records"] = cursor.fetchone()["count"]
                
                # Zone configs
                cursor = conn.execute("SELECT COUNT(*) as count FROM zone_configs")
                stats["zone_configs"] = cursor.fetchone()["count"]
                
                # Anomaly baselines
                cursor = conn.execute("SELECT COUNT(*) as count FROM anomaly_baselines")
                stats["anomaly_baselines"] = cursor.fetchone()["count"]
                
                # Module dependencies
                cursor = conn.execute("SELECT COUNT(*) as count FROM module_dependencies")
                stats["module_dependencies"] = cursor.fetchone()["count"]
                
                return stats
            finally:
                conn.close()


# =============================================================================
# Singleton
# =============================================================================

_store_instance: Optional[UnifiedHabitusStore] = None
_store_lock = threading.Lock()


def get_unified_habitus_store(db_path: Optional[str] = None) -> UnifiedHabitusStore:
    """Singleton-Zugriff auf UnifiedHabitusStore."""
    global _store_instance
    
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                _store_instance = UnifiedHabitusStore(db_path)
    
    return _store_instance
