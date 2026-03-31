"""Zentrales Habitus-Storage — Life-Long-Learning für PilotSuite.

Dies ist das HERZSTÜCK des Dachsystems:
- Speichert übergreifende Patterns (cross-module, cross-zone)
- Lernt Nutzer-Präferenzen, Routinen, Gewohnheiten
- Verbindet Neurons, Modules, Zones, Chat-Feedback
- Ermöglicht proaktive Vorhersagen

Architecture:
┌──────────────────────────────────────────────────────────────┐
│                    HABITUS STORAGE                            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Patterns (A→B Regeln mit Confidence)                        │
│  User-Model (Präferenzen, Routinen, Feedback)                │
│  Context-History (Kontext für Pattern-Mining)                │
│  Cross-Module-Learning (Synergien zwischen Modulen)          │
│                                                               │
└──────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from enum import Enum

_LOGGER = logging.getLogger(__name__)

DB_PATH = os.environ.get("HABITUS_STORAGE_DB", "/data/habitus_storage.db")


# =============================================================================
# Data Models
# =============================================================================

class PatternState(str, Enum):
    """State eines Patterns im Lernprozess."""
    OBSERVING = "observing"      # Wird beobachtet (noch nicht genug Daten)
    LEARNING = "learning"        # Lernt (genug Daten, noch nicht stabil)
    STABLE = "stable"            # Stabil (kann vorgeschlagen werden)
    ACTIVE = "active"            # Aktiv (wird automatisch ausgeführt)
    DISABLED = "disabled"        # Deaktiviert (Nutzer hat abgelehnt)


class FeedbackType(str, Enum):
    """Feedback-Typ vom Nutzer."""
    ACCEPTED = "accepted"        # Vorschlag akzeptiert
    REJECTED = "rejected"        # Vorschlag abgelehnt
    IGNORED = "ignored"          # Vorschlag ignoriert
    CORRECTED = "corrected"      # Vorschlag korrigiert
    MANUAL = "manual"            # Manuelle Aktion (implizites Feedback)


@dataclass
class Pattern:
    """Ein gelerntes Pattern (A→B Regel).
    
    Example:
    {
        "trigger": {"time": "19:30", "presence": True, "zone": "living"},
        "action": {"module": "light", "command": "turn_on"},
        "confidence": 0.95,
        "acceptances": 45,
        "rejections": 2,
    }
    """
    
    id: str
    description: str
    trigger: Dict[str, Any]
    action: Dict[str, Any]
    
    # Learning metrics
    confidence: float = 0.0
    support: int = 0  # Wie oft beobachtet
    acceptances: int = 0
    rejections: int = 0
    ignores: int = 0
    
    # State
    state: PatternState = PatternState.OBSERVING
    
    # Context
    zones: List[str] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)
    contexts: List[str] = field(default_factory=list)  # Wetter, Tageszeit, etc.
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_triggered: Optional[str] = None
    last_learned: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Pattern:
        return cls(**data)
    
    def update_confidence(self) -> None:
        """Confidence basierend auf Feedback neu berechnen."""
        total = self.acceptances + self.rejections + self.ignores
        if total == 0:
            self.confidence = 0.0
        else:
            # Wilson Score Interval für robuste Confidence
            self.confidence = self.acceptances / total
        
        # State-Update basierend auf Confidence + Support
        if self.support >= 10 and self.confidence >= 0.8:
            self.state = PatternState.STABLE
        elif self.support >= 5:
            self.state = PatternState.LEARNING
        elif self.support >= 1:
            self.state = PatternState.OBSERVING


@dataclass
class UserPreference:
    """Nutzer-Präferenz (Licht, Temperatur, Musik, etc.)."""
    
    category: str  # light, climate, music, etc.
    key: str       # brightness, temperature, volume, etc.
    value: Any     # Der bevorzugte Wert
    zone: Optional[str] = None  # Optional: zonen-spezifisch
    context: Optional[str] = None  # Optional: kontext-spezifisch (Abend, Morgen)
    
    # Learning
    confidence: float = 0.0
    observations: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UserRoutine:
    """Nutzer-Routine (wiederkehrende Aktivität)."""
    
    id: str
    name: str
    description: str
    
    # Zeit
    time_pattern: Dict[str, Any]  # {"weekday": "mon-fri", "time": "07:00"}
    duration_minutes: int = 30
    
    # Aktionen
    actions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Zonen
    zones: List[str] = field(default_factory=list)
    
    # Learning
    confidence: float = 0.0
    occurrences: int = 0
    last_occurrence: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UserFeedback:
    """Feedback vom Nutzer (explizit oder implizit)."""
    
    id: str
    pattern_id: Optional[str]  # Falls Pattern-bezogen
    feedback_type: FeedbackType
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Kontext
    zone: Optional[str] = None
    module: Optional[str] = None
    action: Optional[Dict[str, Any]] = None
    
    # Details
    comment: Optional[str] = None  # Nutzer-Kommentar
    correction: Optional[Dict[str, Any]] = None  # Falls korrigiert
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContextHistory:
    """Kontext-History für Pattern-Mining."""
    
    timestamp: str
    zone: str
    modules: List[str]
    entities: Dict[str, Any]  # entity_id → value
    neurons: Dict[str, float]  # neuron_id → activation
    mood: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Central Habitus Storage
# =============================================================================

class HabitusStorage:
    """Zentrales Storage für Habitus (Patterns, User-Model, Context).
    
    Usage:
        storage = HabitusStorage()
        
        # Pattern speichern
        pattern = Pattern(id="p1", description="...", trigger={...}, action={...})
        storage.save_pattern(pattern)
        
        # Feedback geben
        storage.add_feedback(UserFeedback(pattern_id="p1", feedback_type=FeedbackType.ACCEPTED))
        
        # Patterns abfragen
        patterns = storage.get_patterns(zone="living", state=PatternState.STABLE)
    """
    
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or DB_PATH
        self._lock = threading.Lock()
        self._init_db()
        _LOGGER.info("HabitusStorage initialized at %s", self._db_path)
    
    def _init_db(self) -> None:
        """Datenbank-Tabellen erstellen."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.executescript("""
                    -- Patterns
                    CREATE TABLE IF NOT EXISTS patterns (
                        id TEXT PRIMARY KEY,
                        description TEXT NOT NULL,
                        trigger_json TEXT NOT NULL,
                        action_json TEXT NOT NULL,
                        confidence REAL DEFAULT 0.0,
                        support INTEGER DEFAULT 0,
                        acceptances INTEGER DEFAULT 0,
                        rejections INTEGER DEFAULT 0,
                        ignores INTEGER DEFAULT 0,
                        state TEXT DEFAULT 'observing',
                        zones_json TEXT DEFAULT '[]',
                        modules_json TEXT DEFAULT '[]',
                        contexts_json TEXT DEFAULT '[]',
                        created_at TEXT NOT NULL,
                        last_triggered TEXT,
                        last_learned TEXT
                    );
                    
                    -- User Preferences
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        category TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value_json TEXT NOT NULL,
                        zone TEXT,
                        context TEXT,
                        confidence REAL DEFAULT 0.0,
                        observations INTEGER DEFAULT 0,
                        PRIMARY KEY (category, key, zone, context)
                    );
                    
                    -- User Routines
                    CREATE TABLE IF NOT EXISTS user_routines (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL,
                        time_pattern_json TEXT NOT NULL,
                        duration_minutes INTEGER DEFAULT 30,
                        actions_json TEXT DEFAULT '[]',
                        zones_json TEXT DEFAULT '[]',
                        confidence REAL DEFAULT 0.0,
                        occurrences INTEGER DEFAULT 0,
                        last_occurrence TEXT
                    );
                    
                    -- User Feedback
                    CREATE TABLE IF NOT EXISTS user_feedback (
                        id TEXT PRIMARY KEY,
                        pattern_id TEXT,
                        feedback_type TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        zone TEXT,
                        module TEXT,
                        action_json TEXT,
                        comment TEXT,
                        correction_json TEXT,
                        FOREIGN KEY (pattern_id) REFERENCES patterns(id)
                    );
                    
                    -- Context History (rolling window, max 10000)
                    CREATE TABLE IF NOT EXISTS context_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        zone TEXT NOT NULL,
                        modules_json TEXT NOT NULL,
                        entities_json TEXT NOT NULL,
                        neurons_json TEXT,
                        mood TEXT,
                        events_json TEXT DEFAULT '[]'
                    );
                    
                    -- Indexes
                    CREATE INDEX IF NOT EXISTS idx_patterns_state ON patterns(state);
                    CREATE INDEX IF NOT EXISTS idx_patterns_zones ON patterns(zones_json);
                    CREATE INDEX IF NOT EXISTS idx_feedback_pattern ON user_feedback(pattern_id);
                    CREATE INDEX IF NOT EXISTS idx_context_timestamp ON context_history(timestamp);
                """)
                conn.commit()
            finally:
                conn.close()
    
    # ======================================================================
    # Patterns
    # ======================================================================
    
    def save_pattern(self, pattern: Pattern) -> None:
        """Pattern speichern (upsert)."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO patterns 
                    (id, description, trigger_json, action_json, confidence, support,
                     acceptances, rejections, ignores, state, zones_json, modules_json,
                     contexts_json, created_at, last_triggered, last_learned)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pattern.id,
                    pattern.description,
                    json.dumps(pattern.trigger),
                    json.dumps(pattern.action),
                    pattern.confidence,
                    pattern.support,
                    pattern.acceptances,
                    pattern.rejections,
                    pattern.ignores,
                    pattern.state.value,
                    json.dumps(pattern.zones),
                    json.dumps(pattern.modules),
                    json.dumps(pattern.contexts),
                    pattern.created_at,
                    pattern.last_triggered,
                    pattern.last_learned,
                ))
                conn.commit()
            finally:
                conn.close()
    
    def get_pattern(self, pattern_id: str) -> Optional[Pattern]:
        """Pattern by ID laden."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM patterns WHERE id = ?", (pattern_id,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                return Pattern(
                    id=row["id"],
                    description=row["description"],
                    trigger=json.loads(row["trigger_json"]),
                    action=json.loads(row["action_json"]),
                    confidence=row["confidence"],
                    support=row["support"],
                    acceptances=row["acceptances"],
                    rejections=row["rejections"],
                    ignores=row["ignores"],
                    state=PatternState(row["state"]),
                    zones=json.loads(row["zones_json"]),
                    modules=json.loads(row["modules_json"]),
                    contexts=json.loads(row["contexts_json"]),
                    created_at=row["created_at"],
                    last_triggered=row["last_triggered"],
                    last_learned=row["last_learned"],
                )
            finally:
                conn.close()
    
    def get_patterns(
        self,
        zone: Optional[str] = None,
        state: Optional[PatternState] = None,
        min_confidence: float = 0.0,
    ) -> List[Pattern]:
        """Patterns filtern (by zone, state, confidence)."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                
                query = "SELECT * FROM patterns WHERE confidence >= ?"
                params = [min_confidence]
                
                if zone:
                    query += " AND zones_json LIKE ?"
                    params.append(f'%"{zone}"%')
                
                if state:
                    query += " AND state = ?"
                    params.append(state.value)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [
                    Pattern(
                        id=row["id"],
                        description=row["description"],
                        trigger=json.loads(row["trigger_json"]),
                        action=json.loads(row["action_json"]),
                        confidence=row["confidence"],
                        support=row["support"],
                        acceptances=row["acceptances"],
                        rejections=row["rejections"],
                        ignores=row["ignores"],
                        state=PatternState(row["state"]),
                        zones=json.loads(row["zones_json"]),
                        modules=json.loads(row["modules_json"]),
                        contexts=json.loads(row["contexts_json"]),
                        created_at=row["created_at"],
                        last_triggered=row["last_triggered"],
                        last_learned=row["last_learned"],
                    )
                    for row in rows
                ]
            finally:
                conn.close()
    
    def delete_pattern(self, pattern_id: str) -> bool:
        """Pattern löschen."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.execute("DELETE FROM patterns WHERE id = ?", (pattern_id,))
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()
    
    # ======================================================================
    # User Preferences
    # ======================================================================
    
    def save_preference(self, pref: UserPreference) -> None:
        """Nutzer-Präferenz speichern."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO user_preferences 
                    (category, key, value_json, zone, context, confidence, observations)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    pref.category,
                    pref.key,
                    json.dumps(pref.value),
                    pref.zone,
                    pref.context,
                    pref.confidence,
                    pref.observations,
                ))
                conn.commit()
            finally:
                conn.close()
    
    def get_preferences(
        self,
        category: Optional[str] = None,
        zone: Optional[str] = None,
    ) -> List[UserPreference]:
        """Nutzer-Präferenzen laden."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                
                query = "SELECT * FROM user_preferences"
                params = []
                
                if category:
                    query += " WHERE category = ?"
                    params.append(category)
                
                if zone:
                    query += " AND zone = ?" if not category else " AND zone = ?"
                    params.append(zone)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [
                    UserPreference(
                        category=row["category"],
                        key=row["key"],
                        value=json.loads(row["value_json"]),
                        zone=row["zone"],
                        context=row["context"],
                        confidence=row["confidence"],
                        observations=row["observations"],
                    )
                    for row in rows
                ]
            finally:
                conn.close()
    
    # ======================================================================
    # User Routines
    # ======================================================================
    
    def save_routine(self, routine: UserRoutine) -> None:
        """Nutzer-Routine speichern."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO user_routines 
                    (id, name, description, time_pattern_json, duration_minutes,
                     actions_json, zones_json, confidence, occurrences, last_occurrence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    routine.id,
                    routine.name,
                    routine.description,
                    json.dumps(routine.time_pattern),
                    routine.duration_minutes,
                    json.dumps(routine.actions),
                    json.dumps(routine.zones),
                    routine.confidence,
                    routine.occurrences,
                    routine.last_occurrence,
                ))
                conn.commit()
            finally:
                conn.close()
    
    def get_routines(self) -> List[UserRoutine]:
        """Alle Nutzer-Routinen laden."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM user_routines")
                rows = cursor.fetchall()
                
                return [
                    UserRoutine(
                        id=row["id"],
                        name=row["name"],
                        description=row["description"],
                        time_pattern=json.loads(row["time_pattern_json"]),
                        duration_minutes=row["duration_minutes"],
                        actions=json.loads(row["actions_json"]),
                        zones=json.loads(row["zones_json"]),
                        confidence=row["confidence"],
                        occurrences=row["occurrences"],
                        last_occurrence=row["last_occurrence"],
                    )
                    for row in rows
                ]
            finally:
                conn.close()
    
    # ======================================================================
    # User Feedback
    # ======================================================================
    
    def add_feedback(self, feedback: UserFeedback) -> None:
        """Feedback hinzufügen."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute("""
                    INSERT INTO user_feedback 
                    (id, pattern_id, feedback_type, timestamp, zone, module, action_json, comment, correction_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    feedback.id,
                    feedback.pattern_id,
                    feedback.feedback_type.value,
                    feedback.timestamp,
                    feedback.zone,
                    feedback.module,
                    json.dumps(feedback.action) if feedback.action else None,
                    feedback.comment,
                    json.dumps(feedback.correction) if feedback.correction else None,
                ))
                
                # Pattern-Feedback zählen updaten
                if feedback.pattern_id:
                    if feedback.feedback_type == FeedbackType.ACCEPTED:
                        conn.execute(
                            "UPDATE patterns SET acceptances = acceptances + 1 WHERE id = ?",
                            (feedback.pattern_id,)
                        )
                    elif feedback.feedback_type == FeedbackType.REJECTED:
                        conn.execute(
                            "UPDATE patterns SET rejections = rejections + 1 WHERE id = ?",
                            (feedback.pattern_id,)
                        )
                    elif feedback.feedback_type == FeedbackType.IGNORED:
                        conn.execute(
                            "UPDATE patterns SET ignores = ignores + 1 WHERE id = ?",
                            (feedback.pattern_id,)
                        )
                
                conn.commit()
            finally:
                conn.close()
    
    def get_feedback(
        self,
        pattern_id: Optional[str] = None,
        feedback_type: Optional[FeedbackType] = None,
        limit: int = 100,
    ) -> List[UserFeedback]:
        """Feedback laden (gefiltert)."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                
                query = "SELECT * FROM user_feedback"
                params = []
                conditions = []
                
                if pattern_id:
                    conditions.append("pattern_id = ?")
                    params.append(pattern_id)
                
                if feedback_type:
                    conditions.append("feedback_type = ?")
                    params.append(feedback_type.value)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [
                    UserFeedback(
                        id=row["id"],
                        pattern_id=row["pattern_id"],
                        feedback_type=FeedbackType(row["feedback_type"]),
                        timestamp=row["timestamp"],
                        zone=row["zone"],
                        module=row["module"],
                        action=json.loads(row["action_json"]) if row["action_json"] else None,
                        comment=row["comment"],
                        correction=json.loads(row["correction_json"]) if row["correction_json"] else None,
                    )
                    for row in rows
                ]
            finally:
                conn.close()
    
    # ======================================================================
    # Context History
    # ======================================================================
    
    def add_context(self, context: ContextHistory) -> None:
        """Kontext zur History hinzufügen."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute("""
                    INSERT INTO context_history 
                    (timestamp, zone, modules_json, entities_json, neurons_json, mood, events_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    context.timestamp,
                    context.zone,
                    json.dumps(context.modules),
                    json.dumps(context.entities),
                    json.dumps(context.neurons) if context.neurons else None,
                    context.mood,
                    json.dumps(context.events),
                ))
                
                # Rolling window: Alte Einträge löschen (max 10000)
                conn.execute("""
                    DELETE FROM context_history 
                    WHERE id NOT IN (
                        SELECT id FROM context_history ORDER BY timestamp DESC LIMIT 10000
                    )
                """)
                
                conn.commit()
            finally:
                conn.close()
    
    def get_context_history(
        self,
        zone: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 1000,
    ) -> List[ContextHistory]:
        """Kontext-History laden."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                
                query = "SELECT * FROM context_history"
                params = []
                conditions = []
                
                if zone:
                    conditions.append("zone = ?")
                    params.append(zone)
                
                if start_time:
                    conditions.append("timestamp >= ?")
                    params.append(start_time)
                
                if end_time:
                    conditions.append("timestamp <= ?")
                    params.append(end_time)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [
                    ContextHistory(
                        timestamp=row["timestamp"],
                        zone=row["zone"],
                        modules=json.loads(row["modules_json"]),
                        entities=json.loads(row["entities_json"]),
                        neurons=json.loads(row["neurons_json"]) if row["neurons_json"] else None,
                        mood=row["mood"],
                        events=json.loads(row["events_json"]) if row["events_json"] else None,
                    )
                    for row in rows
                ]
            finally:
                conn.close()
    
    # ======================================================================
    # Analytics
    # ======================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Statistiken über Habitus-Storage."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                
                stats = {}
                
                # Patterns
                cursor = conn.execute("SELECT COUNT(*) as count FROM patterns")
                stats["patterns_total"] = cursor.fetchone()["count"]
                
                cursor = conn.execute("SELECT state, COUNT(*) as count FROM patterns GROUP BY state")
                stats["patterns_by_state"] = {row["state"]: row["count"] for row in cursor.fetchall()}
                
                # Preferences
                cursor = conn.execute("SELECT COUNT(*) as count FROM user_preferences")
                stats["preferences_total"] = cursor.fetchone()["count"]
                
                # Routines
                cursor = conn.execute("SELECT COUNT(*) as count FROM user_routines")
                stats["routines_total"] = cursor.fetchone()["count"]
                
                # Feedback
                cursor = conn.execute("SELECT feedback_type, COUNT(*) as count FROM user_feedback GROUP BY feedback_type")
                stats["feedback_by_type"] = {row["feedback_type"]: row["count"] for row in cursor.fetchall()}
                
                # Context History
                cursor = conn.execute("SELECT COUNT(*) as count FROM context_history")
                stats["context_history_total"] = cursor.fetchone()["count"]
                
                return stats
            finally:
                conn.close()


# =============================================================================
# Singleton
# =============================================================================

_storage_instance: Optional[HabitusStorage] = None
_storage_lock = threading.Lock()


def get_habitus_storage(db_path: Optional[str] = None) -> HabitusStorage:
    """Singleton-Zugriff auf HabitusStorage."""
    global _storage_instance
    
    if _storage_instance is None:
        with _storage_lock:
            if _storage_instance is None:
                _storage_instance = HabitusStorage(db_path)
    
    return _storage_instance
