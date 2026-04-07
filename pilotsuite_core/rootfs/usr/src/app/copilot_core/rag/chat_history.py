"""RAG Chat Conversation History (Slice 145) - Async Optimized.

Persistent chat history with RAG context for multi-turn conversations.

Performance optimizations:
- All DB operations run in ThreadPoolExecutor to avoid blocking event loop
- Uses asyncio.get_running_loop().run_in_executor for non-blocking I/O
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

DB_PATH = Path("/data/rag_chat_history.db")

# Thread pool for async DB operations
_db_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chat-history")


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
    """SQLite-backed chat history store with async operations."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._db_path_str = str(db_path)
        self._lock = threading.RLock()
        self._init_db_sync()
        _LOGGER.info("ChatHistoryStore initialized at %s", self._db_path)
    
    def _init_db_sync(self) -> None:
        """Create tables if not exists (sync, called once at startup)."""
        with self._lock:
            conn = sqlite3.connect(self._db_path_str)
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
    
    async def create_session(self, title: Optional[str] = None) -> ChatSession:
        """Create new chat session (async, non-blocking)."""
        session = ChatSession(title=title)
        
        def _create():
            with self._lock:
                conn = sqlite3.connect(self._db_path_str)
                try:
                    conn.execute(
                        """INSERT INTO chat_sessions (session_id, title, created_at, updated_at, message_count)
                           VALUES (?, ?, ?, ?, ?)""",
                        (session.session_id, session.title, session.created_at, session.updated_at, 0)
                    )
                    conn.commit()
                finally:
                    conn.close()
        
        await asyncio.get_running_loop().run_in_executor(_db_executor, _create)
        return session
    
    async def save_message(self, session_id: str, message: ChatMessage) -> None:
        """Save message to session (async, non-blocking)."""
        def _save():
            with self._lock:
                conn = sqlite3.connect(self._db_path_str)
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
        
        await asyncio.get_running_loop().run_in_executor(_db_executor, _save)
    
    async def load_session(self, session_id: str) -> Optional[ChatSession]:
        """Load session with all messages (async, non-blocking)."""
        def _load() -> Optional[ChatSession]:
            with self._lock:
                conn = sqlite3.connect(self._db_path_str)
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
                    
                    for r in rows:
                        msg = ChatMessage(
                            message_id=r[0],
                            role=r[2],
                            content=r[3],
                            timestamp=r[4],
                            context_refs=json.loads(r[5]) if r[5] else [],
                        )
                        session.messages.append(msg)
                    
                    return session
                finally:
                    conn.close()
        
        return await asyncio.get_running_loop().run_in_executor(_db_executor, _load)
    
    async def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent chat sessions (async, non-blocking)."""
        def _list() -> List[Dict[str, Any]]:
            with self._lock:
                conn = sqlite3.connect(self._db_path_str)
                try:
                    rows = conn.execute(
                        "SELECT session_id, title, created_at, updated_at, message_count FROM chat_sessions ORDER BY updated_at DESC LIMIT ?",
                        (limit,)
                    ).fetchall()
                    return [
                        {
                            "session_id": r[0],
                            "title": r[1],
                            "created_at": r[2],
                            "updated_at": r[3],
                            "message_count": r[4],
                        }
                        for r in rows
                    ]
                finally:
                    conn.close()
        
        return await asyncio.get_running_loop().run_in_executor(_db_executor, _list)
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session and all messages (async, non-blocking)."""
        def _delete() -> bool:
            with self._lock:
                conn = sqlite3.connect(self._db_path_str)
                try:
                    # Delete messages first
                    conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
                    # Delete session
                    cursor = conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
                    conn.commit()
                    return cursor.rowcount > 0
                finally:
                    conn.close()
        
        return await asyncio.get_running_loop().run_in_executor(_db_executor, _delete)
    
    async def close(self):
        """Cleanup: shutdown the thread pool."""
        _db_executor.shutdown(wait=True)
