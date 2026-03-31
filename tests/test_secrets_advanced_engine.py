"""Tests for Secret Manager Advanced Engine — Slice 62."""
import pytest
from copilot_core.secrets_advanced.engine import (
    SecretManagerEngine,
    SecretType,
    SecretStatus,
    Secret,
    SecretVersion,
    AccessAudit,
    create_secret_manager_engine,
)
from datetime import datetime, timezone, timedelta


class TestSecret:
    """Test secret definition."""
    
    def test_create_secret(self):
        """Test creating secret."""
        secret = Secret(
            secret_id="sec_test",
            name="Test Secret",
            secret_type=SecretType.PASSWORD,
            encrypted_value="encrypted_value",
        )
        
        assert secret.secret_id == "sec_test"
        assert secret.status == SecretStatus.ACTIVE
    
    def test_secret_to_dict(self):
        """Test secret serialization."""
        secret = Secret(
            secret_id="sec_test",
            name="Test",
            secret_type=SecretType.API_KEY,
            encrypted_value="encrypted",
            tags={"production", "backend"},
            current_version=3,
        )
        
        d = secret.to_dict(include_value=False)
        
        assert d["secret_id"] == "sec_test"
        assert "production" in d["tags"]
        assert d["current_version"] == 3
    
    def test_secret_to_dict_with_value(self):
        """Test secret serialization with value."""
        secret = Secret(
            secret_id="sec_test",
            name="Test",
            secret_type=SecretType.GENERIC,
            encrypted_value="encrypted_value",
        )
        
        d = secret.to_dict(include_value=True)
        
        assert d["encrypted_value"] == "encrypted_value"
    
    def test_secret_not_expired_no_expiry(self):
        """Test secret not expired when no expiry set."""
        secret = Secret(
            secret_id="sec_test",
            name="Test",
            secret_type=SecretType.GENERIC,
            encrypted_value="encrypted",
        )
        
        assert secret.is_expired() is False
    
    def test_secret_expired(self):
        """Test secret expired."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        secret = Secret(
            secret_id="sec_test",
            name="Test",
            secret_type=SecretType.GENERIC,
            encrypted_value="encrypted",
            expires_at=past,
        )
        
        assert secret.is_expired() is True
    
    def test_secret_not_expired_future(self):
        """Test secret not expired with future expiry."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        
        secret = Secret(
            secret_id="sec_test",
            name="Test",
            secret_type=SecretType.GENERIC,
            encrypted_value="encrypted",
            expires_at=future,
        )
        
        assert secret.is_expired() is False
    
    def test_secret_needs_rotation(self):
        """Test secret needs rotation."""
        past = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        
        secret = Secret(
            secret_id="sec_test",
            name="Test",
            secret_type=SecretType.GENERIC,
            encrypted_value="encrypted",
            rotation_interval_days=30,
            rotated_at=past,
        )
        
        assert secret.needs_rotation() is True
    
    def test_secret_no_rotation_interval(self):
        """Test secret without rotation interval."""
        secret = Secret(
            secret_id="sec_test",
            name="Test",
            secret_type=SecretType.GENERIC,
            encrypted_value="encrypted",
        )
        
        assert secret.needs_rotation() is False
    
    def test_secret_needs_rotation_no_rotation_date(self):
        """Test secret needs rotation when never rotated."""
        past = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        
        secret = Secret(
            secret_id="sec_test",
            name="Test",
            secret_type=SecretType.GENERIC,
            encrypted_value="encrypted",
            rotation_interval_days=30,
            created_at=past,
        )
        
        assert secret.needs_rotation() is True


class TestSecretVersion:
    """Test secret version."""
    
    def test_create_version(self):
        """Test creating secret version."""
        version = SecretVersion(
            version_id="v1_abc123",
            secret_id="sec_test",
            value_hash="sha256_hash",
            created_at="2025-01-01T00:00:00Z",
            created_by="admin",
        )
        
        assert version.version_id == "v1_abc123"
        assert version.is_current is False
    
    def test_version_to_dict(self):
        """Test version serialization."""
        version = SecretVersion(
            version_id="v2_def456",
            secret_id="sec_test",
            value_hash="hash123",
            created_at="2025-01-01T00:00:00Z",
            created_by="user",
            is_current=True,
        )
        
        d = version.to_dict()
        
        assert d["is_current"] is True
        assert d["created_by"] == "user"


class TestAccessAudit:
    """Test access audit record."""
    
    def test_create_audit(self):
        """Test creating audit record."""
        audit = AccessAudit(
            audit_id="aud_test",
            secret_id="sec_test",
            accessor="user_123",
            action="read",
            timestamp="2025-01-01T00:00:00Z",
            success=True,
        )
        
        assert audit.audit_id == "aud_test"
        assert audit.success is True
    
    def test_audit_to_dict(self):
        """Test audit serialization."""
        audit = AccessAudit(
            audit_id="aud_test",
            secret_id="sec_test",
            accessor="user_123",
            action="write",
            timestamp="2025-01-01T00:00:00Z",
            success=False,
            reason="access_denied",
            ip_address="192.168.1.1",
        )
        
        d = audit.to_dict()
        
        assert d["reason"] == "access_denied"
        assert d["ip_address"] == "192.168.1.1"


class TestSecretManagerEngine:
    """Test secret manager engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_secret_manager_engine()
        assert engine is not None
    
    def test_create_engine_with_key(self):
        """Test engine creation with encryption key."""
        key = b"0123456789abcdef0123456789abcdef"
        engine = SecretManagerEngine(encryption_key=key)
        assert engine is not None
    
    def test_create_secret(self):
        """Test creating secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="DB Password",
            value="super_secret_password",
            secret_type=SecretType.PASSWORD,
        )
        
        assert secret_id is not None
        assert secret_id.startswith("sec_")
        
        # Should be able to retrieve
        value = engine.get_secret(secret_id)
        
        assert value == "super_secret_password"
    
    def test_create_secret_with_expiry(self):
        """Test creating secret with expiry."""
        engine = SecretManagerEngine()
        
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        
        secret_id = engine.create_secret(
            name="Expiring Secret",
            value="secret_value",
            expires_at=future,
        )
        
        info = engine.get_secret_info(secret_id)
        
        assert info["expires_at"] is not None
    
    def test_create_secret_with_rotation(self):
        """Test creating secret with rotation interval."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="Rotating Secret",
            value="secret_value",
            rotation_interval_days=30,
        )
        
        info = engine.get_secret_info(secret_id)
        
        assert info["rotation_interval_days"] == 30
    
    def test_create_secret_with_metadata(self):
        """Test creating secret with metadata."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="API Key",
            value="key_123",
            metadata={"service": "payment", "env": "prod"},
        )
        
        info = engine.get_secret_info(secret_id)
        
        assert info["metadata"]["service"] == "payment"
    
    def test_create_secret_with_tags(self):
        """Test creating secret with tags."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="Secret",
            value="value",
            tags={"production", "critical"},
        )
        
        info = engine.get_secret_info(secret_id)
        
        assert "production" in info["tags"]
        assert "critical" in info["tags"]
    
    def test_get_secret(self):
        """Test getting secret value."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "my_secret_value")
        
        value = engine.get_secret(secret_id)
        
        assert value == "my_secret_value"
    
    def test_get_secret_nonexistent(self):
        """Test getting nonexistent secret."""
        engine = SecretManagerEngine()
        
        value = engine.get_secret("nonexistent")
        
        assert value is None
    
    def test_get_secret_access_denied(self):
        """Test getting secret with access denied."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        engine.set_access_policy(secret_id, {"allowed_user"})
        
        value = engine.get_secret(secret_id, accessor="unauthorized_user")
        
        assert value is None
    
    def test_get_secret_expired(self):
        """Test getting expired secret."""
        engine = SecretManagerEngine()
        
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        secret_id = engine.create_secret(
            "Expiring", "value", expires_at=past,
        )
        
        value = engine.get_secret(secret_id)
        
        assert value is None
    
    def test_get_secret_revoked(self):
        """Test getting revoked secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        engine.revoke_secret(secret_id)
        
        value = engine.get_secret(secret_id)
        
        assert value is None
    
    def test_get_secret_suspended(self):
        """Test getting suspended secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        engine.suspend_secret(secret_id)
        
        value = engine.get_secret(secret_id)
        
        assert value is None
    
    def test_update_secret(self):
        """Test updating secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "original_value")
        
        result = engine.update_secret(secret_id, "new_value")
        
        assert result is True
        
        value = engine.get_secret(secret_id)
        
        assert value == "new_value"
    
    def test_update_secret_nonexistent(self):
        """Test updating nonexistent secret."""
        engine = SecretManagerEngine()
        
        result = engine.update_secret("nonexistent", "value")
        
        assert result is False
    
    def test_update_secret_increments_version(self):
        """Test that update increments version."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "v1")
        
        engine.update_secret(secret_id, "v2")
        engine.update_secret(secret_id, "v3")
        
        info = engine.get_secret_info(secret_id)
        
        assert info["current_version"] == 3
    
    def test_delete_secret(self):
        """Test deleting secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        result = engine.delete_secret(secret_id)
        
        assert result is True
        assert engine.get_secret(secret_id) is None
    
    def test_delete_secret_nonexistent(self):
        """Test deleting nonexistent secret."""
        engine = SecretManagerEngine()
        
        result = engine.delete_secret("nonexistent")
        
        assert result is False
    
    def test_rotate_secret(self):
        """Test rotating secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "old_value")
        
        result = engine.rotate_secret(secret_id, "new_rotated_value")
        
        assert result is True
        
        value = engine.get_secret(secret_id)
        
        assert value == "new_rotated_value"
    
    def test_rotate_secret_updates_rotated_at(self):
        """Test that rotation updates rotated_at."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        engine.rotate_secret(secret_id, "new_value")
        
        info = engine.get_secret_info(secret_id)
        
        assert info["rotated_at"] is not None
    
    def test_rotate_secret_nonexistent(self):
        """Test rotating nonexistent secret."""
        engine = SecretManagerEngine()
        
        result = engine.rotate_secret("nonexistent", "value")
        
        assert result is False
    
    def test_revoke_secret(self):
        """Test revoking secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        result = engine.revoke_secret(secret_id)
        
        assert result is True
        
        info = engine.get_secret_info(secret_id)
        
        assert info["status"] == "revoked"
    
    def test_revoke_secret_nonexistent(self):
        """Test revoking nonexistent secret."""
        engine = SecretManagerEngine()
        
        result = engine.revoke_secret("nonexistent")
        
        assert result is False
    
    def test_suspend_secret(self):
        """Test suspending secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        result = engine.suspend_secret(secret_id)
        
        assert result is True
        
        info = engine.get_secret_info(secret_id)
        
        assert info["status"] == "suspended"
    
    def test_activate_secret(self):
        """Test activating suspended secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        engine.suspend_secret(secret_id)
        
        result = engine.activate_secret(secret_id)
        
        assert result is True
        
        info = engine.get_secret_info(secret_id)
        
        assert info["status"] == "active"
    
    def test_activate_secret_nonexistent(self):
        """Test activating nonexistent secret."""
        engine = SecretManagerEngine()
        
        result = engine.activate_secret("nonexistent")
        
        assert result is False
    
    def test_set_access_policy(self):
        """Test setting access policy."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        result = engine.set_access_policy(secret_id, {"user1", "user2"})
        
        assert result is True
        
        # user1 should have access
        value = engine.get_secret(secret_id, accessor="user1")
        
        assert value == "value"
        
        # user3 should not
        value = engine.get_secret(secret_id, accessor="user3")
        
        assert value is None
    
    def test_set_access_policy_nonexistent(self):
        """Test setting policy for nonexistent secret."""
        engine = SecretManagerEngine()
        
        result = engine.set_access_policy("nonexistent", {"user1"})
        
        assert result is False
    
    def test_add_accessor(self):
        """Test adding accessor."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        engine.set_access_policy(secret_id, {"user1"})
        
        result = engine.add_accessor(secret_id, "user2")
        
        assert result is True
        
        value = engine.get_secret(secret_id, accessor="user2")
        
        assert value == "value"
    
    def test_remove_accessor(self):
        """Test removing accessor."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        engine.set_access_policy(secret_id, {"user1", "user2"})
        
        result = engine.remove_accessor(secret_id, "user2")
        
        assert result is True
        
        # user2 should no longer have access
        value = engine.get_secret(secret_id, accessor="user2")
        
        assert value is None
    
    def test_get_secret_info(self):
        """Test getting secret info."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            "Test Secret",
            "value",
            secret_type=SecretType.API_KEY,
        )
        
        info = engine.get_secret_info(secret_id)
        
        assert info["name"] == "Test Secret"
        assert info["secret_type"] == "api_key"
        assert "encrypted_value" not in info
    
    def test_get_secret_info_nonexistent(self):
        """Test getting info for nonexistent secret."""
        engine = SecretManagerEngine()
        
        info = engine.get_secret_info("nonexistent")
        
        assert info is None
    
    def test_list_secrets(self):
        """Test listing secrets."""
        engine = SecretManagerEngine()
        
        engine.create_secret("Secret 1", "value1")
        engine.create_secret("Secret 2", "value2")
        engine.create_secret("Secret 3", "value3")
        
        secrets = engine.list_secrets()
        
        assert len(secrets) == 3
    
    def test_list_secrets_by_status(self):
        """Test listing secrets by status."""
        engine = SecretManagerEngine()
        
        id1 = engine.create_secret("Active", "value")
        id2 = engine.create_secret("Revoked", "value")
        engine.revoke_secret(id2)
        
        active = engine.list_secrets(status=SecretStatus.ACTIVE)
        revoked = engine.list_secrets(status=SecretStatus.REVOKED)
        
        assert len(active) == 1
        assert len(revoked) == 1
    
    def test_list_secrets_by_type(self):
        """Test listing secrets by type."""
        engine = SecretManagerEngine()
        
        engine.create_secret("Password", "value", secret_type=SecretType.PASSWORD)
        engine.create_secret("API Key", "value", secret_type=SecretType.API_KEY)
        
        passwords = engine.list_secrets(secret_type=SecretType.PASSWORD)
        api_keys = engine.list_secrets(secret_type=SecretType.API_KEY)
        
        assert len(passwords) == 1
        assert len(api_keys) == 1
    
    def test_list_secrets_by_tag(self):
        """Test listing secrets by tag."""
        engine = SecretManagerEngine()
        
        engine.create_secret("Prod Secret", "value", tags={"production"})
        engine.create_secret("Dev Secret", "value", tags={"development"})
        
        prod = engine.list_secrets(tag="production")
        dev = engine.list_secrets(tag="development")
        
        assert len(prod) == 1
        assert len(dev) == 1
    
    def test_get_versions(self):
        """Test getting version history."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "v1")
        engine.update_secret(secret_id, "v2")
        engine.update_secret(secret_id, "v3")
        
        versions = engine.get_versions(secret_id)
        
        assert len(versions) == 3
    
    def test_get_versions_nonexistent(self):
        """Test getting versions for nonexistent secret."""
        engine = SecretManagerEngine()
        
        versions = engine.get_versions("nonexistent")
        
        assert versions == []
    
    def test_get_audit_log(self):
        """Test getting audit log."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        engine.get_secret(secret_id, accessor="user1")
        engine.get_secret(secret_id, accessor="user2")
        
        logs = engine.get_audit_log(limit=10)
        
        assert len(logs) >= 3  # create + 2 reads
    
    def test_get_audit_log_by_secret(self):
        """Test getting audit log filtered by secret."""
        engine = SecretManagerEngine()
        
        id1 = engine.create_secret("Secret 1", "value")
        id2 = engine.create_secret("Secret 2", "value")
        
        engine.get_secret(id1, accessor="user1")
        engine.get_secret(id2, accessor="user1")
        
        logs1 = engine.get_audit_log(secret_id=id1)
        logs2 = engine.get_audit_log(secret_id=id2)
        
        # Each should only have entries for its secret
        assert all(l["secret_id"] == id1 for l in logs1)
        assert all(l["secret_id"] == id2 for l in logs2)
    
    def test_get_audit_log_by_accessor(self):
        """Test getting audit log filtered by accessor."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        engine.get_secret(secret_id, accessor="user1")
        engine.get_secret(secret_id, accessor="user2")
        engine.get_secret(secret_id, accessor="user1")
        
        logs = engine.get_audit_log(accessor="user1")
        
        # Should only have user1 entries
        assert all(l["accessor"] == "user1" for l in logs)
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = SecretManagerEngine()
        
        engine.create_secret("Secret 1", "value")
        engine.create_secret("Secret 2", "value")
        engine.get_secret(engine._secrets.keys().__iter__().__next__())
        
        stats = engine.get_statistics()
        
        assert stats["total_secrets"] == 2
        assert stats["total_accesses"] >= 1
    
    def test_statistics_active_secrets(self):
        """Test that statistics track active secrets."""
        engine = SecretManagerEngine()
        
        id1 = engine.create_secret("Active", "value")
        id2 = engine.create_secret("To Revoke", "value")
        engine.revoke_secret(id2)
        
        stats = engine.get_statistics()
        
        assert stats["active_secrets"] == 1
        assert stats["revoked_secrets"] == 1
    
    def test_statistics_expired_secrets(self):
        """Test that statistics track expired secrets."""
        engine = SecretManagerEngine()
        
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        engine.create_secret("Expiring", "value", expires_at=past)
        
        # Access to trigger expiration check
        engine.get_secret(engine._secrets.keys().__iter__().__next__())
        
        stats = engine.get_statistics()
        
        assert stats["expired_secrets"] == 1
    
    def test_statistics_needs_rotation(self):
        """Test that statistics track secrets needing rotation."""
        engine = SecretManagerEngine()
        
        past = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        
        engine.create_secret(
            "Rotating", "value",
            rotation_interval_days=30,
            created_at=past,
        )
        
        stats = engine.get_statistics()
        
        assert stats["needs_rotation"] == 1
    
    def test_clear_audit_log(self):
        """Test clearing audit log."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        engine.get_secret(secret_id)
        engine.get_secret(secret_id)
        
        count = engine.clear_audit_log()
        
        assert count > 0
        
        logs = engine.get_audit_log()
        
        assert len(logs) == 0
    
    def test_get_expiring_secrets(self):
        """Test getting expiring secrets."""
        engine = SecretManagerEngine()
        
        soon = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        later = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
        
        engine.create_secret("Soon", "value", expires_at=soon)
        engine.create_secret("Later", "value", expires_at=later)
        
        expiring = engine.get_expiring_secrets(days=30)
        
        assert len(expiring) == 1
        assert expiring[0]["name"] == "Soon"
    
    def test_get_rotation_candidates(self):
        """Test getting rotation candidates."""
        engine = SecretManagerEngine()
        
        past = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        
        engine.create_secret(
            "Needs Rotation", "value",
            rotation_interval_days=30,
            created_at=past,
        )
        
        engine.create_secret("OK", "value", rotation_interval_days=30)
        
        candidates = engine.get_rotation_candidates()
        
        assert len(candidates) == 1
        assert candidates[0]["name"] == "Needs Rotation"
    
    def test_secret_type_enum_values(self):
        """Test secret type enum values."""
        assert SecretType.PASSWORD.value == "password"
        assert SecretType.API_KEY.value == "api_key"
        assert SecretType.TOKEN.value == "token"
        assert SecretType.CERTIFICATE.value == "certificate"
        assert SecretType.GENERIC.value == "generic"
    
    def test_secret_status_enum_values(self):
        """Test secret status enum values."""
        assert SecretStatus.ACTIVE.value == "active"
        assert SecretStatus.EXPIRED.value == "expired"
        assert SecretStatus.REVOKED.value == "revoked"
        assert SecretStatus.SUSPENDED.value == "suspended"
    
    def test_create_secret_access_tracking(self):
        """Test that get_secret tracks access."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        engine.get_secret(secret_id, accessor="user1")
        engine.get_secret(secret_id, accessor="user2")
        engine.get_secret(secret_id, accessor="user1")
        
        info = engine.get_secret_info(secret_id)
        
        assert info["access_count"] == 3
        assert info["last_accessed"] is not None
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test encryption/decryption roundtrip."""
        engine = SecretManagerEngine()
        
        original = "my_secret_value_123!@#"
        
        encrypted = engine._encrypt(original)
        decrypted = engine._decrypt(encrypted)
        
        assert decrypted == original
    
    def test_hash_value_consistent(self):
        """Test that hash is consistent."""
        engine = SecretManagerEngine()
        
        value = "test_value"
        
        hash1 = engine._hash_value(value)
        hash2 = engine._hash_value(value)
        
        assert hash1 == hash2
    
    def test_hash_value_different(self):
        """Test that different values have different hashes."""
        engine = SecretManagerEngine()
        
        hash1 = engine._hash_value("value1")
        hash2 = engine._hash_value("value2")
        
        assert hash1 != hash2
    
    def test_audit_log_limited_to_1000(self):
        """Test that audit log is limited to 1000 entries."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        # Generate many audit entries
        for i in range(1100):
            engine.get_secret(secret_id, accessor=f"user_{i}")
        
        logs = engine.get_audit_log(limit=2000)
        
        assert len(logs) == 1000
    
    def test_version_is_current_tracking(self):
        """Test that version is_current is tracked correctly."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "v1")
        engine.update_secret(secret_id, "v2")
        
        versions = engine.get_versions(secret_id)
        
        # Only the latest should be current
        current_versions = [v for v in versions if v["is_current"]]
        
        assert len(current_versions) == 1
    
    def test_get_secret_updates_last_accessed(self):
        """Test that get_secret updates last_accessed."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        info1 = engine.get_secret_info(secret_id)
        
        assert info1["last_accessed"] is None
        
        engine.get_secret(secret_id)
        
        info2 = engine.get_secret_info(secret_id)
        
        assert info2["last_accessed"] is not None
    
    def test_statistics_failed_accesses(self):
        """Test that statistics track failed accesses."""
        engine = SecretManagerEngine()
        
        engine.get_secret("nonexistent")
        engine.get_secret("also_nonexistent")
        
        stats = engine.get_statistics()
        
        assert stats["failed_accesses"] == 2
    
    def test_statistics_successful_accesses(self):
        """Test that statistics track successful accesses."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        engine.get_secret(secret_id)
        engine.get_secret(secret_id)
        
        stats = engine.get_statistics()
        
        assert stats["successful_accesses"] == 2
    
    def test_statistics_total_rotations(self):
        """Test that statistics track rotations."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        engine.rotate_secret(secret_id, "new_value")
        engine.rotate_secret(secret_id, "newer_value")
        
        stats = engine.get_statistics()
        
        assert stats["total_rotations"] == 2
    
    def test_list_secrets_empty(self):
        """Test listing secrets when empty."""
        engine = SecretManagerEngine()
        
        secrets = engine.list_secrets()
        
        assert secrets == []
    
    def test_get_audit_log_empty(self):
        """Test getting audit log when empty."""
        engine = SecretManagerEngine()
        
        logs = engine.get_audit_log()
        
        assert logs == []
    
    def test_get_audit_log_limit(self):
        """Test audit log limit."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        for i in range(50):
            engine.get_secret(secret_id, accessor=f"user_{i}")
        
        logs = engine.get_audit_log(limit=10)
        
        assert len(logs) == 10
    
    def test_access_policy_no_policy_allows_all(self):
        """Test that no policy allows all accessors."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        # No policy set
        
        value = engine.get_secret(secret_id, accessor="anyone")
        
        assert value == "value"
    
    def test_secret_id_unique(self):
        """Test that secret IDs are unique."""
        engine = SecretManagerEngine()
        
        ids = set()
        for i in range(50):
            secret_id = engine.create_secret(f"Secret {i}", "value")
            ids.add(secret_id)
        
        assert len(ids) == 50
    
    def test_audit_id_unique(self):
        """Test that audit IDs are unique."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        ids = set()
        for i in range(50):
            engine.get_secret(secret_id, accessor=f"user_{i}")
        
        for entry in engine._audit_log:
            ids.add(entry.audit_id)
        
        assert len(ids) == 51  # 50 reads + 1 create
    
    def test_version_id_unique(self):
        """Test that version IDs are unique."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "v1")
        
        for i in range(10):
            engine.update_secret(secret_id, f"v{i+2}")
        
        versions = engine.get_versions(secret_id)
        
        ids = set(v["version_id"] for v in versions)
        
        assert len(ids) == 11
    
    def test_multiple_secrets_independent(self):
        """Test that multiple secrets are independent."""
        engine = SecretManagerEngine()
        
        id1 = engine.create_secret("Secret 1", "value1")
        id2 = engine.create_secret("Secret 2", "value2")
        
        # Revoke secret 1
        engine.revoke_secret(id1)
        
        # Secret 1 should be inaccessible
        assert engine.get_secret(id1) is None
        
        # Secret 2 should still work
        assert engine.get_secret(id2) == "value2"
    
    def test_get_expiring_secrets_empty(self):
        """Test getting expiring secrets when none expiring."""
        engine = SecretManagerEngine()
        
        far_future = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        
        engine.create_secret("Future", "value", expires_at=far_future)
        
        expiring = engine.get_expiring_secrets(days=30)
        
        assert len(expiring) == 0
    
    def test_get_rotation_candidates_empty(self):
        """Test getting rotation candidates when none need rotation."""
        engine = SecretManagerEngine()
        
        engine.create_secret("Fresh", "value", rotation_interval_days=90)
        
        candidates = engine.get_rotation_candidates()
        
        assert len(candidates) == 0
    
    def test_secret_created_at_set(self):
        """Test that secret created_at is set."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        info = engine.get_secret_info(secret_id)
        
        assert info["created_at"] is not None
    
    def test_secret_updated_at_on_update(self):
        """Test that secret updated_at changes on update."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        info1 = engine.get_secret_info(secret_id)
        
        import time
        time.sleep(0.01)
        
        engine.update_secret(secret_id, "new_value")
        
        info2 = engine.get_secret_info(secret_id)
        
        assert info2["updated_at"] > info1["updated_at"]
    
    def test_statistics_total_audit_entries(self):
        """Test that statistics track audit entries."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        engine.get_secret(secret_id)
        
        stats = engine.get_statistics()
        
        assert stats["total_audit_entries"] >= 2
    
    def test_access_policy_case_sensitive(self):
        """Test that access policy is case sensitive."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        engine.set_access_policy(secret_id, {"User1"})
        
        # Different case should not match
        value = engine.get_secret(secret_id, accessor="user1")
        
        assert value is None
    
    def test_tags_as_list_in_dict(self):
        """Test that tags are converted to list in to_dict."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            "Test", "value", tags={"tag1", "tag2"},
        )
        
        info = engine.get_secret_info(secret_id)
        
        assert isinstance(info["tags"], list)
        assert "tag1" in info["tags"]
    
    def test_metadata_empty_by_default(self):
        """Test that metadata is empty dict by default."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        info = engine.get_secret_info(secret_id)
        
        assert info["metadata"] == {}
    
    def test_tags_empty_by_default(self):
        """Test that tags are empty set by default."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("Test", "value")
        
        info = engine.get_secret_info(secret_id)
        
        assert info["tags"] == []
    
    def test_remove_accessor_nonexistent_secret(self):
        """Test removing accessor for nonexistent secret."""
        engine = SecretManagerEngine()
        
        result = engine.remove_accessor("nonexistent", "user1")
        
        assert result is False
    
    def test_add_accessor_nonexistent_secret(self):
        """Test adding accessor for nonexistent secret."""
        engine = SecretManagerEngine()
        
        result = engine.add_accessor("nonexistent", "user1")
        
        assert result is False
    
    def test_get_expiring_secrets_includes_expired(self):
        """Test that expiring secrets includes already expired."""
        engine = SecretManagerEngine()
        
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        engine.create_secret("Expired", "value", expires_at=past)
        
        expiring = engine.get_expiring_secrets(days=30)
        
        assert len(expiring) == 1
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = SecretManagerEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_secrets"] == 0
        assert stats["total_accesses"] == 0
        assert stats["successful_accesses"] == 0
        assert stats["failed_accesses"] == 0
        assert stats["total_rotations"] == 0
        assert stats["total_audit_entries"] == 0
