"""Multi-User Collaboration — Shared Spaces, Permissions, Conflicts."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum
import time

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles in collaboration."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    GUEST = "guest"
    SERVICE = "service"


class Permission(Enum):
    """Permission types."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    SHARE = "share"
    AUTOMATION_CREATE = "automation_create"
    AUTOMATION_EDIT = "automation_edit"
    DEVICE_CONTROL = "device_control"


@dataclass
class User:
    """User in the system."""
    id: str
    name: str
    email: Optional[str] = None
    role: UserRole = UserRole.MEMBER
    permissions: Set[Permission] = field(default_factory=set)
    preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())
    last_active: Optional[float] = None


@dataclass
class SharedSpace:
    """Shared collaboration space."""
    id: str
    name: str
    description: str
    owner_id: str
    members: Dict[str, UserRole] = field(default_factory=dict)
    resources: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())


@dataclass
class ConflictResolution:
    """Conflict resolution record."""
    id: str
    resource_id: str
    conflicting_users: List[str]
    resolution_strategy: str
    winner_user_id: str
    resolved_at: float
    details: Dict[str, Any] = field(default_factory=dict)


class CollaborationEngine:
    """Multi-user collaboration engine."""

    def __init__(self):
        self._users: Dict[str, User] = {}
        self._spaces: Dict[str, SharedSpace] = {}
        self._active_sessions: Dict[str, Dict] = {}
        self._conflict_history: List[ConflictResolution] = []
        self._default_permissions: Dict[UserRole, Set[Permission]] = self._init_default_permissions()

    def _init_default_permissions(self) -> Dict[UserRole, Set[Permission]]:
        """Initialize default permissions per role."""
        return {
            UserRole.OWNER: set(Permission),  # All permissions
            UserRole.ADMIN: {
                Permission.READ, Permission.WRITE, Permission.DELETE,
                Permission.SHARE, Permission.AUTOMATION_CREATE,
                Permission.AUTOMATION_EDIT, Permission.DEVICE_CONTROL,
            },
            UserRole.MEMBER: {
                Permission.READ, Permission.WRITE,
                Permission.AUTOMATION_CREATE, Permission.DEVICE_CONTROL,
            },
            UserRole.GUEST: {Permission.READ},
            UserRole.SERVICE: {Permission.READ, Permission.WRITE},
        }

    def create_user(self, user_id: str, name: str, email: Optional[str] = None, role: UserRole = UserRole.MEMBER) -> User:
        """Create a new user."""
        permissions = self._default_permissions.get(role, set())
        
        user = User(
            id=user_id,
            name=name,
            email=email,
            role=role,
            permissions=permissions,
        )
        
        self._users[user_id] = user
        logger.info(f"User created: {name} ({user_id})")
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self._users.get(user_id)

    def create_space(self, space_id: str, name: str, owner_id: str, description: str = "") -> SharedSpace:
        """Create a shared space."""
        if owner_id not in self._users:
            raise ValueError(f"Owner user not found: {owner_id}")
        
        space = SharedSpace(
            id=space_id,
            name=name,
            description=description,
            owner_id=owner_id,
            members={owner_id: UserRole.OWNER},
        )
        
        self._spaces[space_id] = space
        logger.info(f"Space created: {name} ({space_id})")
        return space

    def add_member(self, space_id: str, user_id: str, role: UserRole) -> bool:
        """Add a member to a space."""
        if space_id not in self._spaces:
            return False
        
        space = self._spaces[space_id]
        space.members[user_id] = role
        
        # Update user permissions based on space role
        if user_id in self._users:
            user = self._users[user_id]
            user.permissions = self._default_permissions.get(role, set())
        
        logger.info(f"User {user_id} added to space {space_id} as {role.value}")
        return True

    def remove_member(self, space_id: str, user_id: str) -> bool:
        """Remove a member from a space."""
        if space_id not in self._spaces:
            return False
        
        space = self._spaces[space_id]
        if user_id in space.members:
            del space.members[user_id]
            logger.info(f"User {user_id} removed from space {space_id}")
            return True
        
        return False

    def check_permission(self, user_id: str, space_id: str, permission: Permission) -> bool:
        """Check if user has permission in a space."""
        if user_id not in self._users:
            return False
        
        if space_id not in self._spaces:
            return False
        
        user = self._users[user_id]
        space = self._spaces[space_id]
        
        # Owner has all permissions
        if space.members.get(user_id) == UserRole.OWNER:
            return True
        
        return permission in user.permissions

    def start_session(self, user_id: str, space_id: str, device_info: str) -> Optional[str]:
        """Start a collaboration session."""
        if not self.check_permission(user_id, space_id, Permission.READ):
            return None
        
        session_id = f"session_{user_id}_{int(time.time())}"
        
        self._active_sessions[session_id] = {
            "user_id": user_id,
            "space_id": space_id,
            "device_info": device_info,
            "started_at": time.time(),
            "last_activity": time.time(),
            "operations": [],
        }
        
        # Update user last active
        if user_id in self._users:
            self._users[user_id].last_active = time.time()
        
        logger.info(f"Session started: {session_id}")
        return session_id

    def end_session(self, session_id: str) -> bool:
        """End a collaboration session."""
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
            logger.info(f"Session ended: {session_id}")
            return True
        return False

    def record_operation(self, session_id: str, operation: Dict) -> bool:
        """Record an operation in a session."""
        if session_id not in self._active_sessions:
            return False
        
        session = self._active_sessions[session_id]
        session["operations"].append({
            "timestamp": time.time(),
            "operation": operation,
        })
        session["last_activity"] = time.time()
        
        return True

    def resolve_conflict(self, resource_id: str, conflicting_users: List[str], 
                         strategy: str = "last_write_wins") -> ConflictResolution:
        """Resolve a conflict between users."""
        # Determine winner based on strategy
        if strategy == "last_write_wins":
            # Most recent write wins
            winner = conflicting_users[-1] if conflicting_users else None
        elif strategy == "owner_wins":
            # Space owner wins
            winner = next((uid for uid in conflicting_users if self._users.get(uid, User("", "")).role == UserRole.OWNER), None)
        elif strategy == "manual":
            # Requires manual resolution
            winner = None
        else:
            winner = conflicting_users[0] if conflicting_users else None
        
        resolution = ConflictResolution(
            id=f"conflict_{resource_id}_{int(time.time())}",
            resource_id=resource_id,
            conflicting_users=conflicting_users,
            resolution_strategy=strategy,
            winner_user_id=winner or "unresolved",
            resolved_at=time.time(),
        )
        
        self._conflict_history.append(resolution)
        logger.info(f"Conflict resolved: {resolution.id} - strategy: {strategy}")
        
        return resolution

    def get_active_users(self, space_id: str) -> List[Dict]:
        """Get currently active users in a space."""
        active = []
        for session in self._active_sessions.values():
            if session["space_id"] == space_id:
                user = self._users.get(session["user_id"])
                if user:
                    active.append({
                        "user_id": user.id,
                        "name": user.name,
                        "role": user.role.value,
                        "session_id": session["session_id"] if "session_id" in session else None,
                        "last_activity": session["last_activity"],
                    })
        return active

    def get_shared_spaces(self, user_id: str) -> List[SharedSpace]:
        """Get all spaces a user is member of."""
        return [
            space for space in self._spaces.values()
            if user_id in space.members
        ]

    def export_space_config(self, space_id: str) -> Optional[Dict]:
        """Export space configuration for backup/sharing."""
        if space_id not in self._spaces:
            return None
        
        space = self._spaces[space_id]
        return {
            "id": space.id,
            "name": space.name,
            "description": space.description,
            "owner_id": space.owner_id,
            "members": {uid: role.value for uid, role in space.members.items()},
            "settings": space.settings,
            "created_at": space.created_at,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get collaboration statistics."""
        return {
            "total_users": len(self._users),
            "total_spaces": len(self._spaces),
            "active_sessions": len(self._active_sessions),
            "conflicts_resolved": len(self._conflict_history),
        }


# Global default collaboration engine
default_collaboration: Optional[CollaborationEngine] = None


def init_collaboration_engine() -> CollaborationEngine:
    """Initialize global collaboration engine."""
    global default_collaboration
    default_collaboration = CollaborationEngine()
    return default_collaboration
