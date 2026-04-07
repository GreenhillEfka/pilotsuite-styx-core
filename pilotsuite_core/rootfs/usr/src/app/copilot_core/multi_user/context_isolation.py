"""Multi-User Context Isolation (Slice 150).

Isolierte Kontexte für mehrere Benutzer mit:
- Per-User Memory
- Privacy-First Design
- Kontext-Switching
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

_LOGGER = logging.getLogger(__name__)


@dataclass
class UserContext:
    """Isolated context for a single user."""
    user_id: str
    preferences: Dict[str, Any] = field(default_factory=dict)
    memory: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.monotonic)
    last_active: float = field(default_factory=time.monotonic)
    
    def touch(self) -> None:
        """Update last active timestamp."""
        self.last_active = time.monotonic()


class ContextIsolationManager:
    """Manages isolated contexts for multiple users."""
    
    def __init__(self, max_users: int = 100, ttl_seconds: float = 3600.0):
        self.max_users = max_users
        self.ttl_seconds = ttl_seconds
        self._contexts: Dict[str, UserContext] = {}
        self._lock = threading.RLock()
        self._cleanup_interval = 300.0  # 5 minutes
        self._last_cleanup = time.monotonic()
    
    def _get_user_key(self, user_id: str) -> str:
        """Hash user ID for privacy."""
        return hashlib.sha256(user_id.encode()).hexdigest()[:16]
    
    def get_context(self, user_id: str, create: bool = True) -> Optional[UserContext]:
        """Get or create user context."""
        self._maybe_cleanup()
        
        key = self._get_user_key(user_id)
        
        with self._lock:
            if key in self._contexts:
                ctx = self._contexts[key]
                ctx.touch()
                return ctx
            
            if create and len(self._contexts) < self.max_users:
                ctx = UserContext(user_id=key)
                self._contexts[key] = ctx
                _LOGGER.debug("Created context for user %s...", key[:8])
                return ctx
            
            return None
    
    def set_preference(self, user_id: str, key: str, value: Any) -> bool:
        """Set user preference."""
        ctx = self.get_context(user_id)
        if ctx:
            ctx.preferences[key] = value
            return True
        return False
    
    def get_preference(self, user_id: str, key: str, default: Any = None) -> Any:
        """Get user preference."""
        ctx = self.get_context(user_id, create=False)
        if ctx:
            return ctx.preferences.get(key, default)
        return default
    
    def store_memory(self, user_id: str, key: str, value: Any) -> bool:
        """Store user-specific memory."""
        ctx = self.get_context(user_id)
        if ctx:
            ctx.memory[key] = value
            return True
        return False
    
    def retrieve_memory(self, user_id: str, key: str) -> Optional[Any]:
        """Retrieve user-specific memory."""
        ctx = self.get_context(user_id, create=False)
        if ctx:
            return ctx.memory.get(key)
        return None
    
    def delete_context(self, user_id: str) -> bool:
        """Delete user context (GDPR compliance)."""
        key = self._get_user_key(user_id)
        with self._lock:
            if key in self._contexts:
                del self._contexts[key]
                _LOGGER.info("Deleted context for user %s...", key[:8])
                return True
        return False
    
    def _maybe_cleanup(self) -> None:
        """Remove expired contexts."""
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        with self._lock:
            expired = [
                key for key, ctx in self._contexts.items()
                if now - ctx.last_active > self.ttl_seconds
            ]
            for key in expired:
                del self._contexts[key]
            
            if expired:
                _LOGGER.info("Cleaned up %d expired contexts", len(expired))
            
            self._last_cleanup = now
    
    def get_stats(self) -> Dict[str, Any]:
        """Get isolation stats."""
        with self._lock:
            return {
                "active_contexts": len(self._contexts),
                "max_users": self.max_users,
                "ttl_seconds": self.ttl_seconds,
            }


# Global instance
_context_manager: Optional[ContextIsolationManager] = None
_context_lock = threading.Lock()


def get_context_manager() -> ContextIsolationManager:
    """Get singleton ContextIsolationManager."""
    global _context_manager
    with _context_lock:
        if _context_manager is None:
            _context_manager = ContextIsolationManager()
        return _context_manager
