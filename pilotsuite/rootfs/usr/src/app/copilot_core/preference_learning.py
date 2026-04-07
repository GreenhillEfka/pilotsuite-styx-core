"""Per-User Preference Learning from Conversation Context (P1-003).

Extracts and learns user preferences from natural language conversations.
Privacy-first: all learning happens locally, no external API calls.

Features:
- Extract preferences from natural language (not just explicit settings)
- Confidence scoring based on repetition and recency
- Per-user preference storage
- Context-aware preference inference
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("PREFERENCE_LEARNING_DB", "/data/preference_learning.db")
PREFERENCE_HALF_LIFE_DAYS = 60  # Preferences decay over 60 days


@dataclass
class LearnedPreference:
    """A learned user preference."""
    user_id: str
    key: str  # e.g., "preferred_temperature", "wake_time"
    value: str  # e.g., "22", "06:30"
    confidence: float = 0.5  # 0-1, increases with repetition
    source: str = "inferred"  # "explicit" or "inferred"
    last_updated: float = field(default_factory=time.time)
    mention_count: int = 1
    context: Dict[str, Any] = field(default_factory=dict)  # e.g., {"topic": "climate", "mood": "comfort"}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
            "last_updated": self.last_updated,
            "mention_count": self.mention_count,
            "context": self.context,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearnedPreference":
        return cls(
            user_id=data.get("user_id", ""),
            key=data.get("key", ""),
            value=data.get("value", ""),
            confidence=data.get("confidence", 0.5),
            source=data.get("source", "inferred"),
            last_updated=data.get("last_updated", time.time()),
            mention_count=data.get("mention_count", 1),
            context=data.get("context", {}),
        )


class PreferenceLearner:
    """Learns user preferences from conversation context.
    
    Extracts preferences using:
    - Explicit statements ("I like it at 22 degrees")
    - Implicit patterns (repeated requests for same value)
    - Context inference (time of day, location, activity)
    """
    
    def __init__(self, db_path: str = None):
        self._db_path = db_path or DB_PATH
        self._lock = threading.Lock()
        self._init_db()
        logger.info("PreferenceLearner initialized at %s", self._db_path)
    
    def _init_db(self):
        """Initialize SQLite database."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS preferences (
                        user_id TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        confidence REAL DEFAULT 0.5,
                        source TEXT DEFAULT 'inferred',
                        last_updated REAL NOT NULL,
                        mention_count INTEGER DEFAULT 1,
                        context TEXT DEFAULT '{}',
                        PRIMARY KEY (user_id, key)
                    );
                    CREATE INDEX IF NOT EXISTS idx_prefs_user ON preferences(user_id);
                    CREATE INDEX IF NOT EXISTS idx_prefs_confidence ON preferences(confidence DESC);
                """)
                conn.commit()
            finally:
                conn.close()
    
    def extract_preferences(self, user_id: str, text: str, 
                            context: Dict[str, Any] = None) -> List[LearnedPreference]:
        """Extract preferences from user message.
        
        Args:
            user_id: User ID
            text: User message text
            context: Optional context (topic, mood, time, etc.)
        
        Returns:
            List of extracted preferences
        """
        prefs = []
        text_lower = text.lower()
        ctx = context or {}
        
        # Temperature preferences
        temp_match = re.search(r'(\d{1,2})\s*(?:grad|°|degrees?)', text_lower)
        if temp_match:
            if any(w in text_lower for w in ["temperatur", "heiz", "warm", "kalt", "climate"]):
                prefs.append(LearnedPreference(
                    user_id=user_id,
                    key="preferred_temperature",
                    value=temp_match.group(1),
                    source="explicit" if any(w in text_lower for w in ["mag", "liebe", "moechte", "will"]) else "inferred",
                    context={"topic": "climate", **ctx},
                ))
        
        # Time preferences (wake/bedtime)
        time_match = re.search(r'(?:um|gegen)\s+(\d{1,2}[:.]\d{2})', text_lower)
        if time_match:
            time_val = time_match.group(1).replace(".", ":")
            if any(w in text_lower for w in ["aufsteh", "weck", "morgen"]):
                prefs.append(LearnedPreference(
                    user_id=user_id,
                    key="wake_time",
                    value=time_val,
                    source="explicit",
                    context={"topic": "routine", **ctx},
                ))
            elif any(w in text_lower for w in ["schlaf", "bett", "nacht", "abend"]):
                prefs.append(LearnedPreference(
                    user_id=user_id,
                    key="bedtime",
                    value=time_val,
                    source="explicit",
                    context={"topic": "routine", **ctx},
                ))
        
        # Light preferences
        if any(w in text_lower for w in ["licht", "lampe", "light"]):
            if "hell" in text_lower or "bright" in text_lower:
                prefs.append(LearnedPreference(
                    user_id=user_id,
                    key="light_preference",
                    value="bright",
                    source="inferred",
                    context={"topic": "lighting", **ctx},
                ))
            elif "dunkel" in text_lower or "dim" in text_lower:
                prefs.append(LearnedPreference(
                    user_id=user_id,
                    key="light_preference",
                    value="dim",
                    source="inferred",
                    context={"topic": "lighting", **ctx},
                ))
        
        # Music/media preferences
        music_keywords = ["musik", "music", "spotify", "playlist", "genre"]
        if any(kw in text_lower for kw in music_keywords):
            genre_match = re.search(r'(?:gerne|like|hoere|listen).{0,20}?(jazz|classical|rock|pop|electronic|ambient|metal|folk)', text_lower)
            if genre_match:
                prefs.append(LearnedPreference(
                    user_id=user_id,
                    key="music_genre",
                    value=genre_match.group(1),
                    source="explicit",
                    context={"topic": "media", **ctx},
                ))
        
        # Explicit likes/dislikes
        like_match = re.search(r'(?:mag|liebe|bevorzuge|moechte|will|prefer).{0,30}?(.{3,40})', text_lower)
        if like_match and not any(w in text_lower for w in ["nicht", "no", "never"]):
            # Only capture if it looks like a preference
            captured = like_match.group(1).strip()
            if len(captured) > 3 and len(captured) < 40:
                prefs.append(LearnedPreference(
                    user_id=user_id,
                    key="likes",
                    value=captured,
                    source="explicit",
                    context=ctx,
                ))
        
        # Dislikes
        dislike_match = re.search(r'(?:mag\s+nicht|hasse|nervt|dislike|hate).{0,30}?(.{3,40})', text_lower)
        if dislike_match:
            captured = dislike_match.group(1).strip()
            if len(captured) > 3 and len(captured) < 40:
                prefs.append(LearnedPreference(
                    user_id=user_id,
                    key="dislikes",
                    value=captured,
                    source="explicit",
                    context=ctx,
                ))
        
        # Mood/comfort preferences
        if any(w in text_lower for w in ["gemuetlich", "cozy", "comfort", "wohl"]):
            prefs.append(LearnedPreference(
                user_id=user_id,
                key="mood_preference",
                value="comfort",
                source="inferred",
                context={"topic": "mood", **ctx},
            ))
        
        if any(w in text_lower for w in ["produktiv", "productive", "focus", "arbeit"]):
            prefs.append(LearnedPreference(
                user_id=user_id,
                key="mood_preference",
                value="focus",
                source="inferred",
                context={"topic": "mood", **ctx},
            ))
        
        return prefs
    
    def learn_preference(self, user_id: str, key: str, value: str,
                         source: str = "inferred", context: Dict[str, Any] = None) -> LearnedPreference:
        """Store or update a learned preference.
        
        Confidence increases with repetition (asymptotic to 1.0).
        """
        now = time.time()
        ctx = json.dumps(context or {})
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                existing = conn.execute(
                    "SELECT confidence, mention_count FROM preferences "
                    "WHERE user_id = ? AND key = ?",
                    (user_id, key)
                ).fetchone()
                
                if existing:
                    old_conf, count = existing
                    # Boost confidence (asymptotic to 1.0)
                    new_conf = min(1.0, old_conf + (1.0 - old_conf) * 0.2)
                    conn.execute(
                        "UPDATE preferences SET value = ?, confidence = ?, "
                        "source = ?, last_updated = ?, mention_count = ?, context = ? "
                        "WHERE user_id = ? AND key = ?",
                        (value, new_conf, source, now, count + 1, ctx, user_id, key)
                    )
                    pref = LearnedPreference(
                        user_id=user_id, key=key, value=value,
                        confidence=new_conf, source=source,
                        last_updated=now, mention_count=count + 1,
                        context=context or {},
                    )
                else:
                    conn.execute(
                        "INSERT INTO preferences (user_id, key, value, confidence, "
                        "source, last_updated, mention_count, context) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (user_id, key, value, 0.4, source, now, 1, ctx)
                    )
                    pref = LearnedPreference(
                        user_id=user_id, key=key, value=value,
                        confidence=0.4, source=source,
                        last_updated=now, mention_count=1,
                        context=context or {},
                    )
                
                conn.commit()
                logger.debug("Learned preference for %s: %s=%s (conf=%.2f)", 
                           user_id, key, value, pref.confidence)
                return pref
            finally:
                conn.close()
    
    def learn_from_message(self, user_id: str, text: str,
                           context: Dict[str, Any] = None) -> List[LearnedPreference]:
        """Extract and learn preferences from a user message.
        
        Combines extraction and storage in one call.
        """
        extracted = self.extract_preferences(user_id, text, context)
        learned = []
        for pref in extracted:
            result = self.learn_preference(
                user_id=user_id,
                key=pref.key,
                value=pref.value,
                source=pref.source,
                context=pref.context,
            )
            learned.append(result)
        return learned
    
    def get_user_preferences(self, user_id: str, 
                             min_confidence: float = 0.3) -> List[LearnedPreference]:
        """Get all preferences for a user.
        
        Args:
            user_id: User ID
            min_confidence: Minimum confidence threshold (default 0.3)
        
        Returns:
            List of preferences sorted by confidence (highest first)
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT user_id, key, value, confidence, source, "
                    "last_updated, mention_count, context "
                    "FROM preferences WHERE user_id = ? AND confidence >= ? "
                    "ORDER BY confidence DESC",
                    (user_id, min_confidence)
                ).fetchall()
                return [
                    LearnedPreference(
                        user_id=row[0], key=row[1], value=row[2],
                        confidence=row[3], source=row[4],
                        last_updated=row[5], mention_count=row[6],
                        context=json.loads(row[7]),
                    )
                    for row in rows
                ]
            finally:
                conn.close()
    
    def get_preference(self, user_id: str, key: str) -> Optional[LearnedPreference]:
        """Get a specific preference for a user."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                row = conn.execute(
                    "SELECT user_id, key, value, confidence, source, "
                    "last_updated, mention_count, context "
                    "FROM preferences WHERE user_id = ? AND key = ?",
                    (user_id, key)
                ).fetchone()
                if row:
                    return LearnedPreference(
                        user_id=row[0], key=row[1], value=row[2],
                        confidence=row[3], source=row[4],
                        last_updated=row[5], mention_count=row[6],
                        context=json.loads(row[7]),
                    )
                return None
            finally:
                conn.close()
    
    def update_preference(self, user_id: str, key: str, value: str,
                          confidence: float = None) -> Optional[LearnedPreference]:
        """Manually update a preference (explicit user setting)."""
        now = time.time()
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                existing = conn.execute(
                    "SELECT mention_count FROM preferences "
                    "WHERE user_id = ? AND key = ?",
                    (user_id, key)
                ).fetchone()
                
                if existing:
                    count = existing[0]
                    new_conf = confidence if confidence is not None else min(1.0, 0.8 + count * 0.05)
                    conn.execute(
                        "UPDATE preferences SET value = ?, confidence = ?, "
                        "source = 'explicit', last_updated = ? "
                        "WHERE user_id = ? AND key = ?",
                        (value, new_conf, now, user_id, key)
                    )
                else:
                    new_conf = confidence if confidence is not None else 0.9
                    conn.execute(
                        "INSERT INTO preferences (user_id, key, value, confidence, "
                        "source, last_updated, mention_count, context) "
                        "VALUES (?, ?, ?, ?, 'explicit', ?, ?, '{}')",
                        (user_id, key, value, new_conf, now, 1)
                    )
                
                conn.commit()
                return self.get_preference(user_id, key)
            finally:
                conn.close()
    
    def delete_preference(self, user_id: str, key: str) -> bool:
        """Delete a specific preference (user request)."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                result = conn.execute(
                    "DELETE FROM preferences WHERE user_id = ? AND key = ?",
                    (user_id, key)
                )
                conn.commit()
                if result.rowcount > 0:
                    logger.info("Deleted preference %s for user %s", key, user_id)
                    return True
                return False
            finally:
                conn.close()
    
    def delete_all_user_preferences(self, user_id: str) -> int:
        """Delete all preferences for a user (GDPR)."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                result = conn.execute(
                    "DELETE FROM preferences WHERE user_id = ?",
                    (user_id,)
                )
                conn.commit()
                logger.info("Deleted %d preferences for user %s", result.rowcount, user_id)
                return result.rowcount
            finally:
                conn.close()
    
    def get_all_users_with_preferences(self) -> List[str]:
        """Get list of all users who have learned preferences."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT DISTINCT user_id FROM preferences ORDER BY user_id"
                ).fetchall()
                return [row[0] for row in rows]
            finally:
                conn.close()
    
    def get_preferences_for_prompt(self, user_id: str) -> str:
        """Get user preferences formatted for LLM system prompt injection."""
        prefs = self.get_user_preferences(user_id, min_confidence=0.5)
        if not prefs:
            return ""
        
        lines = []
        for p in prefs[:15]:
            source_marker = "*" if p.source == "explicit" else "~"
            lines.append(f"  {source_marker} {p.key}: {p.value}")
        
        return "\nGelernte Nutzerpraeferenzen (* = direkt gesagt, ~ = abgeleitet):\n" + "\n".join(lines)
    
    def export_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Export all preferences for a user (GDPR)."""
        prefs = self.get_user_preferences(user_id, min_confidence=0.0)
        if not prefs:
            return None
        
        return {
            "user_id": user_id,
            "preferences": [p.to_dict() for p in prefs],
            "count": len(prefs),
            "exported_at": time.time(),
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get preference learning statistics."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                total_prefs = conn.execute("SELECT COUNT(*) FROM preferences").fetchone()[0]
                unique_users = conn.execute("SELECT COUNT(DISTINCT user_id) FROM preferences").fetchone()[0]
                explicit = conn.execute("SELECT COUNT(*) FROM preferences WHERE source = 'explicit'").fetchone()[0]
                inferred = conn.execute("SELECT COUNT(*) FROM preferences WHERE source = 'inferred'").fetchone()[0]
                high_conf = conn.execute("SELECT COUNT(*) FROM preferences WHERE confidence >= 0.7").fetchone()[0]
                
                return {
                    "total_preferences": total_prefs,
                    "unique_users": unique_users,
                    "explicit_preferences": explicit,
                    "inferred_preferences": inferred,
                    "high_confidence_count": high_conf,
                    "db_path": self._db_path,
                }
            finally:
                conn.close()
    
    def apply_decay(self) -> int:
        """Apply time-based decay to old preferences.
        
        Reduces confidence for preferences not updated recently.
        Returns count of updated preferences.
        """
        now = time.time()
        decay_threshold = now - (PREFERENCE_HALF_LIFE_DAYS * 86400)
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                # Get preferences that need decay
                rows = conn.execute(
                    "SELECT user_id, key, confidence, last_updated FROM preferences "
                    "WHERE last_updated < ?",
                    (decay_threshold,)
                ).fetchall()
                
                updated = 0
                for user_id, key, conf, last_ts in rows:
                    # Calculate decay factor based on age
                    age_days = (now - last_ts) / 86400
                    decay_factor = 0.5 ** (age_days / PREFERENCE_HALF_LIFE_DAYS)
                    new_conf = round(conf * decay_factor, 3)
                    
                    conn.execute(
                        "UPDATE preferences SET confidence = ? WHERE user_id = ? AND key = ?",
                        (new_conf, user_id, key)
                    )
                    updated += 1
                
                conn.commit()
                if updated > 0:
                    logger.info("Applied decay to %d preferences", updated)
                return updated
            finally:
                conn.close()


# Singleton instance
_learner: Optional[PreferenceLearner] = None


def get_preference_learner() -> PreferenceLearner:
    """Get the global PreferenceLearner instance."""
    global _learner
    if _learner is None:
        _learner = PreferenceLearner()
    return _learner


def init_preference_learner(db_path: str = None) -> PreferenceLearner:
    """Initialize the global PreferenceLearner with custom config."""
    global _learner
    _learner = PreferenceLearner(db_path=db_path)
    return _learner
