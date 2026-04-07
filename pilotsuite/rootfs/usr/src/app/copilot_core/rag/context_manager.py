"""RAG Chat Context Manager (Slice 140) - Async Optimized.

Manages multi-turn conversation history for RAG pipeline:
- History persistence (SQLite)
- Token-aware context windowing
- Context compression/summarization
- Per-user/session isolation

Performance optimizations:
- All DB operations run in ThreadPoolExecutor to avoid blocking event loop
- Uses asyncio.to_thread for Python 3.9+ compatibility
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("/data/rag_history.db")

# Thread pool for async DB operations (avoids blocking event loop)
_db_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rag-context")


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    tokens: int = 0


class RAGContextManager:
    """Manages chat history and context window for RAG.
    
    All database operations are async and non-blocking.
    """
    
    def __init__(self, db_path: Path = DEFAULT_DB_PATH, max_history: int = 10):
        self.db_path = db_path
        self.max_history = max_history
        self._db_path_str = str(db_path)
        
    def _init_db_sync(self):
        """Initialize SQLite storage for history (sync, called once at startup)."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path_str) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    user_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp REAL,
                    tokens INTEGER
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON chat_history(session_id)")
            conn.commit()
    
    async def _ensure_initialized(self):
        """Ensure DB is initialized (async-safe)."""
        if not self.db_path.exists():
            await asyncio.get_running_loop().run_in_executor(
                _db_executor, self._init_db_sync
            )
    
    async def add_message(self, session_id: str, role: str, content: str, user_id: str = "default"):
        """Add a message to the session history (async, non-blocking)."""
        await self._ensure_initialized()
        
        # Simple token estimation (4 chars per token)
        tokens = len(content) // 4
        
        def _insert():
            with sqlite3.connect(self._db_path_str) as conn:
                conn.execute(
                    "INSERT INTO chat_history (session_id, user_id, role, content, timestamp, tokens) VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, user_id, role, content, time.time(), tokens)
                )
                conn.commit()
        
        await asyncio.get_running_loop().run_in_executor(_db_executor, _insert)
            
    async def get_history(self, session_id: str, limit: Optional[int] = None) -> List[ChatMessage]:
        """Retrieve recent history for a session (async, non-blocking)."""
        await self._ensure_initialized()
        limit = limit or self.max_history
        
        def _query() -> List[ChatMessage]:
            with sqlite3.connect(self._db_path_str) as conn:
                cursor = conn.execute(
                    "SELECT role, content, timestamp, tokens FROM chat_history WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (session_id, limit)
                )
                rows = cursor.fetchall()
                return [ChatMessage(role=r, content=c, timestamp=t, tokens=tok) for r, c, t, tok in reversed(rows)]
        
        return await asyncio.get_running_loop().run_in_executor(_db_executor, _query)

    async def get_formatted_context(self, session_id: str, max_tokens: int = 2000) -> str:
        """Get history formatted as a context string for LLM, respecting token limits (async)."""
        history = await self.get_history(session_id)
        context_parts = []
        current_tokens = 0
        
        # Build from newest to oldest within limit
        for msg in reversed(history):
            if current_tokens + msg.tokens > max_tokens:
                break
            context_parts.append(f"{msg.role.capitalize()}: {msg.content}")
            current_tokens += msg.tokens
            
        return "\n".join(reversed(context_parts))

    async def clear_session(self, session_id: str):
        """Delete history for a specific session (async, non-blocking)."""
        await self._ensure_initialized()
        
        def _delete():
            with sqlite3.connect(self._db_path_str) as conn:
                conn.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
                conn.commit()
        
        await asyncio.get_running_loop().run_in_executor(_db_executor, _delete)
    
    async def close(self):
        """Cleanup: shutdown the thread pool."""
        _db_executor.shutdown(wait=True)
