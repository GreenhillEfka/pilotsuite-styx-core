"""Calendar Analytics Surface — Usage, Patterns, Effectiveness.

Follows the same pattern as other analytics surfaces (Slices 46-62):
- Usage history tracking
- Zone/Pattern analysis
- Effectiveness metrics
- Revision tracking for delta polling
"""

import sqlite3
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class CalendarEventType(str, Enum):
    """Calendar event types for analytics."""
    MEETING = "meeting"
    TASK = "task"
    FOCUS_BLOCK = "focus_block"
    BREAK = "break"
    LUNCH = "lunch"
    PERSONAL = "personal"
    OTHER = "other"


class SuggestionType(str, Enum):
    """Proactive suggestion types."""
    BREAK_REMINDER = "break_reminder"
    MEETING_PREP = "meeting_prep"
    FOCUS_BLOCK = "focus_block"
    ALARM_ADJUSTMENT = "alarm_adjustment"
    LIGHTING_SCENE = "lighting_scene"
    STRESS_RELIEF = "stress_relief"
    LUNCH_REMINDER = "lunch_reminder"
    END_OF_DAY_WRAP = "end_of_day_wrap"


class SuggestionAction(str, Enum):
    """Suggestion user actions."""
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    EXPIRED = "expired"
    PENDING = "pending"


@dataclass
class CalendarUsageEntry:
    """Single calendar usage event."""
    entry_id: str
    timestamp: str
    event_type: str
    duration_minutes: int
    source: str  # ha_calendar, smart_recommend, mood_recommend
    zone_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CalendarUsageHistory:
    """Aggregated usage history."""
    entries: List[CalendarUsageEntry]
    total_count: int
    date_range: Dict[str, str]
    revision: int


@dataclass
class CalendarPatternEntry:
    """Pattern analysis for a specific dimension."""
    dimension: str  # event_type, hour, day_of_week, zone
    value: str
    count: int
    percentage: float
    avg_duration_minutes: float
    peak_hours: List[int] = field(default_factory=list)


@dataclass
class CalendarPatterns:
    """Aggregated pattern analysis."""
    by_event_type: List[CalendarPatternEntry]
    by_hour: List[CalendarPatternEntry]
    by_day_of_week: List[CalendarPatternEntry]
    by_zone: List[CalendarPatternEntry]
    revision: int


@dataclass
class CalendarEffectivenessMetrics:
    """Effectiveness metrics for calendar features."""
    total_events: int
    smart_recommendations_count: int
    mood_recommendations_count: int
    suggestions_generated: int
    suggestions_accepted: int
    suggestions_dismissed: int
    acceptance_rate: float
    avg_lead_time_minutes: float
    focus_block_utilization: float
    break_compliance_rate: float
    revision: int


@dataclass
class CalendarAnalyticsSummary:
    """Summary of all calendar analytics."""
    usage: CalendarUsageHistory
    patterns: CalendarPatterns
    effectiveness: CalendarEffectivenessMetrics
    generated_at: str
    revision: int


class CalendarAnalyticsStore:
    """SQLite-backed analytics store for calendar surface."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path(__file__).parent.parent / "storage" / "calendar_analytics.db")
        self.db_path = db_path
        self._revision = 0
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS usage_entries (
                    entry_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    zone_id TEXT,
                    user_id TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                
                CREATE TABLE IF NOT EXISTS suggestion_events (
                    event_id TEXT PRIMARY KEY,
                    suggestion_id TEXT NOT NULL,
                    suggestion_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    zone_id TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                
                CREATE TABLE IF NOT EXISTS analytics_revision (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    revision INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                
                CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_entries(timestamp);
                CREATE INDEX IF NOT EXISTS idx_usage_event_type ON usage_entries(event_type);
                CREATE INDEX IF NOT EXISTS idx_usage_zone ON usage_entries(zone_id);
                CREATE INDEX IF NOT EXISTS idx_suggestion_type ON suggestion_events(suggestion_type);
                CREATE INDEX IF NOT EXISTS idx_suggestion_action ON suggestion_events(action);
                
                INSERT OR IGNORE INTO analytics_revision (id, revision) VALUES (1, 0);
            """)
            conn.commit()
    
    def _increment_revision(self) -> int:
        """Increment and return new revision."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE analytics_revision SET revision = revision + 1, updated_at = datetime('now') WHERE id = 1")
            conn.commit()
            cursor = conn.execute("SELECT revision FROM analytics_revision WHERE id = 1")
            self._revision = cursor.fetchone()[0]
            return self._revision
    
    def _get_revision(self) -> int:
        """Get current revision."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT revision FROM analytics_revision WHERE id = 1")
            return cursor.fetchone()[0]
    
    def add_usage_entry(self, entry: CalendarUsageEntry) -> None:
        """Record a calendar usage event."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO usage_entries 
                (entry_id, timestamp, event_type, duration_minutes, source, zone_id, user_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.entry_id,
                entry.timestamp,
                entry.event_type,
                entry.duration_minutes,
                entry.source,
                entry.zone_id,
                entry.user_id,
                json.dumps(entry.metadata),
            ))
            conn.commit()
            self._increment_revision()
    
    def add_suggestion_event(self, suggestion_id: str, suggestion_type: str, action: str, 
                            zone_id: Optional[str] = None, metadata: Optional[Dict] = None) -> None:
        """Record a suggestion action (accept/dismiss/expire)."""
        event_id = f"{suggestion_id}_{action}_{datetime.now().isoformat()}"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO suggestion_events 
                (event_id, suggestion_id, suggestion_type, action, timestamp, zone_id, metadata)
                VALUES (?, ?, ?, ?, datetime('now'), ?, ?)
            """, (
                event_id,
                suggestion_id,
                suggestion_type,
                action,
                zone_id,
                json.dumps(metadata or {}),
            ))
            conn.commit()
            self._increment_revision()
    
    def build_usage_history(self, start_date: Optional[str] = None, end_date: Optional[str] = None,
                           limit: int = 1000) -> CalendarUsageHistory:
        """Build usage history for date range."""
        now = datetime.now()
        if not start_date:
            start_date = (now - timedelta(days=30)).isoformat()
        if not end_date:
            end_date = now.isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT entry_id, timestamp, event_type, duration_minutes, source, zone_id, user_id, metadata
                FROM usage_entries
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (start_date, end_date, limit))
            
            entries = []
            for row in cursor.fetchall():
                entries.append(CalendarUsageEntry(
                    entry_id=row["entry_id"],
                    timestamp=row["timestamp"],
                    event_type=row["event_type"],
                    duration_minutes=row["duration_minutes"],
                    source=row["source"],
                    zone_id=row["zone_id"],
                    user_id=row["user_id"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                ))
        
        return CalendarUsageHistory(
            entries=entries,
            total_count=len(entries),
            date_range={"start": start_date, "end": end_date},
            revision=self._get_revision(),
        )
    
    def build_patterns(self) -> CalendarPatterns:
        """Build pattern analysis from usage data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # By event type
            type_cursor = conn.execute("""
                SELECT event_type, COUNT(*) as count, AVG(duration_minutes) as avg_duration
                FROM usage_entries
                GROUP BY event_type
                ORDER BY count DESC
            """)
            total = sum(row["count"] for row in type_cursor.fetchall())
            type_cursor = conn.execute("""
                SELECT event_type, COUNT(*) as count, AVG(duration_minutes) as avg_duration
                FROM usage_entries
                GROUP BY event_type
                ORDER BY count DESC
            """)
            by_event_type = [
                CalendarPatternEntry(
                    dimension="event_type",
                    value=row["event_type"],
                    count=row["count"],
                    percentage=(row["count"] / total * 100) if total > 0 else 0,
                    avg_duration_minutes=row["avg_duration"] or 0,
                )
                for row in type_cursor.fetchall()
            ]
            
            # By hour
            hour_cursor = conn.execute("""
                SELECT strftime('%H', timestamp) as hour, COUNT(*) as count, AVG(duration_minutes) as avg_duration
                FROM usage_entries
                GROUP BY hour
                ORDER BY hour
            """)
            by_hour = [
                CalendarPatternEntry(
                    dimension="hour",
                    value=row["hour"],
                    count=row["count"],
                    percentage=0,
                    avg_duration_minutes=row["avg_duration"] or 0,
                    peak_hours=[int(row["hour"])],
                )
                for row in hour_cursor.fetchall()
            ]
            
            # By day of week
            dow_cursor = conn.execute("""
                SELECT strftime('%w', timestamp) as dow, COUNT(*) as count, AVG(duration_minutes) as avg_duration
                FROM usage_entries
                GROUP BY dow
                ORDER BY dow
            """)
            day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
            by_day_of_week = [
                CalendarPatternEntry(
                    dimension="day_of_week",
                    value=day_names[int(row["dow"])],
                    count=row["count"],
                    percentage=0,
                    avg_duration_minutes=row["avg_duration"] or 0,
                )
                for row in dow_cursor.fetchall()
            ]
            
            # By zone
            zone_cursor = conn.execute("""
                SELECT zone_id, COUNT(*) as count, AVG(duration_minutes) as avg_duration
                FROM usage_entries
                WHERE zone_id IS NOT NULL
                GROUP BY zone_id
                ORDER BY count DESC
            """)
            by_zone = [
                CalendarPatternEntry(
                    dimension="zone",
                    value=row["zone_id"] or "unknown",
                    count=row["count"],
                    percentage=0,
                    avg_duration_minutes=row["avg_duration"] or 0,
                )
                for row in zone_cursor.fetchall()
            ]
        
        return CalendarPatterns(
            by_event_type=by_event_type,
            by_hour=by_hour,
            by_day_of_week=by_day_of_week,
            by_zone=by_zone,
            revision=self._get_revision(),
        )
    
    def get_effectiveness_metrics(self) -> CalendarEffectivenessMetrics:
        """Calculate effectiveness metrics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Total events
            cursor = conn.execute("SELECT COUNT(*) as total FROM usage_entries")
            total_events = cursor.fetchone()["total"]
            
            # Smart recommendations
            cursor = conn.execute("SELECT COUNT(*) as count FROM usage_entries WHERE source = 'smart_recommend'")
            smart_count = cursor.fetchone()["count"]
            
            # Mood recommendations
            cursor = conn.execute("SELECT COUNT(*) as count FROM usage_entries WHERE source = 'mood_recommend'")
            mood_count = cursor.fetchone()["count"]
            
            # Suggestions
            cursor = conn.execute("SELECT COUNT(*) as count FROM suggestion_events")
            suggestions_generated = cursor.fetchone()["count"]
            
            cursor = conn.execute("SELECT COUNT(*) as count FROM suggestion_events WHERE action = 'accepted'")
            suggestions_accepted = cursor.fetchone()["count"]
            
            cursor = conn.execute("SELECT COUNT(*) as count FROM suggestion_events WHERE action = 'dismissed'")
            suggestions_dismissed = cursor.fetchone()["count"]
            
            acceptance_rate = (suggestions_accepted / suggestions_generated * 100) if suggestions_generated > 0 else 0
            
            # Focus block utilization (events during peak hours 9-12)
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM usage_entries 
                WHERE strftime('%H', timestamp) BETWEEN '09' AND '12'
                AND event_type = 'focus_block'
            """)
            focus_count = cursor.fetchone()["count"]
            focus_utilization = (focus_count / total_events * 100) if total_events > 0 else 0
            
            # Break compliance
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM usage_entries WHERE event_type = 'break'
            """)
            break_count = cursor.fetchone()["count"]
            break_compliance = (break_count / total_events * 100) if total_events > 0 else 0
        
        return CalendarEffectivenessMetrics(
            total_events=total_events,
            smart_recommendations_count=smart_count,
            mood_recommendations_count=mood_count,
            suggestions_generated=suggestions_generated,
            suggestions_accepted=suggestions_accepted,
            suggestions_dismissed=suggestions_dismissed,
            acceptance_rate=acceptance_rate,
            avg_lead_time_minutes=0,  # Would need timestamp comparison
            focus_block_utilization=focus_utilization,
            break_compliance_rate=break_compliance,
            revision=self._get_revision(),
        )
    
    def build_summary(self) -> CalendarAnalyticsSummary:
        """Build complete analytics summary."""
        return CalendarAnalyticsSummary(
            usage=self.build_usage_history(),
            patterns=self.build_patterns(),
            effectiveness=self.get_effectiveness_metrics(),
            generated_at=datetime.now().isoformat(),
            revision=self._get_revision(),
        )
