"""Multi-Home Sync Package for PilotSuite.

Provides secure, encrypted synchronization between multiple PilotSuite
home instances (primary home, vacation home, office, etc.).

Modules:
- multi_home_sync: Main orchestrator for cross-home sync operations
- homes_registry: Persistent registration of home instances
- sync_protocol: HTTP-based signed message protocol
- conflict_resolver: Conflict detection and resolution strategies
- transfer: Encrypted bulk data transfer with chunking

Usage:
    from copilot_core.sync import MultiHomeSync, SyncMode, SyncScope

    sync = MultiHomeSync(home_id="home-1", shared_secret="...")
    sync.register_home("home-2", "Ferienhaus", HomeType.VACATION, "https://...")
    job = sync.sync_to("home-2", mode=SyncMode.INCREMENTAL, scope=SyncScope.ALL)
"""

from .multi_home_sync import MultiHomeSync, SyncJob, SyncMode, SyncScope
from .homes_registry import HomesRegistry, HomeRegistration, HomeType, HomeStatus
from .sync_protocol import SyncProtocol, SyncEnvelope, SyncResponse, MessageType, SyncDirection
from .conflict_resolver import ConflictResolver, ConflictStrategy, ConflictRecord
from .transfer import SecureTransfer, TransferResult, EncryptedPayload

__all__ = [
    # Main orchestrator
    "MultiHomeSync",
    "SyncJob",
    "SyncMode",
    "SyncScope",
    # Registry
    "HomesRegistry",
    "HomeRegistration",
    "HomeType",
    "HomeStatus",
    # Protocol
    "SyncProtocol",
    "SyncEnvelope",
    "SyncResponse",
    "MessageType",
    "SyncDirection",
    # Conflicts
    "ConflictResolver",
    "ConflictStrategy",
    "ConflictRecord",
    # Transfer
    "SecureTransfer",
    "TransferResult",
    "EncryptedPayload",
]

__version__ = "1.0.0"
