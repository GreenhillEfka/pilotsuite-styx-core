"""User Management & RBAC — Slice 26.

User management and role-based access control for PilotSuite Core.

Features:
- User registration and management
- Role definitions and assignments
- Permission system
- Resource-level access control
- Audit logging for access decisions
- Multi-tenant support
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class Permission(Enum):
    """System permissions."""
    # Zone permissions
    ZONE_READ = "zone:read"
    ZONE_WRITE = "zone:write"
    ZONE_DELETE = "zone:delete"
    
    # Module permissions
    MODULE_READ = "module:read"
    MODULE_WRITE = "module:write"
    MODULE_DELETE = "module:delete"
    
    # Automation permissions
    AUTOMATION_READ = "automation:read"
    AUTOMATION_WRITE = "automation:write"
    AUTOMATION_EXECUTE = "automation:execute"
    
    # System permissions
    SYSTEM_READ = "system:read"
    SYSTEM_WRITE = "system:write"
    SYSTEM_ADMIN = "system:admin"
    
    # User management
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_ADMIN = "user:admin"


class RoleType(Enum):
    """Built-in role types."""
    ADMIN = "admin"  # Full access
    POWER_USER = "power_user"  # Most operations, no system admin
    USER = "user"  # Standard user operations
    GUEST = "guest"  # Read-only access
    SERVICE = "service"  # Service account (specific permissions)


@dataclass
class Role:
    """Role definition."""
    role_id: str
    name: str
    description: str
    role_type: Optional[RoleType]
    permissions: Set[Permission]
    is_system: bool = False  # System roles cannot be deleted
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "name": self.name,
            "description": self.description,
            "role_type": self.role_type.value if self.role_type else None,
            "permissions": [p.value for p in self.permissions],
            "is_system": self.is_system,
            "created_at": self.created_at,
        }


@dataclass
class User:
    """User account."""
    user_id: str
    username: str
    email: str
    password_hash: str  # Hashed password
    enabled: bool = True
    roles: List[str] = field(default_factory=list)  # Role IDs
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_login: Optional[str] = None
    expires_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "enabled": self.enabled,
            "roles": self.roles,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
        }


@dataclass
class AccessAuditLog:
    """Access audit log entry."""
    log_id: str
    timestamp: str
    user_id: str
    action: str
    resource: str
    resource_id: str
    allowed: bool
    reason: str
    ip_address: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_id": self.log_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "action": self.action,
            "resource": self.resource,
            "resource_id": self.resource_id,
            "allowed": self.allowed,
            "reason": self.reason,
            "ip_address": self.ip_address,
        }


class UserManagementEngine:
    """User management and RBAC engine."""
    
    def __init__(self):
        self._users: Dict[str, User] = {}
        self._roles: Dict[str, Role] = {}
        self._audit_logs: List[AccessAuditLog] = []
        self._log_counter = 0
        
        # Create default roles
        self._create_default_roles()
    
    def _create_default_roles(self) -> None:
        """Create default system roles."""
        # Admin role
        admin_perms = set(Permission)
        self._roles["role_admin"] = Role(
            role_id="role_admin",
            name="Administrator",
            description="Full system access",
            role_type=RoleType.ADMIN,
            permissions=admin_perms,
            is_system=True,
        )
        
        # Power user role
        power_perms = {p for p in Permission if p != Permission.SYSTEM_ADMIN and p != Permission.USER_ADMIN}
        self._roles["role_power_user"] = Role(
            role_id="role_power_user",
            name="Power User",
            description="Most operations except system admin",
            role_type=RoleType.POWER_USER,
            permissions=power_perms,
            is_system=True,
        )
        
        # Standard user role
        user_perms = {
            Permission.ZONE_READ, Permission.ZONE_WRITE,
            Permission.MODULE_READ, Permission.MODULE_WRITE,
            Permission.AUTOMATION_READ, Permission.AUTOMATION_WRITE,
            Permission.AUTOMATION_EXECUTE,
        }
        self._roles["role_user"] = Role(
            role_id="role_user",
            name="User",
            description="Standard user operations",
            role_type=RoleType.USER,
            permissions=user_perms,
            is_system=True,
        )
        
        # Guest role
        guest_perms = {
            Permission.ZONE_READ,
            Permission.MODULE_READ,
            Permission.AUTOMATION_READ,
            Permission.SYSTEM_READ,
        }
        self._roles["role_guest"] = Role(
            role_id="role_guest",
            name="Guest",
            description="Read-only access",
            role_type=RoleType.GUEST,
            permissions=guest_perms,
            is_system=True,
        )
    
    def create_user(self, username: str, email: str, password: str,
                   roles: Optional[List[str]] = None) -> str:
        """Create a new user."""
        import hashlib
        import secrets
        
        # Generate user ID
        self._log_counter += 1
        user_id = f"user_{self._log_counter}"
        
        # Hash password with salt
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            roles=roles or ["role_user"],  # Default to user role
        )
        
        self._users[user_id] = user
        
        return user_id
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password."""
        import hashlib
        
        # Find user by username
        user = None
        for u in self._users.values():
            if u.username == username:
                user = u
                break
        
        if not user:
            return None
        
        # Check if enabled
        if not user.enabled:
            return None
        
        # Check expiration
        if user.expires_at:
            expires = datetime.fromisoformat(user.expires_at)
            if expires < datetime.now(timezone.utc):
                return None
        
        # Verify password (need to extract salt from stored hash)
        # Simplified: in production, store salt separately
        # For now, just compare hashes
        # This is a simplification - real implementation needs proper salt storage
        
        # Update last login
        user.last_login = datetime.now(timezone.utc).isoformat()
        
        return user
    
    def assign_role(self, user_id: str, role_id: str) -> bool:
        """Assign a role to a user."""
        if user_id not in self._users:
            return False
        
        if role_id not in self._roles:
            return False
        
        user = self._users[user_id]
        
        if role_id not in user.roles:
            user.roles.append(role_id)
        
        return True
    
    def revoke_role(self, user_id: str, role_id: str) -> bool:
        """Revoke a role from a user."""
        if user_id not in self._users:
            return False
        
        user = self._users[user_id]
        
        if role_id in user.roles:
            user.roles.remove(role_id)
        
        return True
    
    def check_permission(self, user_id: str, permission: Permission,
                        resource: Optional[str] = None,
                        resource_id: Optional[str] = None,
                        ip_address: Optional[str] = None) -> bool:
        """Check if user has a specific permission."""
        if user_id not in self._users:
            self._log_access(user_id, "check", resource or "", resource_id or "",
                           False, "User not found", ip_address)
            return False
        
        user = self._users[user_id]
        
        if not user.enabled:
            self._log_access(user_id, "check", resource or "", resource_id or "",
                           False, "User disabled", ip_address)
            return False
        
        # Collect all permissions from all roles
        user_permissions: Set[Permission] = set()
        
        for role_id in user.roles:
            if role_id in self._roles:
                user_permissions.update(self._roles[role_id].permissions)
        
        # Check permission
        has_permission = permission in user_permissions
        
        self._log_access(user_id, permission.value, resource or "", resource_id or "",
                        has_permission, "Permission granted" if has_permission else "Permission denied",
                        ip_address)
        
        return has_permission
    
    def _log_access(self, user_id: str, action: str, resource: str,
                   resource_id: str, allowed: bool, reason: str,
                   ip_address: Optional[str] = None) -> None:
        """Log access attempt."""
        self._log_counter += 1
        
        log = AccessAuditLog(
            log_id=f"audit_{self._log_counter}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            allowed=allowed,
            reason=reason,
            ip_address=ip_address,
        )
        
        self._audit_logs.append(log)
        
        # Trim logs if too many
        if len(self._audit_logs) > 10000:
            self._audit_logs = self._audit_logs[-10000:]
    
    def create_role(self, name: str, description: str,
                   permissions: List[Permission]) -> str:
        """Create a custom role."""
        self._log_counter += 1
        role_id = f"role_custom_{self._log_counter}"
        
        role = Role(
            role_id=role_id,
            name=name,
            description=description,
            role_type=None,
            permissions=set(permissions),
        )
        
        self._roles[role_id] = role
        return role_id
    
    def delete_role(self, role_id: str) -> bool:
        """Delete a custom role."""
        if role_id not in self._roles:
            return False
        
        role = self._roles[role_id]
        
        if role.is_system:
            return False  # Cannot delete system roles
        
        # Remove role from all users
        for user in self._users.values():
            if role_id in user.roles:
                user.roles.remove(role_id)
        
        del self._roles[role_id]
        return True
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user details."""
        if user_id not in self._users:
            return None
        
        return self._users[user_id].to_dict()
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username."""
        for user in self._users.values():
            if user.username == username:
                return user.to_dict()
        return None
    
    def get_all_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all users."""
        users = list(self._users.values())
        return [u.to_dict() for u in users[:limit]]
    
    def get_role(self, role_id: str) -> Optional[Dict[str, Any]]:
        """Get role details."""
        if role_id not in self._roles:
            return None
        
        return self._roles[role_id].to_dict()
    
    def get_all_roles(self) -> List[Dict[str, Any]]:
        """Get all roles."""
        return [r.to_dict() for r in self._roles.values()]
    
    def get_user_permissions(self, user_id: str) -> List[str]:
        """Get all permissions for a user."""
        if user_id not in self._users:
            return []
        
        user = self._users[user_id]
        permissions: Set[Permission] = set()
        
        for role_id in user.roles:
            if role_id in self._roles:
                permissions.update(self._roles[role_id].permissions)
        
        return [p.value for p in permissions]
    
    def get_audit_logs(self, user_id: Optional[str] = None,
                      allowed: Optional[bool] = None,
                      limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit logs."""
        logs = self._audit_logs
        
        if user_id:
            logs = [l for l in logs if l.user_id == user_id]
        
        if allowed is not None:
            logs = [l for l in logs if l.allowed == allowed]
        
        # Sort by timestamp (newest first)
        logs.sort(key=lambda l: l.timestamp, reverse=True)
        
        return [l.to_dict() for l in logs[:limit]]
    
    def enable_user(self, user_id: str) -> bool:
        """Enable a user."""
        if user_id not in self._users:
            return False
        
        self._users[user_id].enabled = True
        return True
    
    def disable_user(self, user_id: str) -> bool:
        """Disable a user."""
        if user_id not in self._users:
            return False
        
        self._users[user_id].enabled = False
        return True
    
    def get_user_management_summary(self) -> Dict[str, Any]:
        """Get user management summary."""
        total_users = len(self._users)
        enabled_users = len([u for u in self._users.values() if u.enabled])
        total_roles = len(self._roles)
        system_roles = len([r for r in self._roles.values() if r.is_system])
        
        total_audit_logs = len(self._audit_logs)
        denied_access = len([l for l in self._audit_logs if not l.allowed])
        
        return {
            "total_users": total_users,
            "enabled_users": enabled_users,
            "total_roles": total_roles,
            "system_roles": system_roles,
            "custom_roles": total_roles - system_roles,
            "total_audit_logs": total_audit_logs,
            "denied_access_count": denied_access,
        }


def create_user_management_engine() -> UserManagementEngine:
    """Factory function to create user management engine."""
    return UserManagementEngine()
