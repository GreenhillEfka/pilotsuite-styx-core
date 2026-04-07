"""
User Store for PilotSuite Core.

Persistent storage for user profiles and notification preferences.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..users.contracts import (
    UserProfileV1,
    NotificationPreferencesV1,
    ChannelPreferencesV1,
    UserSettingsV1,
    NotificationChannel,
    NotificationCategory,
    NotificationPriority,
    DeliveryMode,
)


class UserStore:
    """
    SQLite-backed store for user profiles and preferences.
    """
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                timezone TEXT NOT NULL DEFAULT 'Europe/Berlin',
                language TEXT NOT NULL DEFAULT 'de',
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                revision INTEGER NOT NULL DEFAULT 1
            )
        """)
        
        # Notification preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_preferences (
                user_id TEXT PRIMARY KEY,
                global_enabled INTEGER NOT NULL DEFAULT 1,
                global_quiet_hours_start TEXT,
                global_quiet_hours_end TEXT,
                do_not_disturb INTEGER NOT NULL DEFAULT 0,
                do_not_disturb_until TEXT,
                default_channel TEXT NOT NULL DEFAULT 'telegram',
                digest_schedule TEXT,
                digest_enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT,
                revision INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Channel preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channel_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                delivery_mode TEXT NOT NULL DEFAULT 'immediate',
                min_priority TEXT NOT NULL DEFAULT 'low',
                allowed_categories TEXT NOT NULL DEFAULT '[]',
                quiet_hours_start TEXT,
                quiet_hours_end TEXT,
                max_per_hour INTEGER,
                max_per_day INTEGER,
                UNIQUE(user_id, channel),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_channel_prefs_user 
            ON channel_preferences(user_id)
        """)
        
        conn.commit()
        conn.close()
    
    def get_profile(self, user_id: str) -> Optional[UserProfileV1]:
        """Get user profile by ID."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return UserProfileV1(
            user_id=row[0],
            name=row[1],
            email=row[2],
            timezone=row[3],
            language=row[4],
            created_at=datetime.fromisoformat(row[5]) if row[5] else None,
            updated_at=datetime.fromisoformat(row[6]) if row[6] else None,
            metadata=json.loads(row[7]),
            revision=row[8],
        )
    
    def get_preferences(self, user_id: str) -> Optional[NotificationPreferencesV1]:
        """Get notification preferences by user ID."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM notification_preferences WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        # Load channel preferences
        cursor.execute("SELECT * FROM channel_preferences WHERE user_id = ?", (user_id,))
        channel_rows = cursor.fetchall()
        conn.close()
        
        channel_prefs = {}
        for ch_row in channel_rows:
            channel_prefs[ch_row[2]] = ChannelPreferencesV1(
                channel=NotificationChannel(ch_row[2]),
                enabled=bool(ch_row[3]),
                delivery_mode=DeliveryMode(ch_row[4]),
                min_priority=NotificationPriority(ch_row[5]),
                allowed_categories=[NotificationCategory(c) for c in json.loads(ch_row[6])],
                quiet_hours_start=ch_row[7],
                quiet_hours_end=ch_row[8],
                max_per_hour=ch_row[9],
                max_per_day=ch_row[10],
            )
        
        return NotificationPreferencesV1(
            user_id=row[0],
            global_enabled=bool(row[1]),
            global_quiet_hours_start=row[2],
            global_quiet_hours_end=row[3],
            do_not_disturb=bool(row[4]),
            do_not_disturb_until=datetime.fromisoformat(row[5]) if row[5] else None,
            default_channel=NotificationChannel(row[6]),
            channel_preferences=channel_prefs,
            digest_schedule=row[7],
            digest_enabled=bool(row[8]),
            updated_at=datetime.fromisoformat(row[9]) if row[9] else None,
            revision=row[10],
        )
    
    def get_settings(self, user_id: str) -> Optional[UserSettingsV1]:
        """Get combined user settings (profile + preferences)."""
        profile = self.get_profile(user_id)
        preferences = self.get_preferences(user_id)
        
        if not profile or not preferences:
            return None
        
        return UserSettingsV1(profile=profile, preferences=preferences)
    
    def upsert_profile(self, profile: UserProfileV1) -> UserProfileV1:
        """Create or update user profile."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc)
        profile.updated_at = now
        
        # Check if exists to determine revision
        cursor.execute("SELECT revision FROM users WHERE user_id = ?", (profile.user_id,))
        existing = cursor.fetchone()
        profile.revision = (existing[0] + 1) if existing else 1
        
        cursor.execute("""
            INSERT INTO users (user_id, name, email, timezone, language, created_at, updated_at, metadata, revision)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name=excluded.name,
                email=excluded.email,
                timezone=excluded.timezone,
                language=excluded.language,
                updated_at=excluded.updated_at,
                metadata=excluded.metadata,
                revision=excluded.revision
        """, (
            profile.user_id,
            profile.name,
            profile.email,
            profile.timezone,
            profile.language,
            profile.created_at.isoformat() if profile.created_at else now.isoformat(),
            profile.updated_at.isoformat(),
            json.dumps(profile.metadata),
            profile.revision,
        ))
        
        conn.commit()
        conn.close()
        
        return profile
    
    def upsert_preferences(self, preferences: NotificationPreferencesV1) -> NotificationPreferencesV1:
        """Create or update notification preferences."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc)
        preferences.updated_at = now
        
        # Check if exists to determine revision
        cursor.execute("SELECT revision FROM notification_preferences WHERE user_id = ?", (preferences.user_id,))
        existing = cursor.fetchone()
        preferences.revision = (existing[0] + 1) if existing else 1
        
        cursor.execute("""
            INSERT INTO notification_preferences (
                user_id, global_enabled, global_quiet_hours_start, global_quiet_hours_end,
                do_not_disturb, do_not_disturb_until, default_channel,
                digest_schedule, digest_enabled, updated_at, revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                global_enabled=excluded.global_enabled,
                global_quiet_hours_start=excluded.global_quiet_hours_start,
                global_quiet_hours_end=excluded.global_quiet_hours_end,
                do_not_disturb=excluded.do_not_disturb,
                do_not_disturb_until=excluded.do_not_disturb_until,
                default_channel=excluded.default_channel,
                digest_schedule=excluded.digest_schedule,
                digest_enabled=excluded.digest_enabled,
                updated_at=excluded.updated_at,
                revision=excluded.revision
        """, (
            preferences.user_id,
            1 if preferences.global_enabled else 0,
            preferences.global_quiet_hours_start,
            preferences.global_quiet_hours_end,
            1 if preferences.do_not_disturb else 0,
            preferences.do_not_disturb_until.isoformat() if preferences.do_not_disturb_until else None,
            preferences.default_channel.value,
            preferences.digest_schedule,
            1 if preferences.digest_enabled else 0,
            preferences.updated_at.isoformat(),
            preferences.revision,
        ))
        
        # Upsert channel preferences
        for channel, ch_prefs in preferences.channel_preferences.items():
            cursor.execute("""
                INSERT INTO channel_preferences (
                    user_id, channel, enabled, delivery_mode, min_priority,
                    allowed_categories, quiet_hours_start, quiet_hours_end,
                    max_per_hour, max_per_day
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, channel) DO UPDATE SET
                    enabled=excluded.enabled,
                    delivery_mode=excluded.delivery_mode,
                    min_priority=excluded.min_priority,
                    allowed_categories=excluded.allowed_categories,
                    quiet_hours_start=excluded.quiet_hours_start,
                    quiet_hours_end=excluded.quiet_hours_end,
                    max_per_hour=excluded.max_per_hour,
                    max_per_day=excluded.max_per_day
            """, (
                preferences.user_id,
                ch_prefs.channel.value,
                1 if ch_prefs.enabled else 0,
                ch_prefs.delivery_mode.value,
                ch_prefs.min_priority.value,
                json.dumps([c.value for c in ch_prefs.allowed_categories]),
                ch_prefs.quiet_hours_start,
                ch_prefs.quiet_hours_end,
                ch_prefs.max_per_hour,
                ch_prefs.max_per_day,
            ))
        
        conn.commit()
        conn.close()
        
        return preferences
    
    def update_preferences_dnd(self, user_id: str, do_not_disturb: bool, until: Optional[datetime] = None) -> Optional[NotificationPreferencesV1]:
        """Update do-not-disturb status."""
        prefs = self.get_preferences(user_id)
        if not prefs:
            return None
        
        prefs.do_not_disturb = do_not_disturb
        prefs.do_not_disturb_until = until
        return self.upsert_preferences(prefs)
    
    def update_channel_preference(
        self,
        user_id: str,
        channel: NotificationChannel,
        enabled: Optional[bool] = None,
        delivery_mode: Optional[DeliveryMode] = None,
        min_priority: Optional[NotificationPriority] = None,
    ) -> Optional[NotificationPreferencesV1]:
        """Update a specific channel preference."""
        prefs = self.get_preferences(user_id)
        if not prefs:
            return None
        
        if channel not in prefs.channel_preferences:
            prefs.channel_preferences[channel.value] = ChannelPreferencesV1(channel=channel)
        
        ch_prefs = prefs.channel_preferences[channel.value]
        
        if enabled is not None:
            ch_prefs.enabled = enabled
        if delivery_mode is not None:
            ch_prefs.delivery_mode = delivery_mode
        if min_priority is not None:
            ch_prefs.min_priority = min_priority
        
        return self.upsert_preferences(prefs)
    
    def delete_user(self, user_id: str) -> bool:
        """Delete user and all associated data."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM channel_preferences WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM notification_preferences WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
