"""
Database Layer for PilotSuite Core.

Provides SQLite/PostgreSQL persistence with SQLAlchemy ORM.
"""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import sqlite3
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

# Global database path
DB_PATH = Path("/config/copilot_core/data/pilotsuite.db")


@dataclass
class DatabaseConfig:
    """Database configuration."""
    path: str = "/config/copilot_core/data/pilotsuite.db"
    backup_path: str = "/config/copilot_core/data/backup"
    max_connections: int = 10
    timeout: float = 30.0
    wal_mode: bool = True


class DatabaseManager:
    """Database manager with connection pooling."""

    def __init__(self, config: Optional[DatabaseConfig] = None) -> None:
        """Initialize database manager."""
        self._config = config or DatabaseConfig()
        self._connections: Dict[int, sqlite3.Connection] = {}
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Core tables
        cursor.executescript("""
            -- Zones table
            CREATE TABLE IF NOT EXISTS zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL DEFAULT 'room',
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Entities table
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT NOT NULL UNIQUE,
                zone_id INTEGER,
                state TEXT,
                attributes TEXT,
                last_changed TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id)
            );
            
            -- State history table
            CREATE TABLE IF NOT EXISTS state_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT NOT NULL,
                state TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT
            );
            
            -- Patterns table (Habitus)
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger_entity TEXT NOT NULL,
                action_sequence TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                times_triggered INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Users table
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                preferences TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Events table
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                source TEXT,
                data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Create indexes
            CREATE INDEX IF NOT EXISTS idx_entities_zone ON entities(zone_id);
            CREATE INDEX IF NOT EXISTS idx_state_history_entity ON state_history(entity_id);
            CREATE INDEX IF NOT EXISTS idx_state_history_time ON state_history(timestamp);
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
        """)
        
        conn.commit()
        _LOGGER.info("Database initialized at %s", DB_PATH)

    @contextmanager
    def get_connection(self):
        """Get database connection (context manager)."""
        conn = self._get_connection()
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            _LOGGER.error("Database error: %s", e)
            raise
        finally:
            pass  # Connection pooling - keep connection open

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        thread_id = id(conn := __import__('threading').current_thread())
        if thread_id not in self._connections:
            self._connections[thread_id] = sqlite3.connect(
                DB_PATH,
                timeout=self._config.timeout,
                detect_types=sqlite3.PARSE_DECLTYPES
            )
            self._connections[thread_id].row_factory = sqlite3.Row
            if self._config.wal_mode:
                self._connections[thread_id].execute("PRAGMA journal_mode=WAL")
        return self._connections[thread_id]

    def execute(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Execute query and return results."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def execute_many(self, query: str, params_list: List[tuple]) -> None:
        """Execute many query."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()

    # Zone operations
    def create_zone(self, name: str, zone_type: str = "room", metadata: Dict = None) -> int:
        """Create zone."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO zones (name, type, metadata) VALUES (?, ?, ?)",
                (name, zone_type, json.dumps(metadata) if metadata else None)
            )
            conn.commit()
            return cursor.lastrowid

    def get_zones(self) -> List[Dict[str, Any]]:
        """Get all zones."""
        rows = self.execute("SELECT * FROM zones ORDER BY name")
        return [dict(row) for row in rows]

    # Entity operations
    def save_entity_state(self, entity_id: str, state: str, attributes: Dict = None, zone_id: int = None) -> None:
        """Save entity state."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO entities (entity_id, zone_id, state, attributes, last_changed)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(entity_id) DO UPDATE SET
                    state = excluded.state,
                    attributes = excluded.attributes,
                    last_changed = CURRENT_TIMESTAMP
            """, (entity_id, zone_id, state, json.dumps(attributes) if attributes else None))
            conn.commit()

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by ID."""
        rows = self.execute("SELECT * FROM entities WHERE entity_id = ?", (entity_id,))
        return dict(rows[0]) if rows else None

    # Pattern operations
    def save_pattern(self, trigger_entity: str, action_sequence: List[Dict], confidence: float = 0.5) -> int:
        """Save learned pattern."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO patterns (trigger_entity, action_sequence, confidence)
                VALUES (?, ?, ?)
            """, (trigger_entity, json.dumps(action_sequence), confidence))
            conn.commit()
            return cursor.lastrowid

    def get_patterns(self, min_confidence: float = 0.0) -> List[Dict[str, Any]]:
        """Get patterns above confidence threshold."""
        rows = self.execute(
            "SELECT * FROM patterns WHERE confidence >= ? ORDER BY confidence DESC",
            (min_confidence,)
        )
        return [dict(row) for row in rows]

    def increment_pattern_trigger(self, pattern_id: int, success: bool) -> None:
        """Increment pattern trigger count."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE patterns 
                SET times_triggered = times_triggered + 1,
                    success_rate = (success_rate * times_triggered + ?) / (times_triggered + 1),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (1 if success else 0, pattern_id))
            conn.commit()

    def close(self) -> None:
        """Close all connections."""
        for conn in self._connections.values():
            conn.close()
        self._connections.clear()


# Global instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get global database manager."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


__all__ = [
    "DatabaseManager",
    "DatabaseConfig",
    "get_db_manager",
]
