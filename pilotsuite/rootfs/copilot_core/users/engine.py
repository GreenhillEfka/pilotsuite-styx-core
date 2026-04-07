"""User Management Engine — Slice 26.

User management, authentication, and RBAC for PilotSuite Core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import secrets


class RoleType(str, Enum):
    """Built-in role types."""
    ADMIN = "admin"
    POWER_USER = "power_user"
    USER = "user"
    GUEST = "guest"


class Permission(str, Enum):
    """Core permissions."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    CONFIGURE = "configure"


@dataclass
class Role:
    """User role definition."""
    id: str
    name: str
    description: str
    permissions: List[Permission] = field(default_factory=list)
    is_builtin: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": [p.value for p in self.permissions],
            "is_builtin": self.is_builtin,
        }


@dataclass
class User:
    """User account."""
    id: str
    username: str
    email: str
    password_hash: str
    role_id: str
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role_id": self.role_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
        if include_sensitive:
            d["password_hash"] = self.password_hash
        return d


class UserManagementEngine:
    """User management and RBAC engine."""
    
    def __init__(self):
        self._users: Dict[str, User] = {}
        self._roles: Dict[str, Role] = {}
        self._init_default_roles()
    
    def _init_default_roles(self) -> None:
        """Initialize default roles."""
        default_roles = [
            Role(
                id="admin",
                name="Administrator",
                description="Full system access",
                permissions=[Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN, Permission.CONFIGURE],
                is_builtin=True,
            ),
            Role(
                id="power_user",
                name="Power User",
                description="Advanced user with write access",
                permissions=[Permission.READ, Permission.WRITE, Permission.CONFIGURE],
                is_builtin=True,
            ),
            Role(
                id="user",
                name="User",
                description="Standard user",
                permissions=[Permission.READ, Permission.WRITE],
                is_builtin=True,
            ),
            Role(
                id="guest",
                name="Guest",
                description="Read-only access",
                permissions=[Permission.READ],
                is_builtin=True,
            ),
        ]
        for role in default_roles:
            self._roles[role.id] = role
    
    def _hash_password(self, password: str) -> str:
        """Hash a password."""
        salt = secrets.token_hex(16)
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}${hash_obj.hex()}"
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role_id: str = "user",
    ) -> Optional[str]:
        """Create a new user."""
        if username in [u.username for u in self._users.values()]:
            return None
        
        user_id = secrets.token_hex(8)
        user = User(
            id=user_id,
            username=username,
            email=email,
            password_hash=self._hash_password(password),
            role_id=role_id,
        )
        self._users[user_id] = user
        return user_id
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self._users.get(user_id)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        for user in self._users.values():
            if user.username == username:
                return user
        return None
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        if user_id in self._users:
            del self._users[user_id]
            return True
        return False
    
    def update_user_role(self, user_id: str, role_id: str) -> bool:
        """Update user's role."""
        user = self._users.get(user_id)
        if not user:
            return False
        user.role_id = role_id
        return True
    
    def create_role(
        self,
        name: str,
        description: str,
        permissions: List[Permission],
    ) -> str:
        """Create a custom role."""
        role_id = secrets.token_hex(4)
        role = Role(
            id=role_id,
            name=name,
            description=description,
            permissions=permissions,
        )
        self._roles[role_id] = role
        return role_id
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """Get role by ID."""
        return self._roles.get(role_id)
    
    def get_all_roles(self) -> List[Dict[str, Any]]:
        """Get all roles."""
        return [r.to_dict() for r in self._roles.values()]
    
    def delete_role(self, role_id: str) -> bool:
        """Delete a custom role."""
        role = self._roles.get(role_id)
        if role and not role.is_builtin:
            del self._roles[role_id]
            return True
        return False
    
    def has_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if user has a permission."""
        user = self._users.get(user_id)
        if not user:
            return False
        role = self._roles.get(user.role_id)
        if not role:
            return False
        return permission in role.permissions
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user."""
        user = self.get_user_by_username(username)
        if not user:
            return None
        
        salt, hash_hex = user.password_hash.split('$')
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        if hash_obj.hex() != hash_hex:
            return None
        
        user.last_login = datetime.now(timezone.utc)
        return user


def create_user_management_engine() -> UserManagementEngine:
    """Factory function."""
    return UserManagementEngine()
