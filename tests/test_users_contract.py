"""
Contract tests for User Profile and Preferences API and Store.
"""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from copilot_core.users.contracts import (
    UserProfileV1,
    NotificationPreferencesV1,
    ChannelPreferencesV1,
    UserSettingsV1,
    NotificationChannel,
    NotificationCategory,
    NotificationPriority,
    DeliveryMode,
)
from copilot_core.users.store import UserStore


@pytest.fixture
def temp_db(tmp_path):
    """Create temporary database path."""
    return str(tmp_path / "users.db")


@pytest.fixture
def store(temp_db):
    """Create UserStore instance."""
    return UserStore(temp_db)


class TestUserContracts:
    """Test user contract classes."""
    
    def test_user_profile_v1_creation(self):
        """Test UserProfileV1 can be created."""
        profile = UserProfileV1(
            user_id="user-123",
            name="Test User",
            email="test@example.com",
            timezone="Europe/Berlin",
            language="de",
        )
        
        assert profile.user_id == "user-123"
        assert profile.name == "Test User"
        assert profile.timezone == "Europe/Berlin"
        assert profile.language == "de"
    
    def test_user_profile_to_dict(self):
        """Test UserProfileV1 serializes correctly."""
        now = datetime.now(timezone.utc)
        profile = UserProfileV1(
            user_id="user-456",
            name="Test",
            email="test@example.com",
            timezone="America/New_York",
            language="en",
            created_at=now,
            updated_at=now,
            metadata={"key": "value"},
            revision=2,
        )
        
        d = profile.to_dict()
        
        assert d["user_id"] == "user-456"
        assert d["timezone"] == "America/New_York"
        assert d["metadata"]["key"] == "value"
        assert d["revision"] == 2
    
    def test_channel_preferences_v1(self):
        """Test ChannelPreferencesV1 structure."""
        prefs = ChannelPreferencesV1(
            channel=NotificationChannel.TELEGRAM,
            enabled=True,
            delivery_mode=DeliveryMode.BATCHED,
            min_priority=NotificationPriority.HIGH,
            allowed_categories=[NotificationCategory.ALERT, NotificationCategory.ACTION_REQUIRED],
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            max_per_hour=5,
            max_per_day=50,
        )
        
        d = prefs.to_dict()
        
        assert d["channel"] == "telegram"
        assert d["delivery_mode"] == "batched"
        assert d["min_priority"] == "high"
        assert d["quiet_hours_start"] == "22:00"
        assert d["max_per_hour"] == 5
    
    def test_notification_preferences_v1(self):
        """Test NotificationPreferencesV1 structure."""
        now = datetime.now(timezone.utc)
        prefs = NotificationPreferencesV1(
            user_id="user-789",
            global_enabled=True,
            global_quiet_hours_start="23:00",
            global_quiet_hours_end="06:00",
            do_not_disturb=False,
            default_channel=NotificationChannel.PUSH,
            digest_enabled=True,
            digest_schedule="0 8 * * *",
            updated_at=now,
            revision=3,
        )
        
        d = prefs.to_dict()
        
        assert d["user_id"] == "user-789"
        assert d["global_enabled"] is True
        assert d["default_channel"] == "push"
        assert d["digest_schedule"] == "0 8 * * *"
        assert d["revision"] == 3
    
    def test_user_settings_v1(self):
        """Test UserSettingsV1 combines profile and preferences."""
        profile = UserProfileV1(user_id="user-combo")
        prefs = NotificationPreferencesV1(user_id="user-combo")
        
        settings = UserSettingsV1(profile=profile, preferences=prefs)
        
        d = settings.to_dict()
        
        assert "profile" in d
        assert "preferences" in d
        assert d["profile"]["user_id"] == "user-combo"
        assert d["preferences"]["user_id"] == "user-combo"
    
    def test_enums(self):
        """Test all enum values."""
        assert len(NotificationChannel) == 6
        assert len(NotificationCategory) == 6
        assert len(NotificationPriority) == 4
        assert len(DeliveryMode) == 4


class TestUserStore:
    """Test UserStore operations."""
    
    def test_store_initialization(self, store):
        """Test store initializes correctly."""
        assert str(store.db_path).endswith("users.db")
    
    def test_upsert_profile(self, store):
        """Test creating/updating user profile."""
        profile = UserProfileV1(
            user_id="test-user",
            name="Test User",
            email="test@example.com",
            timezone="Europe/Berlin",
            language="de",
        )
        
        result = store.upsert_profile(profile)
        
        assert result.user_id == "test-user"
        assert result.revision == 1
        
        # Update
        profile.name = "Updated Name"
        result2 = store.upsert_profile(profile)
        
        assert result2.revision == 2
        assert result2.name == "Updated Name"
    
    def test_get_profile(self, store):
        """Test retrieving user profile."""
        profile = UserProfileV1(
            user_id="get-user",
            name="Get Test",
            email="get@example.com",
        )
        
        store.upsert_profile(profile)
        retrieved = store.get_profile("get-user")
        
        assert retrieved is not None
        assert retrieved.name == "Get Test"
        assert retrieved.email == "get@example.com"
    
    def test_get_profile_not_found(self, store):
        """Test retrieving non-existent profile."""
        result = store.get_profile("non-existent")
        assert result is None
    
    def test_upsert_preferences(self, store):
        """Test creating/updating notification preferences."""
        prefs = NotificationPreferencesV1(
            user_id="prefs-user",
            global_enabled=True,
            default_channel=NotificationChannel.TELEGRAM,
        )
        
        result = store.upsert_preferences(prefs)
        
        assert result.user_id == "prefs-user"
        assert result.revision == 1
        assert result.global_enabled is True
    
    def test_get_preferences(self, store):
        """Test retrieving notification preferences."""
        prefs = NotificationPreferencesV1(
            user_id="get-prefs-user",
            global_enabled=False,
            do_not_disturb=True,
            default_channel=NotificationChannel.EMAIL,
        )
        
        store.upsert_preferences(prefs)
        retrieved = store.get_preferences("get-prefs-user")
        
        assert retrieved is not None
        assert retrieved.global_enabled is False
        assert retrieved.do_not_disturb is True
        assert retrieved.default_channel == NotificationChannel.EMAIL
    
    def test_get_preferences_not_found(self, store):
        """Test retrieving non-existent preferences."""
        result = store.get_preferences("non-existent")
        assert result is None
    
    def test_channel_preferences_persist(self, store):
        """Test channel preferences are persisted."""
        prefs = NotificationPreferencesV1(
            user_id="ch-prefs-user",
            channel_preferences={
                "telegram": ChannelPreferencesV1(
                    channel=NotificationChannel.TELEGRAM,
                    enabled=False,
                    delivery_mode=DeliveryMode.DIGEST_ONLY,
                ),
                "push": ChannelPreferencesV1(
                    channel=NotificationChannel.PUSH,
                    enabled=True,
                    min_priority=NotificationPriority.HIGH,
                ),
            },
        )
        
        store.upsert_preferences(prefs)
        retrieved = store.get_preferences("ch-prefs-user")
        
        assert retrieved is not None
        assert "telegram" in retrieved.channel_preferences
        assert "push" in retrieved.channel_preferences
        assert retrieved.channel_preferences["telegram"].enabled is False
        assert retrieved.channel_preferences["push"].min_priority == NotificationPriority.HIGH
    
    def test_get_settings(self, store):
        """Test retrieving combined settings."""
        profile = UserProfileV1(user_id="settings-user", name="Settings Test")
        prefs = NotificationPreferencesV1(user_id="settings-user")
        
        store.upsert_profile(profile)
        store.upsert_preferences(prefs)
        
        settings = store.get_settings("settings-user")
        
        assert settings is not None
        assert settings.profile.name == "Settings Test"
        assert settings.preferences.user_id == "settings-user"
    
    def test_get_settings_not_found(self, store):
        """Test settings retrieval when profile or prefs missing."""
        # Only profile, no prefs
        profile = UserProfileV1(user_id="partial-user")
        store.upsert_profile(profile)
        
        settings = store.get_settings("partial-user")
        assert settings is None  # Both must exist
    
    def test_update_dnd(self, store):
        """Test do-not-disturb update."""
        prefs = NotificationPreferencesV1(user_id="dnd-user")
        store.upsert_preferences(prefs)
        
        until = datetime.now(timezone.utc) + timedelta(hours=2)
        updated = store.update_preferences_dnd("dnd-user", True, until)
        
        assert updated is not None
        assert updated.do_not_disturb is True
        assert updated.do_not_disturb_until is not None
    
    def test_update_dnd_nonexistent(self, store):
        """Test DND update for non-existent user."""
        result = store.update_preferences_dnd("non-existent", True, None)
        assert result is None
    
    def test_update_channel_preference(self, store):
        """Test updating a specific channel preference."""
        prefs = NotificationPreferencesV1(user_id="ch-update-user")
        store.upsert_preferences(prefs)
        
        updated = store.update_channel_preference(
            "ch-update-user",
            NotificationChannel.PUSH,
            enabled=False,
            delivery_mode=DeliveryMode.SILENT,
        )
        
        assert updated is not None
        assert updated.channel_preferences["push"].enabled is False
        assert updated.channel_preferences["push"].delivery_mode == DeliveryMode.SILENT
    
    def test_update_channel_preference_nonexistent(self, store):
        """Test channel update for non-existent user."""
        result = store.update_channel_preference(
            "non-existent",
            NotificationChannel.TELEGRAM,
            enabled=False,
        )
        assert result is None
    
    def test_delete_user(self, store):
        """Test deleting user and all data."""
        # Create profile and prefs
        profile = UserProfileV1(user_id="delete-user", name="Delete Me")
        prefs = NotificationPreferencesV1(
            user_id="delete-user",
            channel_preferences={
                "telegram": ChannelPreferencesV1(channel=NotificationChannel.TELEGRAM),
            },
        )
        
        store.upsert_profile(profile)
        store.upsert_preferences(prefs)
        
        # Verify exists
        assert store.get_profile("delete-user") is not None
        assert store.get_preferences("delete-user") is not None
        
        # Delete
        deleted = store.delete_user("delete-user")
        
        assert deleted is True
        assert store.get_profile("delete-user") is None
        assert store.get_preferences("delete-user") is None
    
    def test_delete_nonexistent_user(self, store):
        """Test deleting non-existent user."""
        deleted = store.delete_user("non-existent")
        assert deleted is False
    
    def test_profile_revision_increments(self, store):
        """Test profile revision increments on updates."""
        profile = UserProfileV1(user_id="rev-user")
        
        store.upsert_profile(profile)
        assert profile.revision == 1
        
        profile.name = "Update 1"
        p2 = store.upsert_profile(profile)
        assert p2.revision == 2
        
        profile.name = "Update 2"
        p3 = store.upsert_profile(profile)
        assert p3.revision == 3
    
    def test_preferences_revision_increments(self, store):
        """Test preferences revision increments on updates."""
        prefs = NotificationPreferencesV1(user_id="rev-prefs-user")
        
        store.upsert_preferences(prefs)
        assert prefs.revision == 1
        
        prefs.global_enabled = False
        p2 = store.upsert_preferences(prefs)
        assert p2.revision == 2


class TestUserStorePersistence:
    """Test store persistence across instances."""
    
    def test_persistence(self, temp_db):
        """Test data persists across store instances."""
        # Create and populate first store
        store1 = UserStore(temp_db)
        store1.upsert_profile(UserProfileV1(
            user_id="persist-user",
            name="Persist Test",
            email="persist@example.com",
        ))
        
        # Create second store with same DB
        store2 = UserStore(temp_db)
        
        # Verify data persisted
        retrieved = store2.get_profile("persist-user")
        assert retrieved is not None
        assert retrieved.name == "Persist Test"
        assert retrieved.email == "persist@example.com"
