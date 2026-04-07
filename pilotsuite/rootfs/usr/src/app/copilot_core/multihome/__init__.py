"""Multi-Home Synchronization Module.

Provides synchronization capabilities for multiple home locations
(Hauptwohnung, Ferienhaus, Büro) with secure, encrypted communication
and conflict resolution.

Modules:
- sync_engine: Core synchronization engine
- config_sync: Configuration synchronization
- state_sync: State synchronization
"""

from .sync_engine import (
    SyncEngine,
    SyncOperation,
    SyncStatus,
    SyncConflict,
    ConflictResolution,
    HomeInstance,
    HomeType,
    EncryptionHelper,
    get_sync_engine,
)

from .config_sync import (
    ConfigSync,
    get_config_sync,
)

from .state_sync import (
    StateSync,
    EntityState,
    get_state_sync,
)

__all__ = [
    # Sync Engine
    "SyncEngine",
    "SyncOperation",
    "SyncStatus",
    "SyncConflict",
    "ConflictResolution",
    "HomeInstance",
    "HomeType",
    "EncryptionHelper",
    "get_sync_engine",
    # Config Sync
    "ConfigSync",
    "get_config_sync",
    # State Sync
    "StateSync",
    "EntityState",
    "get_state_sync",
]

__version__ = "1.0.0"
