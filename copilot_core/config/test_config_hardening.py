"""Tests for config hardening features.

Tests cover:
1. Pydantic validation
2. Encryption/decryption
3. Secrets management
4. Versioning and rollback
5. Audit logging
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from copilot_core.config.models import (
    ZoneConfig,
    SonosConfig,
    LightConfig,
    PresenceConfig,
    AlarmConfig,
    MoodConfig,
    Conflict,
    ConfigAuditEntry,
    ConfigAuditLog,
)
from copilot_core.config.encryption import (
    ConfigEncryption,
    SecretManager,
    EncryptionError,
)


# ── Pydantic Model Tests ─────────────────────────────────────────────


class TestSonosConfig:
    """Test SonosConfig validation."""
    
    def test_valid_config(self):
        config = SonosConfig(
            room_name="Wohnzimmer",
            volume_default=30,
            volume_ramp_start=10,
            volume_ramp_end=40,
        )
        assert config.room_name == "Wohnzimmer"
        assert config.volume_default == 30
    
    def test_invalid_room_name(self):
        with pytest.raises(ValueError) as exc_info:
            SonosConfig(room_name="Invalid@Room!")
        assert "invalid characters" in str(exc_info.value)
    
    def test_volume_range_validation(self):
        # ramp_start > ramp_end should fail
        with pytest.raises(ValueError) as exc_info:
            SonosConfig(
                volume_ramp_start=50,
                volume_ramp_end=30,
            )
        assert "volume_ramp_start must be <=" in str(exc_info.value)
    
    def test_volume_bounds(self):
        # Out of bounds should fail
        with pytest.raises(ValueError):
            SonosConfig(volume_default=150)  # > 100
        
        with pytest.raises(ValueError):
            SonosConfig(volume_default=-10)  # < 0


class TestLightConfig:
    """Test LightConfig validation."""
    
    def test_valid_entity_ids(self):
        config = LightConfig(entities=["light.wohnzimmer", "light.kuche"])
        assert len(config.entities) == 2
    
    def test_invalid_entity_id(self):
        with pytest.raises(ValueError) as exc_info:
            LightConfig(entities=["invalid_entity"])
        assert "Invalid entity ID format" in str(exc_info.value)
    
    def test_brightness_bounds(self):
        with pytest.raises(ValueError):
            LightConfig(brightness_default=300)  # > 255


class TestAlarmConfig:
    """Test AlarmConfig validation."""
    
    def test_valid_time_format(self):
        config = AlarmConfig(default_time_hhmm="07:00")
        assert config.default_time_hhmm == "07:00"
        
        config = AlarmConfig(default_time_hhmm="23:59")
        assert config.default_time_hhmm == "23:59"
    
    def test_invalid_time_format(self):
        # Missing leading zero - Pydantic allows this, regex is more permissive
        # Actually "7:00" fails the regex, so this should pass
        with pytest.raises(ValueError):
            AlarmConfig(default_time_hhmm="7:00")  # Missing leading zero
        
        with pytest.raises(ValueError):
            AlarmConfig(default_time_hhmm="25:00")  # Invalid hour
    
    def test_valid_repeat(self):
        for repeat in ["once", "daily", "weekdays", "weekends", "custom"]:
            config = AlarmConfig(repeat=repeat, custom_days=[0] if repeat == "custom" else [])
            assert config.repeat == repeat
    
    def test_invalid_repeat(self):
        with pytest.raises(ValueError):
            AlarmConfig(repeat="invalid")
    
    def test_custom_days_validation(self):
        # custom repeat without custom_days should fail
        with pytest.raises(ValueError):
            AlarmConfig(repeat="custom")
        
        # Invalid day number
        with pytest.raises(ValueError):
            AlarmConfig(repeat="custom", custom_days=[7])
        
        # Valid custom days
        config = AlarmConfig(repeat="custom", custom_days=[0, 2, 4])
        assert config.custom_days == [0, 2, 4]


class TestZoneConfig:
    """Test ZoneConfig validation."""
    
    def test_valid_zone(self):
        zone = ZoneConfig(
            zone_id="area_wohnbereich",
            zone_name="Wohnbereich",
        )
        assert zone.zone_id == "area_wohnbereich"
        assert zone.zone_name == "Wohnbereich"
        assert zone.created_at  # Auto-set
        assert zone.updated_at  # Auto-set
    
    def test_invalid_zone_id(self):
        with pytest.raises(ValueError):
            ZoneConfig(zone_id="Invalid@Zone!")
    
    def test_nested_configs(self):
        zone = ZoneConfig(
            zone_id="test",
            sonos=SonosConfig(room_name="Test Room"),
            light=LightConfig(entities=["light.test"]),
        )
        assert zone.sonos.room_name == "Test Room"
        assert zone.light.entities == ["light.test"]
    
    def test_extra_fields_forbidden(self):
        with pytest.raises(ValueError):
            ZoneConfig(
                zone_id="test",
                invalid_field="should be rejected",
            )


class TestConflict:
    """Test Conflict model."""
    
    def test_valid_conflict(self):
        conflict = Conflict(
            conflict_id="test_conflict",
            severity="warning",
            modules=["sonos", "wecker"],
            description="Test conflict",
        )
        assert conflict.severity == "warning"
        assert len(conflict.modules) == 2
    
    def test_invalid_severity(self):
        with pytest.raises(ValueError):
            Conflict(
                conflict_id="test",
                severity="critical",  # Not valid
                modules=[],
                description="Test",
            )


# ── Encryption Tests ─────────────────────────────────────────────────


class TestConfigEncryption:
    """Test encryption utilities."""
    
    def test_encrypt_decrypt_roundtrip(self):
        secret = "my-super-secret-api-key"
        encryptor = ConfigEncryption(master_secret="test-master-secret")
        
        encrypted = encryptor.encrypt(secret)
        assert encrypted != secret
        assert encrypted.startswith("v")
        
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == secret
    
    def test_is_encrypted(self):
        encryptor = ConfigEncryption(master_secret="test")
        
        encrypted = encryptor.encrypt("secret")
        assert encryptor.is_encrypted(encrypted)
        
        plaintext = "not-encrypted"
        assert not encryptor.is_encrypted(plaintext)
    
    def test_encryption_without_master_secret(self):
        # Should initialize but warn
        encryptor = ConfigEncryption()
        assert encryptor._fernet is None
    
    def test_decrypt_with_wrong_key(self):
        encryptor1 = ConfigEncryption(master_secret="secret1")
        encryptor2 = ConfigEncryption(master_secret="secret2")
        
        encrypted = encryptor1.encrypt("test")
        
        with pytest.raises(EncryptionError):
            encryptor2.decrypt(encrypted)
    
    def test_key_versioning(self):
        encryptor = ConfigEncryption(master_secret="test", key_version=1)
        assert encryptor.key_version == 1
        
        encrypted = encryptor.encrypt("test")
        assert encrypted.startswith("v1:")


class TestSecretManager:
    """Test secrets management."""
    
    def test_store_and_retrieve(self):
        encryptor = ConfigEncryption(master_secret="test")
        manager = SecretManager(encryptor)
        
        manager.store("api_key", "secret-value")
        
        retrieved = manager.retrieve("api_key")
        assert retrieved == "secret-value"
    
    def test_store_without_encryption(self):
        encryptor = ConfigEncryption(master_secret="test")
        manager = SecretManager(encryptor)
        
        manager.store("public_value", "not-secret", encrypt=False)
        
        retrieved = manager.retrieve("public_value", decrypt=False)
        assert retrieved == "not-secret"
    
    def test_delete_secret(self):
        encryptor = ConfigEncryption(master_secret="test")
        manager = SecretManager(encryptor)
        
        manager.store("to_delete", "value")
        assert manager.retrieve("to_delete") == "value"
        
        deleted = manager.delete("to_delete")
        assert deleted is True
        assert manager.retrieve("to_delete") is None
    
    def test_rotate_secret(self):
        encryptor = ConfigEncryption(master_secret="test")
        manager = SecretManager(encryptor)
        
        manager.store("api_key", "old-value")
        new_encrypted = manager.rotate_secret("api_key", "new-value")
        
        retrieved = manager.retrieve("api_key")
        assert retrieved == "new-value"
    
    def test_list_secrets(self):
        encryptor = ConfigEncryption(master_secret="test")
        manager = SecretManager(encryptor)
        
        manager.store("key1", "value1")
        manager.store("key2", "value2")
        
        names = manager.list_secrets()
        assert "key1" in names
        assert "key2" in names
        assert len(names) == 2


# ── Audit Log Tests ──────────────────────────────────────────────────


class TestConfigAuditLog:
    """Test audit logging."""
    
    def test_add_entry(self):
        log = ConfigAuditLog()
        
        entry = ConfigAuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action="update",
            zone_id="test_zone",
            old_value={"volume": 30},
            new_value={"volume": 50},
            user="admin",
            reason="Volume adjustment",
        )
        
        log.add_entry(entry)
        assert len(log.entries) == 1
    
    def test_entry_rotation(self):
        log = ConfigAuditLog(max_entries=5)
        
        for i in range(10):
            entry = ConfigAuditEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                action="update",
                user="system",
            )
            log.add_entry(entry)
        
        # Should have max_entries (or close to it)
        assert len(log.entries) <= 5
        assert len(log.entries) > 0


# ── Integration Tests (Mocked) ───────────────────────────────────────


class TestConfigManagerIntegration:
    """Integration tests for ConfigManager (with mocked HA).
    
    Note: These tests require homeassistant module. Skip if not available.
    """
    
    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        
        # Mock Store
        store_mock = AsyncMock()
        store_mock.async_load = AsyncMock(return_value=None)
        store_mock.async_save = AsyncMock()
        
        try:
            with patch('homeassistant.helpers.storage.Store', return_value=store_mock):
                yield hass
        except ModuleNotFoundError:
            pytest.skip("homeassistant not available in test environment")
    
    @pytest.mark.asyncio
    async def test_manager_initialization(self, mock_hass):
        from copilot_core.config.manager import ConfigManager
        
        manager = ConfigManager(mock_hass, master_secret="test")
        await manager.initialize()
        
        assert manager._loaded is True
        assert len(manager.get_all_zones()) == 0
    
    @pytest.mark.asyncio
    async def test_save_zone_with_validation(self, mock_hass):
        from copilot_core.config.manager import ConfigManager
        from copilot_core.config.models import ZoneConfig, SonosConfig
        
        manager = ConfigManager(mock_hass, master_secret="test")
        await manager.initialize()
        
        zone = ZoneConfig(
            zone_id="test_zone",
            zone_name="Test",
            sonos=SonosConfig(room_name="Test Room"),
        )
        
        await manager.save_zone(zone, user="test", reason="Initial setup")
        
        retrieved = manager.get_zone("test_zone")
        assert retrieved is not None
        assert retrieved.zone_name == "Test"
    
    @pytest.mark.asyncio
    async def test_secret_storage(self, mock_hass):
        from copilot_core.config.manager import ConfigManager
        
        manager = ConfigManager(mock_hass, master_secret="test")
        await manager.initialize()
        
        manager.store_secret("api_key", "secret-123", user="admin")
        
        retrieved = manager.get_secret("api_key")
        assert retrieved == "secret-123"
    
    @pytest.mark.asyncio
    async def test_audit_log_recording(self, mock_hass):
        from copilot_core.config.manager import ConfigManager
        from copilot_core.config.models import ZoneConfig
        
        manager = ConfigManager(mock_hass, master_secret="test")
        await manager.initialize()
        
        zone = ZoneConfig(zone_id="test")
        await manager.save_zone(zone, user="admin", reason="Test")
        
        entries = manager.get_audit_log(limit=10)
        assert len(entries) > 0
        assert entries[0].action == "create"
        assert entries[0].user == "admin"


# ── Run Tests ────────────────────────────────────────────────────────


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
