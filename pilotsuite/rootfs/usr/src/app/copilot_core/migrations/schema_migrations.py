"""
Migration System for PilotSuite Core.

Database schema versioning and migration execution.
"""
from __future__ import annotations
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
import json
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

# Migration storage
MIGRATIONS_PATH = Path("/config/copilot_core/data/migrations")
MIGRATIONS_PATH.mkdir(parents=True, exist_ok=True)


@dataclass
class Migration:
    """Database migration."""
    version: str
    name: str
    description: str = ""
    up: Optional[Callable] = None
    down: Optional[Callable] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class MigrationRecord:
    """Applied migration record."""
    version: str
    name: str
    applied_at: datetime = field(default_factory=datetime.now)
    duration_ms: int = 0


class SchemaMigrations:
    """Database schema migration manager."""

    def __init__(self, db_manager) -> None:
        """Initialize migration manager."""
        self._db = db_manager
        self._migrations: Dict[str, Migration] = {}
        self._applied: List[MigrationRecord] = []
        self._init_migration_table()

    def _init_migration_table(self) -> None:
        """Create migrations tracking table."""
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                duration_ms INTEGER DEFAULT 0
            )
        """)
        rows = self._db.execute("SELECT version, name, applied_at, duration_ms FROM schema_migrations ORDER BY version")
        self._applied = [
            MigrationRecord(
                version=row["version"],
                name=row["name"],
                applied_at=datetime.fromisoformat(row["applied_at"]) if row["applied_at"] else datetime.now(),
                duration_ms=row["duration_ms"] or 0,
            )
            for row in rows
        ]

    def register(self, migration: Migration) -> None:
        """Register a migration."""
        self._migrations[migration.version] = migration
        _LOGGER.debug("Migration registered: %s", migration.version)

    def get_pending(self) -> List[Migration]:
        """Get pending migrations."""
        applied_versions = {r.version for r in self._applied}
        return [
            m for v, m in sorted(self._migrations.items())
            if v not in applied_versions
        ]

    def get_applied(self) -> List[MigrationRecord]:
        """Get applied migrations."""
        return self._applied

    def run(self, target_version: Optional[str] = None) -> List[MigrationRecord]:
        """Run pending migrations."""
        pending = self.get_pending()
        applied = []

        for migration in pending:
            if target_version and migration.version > target_version:
                break

            _LOGGER.info("Running migration: %s (%s)", migration.version, migration.name)
            start = datetime.now()

            try:
                if migration.up:
                    migration.up(self._db)
                
                duration = int((datetime.now() - start).total_seconds() * 1000)
                
                # Record migration
                self._db.execute(
                    "INSERT INTO schema_migrations (version, name, duration_ms) VALUES (?, ?, ?)",
                    (migration.version, migration.name, duration)
                )

                record = MigrationRecord(
                    version=migration.version,
                    name=migration.name,
                    duration_ms=duration,
                )
                self._applied.append(record)
                applied.append(record)

                _LOGGER.info("Migration applied: %s (%dms)", migration.version, duration)
            except Exception as e:
                _LOGGER.error("Migration failed: %s - %s", migration.version, e)
                raise

        return applied

    def rollback(self, target_version: str) -> bool:
        """Rollback to target version."""
        applied_versions = [r.version for r in self._applied]
        if target_version not in applied_versions:
            _LOGGER.error("Target version not found: %s", target_version)
            return False

        # Rollback in reverse order
        for record in reversed(self._applied):
            if record.version == target_version:
                break

            migration = self._migrations.get(record.version)
            if migration and migration.down:
                try:
                    migration.down(self._db)
                    self._db.execute("DELETE FROM schema_migrations WHERE version = ?", (record.version,))
                    self._applied.remove(record)
                    _LOGGER.info("Rolled back: %s", record.version)
                except Exception as e:
                    _LOGGER.error("Rollback failed: %s - %s", record.version, e)
                    return False

        return True


# Default migrations
def register_default_migrations(migrations: SchemaMigrations) -> None:
    """Register default schema migrations."""

    # Migration 001: Initial schema
    migrations.register(Migration(
        version="001",
        name="initial_schema",
        description="Create initial database schema",
    ))

    # Migration 002: Add indexes
    migrations.register(Migration(
        version="002",
        name="add_indexes",
        description="Add performance indexes",
        up=lambda db: db.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_trigger ON patterns(trigger_entity);
            CREATE INDEX IF NOT EXISTS idx_events_time ON events(timestamp);
        """),
    ))

    # Migration 003: Add user preferences
    migrations.register(Migration(
        version="003",
        name="user_preferences",
        description="Add user preferences table",
        up=lambda db: db.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                UNIQUE(user_id, key),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """),
    ))


# Global instance
_schema_migrations: Optional[SchemaMigrations] = None


def get_schema_migrations(db_manager) -> SchemaMigrations:
    """Get global schema migrations."""
    global _schema_migrations
    if _schema_migrations is None:
        _schema_migrations = SchemaMigrations(db_manager)
        register_default_migrations(_schema_migrations)
    return _schema_migrations


__all__ = [
    "SchemaMigrations",
    "Migration",
    "MigrationRecord",
    "get_schema_migrations",
    "register_default_migrations",
]
