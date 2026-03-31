"""Secret Manager Engine — Slice 41.

Secure secret management for PilotSuite Core.

Features:
- Encrypted secret storage
- Secret rotation
- Access control and audit
- Secret versioning
- Expiration tracking
- Integration hooks (Vault, AWS Secrets, etc.)
"""
from __future__ import annotations

import logging
import hashlib
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class SecretType(Enum):
    """Secret type."""
    PASSWORD = "password"
    API_KEY = "api_key"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"
    CONNECTION_STRING = "connection_string"
    GENERIC = "generic"


class SecretStatus(Enum):
    """Secret status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING_ROTATION = "pending_rotation"


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
    description: str
    secret_type: SecretType
    status: SecretStatus = SecretStatus.ACTIVE
    value: str = ""  # Encrypted value
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    expires_at: Optional[str] = None
    rotation_days: int = 0  # 0 = no rotation
    last_accessed: Optional[str] = None
    access_count: int = 0
    versions: List[SecretVersion] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = ""
    
    def to_dict(self, include_value: bool = False) -> Dict[str, Any]:
        data = {
            "secret_id": self.secret_id,
            "name": self.name,
            "description": self.description,
            "secret_type": self.secret_type.value,
            "status": self.status.value,
            "metadata": self.metadata,
            "tags": self.tags,
            "expires_at": self.expires_at,
            "rotation_days": self.rotation_days,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "version_count": len(self.versions),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
        }
        
        if include_value:
            data["value"] = self.value
        
        return data


@dataclass
class SecretAccessLog:
    """Secret access audit log."""
    log_id: str
    secret_id: str
    action: str  # read, write, rotate, revoke
    accessed_by: str
    accessed_at: str
    success: bool
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_id": self.log_id,
            "secret_id": self.secret_id,
            "action": self.action,
            "accessed_by": self.accessed_by,
            "accessed_at": self.accessed_at,
            "success": self.success,
            "reason": self.reason,
        }


class SecretManagerEngine:
    """Secret management engine."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        self._secrets: Dict[str, Secret] = {}
        self._access_log: List[SecretAccessLog] = []
        self._max_log_size = 10000
        
        # Encryption (simplified - in production use proper encryption)
        self._encryption_key = encryption_key or "default_key"
        
        # Access control
        self._access_policies: Dict[str, List[str]] = {}  # secret_id -> [allowed_users]
        
        # Callbacks for rotation
        self._rotation_callbacks: Dict[str, Callable] = {}
        
        # Statistics
        self._stats = {
            "total_secrets": 0,
            "total_accesses": 0,
            "failed_accesses": 0,
            "rotations": 0,
        }
    
    def _encrypt(self, value: str) -> str:
        """Encrypt a value (simplified)."""
        # In production: use proper encryption (AES, etc.)
        combined = f"{self._encryption_key}:{value}"
        return base64.b64encode(combined.encode()).decode()
    
    def _decrypt(self, encrypted_value: str) -> str:
        """Decrypt a value (simplified)."""
        try:
            decoded = base64.b64decode(encrypted_value.encode()).decode()
            # Remove key prefix
            parts = decoded.split(":", 1)
            if len(parts) == 2:
                return parts[1]
            return decoded
        except Exception:
            raise ValueError("Failed to decrypt value")
    
    def _hash_value(self, value: str) -> str:
        """Hash a value for version tracking."""
        return hashlib.sha256(value.encode()).hexdigest()
    
    def create_secret(self, name: str, value: str,
                     description: str = "",
                     secret_type: str = "generic",
                     expires_at: Optional[str] = None,
                     rotation_days: int = 0,
                     tags: Optional[List[str]] = None,
                     metadata: Optional[Dict[str, Any]] = None,
                     created_by: str = "system") -> str:
        """Create a new secret."""
        secret_id = f"secret_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        
        secret = Secret(
            secret_id=secret_id,
            name=name,
            description=description,
            secret_type=SecretType(secret_type),
            value=self._encrypt(value),
            expires_at=expires_at,
            rotation_days=rotation_days,
            tags=tags or [],
            metadata=metadata or {},
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        
        # Create initial version
        version = SecretVersion(
            version_id=f"v1_{uuid.uuid4().hex[:8]}",
            secret_id=secret_id,
            value_hash=self._hash_value(value),
            created_at=now,
            created_by=created_by,
            is_current=True,
        )
        secret.versions.append(version)
        
        self._secrets[secret_id] = secret
        self._stats["total_secrets"] += 1
        
        # Log creation
        self._log_access(secret_id, "write", created_by, True, "Secret created")
        
        logger.info("Secret created: %s (%s)", name, secret_id)
        
        return secret_id
    
    def get_secret(self, secret_id: str, accessed_by: str = "system") -> Optional[Dict[str, Any]]:
        """Get secret metadata (without value)."""
        if secret_id not in self._secrets:
            self._log_access(secret_id, "read", accessed_by, False, "Secret not found")
            return None
        
        secret = self._secrets[secret_id]
        
        # Check access policy
        if not self._check_access(secret_id, accessed_by):
            self._log_access(secret_id, "read", accessed_by, False, "Access denied")
            return None
        
        # Check status
        if secret.status != SecretStatus.ACTIVE:
            self._log_access(secret_id, "read", accessed_by, False, f"Secret is {secret.status.value}")
            return None
        
        # Check expiration
        if secret.expires_at:
            expires = datetime.fromisoformat(secret.expires_at)
            if datetime.now(timezone.utc) > expires:
                secret.status = SecretStatus.EXPIRED
                self._log_access(secret_id, "read", accessed_by, False, "Secret expired")
                return None
        
        # Update access tracking
        secret.last_accessed = datetime.now(timezone.utc).isoformat()
        secret.access_count += 1
        self._stats["total_accesses"] += 1
        
        self._log_access(secret_id, "read", accessed_by, True, "Secret accessed")
        
        return secret.to_dict(include_value=False)
    
    def get_secret_value(self, secret_id: str, accessed_by: str = "system") -> Optional[str]:
        """Get secret value (decrypted)."""
        if secret_id not in self._secrets:
            self._log_access(secret_id, "read", accessed_by, False, "Secret not found")
            return None
        
        secret = self._secrets[secret_id]
        
        # Check access policy
        if not self._check_access(secret_id, accessed_by):
            self._log_access(secret_id, "read", accessed_by, False, "Access denied")
            return None
        
        # Check status
        if secret.status != SecretStatus.ACTIVE:
            self._log_access(secret_id, "read", accessed_by, False, f"Secret is {secret.status.value}")
            return None
        
        # Check expiration
        if secret.expires_at:
            expires = datetime.fromisoformat(secret.expires_at)
            if datetime.now(timezone.utc) > expires:
                secret.status = SecretStatus.EXPIRED
                self._log_access(secret_id, "read", accessed_by, False, "Secret expired")
                return None
        
        # Update access tracking
        secret.last_accessed = datetime.now(timezone.utc).isoformat()
        secret.access_count += 1
        self._stats["total_accesses"] += 1
        
        self._log_access(secret_id, "read", accessed_by, True, "Secret value accessed")
        
        return self._decrypt(secret.value)
    
    def update_secret(self, secret_id: str, value: str,
                     updated_by: str = "system") -> bool:
        """Update secret value (creates new version)."""
        if secret_id not in self._secrets:
            self._log_access(secret_id, "write", updated_by, False, "Secret not found")
            return False
        
        secret = self._secrets[secret_id]
        
        # Check access policy
        if not self._check_access(secret_id, updated_by):
            self._log_access(secret_id, "write", updated_by, False, "Access denied")
            return False
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Mark old versions as not current
        for version in secret.versions:
            version.is_current = False
        
        # Create new version
        version = SecretVersion(
            version_id=f"v{len(secret.versions) + 1}_{uuid.uuid4().hex[:8]}",
            secret_id=secret_id,
            value_hash=self._hash_value(value),
            created_at=now,
            created_by=updated_by,
            is_current=True,
        )
        secret.versions.append(version)
        
        # Update value
        secret.value = self._encrypt(value)
        secret.updated_at = now
        
        self._log_access(secret_id, "write", updated_by, True, "Secret updated")
        
        logger.info("Secret updated: %s", secret_id)
        
        return True
    
    def rotate_secret(self, secret_id: str, new_value: str,
                     rotated_by: str = "system") -> bool:
        """Rotate secret (update with new value)."""
        if secret_id not in self._secrets:
            return False
        
        secret = self._secrets[secret_id]
        
        # Check access policy
        if not self._check_access(secret_id, rotated_by):
            self._log_access(secret_id, "rotate", rotated_by, False, "Access denied")
            return False
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Mark old versions as not current
        for version in secret.versions:
            version.is_current = False
        
        # Create new version
        version = SecretVersion(
            version_id=f"v{len(secret.versions) + 1}_{uuid.uuid4().hex[:8]}",
            secret_id=secret_id,
            value_hash=self._hash_value(new_value),
            created_at=now,
            created_by=rotated_by,
            is_current=True,
        )
        secret.versions.append(version)
        
        # Update value
        secret.value = self._encrypt(new_value)
        secret.updated_at = now
        
        # Reset rotation timer
        if secret.rotation_days > 0:
            secret.expires_at = (datetime.now(timezone.utc) + timedelta(days=secret.rotation_days)).isoformat()
        
        self._stats["rotations"] += 1
        self._log_access(secret_id, "rotate", rotated_by, True, "Secret rotated")
        
        logger.info("Secret rotated: %s", secret_id)
        
        return True
    
    def revoke_secret(self, secret_id: str, revoked_by: str = "system",
                     reason: str = "") -> bool:
        """Revoke a secret."""
        if secret_id not in self._secrets:
            return False
        
        secret = self._secrets[secret_id]
        old_status = secret.status
        
        secret.status = SecretStatus.REVOKED
        secret.updated_at = datetime.now(timezone.utc).isoformat()
        secret.metadata["revocation_reason"] = reason
        
        self._log_access(secret_id, "revoke", revoked_by, True, f"Revoked: {reason}")
        
        logger.info("Secret revoked: %s - %s", secret_id, reason)
        
        return True
    
    def delete_secret(self, secret_id: str, deleted_by: str = "system") -> bool:
        """Delete a secret permanently."""
        if secret_id not in self._secrets:
            return False
        
        secret = self._secrets[secret_id]
        
        # Check access policy
        if not self._check_access(secret_id, deleted_by):
            self._log_access(secret_id, "write", deleted_by, False, "Access denied")
            return False
        
        del self._secrets[secret_id]
        self._stats["total_secrets"] -= 1
        
        # Clean up access policies
        if secret_id in self._access_policies:
            del self._access_policies[secret_id]
        
        self._log_access(secret_id, "delete", deleted_by, True, "Secret deleted")
        
        logger.info("Secret deleted: %s", secret_id)
        
        return True
    
    def set_access_policy(self, secret_id: str,
                         allowed_users: List[str]) -> bool:
        """Set access policy for a secret."""
        if secret_id not in self._secrets:
            return False
        
        self._access_policies[secret_id] = allowed_users
        
        logger.info("Access policy set for %s: %s", secret_id, allowed_users)
        
        return True
    
    def _check_access(self, secret_id: str, user: str) -> bool:
        """Check if user has access to secret."""
        if secret_id not in self._access_policies:
            return True  # No policy = allow all
        
        return user in self._access_policies[secret_id]
    
    def _log_access(self, secret_id: str, action: str,
                   accessed_by: str, success: bool,
                   reason: str = "") -> None:
        """Log secret access."""
        log = SecretAccessLog(
            log_id=f"log_{uuid.uuid4().hex[:8]}",
            secret_id=secret_id,
            action=action,
            accessed_by=accessed_by,
            accessed_at=datetime.now(timezone.utc).isoformat(),
            success=success,
            reason=reason,
        )
        
        self._access_log.append(log)
        
        if not success:
            self._stats["failed_accesses"] += 1
        
        # Trim log
        if len(self._access_log) > self._max_log_size:
            self._access_log = self._access_log[-self._max_log_size:]
    
    def register_rotation_callback(self, secret_id: str,
                                  callback: Callable[[str], str]) -> bool:
        """Register callback for automatic rotation."""
        if secret_id not in self._secrets:
            return False
        
        self._rotation_callbacks[secret_id] = callback
        return True
    
    def get_secrets_requiring_rotation(self) -> List[Dict[str, Any]]:
        """Get secrets that need rotation."""
        now = datetime.now(timezone.utc)
        needs_rotation = []
        
        for secret in self._secrets.values():
            if secret.status != SecretStatus.ACTIVE:
                continue
            
            if secret.rotation_days <= 0:
                continue
            
            if secret.expires_at:
                expires = datetime.fromisoformat(secret.expires_at)
                if expires <= now:
                    needs_rotation.append(secret.to_dict())
        
        return needs_rotation
    
    def auto_rotate_secrets(self, rotated_by: str = "system") -> int:
        """Automatically rotate secrets using registered callbacks."""
        rotated_count = 0
        
        for secret_id, callback in self._rotation_callbacks.items():
            if secret_id not in self._secrets:
                continue
            
            secret = self._secrets[secret_id]
            if secret.status != SecretStatus.ACTIVE:
                continue
            
            if secret.expires_at:
                expires = datetime.fromisoformat(secret.expires_at)
                if expires <= datetime.now(timezone.utc):
                    try:
                        new_value = callback(secret_id)
                        self.rotate_secret(secret_id, new_value, rotated_by)
                        rotated_count += 1
                    except Exception as exc:
                        logger.exception("Auto-rotation failed for %s: %s", secret_id, exc)
        
        return rotated_count
    
    def get_access_log(self, secret_id: Optional[str] = None,
                      action: Optional[str] = None,
                      limit: int = 100) -> List[Dict[str, Any]]:
        """Get access log."""
        logs = self._access_log
        
        if secret_id:
            logs = [l for l in logs if l.secret_id == secret_id]
        
        if action:
            logs = [l for l in logs if l.action == action]
        
        # Sort by accessed_at (newest first)
        logs.sort(key=lambda l: l.accessed_at, reverse=True)
        
        return [l.to_dict() for l in logs[:limit]]
    
    def get_secret_versions(self, secret_id: str) -> List[Dict[str, Any]]:
        """Get all versions of a secret."""
        if secret_id not in self._secrets:
            return []
        
        secret = self._secrets[secret_id]
        return [v.to_dict() for v in secret.versions]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get secret manager statistics."""
        by_status = {}
        for secret in self._secrets.values():
            status = secret.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        by_type = {}
        for secret in self._secrets.values():
            stype = secret.secret_type.value
            by_type[stype] = by_type.get(stype, 0) + 1
        
        expiring_soon = len([
            s for s in self._secrets.values()
            if s.expires_at and datetime.fromisoformat(s.expires_at) <= datetime.now(timezone.utc) + timedelta(days=7)
        ])
        
        return {
            **self._stats,
            "by_status": by_status,
            "by_type": by_type,
            "expiring_soon": expiring_soon,
            "access_log_size": len(self._access_log),
        }
    
    def list_secrets(self, status: Optional[SecretStatus] = None,
                    secret_type: Optional[SecretType] = None,
                    tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """List secrets with optional filters."""
        secrets = list(self._secrets.values())
        
        if status:
            secrets = [s for s in secrets if s.status == status]
        
        if secret_type:
            secrets = [s for s in secrets if s.secret_type == secret_type]
        
        if tag:
            secrets = [s for s in secrets if tag in s.tags]
        
        return [s.to_dict() for s in secrets]


def create_secret_manager_engine(encryption_key: Optional[str] = None) -> SecretManagerEngine:
    """Factory function to create secret manager engine."""
    return SecretManagerEngine(encryption_key=encryption_key)
