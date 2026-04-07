"""Secret Manager Advanced Engine — Slice 62.

Advanced secret management for PilotSuite Core.

Features:
- Encrypted secret storage
- Secret rotation
- Access auditing
- Expiration tracking
- Secret versioning
- Multi-backend support
- Secret sharing/leasing
"""
from __future__ import annotations

import logging
import hashlib
import threading
import base64
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable, Set
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class SecretType(Enum):
    """Secret types."""
    PASSWORD = "password"
    API_KEY = "api_key"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"
    CONNECTION_STRING = "connection_string"
    ENCRYPTION_KEY = "encryption_key"
    GENERIC = "generic"


class SecretStatus(Enum):
    """Secret status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING_ROTATION = "pending_rotation"
    SUSPENDED = "suspended"


@dataclass
class SecretVersion:
    """Secret version record."""
    version_id: str
    secret_id: str
    value_hash: str  # Hash of value, not the value itself
    created_at: str
    created_by: str
    is_current: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "secret_id": self.secret_id,
            "value_hash": self.value_hash,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "is_current": self.is_current,
        }


@dataclass
class Secret:
    """Secret definition."""
    secret_id: str
    name: str
    secret_type: SecretType
    encrypted_value: str
    status: SecretStatus = SecretStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    rotated_at: Optional[str] = None
    rotation_interval_days: Optional[int] = None
    access_count: int = 0
    last_accessed: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    current_version: int = 1
    
    def to_dict(self, include_value: bool = False) -> Dict[str, Any]:
        result = {
            "secret_id": self.secret_id,
            "name": self.name,
            "secret_type": self.secret_type.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "rotated_at": self.rotated_at,
            "expires_at": self.expires_at,
            "rotation_interval_days": self.rotation_interval_days,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "metadata": self.metadata,
            "tags": list(self.tags),
            "current_version": self.current_version,
        }
        
        if include_value:
            result["encrypted_value"] = self.encrypted_value
        
        return result
    
    def is_expired(self) -> bool:
        """Check if secret is expired."""
        if not self.expires_at:
            return False
        
        expiry = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
        return datetime.now(timezone.utc) > expiry
    
    def needs_rotation(self) -> bool:
        """Check if secret needs rotation."""
        if not self.rotation_interval_days:
            return False
        
        if not self.rotated_at:
            rotated = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
        else:
            rotated = datetime.fromisoformat(self.rotated_at.replace('Z', '+00:00'))
        
        next_rotation = rotated + timedelta(days=self.rotation_interval_days)
        return datetime.now(timezone.utc) > next_rotation


@dataclass
class AccessAudit:
    """Secret access audit record."""
    audit_id: str
    secret_id: str
    accessor: str
    action: str  # read, write, delete, rotate
    timestamp: str
    success: bool
    reason: Optional[str] = None
    ip_address: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "secret_id": self.secret_id,
            "accessor": self.accessor,
            "action": self.action,
            "timestamp": self.timestamp,
            "success": self.success,
            "reason": self.reason,
            "ip_address": self.ip_address,
        }


class SecretManagerEngine:
    """Advanced secret management engine."""
    
    def __init__(self, encryption_key: Optional[bytes] = None):
        self._secrets: Dict[str, Secret] = {}
        self._versions: Dict[str, List[SecretVersion]] = {}
        self._audit_log: List[AccessAudit] = []
        self._access_policies: Dict[str, Set[str]] = {}  # secret_id -> allowed accessors
        self._lock = threading.Lock()
        
        # Use provided key or generate one
        self._encryption_key = encryption_key or os.urandom(32)
        
        # Statistics
        self._stats = {
            "total_accesses": 0,
            "successful_accesses": 0,
            "failed_accesses": 0,
            "total_rotations": 0,
            "total_expirations": 0,
            "by_secret": {},
        }
    
    def _encrypt(self, value: str) -> str:
        """Simple XOR encryption (for demo - use proper crypto in production)."""
        # In production, use proper encryption (AES-GCM, etc.)
        key_bytes = self._encryption_key
        value_bytes = value.encode('utf-8')
        
        encrypted = bytes(a ^ b for a, b in zip(value_bytes, (key_bytes * ((len(value_bytes) // len(key_bytes)) + 1))[:len(value_bytes)]))
        
        return base64.b64encode(encrypted).decode('utf-8')
    
    def _decrypt(self, encrypted_value: str) -> str:
        """Simple XOR decryption (for demo - use proper crypto in production)."""
        encrypted_bytes = base64.b64decode(encrypted_value.encode('utf-8'))
        key_bytes = self._encryption_key
        
        decrypted = bytes(a ^ b for a, b in zip(encrypted_bytes, (key_bytes * ((len(encrypted_bytes) // len(key_bytes)) + 1))[:len(encrypted_bytes)]))
        
        return decrypted.decode('utf-8')
    
    def _hash_value(self, value: str) -> str:
        """Hash secret value for version tracking."""
        return hashlib.sha256(value.encode('utf-8')).hexdigest()
    
    def create_secret(self, name: str, value: str,
                     secret_type: SecretType = SecretType.GENERIC,
                     expires_at: Optional[str] = None,
                     rotation_interval_days: Optional[int] = None,
                     metadata: Optional[Dict[str, Any]] = None,
                     tags: Optional[Set[str]] = None,
                     created_by: str = "system",
                     created_at: Optional[str] = None) -> str:
        """Create a new secret."""
        secret_id = f"sec_{uuid.uuid4().hex[:16]}"
        
        encrypted = self._encrypt(value)
        value_hash = self._hash_value(value)
        
        now = created_at or datetime.now(timezone.utc).isoformat()
        
        secret = Secret(
            secret_id=secret_id,
            name=name,
            secret_type=secret_type,
            encrypted_value=encrypted,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            rotation_interval_days=rotation_interval_days,
            metadata=metadata or {},
            tags=tags or set(),
        )
        
        version = SecretVersion(
            version_id=f"v1_{uuid.uuid4().hex[:8]}",
            secret_id=secret_id,
            value_hash=value_hash,
            created_at=now,
            created_by=created_by,
            is_current=True,
        )
        
        with self._lock:
            self._secrets[secret_id] = secret
            self._versions[secret_id] = [version]
        
        self._audit("create", secret_id, created_by, True)
        
        logger.info("Secret created: %s (%s)", name, secret_id)
        
        return secret_id
    
    def get_secret(self, secret_id: str, accessor: str = "system",
                  ip_address: Optional[str] = None) -> Optional[str]:
        """Get secret value (decrypted)."""
        with self._lock:
            secret = self._secrets.get(secret_id)
            
            if not secret:
                self._audit("read", secret_id, accessor, False, "not_found", ip_address)
                self._stats["failed_accesses"] += 1
                return None
            
            # Check access policy
            if not self._check_access(secret_id, accessor):
                self._audit("read", secret_id, accessor, False, "access_denied", ip_address)
                self._stats["failed_accesses"] += 1
                return None
            
            # Check status
            if secret.status != SecretStatus.ACTIVE:
                self._audit("read", secret_id, accessor, False, f"status_{secret.status.value}", ip_address)
                self._stats["failed_accesses"] += 1
                return None
            
            # Check expiration
            if secret.is_expired():
                secret.status = SecretStatus.EXPIRED
                self._stats["total_expirations"] += 1
                self._audit("read", secret_id, accessor, False, "expired", ip_address)
                self._stats["failed_accesses"] += 1
                return None
            
            # Decrypt and return
            value = self._decrypt(secret.encrypted_value)
            
            # Update access tracking
            secret.access_count += 1
            secret.last_accessed = datetime.now(timezone.utc).isoformat()
            
            self._stats["total_accesses"] += 1
            self._stats["successful_accesses"] += 1
            self._stats["by_secret"][secret_id] = self._stats["by_secret"].get(secret_id, 0) + 1
        
        self._audit("read", secret_id, accessor, True, ip_address=ip_address)
        
        return value
    
    def update_secret(self, secret_id: str, value: str,
                     updated_by: str = "system") -> bool:
        """Update secret value (creates new version)."""
        with self._lock:
            secret = self._secrets.get(secret_id)
            
            if not secret:
                self._audit("write", secret_id, updated_by, False, "not_found")
                return False
            
            encrypted = self._encrypt(value)
            value_hash = self._hash_value(value)
            now = datetime.now(timezone.utc).isoformat()
            
            # Update secret
            secret.encrypted_value = encrypted
            secret.updated_at = now
            secret.current_version += 1
            
            # Create new version
            version = SecretVersion(
                version_id=f"v{secret.current_version}_{uuid.uuid4().hex[:8]}",
                secret_id=secret_id,
                value_hash=value_hash,
                created_at=now,
                created_by=updated_by,
                is_current=True,
            )
            
            # Mark previous versions as not current
            for v in self._versions[secret_id]:
                v.is_current = False
            
            self._versions[secret_id].append(version)
        
        self._audit("write", secret_id, updated_by, True)
        
        logger.info("Secret updated: %s", secret_id)
        
        return True
    
    def delete_secret(self, secret_id: str, deleted_by: str = "system") -> bool:
        """Delete a secret."""
        with self._lock:
            if secret_id not in self._secrets:
                self._audit("delete", secret_id, deleted_by, False, "not_found")
                return False
            
            del self._secrets[secret_id]
            
            if secret_id in self._versions:
                del self._versions[secret_id]
            
            if secret_id in self._access_policies:
                del self._access_policies[secret_id]
        
        self._audit("delete", secret_id, deleted_by, True)
        
        logger.info("Secret deleted: %s", secret_id)
        
        return True
    
    def rotate_secret(self, secret_id: str, new_value: str,
                     rotated_by: str = "system") -> bool:
        """Rotate secret with new value."""
        with self._lock:
            secret = self._secrets.get(secret_id)
            
            if not secret:
                self._audit("rotate", secret_id, rotated_by, False, "not_found")
                return False
            
            encrypted = self._encrypt(new_value)
            value_hash = self._hash_value(new_value)
            now = datetime.now(timezone.utc).isoformat()
            
            # Update secret
            secret.encrypted_value = encrypted
            secret.rotated_at = now
            secret.updated_at = now
            secret.current_version += 1
            
            # Create new version
            version = SecretVersion(
                version_id=f"v{secret.current_version}_{uuid.uuid4().hex[:8]}",
                secret_id=secret_id,
                value_hash=value_hash,
                created_at=now,
                created_by=rotated_by,
                is_current=True,
            )
            
            # Mark previous versions as not current
            for v in self._versions[secret_id]:
                v.is_current = False
            
            self._versions[secret_id].append(version)
            
            self._stats["total_rotations"] += 1
        
        self._audit("rotate", secret_id, rotated_by, True)
        
        logger.info("Secret rotated: %s", secret_id)
        
        return True
    
    def revoke_secret(self, secret_id: str, revoked_by: str = "system") -> bool:
        """Revoke a secret (mark as revoked)."""
        with self._lock:
            secret = self._secrets.get(secret_id)
            
            if not secret:
                return False
            
            secret.status = SecretStatus.REVOKED
            secret.updated_at = datetime.now(timezone.utc).isoformat()
        
        self._audit("revoke", secret_id, revoked_by, True)
        
        logger.info("Secret revoked: %s", secret_id)
        
        return True
    
    def suspend_secret(self, secret_id: str, suspended_by: str = "system") -> bool:
        """Suspend a secret (temporary disable)."""
        with self._lock:
            secret = self._secrets.get(secret_id)
            
            if not secret:
                return False
            
            secret.status = SecretStatus.SUSPENDED
            secret.updated_at = datetime.now(timezone.utc).isoformat()
        
        self._audit("suspend", secret_id, suspended_by, True)
        
        return True
    
    def activate_secret(self, secret_id: str, activated_by: str = "system") -> bool:
        """Activate a suspended secret."""
        with self._lock:
            secret = self._secrets.get(secret_id)
            
            if not secret:
                return False
            
            secret.status = SecretStatus.ACTIVE
            secret.updated_at = datetime.now(timezone.utc).isoformat()
        
        self._audit("activate", secret_id, activated_by, True)
        
        return True
    
    def set_access_policy(self, secret_id: str, allowed_accessors: Set[str]) -> bool:
        """Set access policy for a secret."""
        with self._lock:
            if secret_id not in self._secrets:
                return False
            
            self._access_policies[secret_id] = allowed_accessors.copy()
        
        return True
    
    def add_accessor(self, secret_id: str, accessor: str) -> bool:
        """Add accessor to secret policy."""
        with self._lock:
            if secret_id not in self._secrets:
                return False
            
            if secret_id not in self._access_policies:
                self._access_policies[secret_id] = set()
            
            self._access_policies[secret_id].add(accessor)
        
        return True
    
    def remove_accessor(self, secret_id: str, accessor: str) -> bool:
        """Remove accessor from secret policy."""
        with self._lock:
            if secret_id not in self._access_policies:
                return False
            
            self._access_policies[secret_id].discard(accessor)
        
        return True
    
    def _check_access(self, secret_id: str, accessor: str) -> bool:
        """Check if accessor has access to secret."""
        if secret_id not in self._access_policies:
            return True  # No policy = allow all
        
        return accessor in self._access_policies[secret_id]
    
    def get_secret_info(self, secret_id: str) -> Optional[Dict[str, Any]]:
        """Get secret metadata (without value)."""
        with self._lock:
            secret = self._secrets.get(secret_id)
            
            if not secret:
                return None
            
            return secret.to_dict(include_value=False)
    
    def list_secrets(self, status: Optional[SecretStatus] = None,
                    secret_type: Optional[SecretType] = None,
                    tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """List secrets with filters."""
        with self._lock:
            secrets = list(self._secrets.values())
            
            if status:
                secrets = [s for s in secrets if s.status == status]
            
            if secret_type:
                secrets = [s for s in secrets if s.secret_type == secret_type]
            
            if tag:
                secrets = [s for s in secrets if tag in s.tags]
            
            return [s.to_dict(include_value=False) for s in secrets]
    
    def get_versions(self, secret_id: str) -> List[Dict[str, Any]]:
        """Get version history for a secret."""
        with self._lock:
            versions = self._versions.get(secret_id, [])
            return [v.to_dict() for v in versions]
    
    def get_audit_log(self, secret_id: Optional[str] = None,
                     accessor: Optional[str] = None,
                     limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit log with filters."""
        with self._lock:
            logs = self._audit_log
            
            if secret_id:
                logs = [l for l in logs if l.secret_id == secret_id]
            
            if accessor:
                logs = [l for l in logs if l.accessor == accessor]
            
            # Return most recent first
            logs = sorted(logs, key=lambda l: l.timestamp, reverse=True)
            
            return [l.to_dict() for l in logs[:limit]]
    
    def _audit(self, action: str, secret_id: str, accessor: str,
              success: bool, reason: Optional[str] = None,
              ip_address: Optional[str] = None) -> None:
        """Record audit entry."""
        audit = AccessAudit(
            audit_id=f"aud_{uuid.uuid4().hex[:16]}",
            secret_id=secret_id,
            accessor=accessor,
            action=action,
            timestamp=datetime.now(timezone.utc).isoformat(),
            success=success,
            reason=reason,
            ip_address=ip_address,
        )
        
        self._audit_log.append(audit)
        
        # Limit audit log size
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-1000:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get secret manager statistics."""
        with self._lock:
            secrets = list(self._secrets.values())
            
            return {
                **self._stats,
                "total_secrets": len(secrets),
                "active_secrets": len([s for s in secrets if s.status == SecretStatus.ACTIVE]),
                "expired_secrets": len([s for s in secrets if s.is_expired()]),
                "revoked_secrets": len([s for s in secrets if s.status == SecretStatus.REVOKED]),
                "needs_rotation": len([s for s in secrets if s.needs_rotation()]),
                "total_audit_entries": len(self._audit_log),
            }
    
    def clear_audit_log(self) -> int:
        """Clear audit log."""
        with self._lock:
            count = len(self._audit_log)
            self._audit_log.clear()
            return count
    
    def get_expiring_secrets(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get secrets expiring within specified days."""
        with self._lock:
            cutoff = datetime.now(timezone.utc) + timedelta(days=days)
            expiring = []
            
            for secret in self._secrets.values():
                if secret.expires_at:
                    expiry = datetime.fromisoformat(secret.expires_at.replace('Z', '+00:00'))
                    if expiry <= cutoff:
                        expiring.append(secret.to_dict(include_value=False))
            
            return expiring
    
    def get_rotation_candidates(self) -> List[Dict[str, Any]]:
        """Get secrets that need rotation."""
        with self._lock:
            candidates = []
            
            for secret in self._secrets.values():
                if secret.needs_rotation():
                    candidates.append(secret.to_dict(include_value=False))
            
            return candidates


def create_secret_manager_engine(encryption_key: Optional[bytes] = None) -> SecretManagerEngine:
    """Factory function to create secret manager engine."""
    return SecretManagerEngine(encryption_key)
