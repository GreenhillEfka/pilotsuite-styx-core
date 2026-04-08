"""
Voice Session Memory — Hierarchical Memory for Voice Sessions

- Short-term: Active session (in-memory LRU cache)
- Medium-term: Last 10 intents (per session)
- Long-term: Habit patterns (SQLite, survives restarts)

Owner: orakel + pilotclaw
Priority: P2
Status: IMPLEMENTING
"""

import sqlite3
import json
import time
import os
from typing import Dict, Any, List, Optional
from collections import OrderedDict


class LRUCache:
    """Simple LRU cache for active sessions."""
    
    def __init__(self, maxsize: int = 100):
        self.cache = OrderedDict()
        self.maxsize = maxsize
    
    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def put(self, key: str, value: Any):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)


class VoiceSessionMemory:
    """Hierarchical memory for voice sessions."""
    
    def __init__(self, data_dir: str = '/data'):
        self.data_dir = data_dir
        self.db_path = os.path.join(data_dir, 'voice_sessions.db')
        self.active_sessions = LRUCache(maxsize=100)
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite for persistence."""
        os.makedirs(self.data_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS voice_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                intents TEXT,
                created_at REAL,
                last_active REAL,
                persisted INTEGER DEFAULT 1
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS voice_habits (
                user_id TEXT,
                intent TEXT,
                slots TEXT,
                count INTEGER DEFAULT 1,
                last_used REAL,
                PRIMARY KEY (user_id, intent)
            )
        ''')
        conn.commit()
        conn.close()
    
    def record_intent(self, session_id: str, user_id: str, intent_data: Dict[str, Any]):
        """Record intent in session (short-term + medium-term)."""
        # In-memory (short-term)
        if session_id not in self.active_sessions:
            self.active_sessions.put(session_id, {
                'user_id': user_id,
                'intents': [],
                'created_at': time.time(),
            })
        
        session = self.active_sessions.get(session_id)
        session['intents'].append({
            'timestamp': time.time(),
            'intent': intent_data,
        })
        
        # Keep only last 10 intents (medium-term)
        session['intents'] = session['intents'][-10:]
        session['last_active'] = time.time()
    
    def flush_to_disk(self, session_id: str):
        """Persist session to SQLite (survives restarts)."""
        session = self.active_sessions.get(session_id)
        if not session:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO voice_sessions
            (session_id, user_id, intents, created_at, last_active, persisted)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (
            session_id,
            session['user_id'],
            json.dumps(session['intents']),
            session['created_at'],
            session['last_active'],
        ))
        conn.commit()
        conn.close()
    
    def get_user_habits(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve user's frequent commands (for RAG disambiguation)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT intent, slots, count, last_used
            FROM voice_habits
            WHERE user_id = ?
            ORDER BY count DESC, last_used DESC
            LIMIT ?
        ''', (user_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        habits = []
        for row in rows:
            habits.append({
                'intent': row[0],
                'slots': json.loads(row[1]) if row[1] else {},
                'count': row[2],
                'last_used': row[3],
            })
        
        return habits
    
    def update_habit(self, user_id: str, intent: str, slots: Dict[str, Any]):
        """Update habit frequency (for learning)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO voice_habits (user_id, intent, slots, count, last_used)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(user_id, intent) DO UPDATE SET
                count = count + 1,
                slots = excluded.slots,
                last_used = excluded.last_used
        ''', (user_id, intent, json.dumps(slots), time.time()))
        conn.commit()
        conn.close()
    
    def auto_purge(self, max_age_hours: int = 24):
        """Auto-purge old sessions (privacy)."""
        cutoff = time.time() - (max_age_hours * 3600)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM voice_sessions
            WHERE last_active < ? AND persisted = 0
        ''', (cutoff,))
        conn.commit()
        conn.close()
    
    def get_session_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get session history (last N intents)."""
        session = self.active_sessions.get(session_id)
        if session:
            return session['intents'][-limit:]
        return []


# Global instance
_memory: Optional[VoiceSessionMemory] = None


def get_voice_session_memory(data_dir: str = '/data') -> VoiceSessionMemory:
    """Get or create global session memory instance."""
    global _memory
    if _memory is None:
        _memory = VoiceSessionMemory(data_dir=data_dir)
    return _memory
