"""User Profiles for Multi-User Preference Learning (P1-003).

Provides user identification by name, voice, or context for multi-household support.
Privacy-first: all user data remains local.

Features:
- User identification (by name, voice ID, or context)
- Per-user profile storage
- Voice fingerprint association (optional, local-only)
- Context-based user inference
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("USER_PROFILES_DB", "/data/user_profiles.db")


@dataclass
class UserProfile:
    """A user profile with identification and preferences."""
    user_id: str  # Unique identifier (UUID or hash)
    name: str  # Display name
    voice_id: Optional[str] = None  # Optional voice fingerprint hash
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    interaction_count: int = 0
    context_hints: Dict[str, Any] = field(default_factory=dict)  # e.g., {"timezone": "Europe/Berlin", "language": "de"}
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "voice_id": self.voice_id,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "interaction_count": self.interaction_count,
            "context_hints": self.context_hints,
            "is_active": self.is_active,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        return cls(
            user_id=data.get("user_id", ""),
            name=data.get("name", "Unknown"),
            voice_id=data.get("voice_id"),
            created_at=data.get("created_at", time.time()),
            last_seen=data.get("last_seen", time.time()),
            interaction_count=data.get("interaction_count", 0),
            context_hints=data.get("context_hints", {}),
            is_active=data.get("is_active", True),
        )


class UserProfiles:
    """User profile manager for multi-household support.
    
    Supports identification by:
    - Name (explicit user identification)
    - Voice ID (voice fingerprint, optional)
    - Context (timezone, language, device, etc.)
    """
    
    def __init__(self, db_path: str = None):
        self._db_path = db_path or DB_PATH
        self._lock = threading.Lock()
        self._init_db()
        logger.info("UserProfiles initialized at %s", self._db_path)
    
    def _init_db(self):
        """Initialize SQLite database."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        user_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        voice_id TEXT UNIQUE,
                        created_at REAL NOT NULL,
                        last_seen REAL NOT NULL,
                        interaction_count INTEGER DEFAULT 0,
                        context_hints TEXT DEFAULT '{}',
                        is_active INTEGER DEFAULT 1
                    );
                    CREATE INDEX IF NOT EXISTS idx_users_voice ON user_profiles(voice_id);
                    CREATE INDEX IF NOT EXISTS idx_users_name ON user_profiles(name);
                    CREATE INDEX IF NOT EXISTS idx_users_active ON user_profiles(is_active);
                """)
                conn.commit()
            finally:
                conn.close()
    
    def create_user(self, name: str, voice_id: str = None, 
                    context_hints: Dict[str, Any] = None) -> UserProfile:
        """Create a new user profile.
        
        Args:
            name: User display name
            voice_id: Optional voice fingerprint hash
            context_hints: Optional context hints (timezone, language, etc.)
        
        Returns:
            Created UserProfile
        """
        # Generate user_id from name + timestamp
        user_id = hashlib.sha256(f"{name}:{time.time()}".encode()).hexdigest()[:16]
        
        profile = UserProfile(
            user_id=user_id,
            name=name,
            voice_id=voice_id,
            context_hints=context_hints or {},
        )
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    "INSERT INTO user_profiles (user_id, name, voice_id, created_at, "
                    "last_seen, interaction_count, context_hints, is_active) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (profile.user_id, profile.name, profile.voice_id,
                     profile.created_at, profile.last_seen, 0,
                     json.dumps(profile.context_hints), 1 if profile.is_active else 0)
                )
                conn.commit()
                logger.info("Created user profile: %s (%s)", name, user_id)
                return profile
            finally:
                conn.close()
    
    def get_user(self, user_id: str) -> Optional[UserProfile]:
        """Get user by ID."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                row = conn.execute(
                    "SELECT user_id, name, voice_id, created_at, last_seen, "
                    "interaction_count, context_hints, is_active "
                    "FROM user_profiles WHERE user_id = ?",
                    (user_id,)
                ).fetchone()
                if row:
                    return UserProfile(
                        user_id=row[0],
                        name=row[1],
                        voice_id=row[2],
                        created_at=row[3],
                        last_seen=row[4],
                        interaction_count=row[5],
                        context_hints=json.loads(row[6]),
                        is_active=bool(row[7]),
                    )
                return None
            finally:
                conn.close()
    
    def get_user_by_voice(self, voice_id: str) -> Optional[UserProfile]:
        """Get user by voice fingerprint."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                row = conn.execute(
                    "SELECT user_id, name, voice_id, created_at, last_seen, "
                    "interaction_count, context_hints, is_active "
                    "FROM user_profiles WHERE voice_id = ?",
                    (voice_id,)
                ).fetchone()
                if row:
                    return UserProfile(
                        user_id=row[0],
                        name=row[1],
                        voice_id=row[2],
                        created_at=row[3],
                        last_seen=row[4],
                        interaction_count=row[5],
                        context_hints=json.loads(row[6]),
                        is_active=bool(row[7]),
                    )
                return None
            finally:
                conn.close()
    
    def get_user_by_name(self, name: str) -> Optional[UserProfile]:
        """Get user by name (case-insensitive)."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                row = conn.execute(
                    "SELECT user_id, name, voice_id, created_at, last_seen, "
                    "interaction_count, context_hints, is_active "
                    "FROM user_profiles WHERE LOWER(name) = LOWER(?)",
                    (name,)
                ).fetchone()
                if row:
                    return UserProfile(
                        user_id=row[0],
                        name=row[1],
                        voice_id=row[2],
                        created_at=row[3],
                        last_seen=row[4],
                        interaction_count=row[5],
                        context_hints=json.loads(row[6]),
                        is_active=bool(row[7]),
                    )
                return None
            finally:
                conn.close()
    
    def identify_user(self, name: str = None, voice_id: str = None,
                      context_hints: Dict[str, Any] = None) -> UserProfile:
        """Identify or create a user from available context.
        
        Tries to match existing user by:
        1. Voice ID (most reliable)
        2. Name (case-insensitive)
        3. Context hints (timezone, language, etc.)
        
        Creates new user if no match found.
        
        Args:
            name: Optional user name
            voice_id: Optional voice fingerprint
            context_hints: Optional context hints
        
        Returns:
            Matched or created UserProfile
        """
        # Try voice ID first
        if voice_id:
            user = self.get_user_by_voice(voice_id)
            if user:
                self._update_last_seen(user.user_id)
                return user
        
        # Try name
        if name:
            user = self.get_user_by_name(name)
            if user:
                if voice_id and not user.voice_id:
                    # Update voice ID for existing user
                    self._set_voice_id(user.user_id, voice_id)
                self._update_last_seen(user.user_id)
                return user
        
        # Try context hints (simplified: match by timezone)
        if context_hints and "timezone" in context_hints:
            users = self.get_all_users()
            for user in users:
                if user.context_hints.get("timezone") == context_hints["timezone"]:
                    # Fuzzy match - return first active user with same timezone
                    if user.is_active:
                        self._update_last_seen(user.user_id)
                        return user
        
        # Create new user
        display_name = name or f"User_{hashlib.sha256(str(time.time()).encode()).hexdigest()[:6]}"
        return self.create_user(
            name=display_name,
            voice_id=voice_id,
            context_hints=context_hints or {},
        )
    
    def update_user(self, user_id: str, name: str = None, voice_id: str = None,
                    context_hints: Dict[str, Any] = None) -> Optional[UserProfile]:
        """Update user profile fields."""
        user = self.get_user(user_id)
        if not user:
            return None
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                if name is not None:
                    user.name = name
                if voice_id is not None:
                    user.voice_id = voice_id
                if context_hints is not None:
                    user.context_hints.update(context_hints)
                
                conn.execute(
                    "UPDATE user_profiles SET name = ?, voice_id = ?, "
                    "context_hints = ? WHERE user_id = ?",
                    (user.name, user.voice_id, json.dumps(user.context_hints), user_id)
                )
                conn.commit()
                return user
            finally:
                conn.close()
    
    def _set_voice_id(self, user_id: str, voice_id: str) -> bool:
        """Set voice ID for a user."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    "UPDATE user_profiles SET voice_id = ? WHERE user_id = ?",
                    (voice_id, user_id)
                )
                conn.commit()
                return True
            finally:
                conn.close()
    
    def _update_last_seen(self, user_id: str) -> None:
        """Update last seen timestamp and increment interaction count."""
        now = time.time()
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    "UPDATE user_profiles SET last_seen = ?, "
                    "interaction_count = interaction_count + 1 WHERE user_id = ?",
                    (now, user_id)
                )
                conn.commit()
            finally:
                conn.close()
    
    def record_interaction(self, user_id: str) -> None:
        """Record a user interaction."""
        self._update_last_seen(user_id)
    
    def get_all_users(self, active_only: bool = False) -> List[UserProfile]:
        """Get all user profiles."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                query = "SELECT user_id, name, voice_id, created_at, last_seen, interaction_count, context_hints, is_active FROM user_profiles"
                if active_only:
                    query += " WHERE is_active = 1"
                query += " ORDER BY last_seen DESC"
                
                rows = conn.execute(query).fetchall()
                return [
                    UserProfile(
                        user_id=row[0],
                        name=row[1],
                        voice_id=row[2],
                        created_at=row[3],
                        last_seen=row[4],
                        interaction_count=row[5],
                        context_hints=json.loads(row[6]),
                        is_active=bool(row[7]),
                    )
                    for row in rows
                ]
            finally:
                conn.close()
    
    def get_active_users(self) -> List[UserProfile]:
        """Get active users only."""
        return self.get_all_users(active_only=True)
    
    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user profile (soft delete)."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                result = conn.execute(
                    "UPDATE user_profiles SET is_active = 0 WHERE user_id = ?",
                    (user_id,)
                )
                conn.commit()
                return result.rowcount > 0
            finally:
                conn.close()
    
    def delete_user(self, user_id: str) -> bool:
        """Permanently delete a user profile (GDPR)."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                result = conn.execute(
                    "DELETE FROM user_profiles WHERE user_id = ?",
                    (user_id,)
                )
                conn.commit()
                if result.rowcount > 0:
                    logger.info("Deleted user profile: %s", user_id)
                    return True
                return False
            finally:
                conn.close()
    
    def export_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Export all data for a user (GDPR)."""
        user = self.get_user(user_id)
        if not user:
            return None
        
        return {
            "user_profile": user.to_dict(),
            "exported_at": time.time(),
            "format_version": "1.0",
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get user profile statistics."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                total = conn.execute("SELECT COUNT(*) FROM user_profiles").fetchone()[0]
                active = conn.execute("SELECT COUNT(*) FROM user_profiles WHERE is_active = 1").fetchone()[0]
                with_voice = conn.execute("SELECT COUNT(*) FROM user_profiles WHERE voice_id IS NOT NULL").fetchone()[0]
                
                return {
                    "total_users": total,
                    "active_users": active,
                    "users_with_voice": with_voice,
                    "db_path": self._db_path,
                }
            finally:
                conn.close()


# Singleton instance
_profiles: Optional[UserProfiles] = None


def get_user_profiles() -> UserProfiles:
    """Get the global UserProfiles instance."""
    global _profiles
    if _profiles is None:
        _profiles = UserProfiles()
    return _profiles


def init_user_profiles(db_path: str = None) -> UserProfiles:
    """Initialize the global UserProfiles with custom config."""
    global _profiles
    _profiles = UserProfiles(db_path=db_path)
    return _profiles
