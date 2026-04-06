"""RAG Chat Context Manager (Slice 140).

Manages multi-turn conversation history for RAG pipeline:
- History persistence (SQLite)
- Token-aware context windowing
- Context compression/summarization
- Per-user/session isolation
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("/data/rag_history.db")

@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    tokens: int = 0

class RAGContextManager:
    """Manages chat history and context window for RAG."""
    
    def __init__(self, db_path: Path = DEFAULT_DB_PATH, max_history: int = 10):
        self.db_path = db_path
        self.max_history = max_history
        self._init_db()
        
    def _init_db(self):
        """Initialize SQLite storage for history."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
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

    def add_message(self, session_id: str, role: str, content: str, user_id: str = "default"):
        """Add a message to the session history."""
        # Simple token estimation (4 chars per token)
        tokens = len(content) // 4
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO chat_history (session_id, user_id, role, content, timestamp, tokens) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, user_id, role, content, time.time(), tokens)
            )
            
    def get_history(self, session_id: str, limit: Optional[int] = None) -> List[ChatMessage]:
        """Retrieve recent history for a session."""
        limit = limit or self.max_history
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT role, content, timestamp, tokens FROM chat_history WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit)
            )
            rows = cursor.fetchall()
            return [ChatMessage(role=r, content=c, timestamp=t, tokens=tok) for r, c, t, tok in reversed(rows)]

    def get_formatted_context(self, session_id: str, max_tokens: int = 2000) -> str:
        """Get history formatted as a context string for LLM, respecting token limits."""
        history = self.get_history(session_id)
        context_parts = []
        current_tokens = 0
        
        # Build from newest to oldest within limit
        for msg in reversed(history):
            if current_tokens + msg.tokens > max_tokens:
                break
            context_parts.append(f"{msg.role.capitalize()}: {msg.content}")
            current_tokens += msg.tokens
            
        return "\n".join(reversed(context_parts))

    def clear_session(self, session_id: str):
        """Delete history for a specific session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
