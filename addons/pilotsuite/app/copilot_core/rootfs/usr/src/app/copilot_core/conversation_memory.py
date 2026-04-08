"""
Conversation Memory -- Lifelong Learning Store for PilotSuite

Stores conversation history and extracts user preferences over time.
This is the bridge between chat interactions and the PilotSuite neural pipeline:

  User speaks/writes → ConversationMemory stores it
                      → Preferences extracted → Brain Graph / Habitus enriched
                      → Next conversation gets richer context

Design principles:
- Privacy-first: All data stays local (SQLite in /data)
- Lightweight: No heavy embeddings, uses keyword extraction
- Incremental: Each conversation adds to the knowledge base
- Decay: Old memories lose weight over time (configurable half-life)
"""

import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("CONVERSATION_MEMORY_DB", "/data/conversation_memory.db")
MAX_MEMORY_ENTRIES = 10000
MEMORY_HALF_LIFE_DAYS = 90  # Memories decay over 90 days


@dataclass
class MemoryEntry:
    """A single conversation memory entry."""
    id: int
    timestamp: float
    role: str  # "user" or "assistant"
    content: str
    character: str  # Which character preset was active
    extracted_preferences: str  # JSON string of extracted prefs
    topic_tags: str  # Comma-separated topic tags
    mood_context: str  # JSON string of mood at time of conversation


@dataclass
class UserPreference:
    """An extracted user preference from conversation."""
    key: str  # e.g., "preferred_temperature", "wake_time", "music_genre"
    value: str  # e.g., "22", "06:30", "jazz"
    confidence: float  # 0-1, increases with repetition
    source: str  # "explicit" (user said it) or "inferred" (from patterns)
    last_updated: float  # timestamp
    mention_count: int  # How often this was mentioned


class ConversationMemory:
    """Lifelong learning conversation memory store.

    Stores conversations, extracts preferences, and provides
    relevant context for future LLM interactions.
    """

    def __init__(self, db_path: str = None):
        self._db_path = db_path or DB_PATH
        self._lock = threading.Lock()
        self._init_db()
        logger.info("ConversationMemory initialized at %s", self._db_path)

    def _init_db(self):
        """Initialize SQLite database with tables."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        character TEXT DEFAULT 'copilot',
                        extracted_preferences TEXT DEFAULT '{}',
                        topic_tags TEXT DEFAULT '',
                        mood_context TEXT DEFAULT '{}'
                    );
                    CREATE INDEX IF NOT EXISTS idx_conv_timestamp ON conversations(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_conv_role ON conversations(role);

                    CREATE TABLE IF NOT EXISTS user_preferences (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        confidence REAL DEFAULT 0.5,
                        source TEXT DEFAULT 'inferred',
                        last_updated REAL NOT NULL,
                        mention_count INTEGER DEFAULT 1
                    );

                    CREATE TABLE IF NOT EXISTS conversation_summaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        summary TEXT NOT NULL,
                        topics TEXT DEFAULT '',
                        sentiment TEXT DEFAULT 'neutral',
                        key_facts TEXT DEFAULT '[]'
                    );
                    CREATE INDEX IF NOT EXISTS idx_summary_timestamp ON conversation_summaries(timestamp);
                """)
                conn.commit()
            finally:
                conn.close()

    def store_message(self, role: str, content: str, character: str = "copilot",
                      mood_context: dict = None) -> int:
        """Store a conversation message and extract preferences.

        Returns the message ID.
        """
        now = time.time()
        mood_json = json.dumps(mood_context or {})

        # Extract topic tags from content
        topic_tags = self._extract_topics(content)

        # Extract preferences if it's a user message
        prefs = {}
        if role == "user":
            prefs = self._extract_preferences(content)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.execute(
                    "INSERT INTO conversations (timestamp, role, content, character, "
                    "extracted_preferences, topic_tags, mood_context) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (now, role, content, character, json.dumps(prefs), ",".join(topic_tags), mood_json)
                )
                msg_id = cursor.lastrowid

                # Update user preferences table
                for key, value in prefs.items():
                    self._upsert_preference(conn, key, value, "explicit")

                conn.commit()

                # Prune old entries if needed
                self._prune_if_needed(conn)

                return msg_id
            finally:
                conn.close()

    def get_relevant_context(self, query: str, limit: int = 5) -> str:
        """Get relevant conversation context for a new query.

        Searches past conversations for similar topics and returns
        a formatted context string for LLM injection.
        """
        topics = self._extract_topics(query)
        if not topics:
            return self._get_recent_summary()

        context_parts = []

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                # Find conversations matching query topics
                for topic in topics[:3]:  # Max 3 topics
                    rows = conn.execute(
                        "SELECT role, content, timestamp FROM conversations "
                        "WHERE topic_tags LIKE ? AND role = 'user' "
                        "ORDER BY timestamp DESC LIMIT ?",
                        (f"%{topic}%", limit)
                    ).fetchall()
                    for role, content, ts in rows:
                        age_days = (time.time() - ts) / 86400
                        if age_days < MEMORY_HALF_LIFE_DAYS * 2:
                            context_parts.append(f"[Vor {int(age_days)}d] {content[:100]}")

                # Get active user preferences
                prefs = conn.execute(
                    "SELECT key, value, confidence FROM user_preferences "
                    "WHERE confidence > 0.3 ORDER BY confidence DESC LIMIT 10"
                ).fetchall()
                if prefs:
                    pref_lines = [f"  {k}: {v} (Sicherheit: {c:.0%})" for k, v, c in prefs]
                    context_parts.append("Nutzerpraeferenzen:\n" + "\n".join(pref_lines))

            finally:
                conn.close()

        if not context_parts:
            return ""

        return "\nErinnerungen:\n" + "\n".join(f"- {p}" for p in context_parts[:8])

    def get_user_preferences(self) -> List[UserPreference]:
        """Get all stored user preferences."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT key, value, confidence, source, last_updated, mention_count "
                    "FROM user_preferences ORDER BY confidence DESC"
                ).fetchall()
                return [UserPreference(*row) for row in rows]
            finally:
                conn.close()

    def get_preferences_for_prompt(self) -> str:
        """Get user preferences formatted for LLM system prompt injection."""
        prefs = self.get_user_preferences()
        if not prefs:
            return ""

        high_conf = [p for p in prefs if p.confidence >= 0.5]
        if not high_conf:
            return ""

        lines = []
        for p in high_conf[:15]:
            source_marker = "*" if p.source == "explicit" else "~"
            lines.append(f"  {source_marker} {p.key}: {p.value}")

        return "\nGelernte Nutzerpraeferenzen (* = direkt gesagt, ~ = abgeleitet):\n" + "\n".join(lines)

    def store_summary(self, summary: str, topics: list = None,
                      sentiment: str = "neutral", key_facts: list = None):
        """Store a conversation summary for long-term memory."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    "INSERT INTO conversation_summaries (timestamp, summary, topics, sentiment, key_facts) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (time.time(), summary, ",".join(topics or []),
                     sentiment, json.dumps(key_facts or []))
                )
                conn.commit()
            finally:
                conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get memory store statistics."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                total_msgs = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
                user_msgs = conn.execute("SELECT COUNT(*) FROM conversations WHERE role='user'").fetchone()[0]
                total_prefs = conn.execute("SELECT COUNT(*) FROM user_preferences").fetchone()[0]
                total_summaries = conn.execute("SELECT COUNT(*) FROM conversation_summaries").fetchone()[0]

                oldest = conn.execute("SELECT MIN(timestamp) FROM conversations").fetchone()[0]
                newest = conn.execute("SELECT MAX(timestamp) FROM conversations").fetchone()[0]

                return {
                    "total_messages": total_msgs,
                    "user_messages": user_msgs,
                    "assistant_messages": total_msgs - user_msgs,
                    "preferences_learned": total_prefs,
                    "summaries": total_summaries,
                    "oldest_memory": oldest,
                    "newest_memory": newest,
                    "memory_span_days": int((newest - oldest) / 86400) if oldest and newest else 0,
                    "db_path": self._db_path,
                }
            finally:
                conn.close()

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _extract_topics(self, text: str) -> List[str]:
        """Extract topic tags from text using keyword matching.

        Simple but effective -- no ML model needed.
        """
        text_lower = text.lower()
        topics = []

        # HA domain topics
        domain_keywords = {
            "licht": "lighting", "lampe": "lighting", "light": "lighting",
            "heizung": "climate", "temperatur": "climate", "klima": "climate",
            "climate": "climate", "thermostat": "climate",
            "musik": "media", "tv": "media", "fernseher": "media",
            "media": "media", "spotify": "media",
            "tuer": "security", "fenster": "security", "alarm": "security",
            "kamera": "security", "lock": "security",
            "energie": "energy", "strom": "energy", "solar": "energy",
            "verbrauch": "energy", "batterie": "energy",
            "anwesenheit": "presence", "zuhause": "presence",
            "weg": "presence", "urlaub": "presence",
            "morgen": "routine", "abend": "routine", "nacht": "routine",
            "aufstehen": "routine", "schlafen": "routine",
            "automatisierung": "automation", "regel": "automation",
            "szene": "automation",
            "wetter": "weather", "regen": "weather", "sonne": "weather",
        }

        for keyword, topic in domain_keywords.items():
            if keyword in text_lower and topic not in topics:
                topics.append(topic)

        return topics

    def _extract_preferences(self, text: str) -> Dict[str, str]:
        """Extract user preferences from a message.

        Looks for patterns like:
        - "Ich mag es bei 22 Grad" → preferred_temperature: 22
        - "Ich stehe um 6:30 auf" → wake_time: 06:30
        - "Abends hoere ich gerne Jazz" → evening_music: jazz
        """
        prefs = {}
        text_lower = text.lower()

        # Temperature preferences
        import re
        temp_match = re.search(r'(\d{1,2})\s*(?:grad|°)', text_lower)
        if temp_match and "temperatur" in text_lower or "heiz" in text_lower or "warm" in text_lower or "kalt" in text_lower:
            prefs["preferred_temperature"] = temp_match.group(1)

        # Wake/sleep time
        time_match = re.search(r'(?:um|gegen)\s+(\d{1,2}[:.]\d{2})', text_lower)
        if time_match:
            time_val = time_match.group(1).replace(".", ":")
            if any(w in text_lower for w in ["aufsteh", "weck", "morgen"]):
                prefs["wake_time"] = time_val
            elif any(w in text_lower for w in ["schlaf", "bett", "nacht"]):
                prefs["bedtime"] = time_val

        # Light preferences
        if "hell" in text_lower or "dunkel" in text_lower:
            if "hell" in text_lower:
                prefs["light_preference"] = "hell"
            else:
                prefs["light_preference"] = "dunkel"

        # Explicit likes/dislikes
        like_match = re.search(r'(?:mag|liebe|bevorzuge|moechte|will)\s+(?:ich\s+)?(.{3,30})', text_lower)
        if like_match:
            prefs["likes"] = like_match.group(1).strip()

        dislike_match = re.search(r'(?:mag\s+(?:ich\s+)?nicht|hasse|nervt)\s+(.{3,30})', text_lower)
        if dislike_match:
            prefs["dislikes"] = dislike_match.group(1).strip()

        return prefs

    def _upsert_preference(self, conn: sqlite3.Connection, key: str, value: str, source: str):
        """Insert or update a user preference with confidence boosting."""
        existing = conn.execute(
            "SELECT confidence, mention_count FROM user_preferences WHERE key = ?",
            (key,)
        ).fetchone()

        now = time.time()
        if existing:
            old_conf, count = existing
            # Boost confidence with each mention (asymptotic to 1.0)
            new_conf = min(1.0, old_conf + (1.0 - old_conf) * 0.2)
            conn.execute(
                "UPDATE user_preferences SET value = ?, confidence = ?, "
                "source = ?, last_updated = ?, mention_count = ? WHERE key = ?",
                (value, new_conf, source, now, count + 1, key)
            )
        else:
            conn.execute(
                "INSERT INTO user_preferences (key, value, confidence, source, last_updated, mention_count) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (key, value, 0.4, source, now, 1)
            )

    def _prune_if_needed(self, conn: sqlite3.Connection):
        """Remove oldest entries if over MAX_MEMORY_ENTRIES."""
        count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        if count > MAX_MEMORY_ENTRIES:
            excess = count - MAX_MEMORY_ENTRIES
            conn.execute(
                "DELETE FROM conversations WHERE id IN "
                "(SELECT id FROM conversations ORDER BY timestamp ASC LIMIT ?)",
                (excess,)
            )

    def _get_recent_summary(self) -> str:
        """Get a summary of recent conversations."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT summary, timestamp FROM conversation_summaries "
                    "ORDER BY timestamp DESC LIMIT 3"
                ).fetchall()
                if not rows:
                    return ""
                lines = [f"[Vor {int((time.time() - ts) / 86400)}d] {s[:80]}" for s, ts in rows]
                return "\nLetzte Gespraeche:\n" + "\n".join(f"- {l}" for l in lines)
            finally:
                conn.close()
