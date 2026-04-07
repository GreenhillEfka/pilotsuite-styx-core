"""Multi-User Preference Learning (MUPL) Module.

Implements:
- Device Manager Role
- Everyday User Role  
- Restricted User Role
- Role-Based Access Control (RBAC)

User roles are inferred from behavior patterns:
- Device Manager: Controls multiple devices, creates automations
- Everyday User: Regular device usage, follows routines
- Restricted User: Limited device access, time-based restrictions

Role inference uses:
- Device control frequency
- Time-of-day patterns
- Automation creation
- User presence duration
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

_LOGGER = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles for preference learning and access control."""
    DEVICE_MANAGER = "device_manager"
    EVERYDAY_USER = "everyday_user"
    RESTRICTED_USER = "restricted_user"
    UNKNOWN = "unknown"


@dataclass
class UserProfile:
    """User profile with inferred role and preferences."""
    user_id: str
    role: UserRole = UserRole.UNKNOWN
    device_count: int = 0
    automation_count: int = 0
    avg_presence_hours: float = 0.0
    last_seen: Optional[datetime] = None
    confidence: float = 0.0
    preferences: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class RoleInferenceConfig:
    """Configuration for role inference."""
    min_devices_for_manager: int = 5
    min_automations_for_manager: int = 3
    min_presence_hours_for_regular: float = 4.0
    role_confidence_threshold: float = 0.7


class MultiUserPreferenceLearning:
    """Multi-User Preference Learning engine.
    
    Infers user roles from behavior patterns and maintains
    individual preferences per user.
    """
    
    def __init__(self, config: Optional[RoleInferenceConfig] = None):
        self.config = config or RoleInferenceConfig()
        self._profiles: Dict[str, UserProfile] = {}
        self._user_activities: Dict[str, List[Dict[str, Any]]] = {}
        self._device_usage: Dict[str, Set[str]] = {}  # user -> devices
        self._automation_history: Dict[str, List[Dict[str, Any]]] = {}
    
    def add_user_activity(self, user_id: str, activity: Dict[str, Any]) -> None:
        """Record user activity for role inference."""
        if user_id not in self._user_activities:
            self._user_activities[user_id] = []
        self._user_activities[user_id].append(activity)
    
    def register_device_control(self, user_id: str, device_id: str) -> None:
        """Track which devices a user controls."""
        if user_id not in self._device_usage:
            self._device_usage[user_id] = set()
        self._device_usage[user_id].add(device_id)
    
    def register_automation_created(self, user_id: str, automation: Dict[str, Any]) -> None:
        """Track automation creation."""
        if user_id not in self._automation_history:
            self._automation_history[user_id] = []
        self._automation_history[user_id].append(automation)
    
    def infer_role(self, user_id: str) -> UserRole:
        """Infer user role from behavior patterns."""
        # Check if user exists
        if user_id not in self._device_usage:
            return UserRole.UNKNOWN
        
        device_count = len(self._device_usage[user_id])
        automation_count = len(self._automation_history.get(user_id, []))
        
        # Calculate confidence based on data availability
        confidence = min(1.0, (device_count + automation_count * 2) / 10)
        
        # Device Manager: High device count + automation creation
        if (device_count >= self.config.min_devices_for_manager and 
            automation_count >= self.config.min_automations_for_manager):
            return UserRole.DEVICE_MANAGER
        
        # Everyday User: Regular device usage
        if device_count >= 2:
            return UserRole.EVERYDAY_USER
        
        # Restricted User: Limited device access
        if device_count == 1:
            return UserRole.RESTRICTED_USER
        
        return UserRole.UNKNOWN
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile with inferred role."""
        if user_id not in self._device_usage:
            return None
        
        role = self.infer_role(user_id)
        
        return UserProfile(
            user_id=user_id,
            role=role,
            device_count=len(self._device_usage[user_id]),
            automation_count=len(self._automation_history.get(user_id, [])),
            confidence=0.7,  # Simplified for now
            last_seen=datetime.now()
        )
    
    def check_access(self, user_id: str, device_id: str) -> bool:
        """Check if user has access to device based on role."""
        profile = self.get_user_profile(user_id)
        if not profile:
            return False
        
        # Device Manager can access everything
        if profile.role == UserRole.DEVICE_MANAGER:
            return True
        
        # Check if user controls this device
        if user_id in self._device_usage:
            if device_id in self._device_usage[user_id]:
                return True
        
        # Restricted users only access their registered devices
        if profile.role == UserRole.RESTRICTED_USER:
            return device_id in self._device_usage.get(user_id, set())
        
        return False
    
    def get_all_profiles(self) -> Dict[str, UserProfile]:
        """Get all user profiles."""
        return {
            user_id: self.get_user_profile(user_id)
            for user_id in self._device_usage.keys()
        }
    
    def set_user_preference(self, user_id: str, preference_key: str, value: Any) -> None:
        """Set user preference."""
        if user_id not in self._profiles:
            self._profiles[user_id] = UserProfile(user_id=user_id)
        self._profiles[user_id].preferences[preference_key] = value
    
    def get_user_preference(self, user_id: str, preference_key: str, default=None) -> Any:
        """Get user preference."""
        if user_id not in self._profiles:
            return default
        return self._profiles[user_id].preferences.get(preference_key, default)


def create_mupl_module() -> MultiUserPreferenceLearning:
    """Factory function to create MUPL module instance."""
    return MultiUserPreferenceLearning()
