"""PilotSuite Migration System — Database Schema Migrations."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from pathlib import Path
import json

logger = logging.getLogger(__name__)


# =============================================================================
# MIGRATION TYPES
# =============================================================================

@dataclass
class Migration:
    """Database migration definition."""
    version: str
    name: str
    description: str
    created_at: datetime
    up: Callable  # Function to apply migration
    down: Callable  # Function to rollback migration


@dataclass
class MigrationResult:
    """Result of migration execution."""
    version: str
    success: bool
    error: Optional[str] = None
    duration_ms: Optional[int] = None


# =============================================================================
# MIGRATION MANAGER
# =============================================================================

class MigrationManager:
    """
    Database Migration Manager
    
    Features:
    - Version tracking
    - Up/down migrations
    - Rollback support
    - Migration history
    
    Usage:
    ```python
    from copilot_core.database.migrations import MigrationManager
    
    migrations = MigrationManager()
    
    @migrations.migration("001_initial_schema")
    def initial_schema(up=True):
        if up:
            # Create tables
            pass
        else:
            # Drop tables
            pass
    
    # Run migrations
    migrations.run()
    ```
    """

    def __init__(self, migrations_dir: str = "/config/pilotsuite/migrations"):
        self.migrations_dir = Path(migrations_dir)
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        
        self._migrations: List[Migration] = []
        self._applied_migrations: List[str] = []

    def migration(self, name: str, description: str = ""):
        """Decorator to register a migration."""
        def decorator(func: Callable):
            version = name.split("_")[0]  # e.g., "001" from "001_initial_schema"
            
            migration = Migration(
                version=version,
                name=name,
                description=description,
                created_at=datetime.now(),
                up=lambda: func(up=True),
                down=lambda: func(up=False),
            )
            
            self._migrations.append(migration)
            logger.info(f"Registered migration: {name} (v{version})")
            
            return func
        
        return decorator

    async def run(self, target_version: Optional[str] = None):
        """
        Run pending migrations.
        
        Args:
            target_version: Migrate to specific version (None = latest)
        """
        # Load applied migrations
        self._load_applied_migrations()
        
        # Sort migrations by version
        self._migrations.sort(key=lambda m: m.version)
        
        # Find pending migrations
        pending = [
            m for m in self._migrations
            if m.version not in self._applied_migrations
        ]
        
        if not pending:
            logger.info("No pending migrations")
            return []
        
        # Apply migrations
        results = []
        for migration in pending:
            if target_version and migration.version > target_version:
                break
            
            logger.info(f"Applying migration: {migration.name}")
            
            start_time = datetime.now()
            try:
                migration.up()
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                
                self._applied_migrations.append(migration.version)
                self._save_applied_migrations()
                
                results.append(MigrationResult(
                    version=migration.version,
                    success=True,
                    duration_ms=duration_ms,
                ))
                
                logger.info(f"Migration applied: {migration.name} ({duration_ms}ms)")
                
            except Exception as e:
                logger.error(f"Migration failed: {migration.name} - {e}")
                
                results.append(MigrationResult(
                    version=migration.version,
                    success=False,
                    error=str(e),
                ))
                break
        
        return results

    async def rollback(self, target_version: str):
        """
        Rollback to specific version.
        
        Args:
            target_version: Version to rollback to
        """
        # Load applied migrations
        self._load_applied_migrations()
        
        # Sort migrations by version (descending for rollback)
        self._migrations.sort(key=lambda m: m.version, reverse=True)
        
        # Find migrations to rollback
        to_rollback = [
            m for m in self._migrations
            if m.version in self._applied_migrations and m.version > target_version
        ]
        
        if not to_rollback:
            logger.info("No migrations to rollback")
            return []
        
        # Rollback migrations
        results = []
        for migration in to_rollback:
            logger.info(f"Rolling back migration: {migration.name}")
            
            start_time = datetime.now()
            try:
                migration.down()
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                
                self._applied_migrations.remove(migration.version)
                self._save_applied_migrations()
                
                results.append(MigrationResult(
                    version=migration.version,
                    success=True,
                    duration_ms=duration_ms,
                ))
                
                logger.info(f"Migration rolled back: {migration.name} ({duration_ms}ms)")
                
            except Exception as e:
                logger.error(f"Rollback failed: {migration.name} - {e}")
                
                results.append(MigrationResult(
                    version=migration.version,
                    success=False,
                    error=str(e),
                ))
                break
        
        return results

    def _load_applied_migrations(self):
        """Load applied migrations from file."""
        migrations_file = self.migrations_dir / "applied_migrations.json"
        
        if migrations_file.exists():
            with open(migrations_file) as f:
                self._applied_migrations = json.load(f)
        else:
            self._applied_migrations = []

    def _save_applied_migrations(self):
        """Save applied migrations to file."""
        migrations_file = self.migrations_dir / "applied_migrations.json"
        
        with open(migrations_file, "w") as f:
            json.dump(self._applied_migrations, f, indent=2)

    def get_status(self) -> Dict[str, Any]:
        """Get migration status."""
        self._load_applied_migrations()
        
        return {
            "total_migrations": len(self._migrations),
            "applied_migrations": len(self._applied_migrations),
            "pending_migrations": len(self._migrations) - len(self._applied_migrations),
            "current_version": max(self._applied_migrations) if self._applied_migrations else "0",
            "latest_version": max(m.version for m in self._migrations) if self._migrations else "0",
            "migrations": [
                {
                    "version": m.version,
                    "name": m.name,
                    "description": m.description,
                    "applied": m.version in self._applied_migrations,
                }
                for m in self._migrations
            ],
        }


# =============================================================================
# PREDEFINED MIGRATIONS
# =============================================================================

def register_default_migrations(migrations: MigrationManager):
    """Register default PilotSuite migrations."""

    @migrations.migration("001_initial_schema", "Create initial database schema")
    def initial_schema(up=True):
        """Initial database schema creation."""
        from copilot_core.database.models import Base, get_database_manager
        
        db_manager = get_database_manager()
        
        if up:
            # Create all tables
            import asyncio
            asyncio.run(db_manager.init())
        else:
            # Drop all tables
            import asyncio
            async def drop_tables():
                await db_manager.init()
                async with db_manager.engine.begin() as conn:
                    await conn.run_sync(Base.metadata.drop_all)
            asyncio.run(drop_tables())

    @migrations.migration("002_add_user_preferences", "Add user preferences table")
    def add_user_preferences(up=True):
        """Add user preferences table."""
        from copilot_core.database.models import UserPreference, get_database_manager
        
        db_manager = get_database_manager()
        
        if up:
            # Create UserPreference table
            import asyncio
            async def create_table():
                await db_manager.init()
                async with db_manager.engine.begin() as conn:
                    await conn.run_sync(UserPreference.__table__.create)
            asyncio.run(create_table())
        else:
            # Drop UserPreference table
            import asyncio
            async def drop_table():
                await db_manager.init()
                async with db_manager.engine.begin() as conn:
                    await conn.run_sync(UserPreference.__table__.drop)
            asyncio.run(drop_table())

    @migrations.migration("003_add_notifications", "Add notifications table")
    def add_notifications(up=True):
        """Add notifications table."""
        from copilot_core.database.models import Notification, get_database_manager
        
        db_manager = get_database_manager()
        
        if up:
            import asyncio
            async def create_table():
                await db_manager.init()
                async with db_manager.engine.begin() as conn:
                    await conn.run_sync(Notification.__table__.create)
            asyncio.run(create_table())
        else:
            import asyncio
            async def drop_table():
                await db_manager.init()
                async with db_manager.engine.begin() as conn:
                    await conn.run_sync(Notification.__table__.drop)
            asyncio.run(drop_table())


# =============================================================================
# HOME ASSISTANT INTEGRATION
# =============================================================================

async def async_setup_migrations(hass, config: Dict[str, Any]):
    """Set up migrations in Home Assistant."""
    migrations_dir = config.get("migrations_dir", "/config/pilotsuite/migrations")
    
    migrations = MigrationManager(migrations_dir)
    
    # Register default migrations
    register_default_migrations(migrations)
    
    # Run pending migrations
    results = await migrations.run()
    
    # Store in hass.data
    hass.data["pilotsuite_migrations"] = migrations
    
    logger.info(f"Migrations set up: {len(results)} applied")
    
    return migrations
