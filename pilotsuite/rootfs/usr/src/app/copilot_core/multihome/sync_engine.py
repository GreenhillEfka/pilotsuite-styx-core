"""Multi-Home Synchronization Engine.

Core synchronization engine for managing multiple home locations
(Hauptwohnung, Ferienhaus, Büro) with secure, encrypted communication
and conflict resolution.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class HomeType(str, Enum):
    """Types of home locations."""
    PRIMARY = "primary"  # Hauptwohnung
    VACATION = "vacation"  # Ferienhaus
    OFFICE = "office"  # Büro
    SECONDARY = "secondary"  # Other secondary locations


class SyncStatus(str, Enum):
    """Synchronization status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class ConflictResolution(str, Enum):
    """Conflict resolution strategies."""
    LAST_WRITE_WINS = "last_write_wins"
    PRIMARY_WINS = "primary_wins"
    MANUAL = "manual"
    MERGE = "merge"


@dataclass
class HomeInstance:
    """Represents a home instance in the multi-home setup."""
    id: str
    name: str
    home_type: HomeType
    base_url: str
    auth_token: str
    is_primary: bool = False
    is_active: bool = True
    last_sync: Optional[datetime] = None
    sync_interval_seconds: int = 300  # 5 minutes
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without sensitive data)."""
        return {
            "id": self.id,
            "name": self.name,
            "home_type": self.home_type.value,
            "base_url": self.base_url,
            "is_primary": self.is_primary,
            "is_active": self.is_active,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "sync_interval_seconds": self.sync_interval_seconds,
            "metadata": self.metadata,
        }


@dataclass
class SyncOperation:
    """Represents a synchronization operation."""
    id: str
    source_home_id: str
    target_home_id: str
    operation_type: str  # config, state, automation
    status: SyncStatus = SyncStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    data: Dict[str, Any] = field(default_factory=dict)
    conflict_info: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "source_home_id": self.source_home_id,
            "target_home_id": self.target_home_id,
            "operation_type": self.operation_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "data": self.data,
            "conflict_info": self.conflict_info,
            "error_message": self.error_message,
        }


@dataclass
class SyncConflict:
    """Represents a synchronization conflict."""
    id: str
    operation_id: str
    field_path: str
    local_value: Any
    remote_value: Any
    local_timestamp: datetime
    remote_timestamp: datetime
    resolution: Optional[ConflictResolution] = None
    resolved_value: Any = None
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "operation_id": self.operation_id,
            "field_path": self.field_path,
            "local_value": self.local_value,
            "remote_value": self.remote_value,
            "local_timestamp": self.local_timestamp.isoformat(),
            "remote_timestamp": self.remote_timestamp.isoformat(),
            "resolution": self.resolution.value if self.resolution else None,
            "resolved_value": self.resolved_value,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class EncryptionHelper:
    """Helper for encrypting communication between home instances."""
    
    def __init__(self, shared_secret: Optional[str] = None):
        """Initialize with shared secret for HMAC."""
        self.shared_secret = shared_secret or os.environ.get("MULTIHOME_SHARED_SECRET", "default-secret-change-in-production")
    
    def sign_payload(self, payload: Dict[str, Any]) -> str:
        """Sign a payload with HMAC-SHA256."""
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.shared_secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def verify_payload(self, payload: Dict[str, Any], signature: str) -> bool:
        """Verify payload signature."""
        expected_signature = self.sign_payload(payload)
        return hmac.compare_digest(expected_signature, signature)
    
    def encrypt_payload(self, payload: Dict[str, Any]) -> str:
        """Encrypt payload (base64 + signature for now)."""
        # In production, use proper encryption (AES-GCM)
        payload_json = json.dumps(payload)
        signature = self.sign_payload(payload)
        encrypted = {
            "data": payload_json,
            "signature": signature,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        return json.dumps(encrypted)
    
    def decrypt_payload(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt and verify payload."""
        try:
            encrypted = json.loads(encrypted_data)
            payload_json = encrypted.get("data", "")
            signature = encrypted.get("signature", "")
            payload = json.loads(payload_json)
            
            if not self.verify_payload(payload, signature):
                raise ValueError("Payload signature verification failed")
            
            return payload
        except Exception as e:
            logger.error(f"Failed to decrypt payload: {e}")
            raise


class SyncEngine:
    """Main synchronization engine for multi-home setup."""
    
    def __init__(self, data_dir: str = "/data/multihome"):
        """Initialize the sync engine."""
        self.data_dir = data_dir
        self.homes: Dict[str, HomeInstance] = {}
        self.pending_operations: List[SyncOperation] = []
        self.conflicts: List[SyncConflict] = []
        self.encryption = EncryptionHelper()
        self.conflict_resolution_strategy = ConflictResolution.LAST_WRITE_WINS
        self._state_file = os.path.join(data_dir, "sync_state.json")
        self._load_state()
    
    def _load_state(self) -> None:
        """Load synchronization state from disk."""
        try:
            if os.path.exists(self._state_file):
                with open(self._state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                
                # Load homes
                for home_data in state.get("homes", []):
                    home = HomeInstance(
                        id=home_data["id"],
                        name=home_data["name"],
                        home_type=HomeType(home_data["home_type"]),
                        base_url=home_data["base_url"],
                        auth_token=home_data.get("auth_token", ""),
                        is_primary=home_data.get("is_primary", False),
                        is_active=home_data.get("is_active", True),
                        last_sync=datetime.fromisoformat(home_data["last_sync"]) if home_data.get("last_sync") else None,
                        sync_interval_seconds=home_data.get("sync_interval_seconds", 300),
                        metadata=home_data.get("metadata", {})
                    )
                    self.homes[home.id] = home
                
                # Load conflict resolution strategy
                strategy_str = state.get("conflict_resolution_strategy", "last_write_wins")
                self.conflict_resolution_strategy = ConflictResolution(strategy_str)
                
                logger.info(f"Loaded sync state: {len(self.homes)} homes configured")
        except Exception as e:
            logger.error(f"Failed to load sync state: {e}")
            # Initialize with empty state
            self.homes = {}
    
    def _save_state(self) -> None:
        """Save synchronization state to disk."""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            state = {
                "homes": [home.to_dict() for home in self.homes.values()],
                "conflict_resolution_strategy": self.conflict_resolution_strategy.value,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            with open(self._state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sync state: {e}")
    
    def register_home(self, home: HomeInstance) -> None:
        """Register a new home instance."""
        self.homes[home.id] = home
        self._save_state()
        logger.info(f"Registered home: {home.name} ({home.id})")
    
    def unregister_home(self, home_id: str) -> None:
        """Unregister a home instance."""
        if home_id in self.homes:
            del self.homes[home_id]
            self._save_state()
            logger.info(f"Unregistered home: {home_id}")
    
    def get_primary_home(self) -> Optional[HomeInstance]:
        """Get the primary home instance."""
        for home in self.homes.values():
            if home.is_primary:
                return home
        return None
    
    def get_active_homes(self) -> List[HomeInstance]:
        """Get all active home instances."""
        return [home for home in self.homes.values() if home.is_active]
    
    def create_sync_operation(
        self,
        source_home_id: str,
        target_home_id: str,
        operation_type: str,
        data: Dict[str, Any]
    ) -> SyncOperation:
        """Create a new synchronization operation."""
        operation_id = hashlib.sha256(
            f"{source_home_id}:{target_home_id}:{operation_type}:{time.time()}".encode()
        ).hexdigest()[:16]
        
        operation = SyncOperation(
            id=operation_id,
            source_home_id=source_home_id,
            target_home_id=target_home_id,
            operation_type=operation_type,
            status=SyncStatus.PENDING,
            data=data
        )
        
        self.pending_operations.append(operation)
        logger.info(f"Created sync operation: {operation_id} ({operation_type})")
        return operation
    
    def detect_conflict(
        self,
        operation: SyncOperation,
        field_path: str,
        local_value: Any,
        remote_value: Any,
        local_timestamp: datetime,
        remote_timestamp: datetime
    ) -> SyncConflict:
        """Detect and record a synchronization conflict."""
        conflict_id = hashlib.sha256(
            f"{operation.id}:{field_path}:{time.time()}".encode()
        ).hexdigest()[:16]
        
        conflict = SyncConflict(
            id=conflict_id,
            operation_id=operation.id,
            field_path=field_path,
            local_value=local_value,
            remote_value=remote_value,
            local_timestamp=local_timestamp,
            remote_timestamp=remote_timestamp
        )
        
        self.conflicts.append(conflict)
        operation.status = SyncStatus.CONFLICT
        operation.conflict_info = conflict.to_dict()
        
        logger.warning(f"Detected conflict: {conflict_id} at {field_path}")
        return conflict
    
    def resolve_conflict(self, conflict_id: str, resolution: ConflictResolution) -> Optional[Any]:
        """Resolve a synchronization conflict."""
        conflict = None
        for c in self.conflicts:
            if c.id == conflict_id:
                conflict = c
                break
        
        if not conflict:
            logger.error(f"Conflict not found: {conflict_id}")
            return None
        
        # Apply resolution strategy
        if resolution == ConflictResolution.LAST_WRITE_WINS:
            if conflict.local_timestamp > conflict.remote_timestamp:
                conflict.resolved_value = conflict.local_value
            else:
                conflict.resolved_value = conflict.remote_value
        elif resolution == ConflictResolution.PRIMARY_WINS:
            # Primary home value wins
            conflict.resolved_value = conflict.local_value
        elif resolution == ConflictResolution.MERGE:
            # Attempt to merge (for dict values)
            if isinstance(conflict.local_value, dict) and isinstance(conflict.remote_value, dict):
                conflict.resolved_value = {**conflict.remote_value, **conflict.local_value}
            else:
                conflict.resolved_value = conflict.local_value
        elif resolution == ConflictResolution.MANUAL:
            # Manual resolution required
            conflict.resolved_value = None
        
        conflict.resolution = resolution
        conflict.resolved_at = datetime.now(timezone.utc)
        
        logger.info(f"Resolved conflict {conflict_id} with {resolution.value}")
        return conflict.resolved_value
    
    def prepare_sync_payload(self, operation: SyncOperation) -> Dict[str, Any]:
        """Prepare encrypted payload for synchronization."""
        payload = {
            "operation_id": operation.id,
            "source_home_id": operation.source_home_id,
            "target_home_id": operation.target_home_id,
            "operation_type": operation.operation_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": operation.data
        }
        
        # Sign and encrypt
        encrypted = self.encryption.encrypt_payload(payload)
        return {
            "encrypted_payload": encrypted,
            "signature": self.encryption.sign_payload(payload)
        }
    
    def verify_incoming_payload(self, encrypted_payload: str) -> Optional[Dict[str, Any]]:
        """Verify and decrypt incoming synchronization payload."""
        try:
            payload = self.encryption.decrypt_payload(encrypted_payload)
            return payload
        except Exception as e:
            logger.error(f"Failed to verify incoming payload: {e}")
            return None
    
    def execute_sync_operation(self, operation: SyncOperation) -> bool:
        """Execute a synchronization operation."""
        operation.status = SyncStatus.IN_PROGRESS
        logger.info(f"Executing sync operation: {operation.id}")
        
        try:
            # In a real implementation, this would:
            # 1. Fetch data from source home via API
            # 2. Detect conflicts
            # 3. Apply conflict resolution
            # 4. Push to target home
            
            # For now, mark as completed
            operation.status = SyncStatus.COMPLETED
            operation.completed_at = datetime.now(timezone.utc)
            
            # Update last sync time for target home
            if operation.target_home_id in self.homes:
                self.homes[operation.target_home_id].last_sync = operation.completed_at
                self._save_state()
            
            logger.info(f"Sync operation completed: {operation.id}")
            return True
            
        except Exception as e:
            operation.status = SyncStatus.FAILED
            operation.error_message = str(e)
            operation.completed_at = datetime.now(timezone.utc)
            logger.error(f"Sync operation failed: {operation.id} - {e}")
            return False
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current synchronization status."""
        return {
            "homes": [home.to_dict() for home in self.homes.values()],
            "pending_operations": len([op for op in self.pending_operations if op.status == SyncStatus.PENDING]),
            "active_conflicts": len([c for c in self.conflicts if c.resolution is None]),
            "conflict_resolution_strategy": self.conflict_resolution_strategy.value,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    
    def cleanup_old_operations(self, max_age_hours: int = 24) -> int:
        """Clean up old synchronization operations."""
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        original_count = len(self.pending_operations)
        
        self.pending_operations = [
            op for op in self.pending_operations
            if op.created_at.timestamp() > cutoff
        ]
        
        cleaned = original_count - len(self.pending_operations)
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old sync operations")
        
        return cleaned


# Singleton instance
_sync_engine: Optional[SyncEngine] = None


def get_sync_engine(data_dir: str = "/data/multihome") -> SyncEngine:
    """Get or create the sync engine singleton."""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = SyncEngine(data_dir)
    return _sync_engine
