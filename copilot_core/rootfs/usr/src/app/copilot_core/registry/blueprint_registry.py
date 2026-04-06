"""Blueprint Registry — SQLite-backed hash registry with drift detection.

Stores SHA-256 fingerprints of automation blueprints together with
metadata so that runtime drift can be detected and reported.

Schema::

    CREATE TABLE blueprint_registry (
        blueprint_id    TEXT PRIMARY KEY,   -- stable identifier (e.g. "zone_lights")
        domain          TEXT NOT NULL,       -- e.g. "automation"
        name            TEXT NOT NULL,
        hash            TEXT NOT NULL,       -- SHA-256 hex digest
        version         TEXT DEFAULT "",
        source          TEXT DEFAULT "",
        file_path       TEXT DEFAULT "",
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_drift_at   TIMESTAMP,
        drift_count     INTEGER DEFAULT 0,
        is_active       INTEGER DEFAULT 1,
        metadata_json   TEXT DEFAULT "{}"
    );

    CREATE INDEX idx_bp_hash      ON blueprint_registry(hash);
    CREATE INDEX idx_bp_domain    ON blueprint_registry(domain);
    CREATE INDEX idx_bp_drift    ON blueprint_registry(last_drift_at);
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from .hash_calculator import compute_blueprint_hash

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BlueprintEntry:
    """Single registry entry for a blueprint."""
    blueprint_id: str
    domain: str
    name: str
    hash: str
    version: str = ""
    source: str = ""
    file_path: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_drift_at: Optional[str] = None
    drift_count: int = 0
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blueprint_id": self.blueprint_id,
            "domain": self.domain,
            "name": self.name,
            "hash": self.hash,
            "version": self.version,
            "source": self.source,
            "file_path": self.file_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_drift_at": self.last_drift_at,
            "drift_count": self.drift_count,
            "is_active": self.is_active,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Registry store
# ---------------------------------------------------------------------------

class BlueprintRegistryStore:
    """SQLite-backed blueprint registry with hash-based versioning."""

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS blueprint_registry (
            blueprint_id    TEXT PRIMARY KEY,
            domain          TEXT NOT NULL,
            name            TEXT NOT NULL,
            hash            TEXT NOT NULL,
            version         TEXT DEFAULT '',
            source          TEXT DEFAULT '',
            file_path       TEXT DEFAULT '',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_drift_at   TIMESTAMP,
            drift_count     INTEGER DEFAULT 0,
            is_active       INTEGER DEFAULT 1,
            metadata_json   TEXT DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_bp_hash    ON blueprint_registry(hash);
        CREATE INDEX IF NOT EXISTS idx_bp_domain  ON blueprint_registry(domain);
        CREATE INDEX IF NOT EXISTS idx_bp_drift   ON blueprint_registry(last_drift_at);
    """

    def __init__(self, db_path: str | Path = "/data/blueprint_registry.db") -> None:
        self._db_path = Path(db_path)
        self._init_db()

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(self._SCHEMA)
            conn.commit()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _row_to_entry(self, row: sqlite3.Row) -> BlueprintEntry:
        return BlueprintEntry(
            blueprint_id=row["blueprint_id"],
            domain=row["domain"],
            name=row["name"],
            hash=row["hash"],
            version=row["version"] or "",
            source=row["source"] or "",
            file_path=row["file_path"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_drift_at=row["last_drift_at"],
            drift_count=row["drift_count"] or 0,
            is_active=bool(row["is_active"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    # -----------------------------------------------------------------------
    # CRUD operations
    # -----------------------------------------------------------------------

    def upsert(self, entry: BlueprintEntry) -> None:
        """Insert or update a blueprint entry."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO blueprint_registry
                    (blueprint_id, domain, name, hash, version, source, file_path,
                     created_at, updated_at, last_drift_at, drift_count, is_active, metadata_json)
                VALUES
                    (:blueprint_id, :domain, :name, :hash, :version, :source, :file_path,
                     :created_at, :updated_at, :last_drift_at, :drift_count, :is_active, :metadata_json)
                ON CONFLICT(blueprint_id) DO UPDATE SET
                    hash           = excluded.hash,
                    name           = excluded.name,
                    version        = excluded.version,
                    source         = excluded.source,
                    file_path      = excluded.file_path,
                    updated_at     = excluded.updated_at,
                    last_drift_at  = excluded.last_drift_at,
                    drift_count    = excluded.drift_count,
                    is_active      = excluded.is_active,
                    metadata_json  = excluded.metadata_json
                """,
                {
                    "blueprint_id": entry.blueprint_id,
                    "domain": entry.domain,
                    "name": entry.name,
                    "hash": entry.hash,
                    "version": entry.version or "",
                    "source": entry.source or "",
                    "file_path": entry.file_path or "",
                    "created_at": entry.created_at or now,
                    "updated_at": now,
                    "last_drift_at": entry.last_drift_at,
                    "drift_count": entry.drift_count,
                    "is_active": int(entry.is_active),
                    "metadata_json": json.dumps(entry.metadata),
                },
            )
            conn.commit()

    def register_blueprint(
        self,
        blueprint_id: str,
        domain: str,
        name: str,
        blueprint_dict: Dict[str, Any],
        version: str = "",
        source: str = "",
        file_path: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BlueprintEntry:
        """Parse and register a blueprint, computing its hash."""
        blueprint_hash = compute_blueprint_hash(blueprint_dict)
        entry = BlueprintEntry(
            blueprint_id=blueprint_id,
            domain=domain,
            name=name,
            hash=blueprint_hash,
            version=version,
            source=source,
            file_path=file_path,
            metadata=metadata or {},
        )
        self.upsert(entry)
        return entry

    def get(self, blueprint_id: str) -> Optional[BlueprintEntry]:
        """Fetch a single blueprint entry by id."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM blueprint_registry WHERE blueprint_id = ?",
                (blueprint_id,),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def get_by_hash(self, blueprint_hash: str) -> Optional[BlueprintEntry]:
        """Fetch a single blueprint entry by hash."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM blueprint_registry WHERE hash = ?",
                (blueprint_hash,),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def list_all(
        self,
        domain: Optional[str] = None,
        active_only: bool = True,
        limit: int = 500,
    ) -> List[BlueprintEntry]:
        """List all blueprint entries, optionally filtered."""
        sql = "SELECT * FROM blueprint_registry WHERE 1=1"
        params: List[Any] = []
        if domain:
            sql += " AND domain = ?"
            params.append(domain)
        if active_only:
            sql += " AND is_active = 1"
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def delete(self, blueprint_id: str) -> bool:
        """Hard-delete a blueprint entry."""
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM blueprint_registry WHERE blueprint_id = ?",
                (blueprint_id,),
            )
            conn.commit()
            return cur.rowcount > 0

    def deactivate(self, blueprint_id: str) -> bool:
        """Soft-delete (deactivate) a blueprint entry."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                """
                UPDATE blueprint_registry
                SET is_active = 0, updated_at = ?
                WHERE blueprint_id = ?
                """,
                (now, blueprint_id),
            )
            conn.commit()
            return cur.rowcount > 0

    # -----------------------------------------------------------------------
    # Drift helpers
    # -----------------------------------------------------------------------

    def record_drift(self, blueprint_id: str) -> bool:
        """Increment drift count and update last_drift_at timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                """
                UPDATE blueprint_registry
                SET drift_count = drift_count + 1,
                    last_drift_at = ?,
                    updated_at = ?
                WHERE blueprint_id = ?
                """,
                (now, now, blueprint_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def get_drifted(
        self,
        since_iso: Optional[str] = None,
        min_drift_count: int = 1,
    ) -> List[BlueprintEntry]:
        """Return blueprints that have recorded drift."""
        sql = (
            "SELECT * FROM blueprint_registry "
            "WHERE drift_count >= ? AND is_active = 1"
        )
        params: List[Any] = [min_drift_count]
        if since_iso:
            sql += " AND last_drift_at >= ?"
            params.append(since_iso)
        sql += " ORDER BY last_drift_at DESC"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregate statistics."""
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM blueprint_registry WHERE is_active = 1"
            ).fetchone()[0]
            drifted = conn.execute(
                "SELECT COUNT(*) FROM blueprint_registry WHERE drift_count > 0 AND is_active = 1"
            ).fetchone()[0]
            by_domain = conn.execute(
                """
                SELECT domain, COUNT(*) as count
                FROM blueprint_registry
                WHERE is_active = 1
                GROUP BY domain
                """
            ).fetchall()
        return {
            "total_blueprints": total,
            "drifted_blueprints": drifted,
            "by_domain": [{"domain": r["domain"], "count": r["count"]} for r in by_domain],
        }


# ---------------------------------------------------------------------------
# Global instance (lazy)
# ---------------------------------------------------------------------------

_store: Optional[BlueprintRegistryStore] = None


def get_blueprint_registry(
    db_path: str | Path = "/data/blueprint_registry.db",
) -> BlueprintRegistryStore:
    global _store
    if _store is None:
        _store = BlueprintRegistryStore(db_path)
    return _store
