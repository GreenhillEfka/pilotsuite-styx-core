"""Cross-Home Sharing Module – Phase 5.

Implements:
- Discovery: mDNS/Bonjour discovery of other CoPilot instances
- Sync: WebSocket-based entity synchronization between homes
- Registry: Shared entity registry for cross-home sharing
- Conflict: Conflict resolution for concurrent updates

Features:
- Auto-discovery of peer CoPilot instances
- End-to-end encrypted sync protocol
- Entity sharing with access control
- Conflict-free replicated data types (CRDTs)
"""

# Import services from core/sharing (shared between addon and core)
import sys
import os

# Add core directory to path for imports
core_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', '..', '..', 'core')
if os.path.exists(core_path):
    sys.path.insert(0, core_path)

try:
    from sharing import DiscoveryService, SyncProtocol, SharedRegistry, ConflictResolver
except ImportError:
    # Fallback implementations if core/sharing not available
    DiscoveryService = None
    SyncProtocol = None
    SharedRegistry = None
    ConflictResolver = None

__all__ = [
    "DiscoveryService",
    "SyncProtocol",
    "SharedRegistry",
    "ConflictResolver",
]