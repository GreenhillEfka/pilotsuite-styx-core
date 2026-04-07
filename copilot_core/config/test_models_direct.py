"""Direct tests for models.py and encryption.py (bypassing __init__.py)."""
import sys
import importlib.util
from pathlib import Path
from datetime import datetime, timezone

import pytest

# Load modules directly to avoid HA dependency
models_path = Path(__file__).parent / "models.py"
enc_path = Path(__file__).parent / "encryption.py"

# Load models module
spec = importlib.util.spec_from_file_location("models", models_path)
models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(models)

# Load encryption module  
spec = importlib.util.spec_from_file_location("encryption", enc_path)
encryption = importlib.util.module_from_spec(spec)
spec.loader.exec_module(encryption)

# Import from loaded modules
ZoneConfig = models.ZoneConfig
SonosConfig = models.SonosConfig
LightConfig = models.LightConfig
PresenceConfig = models.PresenceConfig
AlarmConfig = models.AlarmConfig
MoodConfig = models.MoodConfig
Conflict = models.Conflict
ConfigAuditEntry = models.ConfigAuditEntry
ConfigAuditLog = models.ConfigAuditLog
ConfigEncryption = encryption.ConfigEncryption
SecretManager = encryption.SecretManager
EncryptionError = encryption.EncryptionError


class TestSonosConfig:
    def test_valid_config(self):
        config = SonosConfig(room_name="Wohnzimmer", volume_default=30)
        assert config.room_name == "Wohnzimmer"
    
    def test_invalid_room_name(self):
        with pytest.raises(ValueError) as exc_info:
            SonosConfig(room_name="Invalid@Room!")
        assert "invalid characters" in str(exc_info.value)
    
    def test_volume_range_validation(self):
        with pytest.raises(ValueError) as exc_info:
            SonosConfig(volume_ramp_start=50, volume_ramp_end=30)
        assert "volume_ramp_start must be <=" in str(exc_info.value)
    
    def test_volume_bounds(self):
        with pytest.raises(ValueError):
            SonosConfig(volume_default=150)


class TestLightConfig:
    def test_valid_entity_ids(self):
        config = LightConfig(entities=["light.wohnzimmer", "light.kuche"])
        assert len(config.entities) == 2
    
    def test_invalid_entity_id(self):
        with pytest.raises(ValueError) as exc_info:
            LightConfig(entities=["invalid_entity"])
        assert "Invalid entity ID format" in str(exc_info.value)


class TestAlarmConfig:
    def test_valid_time_format(self):
        config = AlarmConfig(default_time_hhmm="07:00")
        assert config.default_time_hhmm == "07:00"
    
    def test_invalid_time_format(self):
        with pytest.raises(ValueError):
            AlarmConfig(default_time_hhmm="7:00")
        with pytest.raises(ValueError):
            AlarmConfig(default_time_hhmm="25:00")
    
    def test_valid_repeat(self):
        for repeat in ["once", "daily", "weekdays", "weekends"]:
            config = AlarmConfig(repeat=repeat)
            assert config.repeat == repeat
        config = AlarmConfig(repeat="custom", custom_days=[0, 2, 4])
        assert config.repeat == "custom"
    
    def test_invalid_repeat(self):
        with pytest.raises(ValueError):
            AlarmConfig(repeat="invalid")
    
    def test_custom_days_validation(self):
        with pytest.raises(ValueError):
            AlarmConfig(repeat="custom")
        with pytest.raises(ValueError):
            AlarmConfig(repeat="custom", custom_days=[7])


class TestZoneConfig:
    def test_valid_zone(self):
        zone = ZoneConfig(zone_id="area_wohnbereich", zone_name="Wohnbereich")
        assert zone.zone_id == "area_wohnbereich"
        assert zone.created_at
    
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
    
    def test_extra_fields_forbidden(self):
        with pytest.raises(ValueError):
            ZoneConfig(zone_id="test", invalid_field="rejected")


class TestConflict:
    def test_valid_conflict(self):
        conflict = Conflict(
            conflict_id="test",
            severity="warning",
            modules=["sonos", "wecker"],
            description="Test",
        )
        assert conflict.severity == "warning"
    
    def test_invalid_severity(self):
        with pytest.raises(ValueError):
            Conflict(conflict_id="test", severity="critical", modules=[], description="Test")


class TestConfigEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        encryptor = ConfigEncryption(master_secret="test-secret")
        encrypted = encryptor.encrypt("my-secret")
        assert encrypted.startswith("v")
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == "my-secret"
    
    def test_is_encrypted(self):
        encryptor = ConfigEncryption(master_secret="test")
        encrypted = encryptor.encrypt("secret")
        assert encryptor.is_encrypted(encrypted)
        assert not encryptor.is_encrypted("plaintext")
    
    def test_decrypt_with_wrong_key(self):
        e1 = ConfigEncryption(master_secret="secret1")
        e2 = ConfigEncryption(master_secret="secret2")
        encrypted = e1.encrypt("test")
        with pytest.raises(EncryptionError):
            e2.decrypt(encrypted)
    
    def test_key_versioning(self):
        encryptor = ConfigEncryption(master_secret="test", key_version=1)
        assert encryptor.key_version == 1
        assert encryptor.encrypt("test").startswith("v1:")


class TestSecretManager:
    def test_store_and_retrieve(self):
        encryptor = ConfigEncryption(master_secret="test")
        manager = SecretManager(encryptor)
        manager.store("api_key", "secret-value")
        assert manager.retrieve("api_key") == "secret-value"
    
    def test_delete_secret(self):
        encryptor = ConfigEncryption(master_secret="test")
        manager = SecretManager(encryptor)
        manager.store("to_delete", "value")
        assert manager.delete("to_delete") is True
        assert manager.retrieve("to_delete") is None
    
    def test_rotate_secret(self):
        encryptor = ConfigEncryption(master_secret="test")
        manager = SecretManager(encryptor)
        manager.store("key", "old")
        manager.rotate_secret("key", "new")
        assert manager.retrieve("key") == "new"


class TestConfigAuditLog:
    def test_add_entry(self):
        log = ConfigAuditLog()
        entry = ConfigAuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action="update",
            user="admin",
        )
        log.add_entry(entry)
        assert len(log.entries) == 1
    
    def test_entry_rotation(self):
        log = ConfigAuditLog(max_entries=5)
        for _ in range(10):
            log.add_entry(ConfigAuditEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                action="update",
                user="system",
            ))
        assert len(log.entries) <= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
