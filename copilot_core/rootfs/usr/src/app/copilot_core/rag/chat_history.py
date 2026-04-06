"""RAG Chat Conversation History (Slice 145).

Persistent chat history with RAG context for multi-turn conversations.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

DB_PATH = Path("/data/rag_chat_history.db")


class ChatMessage:
    """Single chat message."""
    
    def __init__(
        self,
        role: str,  # "user" or "assistant"
        content: str,
        message_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        context_refs: Optional[List[Dict[str, Any]]] = None,
    ):
        self.message_id = message_id or str(uuid.uuid4())
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.context_refs = context_refs or []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "context_refs": self.context_refs,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        return cls(
            role=data["role"],
            content=data["content"],
            message_id=data.get("message_id"),
            timestamp=data.get("timestamp"),
            context_refs=data.get("context_refs"),
        )


class ChatSession:
    """Chat session with history."""
    
    def __init__(self, session_id: Optional[str] = None, title: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.title = title or f"Chat {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        self.messages: List[ChatMessage] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
    
    def add_message(self, message: ChatMessage) -> None:
        """Add message to session."""
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc).isoformat()
    
    def get_context_window(self, max_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent messages for RAG context."""
        recent = self.messages[-max_messages:]
        return [{"role": m.role, "content": m.content} for m in recent]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": len(self.messages),
        }


class ChatHistoryStore:
    """SQLite-backed chat history store."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._lock = threading.RLock()
        self._init_db()
        _LOGGER.info("ChatHistoryStore initialized at %s", self._db_path)
    
    def _init_db(self) -> None:
        """Create tables if not exists."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        session_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        message_count INTEGER DEFAULT 0
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        message_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        context_refs TEXT,  -- JSON array
                        FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
                    )
                """)
                conn.commit()
            finally:
                conn.close()
    
    def create_session(self, title: Optional[str] = None) -> ChatSession:
        """Create new chat session."""
        session = ChatSession(title=title)
        
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute(
                    """INSERT INTO chat_sessions (session_id, title, created_at, updated_at, message_count)
                       VALUES (?, ?, ?, ?, ?)""",
                    (session.session_id, session.title, session.created_at, session.updated_at, 0)
                )
                conn.commit()
            finally:
                conn.close()
        
        return session
    
    def save_message(self, session_id: str, message: ChatMessage) -> None:
        """Save message to session."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                # Save message
                context_refs_json = json.dumps(message.context_refs) if message.context_refs else "[]"
                conn.execute(
                    """INSERT INTO chat_messages (message_id, session_id, role, content, timestamp, context_refs)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (message.message_id, session_id, message.role, message.content, message.timestamp, context_refs_json)
                )
                
                # Update session
                updated_at = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """UPDATE chat_sessions SET updated_at = ?, message_count = message_count + 1
                       WHERE session_id = ?""",
                    (updated_at, session_id)
                )
                conn.commit()
            finally:
                conn.close()
    
    def load_session(self, session_id: str) -> Optional[ChatSession]:
        """Load session with all messages."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                # Load session
                row = conn.execute(
                    "SELECT * FROM chat_sessions WHERE session_id = ?",
                    (session_id,)
                ).fetchone()
                
                if not row:
                    return None
                
                session = ChatSession(
                    session_id=row[0],
                    title=row[1],
                )
                session.created_at = row[2]
                session.updated_at = row[3]
                
                # Load messages
                rows = conn.execute(
                    "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY timestamp",
                    (session_id,)
                ).fetchall()
                
                for row in rows:
                    context_refs = json.loads(row[5]) if row[5] else []
                    message = ChatMessage(
                        message_id=row[0],
                        role=row[2],
                        content=row[3],
                        timestamp=row[4],
                        context_refs=context_refs,
                    )
                    session.messages.append(message)
                
                return session
            finally:
                conn.close()
    
    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent chat sessions."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                rows = conn.execute(
                    """SELECT session_id, title, created_at, updated_at, message_count
                       FROM chat_sessions ORDER BY updated_at DESC LIMIT ?""",
                    (limit,)
                ).fetchall()
                
                return [
                    {
                        "session_id": row[0],
                        "title": row[1],
                        "created_at": row[2],
                        "updated_at": row[3],
                        "message_count": row[4],
                    }
                    for row in rows
                ]
            finally:
                conn.close()
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session and all messages."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                # Delete messages first (foreign key constraint)
                conn.execute(
                    "DELETE FROM chat_messages WHERE session_id = ?",
                    (session_id,)
                )
                
                # Delete session
                cursor = conn.execute(
                    "DELETE FROM chat_sessions WHERE session_id = ?",
                    (session_id,)
                )
                conn.commit()
                
                return cursor.rowcount > 0
            finally:
                conn.close()


# Global instance
_history_store: Optional[ChatHistoryStore] = None
_history_lock = threading.Lock()


def get_chat_history_store() -> ChatHistoryStore:
    """Get singleton ChatHistoryStore instance."""
    global _history_store
    with _history_lock:
        if _history_store is None:
            _history_store = ChatHistoryStore()
        return _history_store
