"""Tests for Multi-Home Synchronization module."""

import pytest
from datetime import datetime, timezone, timedelta
import json

from copilot_core.multihome.sync_engine import (
    SyncEngine,
    HomeInstance,
    HomeType,
    SyncStatus,
    ConflictResolution,
    EncryptionHelper,
)
from copilot_core.multihome.config_sync import ConfigSync
from copilot_core.multihome.state_sync import StateSync, EntityState


class TestHomeInstance:
    """Test HomeInstance dataclass."""
    
    def test_create_primary_home(self):
        home = HomeInstance(
            id="primary-home",
            name="Hauptwohnung",
            home_type=HomeType.PRIMARY,
            base_url="http://192.168.1.100:8123",
            auth_token="test-token",
            is_primary=True
        )
        
        assert home.id == "primary-home"
        assert home.is_primary is True
        assert home.home_type == HomeType.PRIMARY
    
    def test_to_dict_excludes_sensitive_data(self):
        home = HomeInstance(
            id="vacation-home",
            name="Ferienhaus",
            home_type=HomeType.VACATION,
            base_url="http://192.168.2.100:8123",
            auth_token="secret-token"
        )
        
        home_dict = home.to_dict()
        
        assert "auth_token" not in home_dict
        assert home_dict["id"] == "vacation-home"
        assert home_dict["home_type"] == "vacation"


class TestSyncEngine:
    """Test SyncEngine functionality."""
    
    @pytest.fixture
    def sync_engine(self, tmp_path):
        engine = SyncEngine(data_dir=str(tmp_path))
        return engine
    
    def test_register_home(self, sync_engine):
        home = HomeInstance(
            id="test-home",
            name="Test Home",
            home_type=HomeType.SECONDARY,
            base_url="http://test:8123",
            auth_token="token"
        )
        
        sync_engine.register_home(home)
        
        assert "test-home" in sync_engine.homes
        assert sync_engine.homes["test-home"].name == "Test Home"
    
    def test_get_primary_home(self, sync_engine):
        primary = HomeInstance(
            id="primary",
            name="Primary",
            home_type=HomeType.PRIMARY,
            base_url="http://primary:8123",
            auth_token="token",
            is_primary=True
        )
        secondary = HomeInstance(
            id="secondary",
            name="Secondary",
            home_type=HomeType.SECONDARY,
            base_url="http://secondary:8123",
            auth_token="token"
        )
        
        sync_engine.register_home(primary)
        sync_engine.register_home(secondary)
        
        result = sync_engine.get_primary_home()
        
        assert result is not None
        assert result.id == "primary"
    
    def test_create_sync_operation(self, sync_engine):
        home = HomeInstance(
            id="home1",
            name="Home 1",
            home_type=HomeType.PRIMARY,
            base_url="http://home1:8123",
            auth_token="token"
        )
        sync_engine.register_home(home)
        
        operation = sync_engine.create_sync_operation(
            source_home_id="home1",
            target_home_id="home1",
            operation_type="config",
            data={"test": "data"}
        )
        
        assert operation.id is not None
        assert operation.operation_type == "config"
        assert operation.status == SyncStatus.PENDING
    
    def test_conflict_resolution_last_write_wins(self, sync_engine):
        operation = sync_engine.create_sync_operation(
            source_home_id="home1",
            target_home_id="home2",
            operation_type="state",
            data={}
        )
        
        local_time = datetime.now(timezone.utc)
        remote_time = local_time - timedelta(minutes=5)
        
        conflict = sync_engine.detect_conflict(
            operation=operation,
            field_path="climate.thermostat",
            local_value={"temperature": 22},
            remote_value={"temperature": 20},
            local_timestamp=local_time,
            remote_timestamp=remote_time
        )
        
        resolved = sync_engine.resolve_conflict(conflict.id, ConflictResolution.LAST_WRITE_WINS)
        
        assert resolved == {"temperature": 22}  # Local is newer


class TestEncryptionHelper:
    """Test encryption helper."""
    
    def test_sign_and_verify_payload(self):
        helper = EncryptionHelper(shared_secret="test-secret")
        payload = {"data": "test", "timestamp": "2024-01-01"}
        
        signature = helper.sign_payload(payload)
        is_valid = helper.verify_payload(payload, signature)
        
        assert is_valid is True
    
    def test_verify_invalid_signature(self):
        helper = EncryptionHelper(shared_secret="test-secret")
        payload = {"data": "test"}
        
        is_valid = helper.verify_payload(payload, "invalid-signature")
        
        assert is_valid is False
    
    def test_encrypt_and_decrypt_payload(self):
        helper = EncryptionHelper(shared_secret="test-secret")
        payload = {"secret": "data", "value": 42}
        
        encrypted = helper.encrypt_payload(payload)
        decrypted = helper.decrypt_payload(encrypted)
        
        assert decrypted == payload


class TestEntityState:
    """Test EntityState for state synchronization."""
    
    def test_create_entity_state(self):
        now = datetime.now(timezone.utc)
        state = EntityState(
            entity_id="climate.living_room",
            state="heat",
            attributes={"temperature": 21.5, "hvac_mode": "heat"},
            last_changed=now,
            last_updated=now
        )
        
        assert state.entity_id == "climate.living_room"
        assert state.state == "heat"
        assert state._version_hash is not None
    
    def test_to_dict_and_from_dict(self):
        now = datetime.now(timezone.utc)
        state = EntityState(
            entity_id="light.kitchen",
            state="on",
            attributes={"brightness": 255},
            last_changed=now,
            last_updated=now
        )
        
        state_dict = state.to_dict()
        restored = EntityState.from_dict(state_dict)
        
        assert restored.entity_id == state.entity_id
        assert restored.state == state.state
        assert restored._version_hash == state._version_hash


class TestConfigSync:
    """Test ConfigSync functionality."""
    
    @pytest.fixture
    def config_sync(self, tmp_path):
        from copilot_core.multihome.sync_engine import SyncEngine
        sync_engine = SyncEngine(data_dir=str(tmp_path))
        return ConfigSync(sync_engine)
    
    def test_get_config_hash(self, config_sync):
        config1 = {"key": "value"}
        config2 = {"key": "different_value"}
        
        hash1 = config_sync.get_config_hash(config1)
        hash2 = config_sync.get_config_hash(config2)
        
        assert hash1 != hash2
        assert len(hash1) == 16  # 16 character hash


class TestStateSync:
    """Test StateSync functionality."""
    
    @pytest.fixture
    def state_sync(self, tmp_path):
        from copilot_core.multihome.sync_engine import SyncEngine
        sync_engine = SyncEngine(data_dir=str(tmp_path))
        return StateSync(sync_engine)
    
    def test_should_sync_entity(self, state_sync):
        assert state_sync.should_sync_entity("climate.thermostat") is True
        assert state_sync.should_sync_entity("light.living_room") is True
        assert state_sync.should_sync_entity("sensor.temperature") is False
        assert state_sync.should_sync_entity("binary_sensor.motion") is False
    
    def test_cache_and_get_state(self, state_sync):
        now = datetime.now(timezone.utc)
        state = EntityState(
            entity_id="climate.bedroom",
            state="heat",
            attributes={"temperature": 20},
            last_changed=now,
            last_updated=now
        )
        
        state_sync.cache_entity_state("home1", state)
        retrieved = state_sync.get_cached_state("home1", "climate.bedroom")
        
        assert retrieved is not None
        assert retrieved.entity_id == "climate.bedroom"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
