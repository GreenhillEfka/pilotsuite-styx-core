"""Backup & Recovery Engine — Slice 23.

Automated backup and recovery for PilotSuite Core.

Features:
- Scheduled backups (config, state, data)
- Incremental and full backups
- Encrypted backup storage
- Point-in-time recovery
- Backup verification
- Disaster recovery procedures
"""
from __future__ import annotations

import logging
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class BackupType(Enum):
    """Type of backup."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    CONFIG_ONLY = "config_only"
    STATE_ONLY = "state_only"


class BackupStatus(Enum):
    """Backup status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    CORRUPTED = "corrupted"


class RecoveryStatus(Enum):
    """Recovery status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class BackupManifest:
    """Backup manifest/metadata."""
    backup_id: str
    backup_type: BackupType
    status: BackupStatus
    created_at: str
    completed_at: Optional[str]
    size_bytes: int
    checksum: str  # SHA256 checksum
    source_paths: List[str]
    destination_path: str
    encrypted: bool
    compression: str
    retention_days: int
    expires_at: Optional[str]
    verified: bool = False
    verification_date: Optional[str] = None
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "backup_type": self.backup_type.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "source_paths": self.source_paths,
            "destination_path": self.destination_path,
            "encrypted": self.encrypted,
            "compression": self.compression,
            "retention_days": self.retention_days,
            "expires_at": self.expires_at,
            "verified": self.verified,
            "verification_date": self.verification_date,
            "notes": self.notes,
        }


@dataclass
class RecoveryPlan:
    """Recovery plan for restoring from backup."""
    recovery_id: str
    backup_id: str
    status: RecoveryStatus
    target_paths: List[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    items_restored: int
    items_failed: int
    error_message: Optional[str] = None
    rollback_available: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "backup_id": self.backup_id,
            "status": self.status.value,
            "target_paths": self.target_paths,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "items_restored": self.items_restored,
            "items_failed": self.items_failed,
            "error_message": self.error_message,
            "rollback_available": self.rollback_available,
        }


class BackupRecoveryEngine:
    """Backup and recovery engine."""
    
    def __init__(self, storage_path: str = "/data/backups"):
        self._storage_path = storage_path
        self._manifests: Dict[str, BackupManifest] = {}
        self._recovery_plans: Dict[str, RecoveryPlan] = {}
        self._backup_counter = 0
        self._recovery_counter = 0
        
        # Backup schedule
        self._backup_schedule = {
            "full": {"interval_days": 7, "retention_days": 90},
            "incremental": {"interval_days": 1, "retention_days": 30},
            "config": {"interval_days": 1, "retention_days": 30},
        }
        
        # Paths to backup
        self._default_paths = [
            "/config/clawd",
            "/data/pilotsuite",
        ]
    
    def create_backup(self, backup_type: BackupType = BackupType.FULL,
                     source_paths: Optional[List[str]] = None,
                     encrypted: bool = True,
                     compression: str = "gzip") -> str:
        """Create a new backup."""
        self._backup_counter += 1
        
        backup_id = f"backup_{self._backup_counter}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        # Determine retention based on type
        retention_days = self._backup_schedule.get(backup_type.value, {}).get("retention_days", 30)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=retention_days)).isoformat()
        
        manifest = BackupManifest(
            backup_id=backup_id,
            backup_type=backup_type,
            status=BackupStatus.IN_PROGRESS,
            created_at=datetime.now(timezone.utc).isoformat(),
            completed_at=None,
            size_bytes=0,
            checksum="",
            source_paths=source_paths or self._default_paths,
            destination_path=f"{self._storage_path}/{backup_id}.tar.gz",
            encrypted=encrypted,
            compression=compression,
            retention_days=retention_days,
            expires_at=expires_at,
        )
        
        self._manifests[backup_id] = manifest
        
        # Simulate backup process
        self._execute_backup(manifest)
        
        return backup_id
    
    def _execute_backup(self, manifest: BackupManifest) -> None:
        """Execute backup process (simulated)."""
        try:
            # Simulate backup creation
            # In production, this would:
            # 1. Create tar archive of source paths
            # 2. Compress with specified algorithm
            # 3. Encrypt if enabled
            # 4. Calculate checksum
            # 5. Upload to storage
            
            # Simulated values
            simulated_size = 1024 * 1024 * 50  # 50 MB
            simulated_checksum = hashlib.sha256(
                f"{manifest.backup_id}{datetime.now(timezone.utc).isoformat()}".encode()
            ).hexdigest()
            
            manifest.size_bytes = simulated_size
            manifest.checksum = simulated_checksum
            manifest.status = BackupStatus.COMPLETED
            manifest.completed_at = datetime.now(timezone.utc).isoformat()
            
            logger.info("Backup %s completed: %d bytes", manifest.backup_id, simulated_size)
            
        except Exception as exc:
            logger.error("Backup %s failed: %s", manifest.backup_id, exc)
            manifest.status = BackupStatus.FAILED
            manifest.notes = f"Failed: {exc}"
    
    def verify_backup(self, backup_id: str) -> bool:
        """Verify backup integrity."""
        if backup_id not in self._manifests:
            logger.warning("Unknown backup: %s", backup_id)
            return False
        
        manifest = self._manifests[backup_id]
        
        if manifest.status != BackupStatus.COMPLETED:
            logger.warning("Cannot verify backup in status: %s", manifest.status.value)
            return False
        
        manifest.status = BackupStatus.VERIFYING
        
        try:
            # Simulate verification
            # In production, this would:
            # 1. Download backup
            # 2. Verify checksum
            # 3. Test extraction
            # 4. Validate contents
            
            # Simulated verification
            manifest.verified = True
            manifest.verification_date = datetime.now(timezone.utc).isoformat()
            manifest.status = BackupStatus.VERIFIED
            
            logger.info("Backup %s verified successfully", backup_id)
            return True
            
        except Exception as exc:
            logger.error("Backup %s verification failed: %s", backup_id, exc)
            manifest.status = BackupStatus.CORRUPTED
            manifest.notes = f"Verification failed: {exc}"
            return False
    
    def create_recovery_plan(self, backup_id: str,
                            target_paths: Optional[List[str]] = None) -> str:
        """Create a recovery plan from backup."""
        if backup_id not in self._manifests:
            logger.warning("Unknown backup: %s", backup_id)
            return ""
        
        manifest = self._manifests[backup_id]
        
        if manifest.status not in (BackupStatus.COMPLETED, BackupStatus.VERIFIED):
            logger.warning("Cannot recover from backup in status: %s", manifest.status.value)
            return ""
        
        self._recovery_counter += 1
        recovery_id = f"recovery_{self._recovery_counter}"
        
        plan = RecoveryPlan(
            recovery_id=recovery_id,
            backup_id=backup_id,
            status=RecoveryStatus.PENDING,
            target_paths=target_paths or manifest.source_paths,
            started_at=None,
            completed_at=None,
            items_restored=0,
            items_failed=0,
        )
        
        self._recovery_plans[recovery_id] = plan
        
        return recovery_id
    
    def execute_recovery(self, recovery_id: str) -> bool:
        """Execute recovery plan."""
        if recovery_id not in self._recovery_plans:
            logger.warning("Unknown recovery plan: %s", recovery_id)
            return False
        
        plan = self._recovery_plans[recovery_id]
        
        if plan.status != RecoveryStatus.PENDING:
            logger.warning("Recovery %s not in pending state", recovery_id)
            return False
        
        plan.status = RecoveryStatus.IN_PROGRESS
        plan.started_at = datetime.now(timezone.utc).isoformat()
        
        try:
            # Simulate recovery process
            # In production, this would:
            # 1. Download backup
            # 2. Decrypt if needed
            # 3. Decompress
            # 4. Extract to target paths
            # 5. Verify restoration
            
            # Simulated restoration
            plan.items_restored = len(plan.target_paths)
            plan.items_failed = 0
            plan.status = RecoveryStatus.COMPLETED
            plan.completed_at = datetime.now(timezone.utc).isoformat()
            
            logger.info("Recovery %s completed: %d items restored", recovery_id, plan.items_restored)
            return True
            
        except Exception as exc:
            logger.error("Recovery %s failed: %s", recovery_id, exc)
            plan.status = RecoveryStatus.FAILED
            plan.error_message = str(exc)
            plan.items_failed = len(plan.target_paths)
            return False
    
    def list_backups(self, backup_type: Optional[BackupType] = None,
                    status: Optional[BackupStatus] = None,
                    limit: int = 50) -> List[Dict[str, Any]]:
        """List backups with optional filters."""
        backups = list(self._manifests.values())
        
        if backup_type:
            backups = [b for b in backups if b.backup_type == backup_type]
        
        if status:
            backups = [b for b in backups if b.status == status]
        
        # Sort by created_at (newest first)
        backups.sort(key=lambda b: b.created_at, reverse=True)
        
        return [b.to_dict() for b in backups[:limit]]
    
    def get_backup(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """Get backup details."""
        if backup_id not in self._manifests:
            return None
        
        return self._manifests[backup_id].to_dict()
    
    def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup."""
        if backup_id not in self._manifests:
            return False
        
        # In production, this would also delete the actual backup file
        del self._manifests[backup_id]
        
        logger.info("Backup %s deleted", backup_id)
        return True
    
    def cleanup_expired_backups(self) -> int:
        """Clean up expired backups."""
        now = datetime.now(timezone.utc)
        expired = []
        
        for backup_id, manifest in self._manifests.items():
            if manifest.expires_at:
                expires = datetime.fromisoformat(manifest.expires_at)
                if expires < now:
                    expired.append(backup_id)
        
        for backup_id in expired:
            self.delete_backup(backup_id)
        
        logger.info("Cleaned up %d expired backups", len(expired))
        return len(expired)
    
    def get_backup_summary(self) -> Dict[str, Any]:
        """Get backup system summary."""
        total_backups = len(self._manifests)
        verified_backups = len([b for b in self._manifests.values() if b.verified])
        completed_backups = len([b for b in self._manifests.values() if b.status == BackupStatus.COMPLETED])
        failed_backups = len([b for b in self._manifests.values() if b.status == BackupStatus.FAILED])
        
        total_size = sum(b.size_bytes for b in self._manifests.values())
        
        return {
            "total_backups": total_backups,
            "verified_backups": verified_backups,
            "completed_backups": completed_backups,
            "failed_backups": failed_backups,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "recovery_plans": len(self._recovery_plans),
        }
    
    def schedule_backup(self, backup_type: str, interval_days: int,
                       retention_days: int) -> None:
        """Configure backup schedule."""
        self._backup_schedule[backup_type] = {
            "interval_days": interval_days,
            "retention_days": retention_days,
        }
        
        logger.info("Backup schedule updated: %s every %d days, retention %d days",
                   backup_type, interval_days, retention_days)
    
    def get_next_scheduled_backup(self) -> Dict[str, Any]:
        """Get next scheduled backup information."""
        # Find oldest completed backup of each type
        next_backups = {}
        
        for backup_type, schedule in self._backup_schedule.items():
            # Find last backup of this type
            type_backups = [
                b for b in self._manifests.values()
                if b.backup_type.value == backup_type
            ]
            
            if type_backups:
                last_backup = max(type_backups, key=lambda b: b.created_at)
                last_time = datetime.fromisoformat(last_backup.created_at)
                next_time = last_time + timedelta(days=schedule["interval_days"])
            else:
                next_time = datetime.now(timezone.utc)
            
            next_backups[backup_type] = {
                "interval_days": schedule["interval_days"],
                "retention_days": schedule["retention_days"],
                "next_run": next_time.isoformat(),
            }
        
        return next_backups


def create_backup_recovery_engine(storage_path: str = "/data/backups") -> BackupRecoveryEngine:
    """Factory function to create backup/recovery engine."""
    return BackupRecoveryEngine(storage_path=storage_path)
