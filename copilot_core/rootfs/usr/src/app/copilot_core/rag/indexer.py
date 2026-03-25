"""Namespace-based Index Manager for RAG Pipeline.

Manages multiple isolated BM25 indexes (namespaces) with
automatic namespace creation, lifecycle methods, and health checks.

Supports:
- Multiple independent namespaces (e.g., ha_docs, user_notes, articles)
- Namespace listing, creation, deletion
- Index health and statistics per namespace
- Namespace metadata and tagging
- Bulk namespace operations
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .bm25 import BM25Config, BM25Document, BM25SqliteIndex

_LOGGER = logging.getLogger(__name__)

# Path for namespace registry database
_DEFAULT_REGISTRY_PATH = os.getenv("COPILOT_CORE_RAG_REGISTRY", "/data/rag_namespaces.db")


@dataclass
class NamespaceInfo:
    """Information about a registered namespace."""

    name: str
    doc_count: int
    term_count: int
    created_at: float
    updated_at: float
    description: str
    tags: List[str]
    db_size_bytes: int


@dataclass
class NamespaceStats:
    """Detailed statistics for a namespace."""

    name: str
    doc_count: int
    term_count: int
    posting_count: int
    avg_doc_len: float
    total_doc_len: int
    db_path: str
    db_size_bytes: int
    created_at: float
    updated_at: Optional[float]


class IndexManager:
    """Manages multiple BM25 namespaces with a central registry.

    The registry stores namespace metadata in a SQLite database.
    Each namespace has its own isolated BM25 index (same SQLite file,
    different logical partitions via the namespace column in bm25 schema).

    Thread-safe singleton with connection-per-thread pattern.

    Usage::

        mgr = IndexManager.get_instance()
        mgr.create_namespace("my_docs", description="My documents")
        mgr.index("my_docs", [BM25Document(doc_id="1", text="Hello world")])
        results = mgr.search("my_docs", "hello")
        stats = mgr.namespace_stats("my_docs")
    """

    _instance: Optional[IndexManager] = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        registry_path: Optional[str] = None,
        bm25_db_path: Optional[str] = None,
    ) -> None:
        """Initialize the index manager.

        Args:
            registry_path: Path to namespace registry SQLite DB.
                           Default: /data/rag_namespaces.db
            bm25_db_path:  Path to BM25 data SQLite DB.
                           Default: /data/copilot_core_rag.sqlite3
        """
        self._registry_path = registry_path or _DEFAULT_REGISTRY_PATH
        self._bm25_db_path = bm25_db_path or os.getenv(
            "COPILOT_CORE_RAG_DB_PATH", "/data/copilot_core_rag.sqlite3"
        )
        self._local = threading.local()
        self._bm25: Optional[BM25SqliteIndex] = None
        self._bm25_lock = threading.Lock()

        self._ensure_dirs()
        self._init_registry()

        _LOGGER.info(
            "IndexManager initialized (registry=%s, bm25=%s)",
            self._registry_path,
            self._bm25_db_path,
        )

    @classmethod
    def get_instance(cls, **kwargs) -> "IndexManager":
        """Get or create the singleton IndexManager instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._instance_lock:
            cls._instance = None

    # ── BM25 access ────────────────────────────────────────────────────────

    def _bm25(self) -> BM25SqliteIndex:
        """Get shared BM25 index instance."""
        if self._bm25 is None:
            with self._bm25_lock:
                if self._bm25 is None:
                    self._bm25 = BM25SqliteIndex(
                        BM25Config(db_path=self._bm25_db_path)
                    )
        return self._bm25

    # ── Registry DB ────────────────────────────────────────────────────────

    def _get_registry_conn(self) -> sqlite3.Connection:
        """Get thread-local registry connection."""
        if not hasattr(self._local, "registry_conn") or self._local.registry_conn is None:
            self._local.registry_conn = sqlite3.connect(
                self._registry_path,
                timeout=30.0,
                check_same_thread=False,
            )
            self._local.registry_conn.row_factory = sqlite3.Row
            self._local.registry_conn.execute("PRAGMA journal_mode = WAL")
        return self._local.registry_conn

    def _ensure_dirs(self) -> None:
        """Create storage directories if they don't exist."""
        for p in [self._registry_path, self._bm25_db_path]:
            if p:
                dir_path = os.path.dirname(p)
                if dir_path:
                    os.makedirs(dir_path, exist_ok=True)

    def _init_registry(self) -> None:
        """Initialize the namespace registry schema."""
        conn = self._get_registry_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS namespaces (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS namespace_metadata (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value_json TEXT,
                PRIMARY KEY (namespace, key),
                FOREIGN KEY (namespace) REFERENCES namespaces(name) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_ns_name ON namespaces(name);
        """)
        conn.commit()

    # ── Namespace CRUD ─────────────────────────────────────────────────────

    def create_namespace(
        self,
        name: str,
        description: str = "",
        tags: Optional[Iterable[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """Register a new namespace.

        Args:
            name: Unique namespace name (alphanumeric, underscore, hyphen)
            description: Human-readable description
            tags: Optional list of tags for categorization
            metadata: Optional key-value metadata

        Returns:
            Tuple of (success, message)
        """
        if not name or len(name) > 128:
            return False, "Namespace name must be 1-128 characters"

        import re

        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            return False, "Namespace must be alphanumeric (underscore/hyphen allowed)"

        now = datetime.now(timezone.utc).timestamp()

        try:
            conn = self._get_registry_conn()

            existing = conn.execute(
                "SELECT name FROM namespaces WHERE name = ?", (name,)
            ).fetchone()

            if existing:
                return False, f"Namespace '{name}' already exists"

            tags_list = sorted(set(tags or []))
            metadata_dict = dict(metadata or {})

            conn.execute(
                """
                INSERT INTO namespaces(name, description, tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, description, json.dumps(tags_list, separators=(",", ":")), now, now),
            )

            for k, v in metadata_dict.items():
                conn.execute(
                    "INSERT INTO namespace_metadata(namespace, key, value_json) VALUES (?, ?, ?)",
                    (name, k, json.dumps(v, separators=(",", ":"))),
                )

            conn.commit()
            _LOGGER.info("Namespace created: %s", name)
            return True, f"Namespace '{name}' created"

        except Exception as exc:
            _LOGGER.exception("Failed to create namespace: %s", name)
            return False, str(exc)

    def delete_namespace(self, name: str, *, delete_documents: bool = False) -> Tuple[bool, str]:
        """Delete a namespace and optionally its documents.

        Args:
            name: Namespace to delete
            delete_documents: If True, delete all documents in the namespace
                             from the BM25 index. If False, only unregisters
                             the namespace (documents remain but are orphaned).

        Returns:
            Tuple of (success, message)
        """
        try:
            conn = self._get_registry_conn()

            existing = conn.execute(
                "SELECT name FROM namespaces WHERE name = ?", (name,)
            ).fetchone()

            if not existing:
                return False, f"Namespace '{name}' does not exist"

            if delete_documents:
                bm = self._bm25()
                bm.delete_namespace(name)  # type: ignore[attr-defined]
                _LOGGER.info("Namespace documents deleted: %s", name)

            conn.execute("DELETE FROM namespace_metadata WHERE namespace = ?", (name,))
            conn.execute("DELETE FROM namespaces WHERE name = ?", (name,))
            conn.commit()

            _LOGGER.info("Namespace unregistered: %s (documents_deleted=%s)", name, delete_documents)
            return True, f"Namespace '{name}' deleted"

        except Exception as exc:
            _LOGGER.exception("Failed to delete namespace: %s", name)
            return False, str(exc)

    def list_namespaces(
        self,
        tag: Optional[str] = None,
        pattern: Optional[str] = None,
    ) -> List[NamespaceInfo]:
        """List all registered namespaces.

        Args:
            tag: Optional tag to filter by
            pattern: Optional name pattern (SQL LIKE)

        Returns:
            List of NamespaceInfo objects
        """
        conn = self._get_registry_conn()
        bm = self._bm25()

        conditions = []
        params: List[Any] = []

        if tag:
            conditions.append("tags_json LIKE ?")
            params.append(f'%"{tag}"%')

        if pattern:
            conditions.append("name LIKE ?")
            params.append(pattern)

        where = " AND ".join(conditions) if conditions else "1=1"

        rows = conn.execute(
            f"SELECT name, description, tags_json, created_at, updated_at FROM namespaces WHERE {where} ORDER BY name",
            params,
        ).fetchall()

        results: List[NamespaceInfo] = []
        for row in rows:
            name = str(row["name"])
            tags: List[str] = json.loads(row["tags_json"] or "[]")

            if tag and tag not in tags:
                continue

            try:
                stats = bm.stats(namespace=name)
            except Exception:
                stats = None

            doc_count = stats.doc_count if stats else 0
            term_count = stats.term_count if stats else 0
            db_size = stats.db_size_bytes if stats else 0

            results.append(
                NamespaceInfo(
                    name=name,
                    doc_count=doc_count,
                    term_count=term_count,
                    created_at=float(row["created_at"]),
                    updated_at=float(row["updated_at"]),
                    description=str(row["description"] or ""),
                    tags=tags,
                    db_size_bytes=db_size,
                )
            )

        return results

    def get_namespace_info(self, name: str) -> Optional[NamespaceInfo]:
        """Get detailed info for a single namespace."""
        ns_list = self.list_namespaces(pattern=name)
        for ns in ns_list:
            if ns.name == name:
                return ns
        return None

    # ── Metadata ──────────────────────────────────────────────────────────

    def set_namespace_metadata(
        self,
        name: str,
        key: str,
        value: Any,
    ) -> bool:
        """Set a metadata key-value pair for a namespace."""
        try:
            conn = self._get_registry_conn()
            conn.execute(
                """
                INSERT INTO namespace_metadata(namespace, key, value_json)
                VALUES (?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET value_json = excluded.value_json
                """,
                (name, key, json.dumps(value, separators=(",", ":"))),
            )
            conn.execute(
                "UPDATE namespaces SET updated_at = ? WHERE name = ?",
                (datetime.now(timezone.utc).timestamp(), name),
            )
            conn.commit()
            return True
        except Exception:
            _LOGGER.exception("Failed to set namespace metadata")
            return False

    def get_namespace_metadata(self, name: str) -> Dict[str, Any]:
        """Get all metadata for a namespace."""
        try:
            conn = self._get_registry_conn()
            rows = conn.execute(
                "SELECT key, value_json FROM namespace_metadata WHERE namespace = ?",
                (name,),
            ).fetchall()
            return {str(r["key"]): json.loads(r["value_json"] or "null") for r in rows}
        except Exception:
            return {}

    # ── Index Operations (delegates to BM25) ─────────────────────────────

    def index(
        self,
        namespace: str,
        documents: Sequence[BM25Document],
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """Index documents into a namespace (auto-creates namespace if needed).

        Args:
            namespace: Target namespace
            documents: Sequence of BM25Document objects

        Returns:
            Tuple of (success_count, error_list)
        """
        # Auto-create namespace if it doesn't exist
        existing = self.get_namespace_info(namespace)
        if existing is None:
            self.create_namespace(namespace)

        bm = self._bm25()
        return bm.upsert_documents(namespace=namespace, documents=documents)

    def index_dicts(
        self,
        namespace: str,
        documents: Sequence[Dict[str, Any]],
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """Index documents from dict list (convenience method).

        Each dict should have 'id' (doc_id) and 'text' keys.
        Optional 'metadata' key is supported.
        """
        docs = [
            BM25Document(
                doc_id=str(d["id"]),
                text=str(d["text"]),
                metadata=d.get("metadata"),
            )
            for d in documents
            if "id" in d and "text" in d
        ]
        return self.index(namespace, docs)

    def search(
        self,
        namespace: str,
        query: str,
        top_k: int = 10,
        include_text: bool = False,
        include_metadata: bool = False,
    ):
        """Search within a namespace using BM25.

        Returns List[BM25Hit].
        """
        bm = self._bm25()
        return bm.search(
            namespace=namespace,
            query=query,
            top_k=top_k,
            include_text=include_text,
            include_metadata=include_metadata,
        )

    def namespace_stats(self, name: str) -> Optional[NamespaceStats]:
        """Get detailed statistics for a namespace."""
        try:
            bm = self._bm25()
            stats = bm.stats(namespace=name)
            return NamespaceStats(
                name=stats.namespace,
                doc_count=stats.doc_count,
                term_count=stats.term_count,
                posting_count=stats.posting_count,
                avg_doc_len=stats.avg_doc_len,
                total_doc_len=stats.total_doc_len,
                db_path=stats.db_path,
                db_size_bytes=stats.db_size_bytes,
                created_at=0.0,  # not tracked at BM25 level
                updated_at=stats.updated_at,
            )
        except Exception:
            return None

    def health_check(self) -> Dict[str, Any]:
        """Perform health check across all namespaces.

        Returns:
            Health status dict with namespace stats
        """
        namespaces = self.list_namespaces()
        total_docs = sum(ns.doc_count for ns in namespaces)

        return {
            "status": "healthy",
            "namespace_count": len(namespaces),
            "total_documents": total_docs,
            "registry_path": self._registry_path,
            "bm25_db_path": self._bm25_db_path,
            "namespaces": [
                {
                    "name": ns.name,
                    "doc_count": ns.doc_count,
                    "term_count": ns.term_count,
                    "db_size_bytes": ns.db_size_bytes,
                }
                for ns in namespaces
            ],
        }

    def close(self) -> None:
        """Close all connections."""
        if hasattr(self._local, "registry_conn") and self._local.registry_conn:
            self._local.registry_conn.close()
            self._local.registry_conn = None
        if self._bm25:
            self._bm25.close()
            self._bm25 = None
