"""Tests for Secret Manager Engine — Slice 41."""
import pytest
from copilot_core.secrets.engine import (
    SecretManagerEngine,
    SecretType,
    SecretStatus,
    Secret,
    SecretVersion,
    SecretAccessLog,
    create_secret_manager_engine,
)
from datetime import datetime, timezone, timedelta


class TestSecretManagerEngine:
    """Test secret manager engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_secret_manager_engine()
        assert engine is not None
    
    def test_create_secret_password(self):
        """Test creating password secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="db_password",
            value="supersecret123",
            description="Database password",
            secret_type="password",
        )
        
        assert secret_id is not None
        assert secret_id.startswith("secret_")
        
        secret = engine.get_secret(secret_id)
        assert secret is not None
        assert secret["secret_type"] == "password"
    
    def test_create_secret_api_key(self):
        """Test creating API key secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="api_key",
            value="sk-1234567890abcdef",
            description="API key",
            secret_type="api_key",
        )
        
        secret = engine.get_secret(secret_id)
        assert secret["secret_type"] == "api_key"
    
    def test_create_secret_token(self):
        """Test creating token secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="auth_token",
            value="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            description="Auth token",
            secret_type="token",
        )
        
        secret = engine.get_secret(secret_id)
        assert secret["secret_type"] == "token"
    
    def test_create_secret_with_expiration(self):
        """Test creating secret with expiration."""
        engine = SecretManagerEngine()
        
        expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        
        secret_id = engine.create_secret(
            name="temp_secret",
            value="temporary",
            secret_type="generic",
            expires_at=expires_at,
        )
        
        secret = engine.get_secret(secret_id)
        assert secret["expires_at"] == expires_at
    
    def test_create_secret_with_rotation(self):
        """Test creating secret with rotation."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="rotating_secret",
            value="initial_value",
            secret_type="api_key",
            rotation_days=30,
        )
        
        secret = engine.get_secret(secret_id)
        assert secret["rotation_days"] == 30
    
    def test_create_secret_with_tags(self):
        """Test creating secret with tags."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="tagged_secret",
            value="value",
            secret_type="generic",
            tags=["production", "database"],
        )
        
        secret = engine.get_secret(secret_id)
        assert "production" in secret["tags"]
        assert "database" in secret["tags"]
    
    def test_create_secret_with_metadata(self):
        """Test creating secret with metadata."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="meta_secret",
            value="value",
            secret_type="generic",
            metadata={"service": "api", "team": "backend"},
        )
        
        secret = engine.get_secret(secret_id)
        assert secret["metadata"]["service"] == "api"
    
    def test_get_secret_value(self):
        """Test getting secret value."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="my_secret_value",
            secret_type="generic",
        )
        
        value = engine.get_secret_value(secret_id)
        
        assert value == "my_secret_value"
    
    def test_get_secret_value_encrypted(self):
        """Test that stored value is encrypted."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="my_secret_value",
            secret_type="generic",
        )
        
        secret = engine._secrets[secret_id]
        
        # Stored value should be encrypted (base64)
        assert secret.value != "my_secret_value"
        assert len(secret.value) > len("my_secret_value")
    
    def test_get_unknown_secret(self):
        """Test getting unknown secret."""
        engine = SecretManagerEngine()
        
        secret = engine.get_secret("unknown_secret")
        
        assert secret is None
    
    def test_get_unknown_secret_value(self):
        """Test getting unknown secret value."""
        engine = SecretManagerEngine()
        
        value = engine.get_secret_value("unknown_secret")
        
        assert value is None
    
    def test_update_secret(self):
        """Test updating secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="initial_value",
            secret_type="generic",
        )
        
        result = engine.update_secret(secret_id, "new_value")
        
        assert result is True
        
        value = engine.get_secret_value(secret_id)
        assert value == "new_value"
    
    def test_update_secret_creates_version(self):
        """Test that update creates new version."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="v1",
            secret_type="generic",
        )
        
        engine.update_secret(secret_id, "v2")
        engine.update_secret(secret_id, "v3")
        
        versions = engine.get_secret_versions(secret_id)
        
        assert len(versions) == 3
    
    def test_rotate_secret(self):
        """Test rotating secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="rotating_secret",
            value="old_value",
            secret_type="api_key",
            rotation_days=30,
        )
        
        result = engine.rotate_secret(secret_id, "new_rotated_value")
        
        assert result is True
        
        value = engine.get_secret_value(secret_id)
        assert value == "new_rotated_value"
    
    def test_rotate_secret_resets_expiration(self):
        """Test that rotation resets expiration."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="rotating_secret",
            value="old_value",
            secret_type="api_key",
            rotation_days=30,
        )
        
        old_expires = engine._secrets[secret_id].expires_at
        
        engine.rotate_secret(secret_id, "new_value")
        
        new_expires = engine._secrets[secret_id].expires_at
        
        assert new_expires != old_expires
    
    def test_revoke_secret(self):
        """Test revoking secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="value",
            secret_type="generic",
        )
        
        result = engine.revoke_secret(secret_id, reason="Security breach")
        
        assert result is True
        
        secret = engine.get_secret(secret_id)
        assert secret is None  # Revoked secrets can't be accessed
        
        # Check internal status
        assert engine._secrets[secret_id].status == SecretStatus.REVOKED
    
    def test_delete_secret(self):
        """Test deleting secret."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="value",
            secret_type="generic",
        )
        
        result = engine.delete_secret(secret_id)
        
        assert result is True
        assert engine.get_secret(secret_id) is None
    
    def test_delete_unknown_secret(self):
        """Test deleting unknown secret."""
        engine = SecretManagerEngine()
        
        result = engine.delete_secret("unknown_secret")
        
        assert result is False
    
    def test_set_access_policy(self):
        """Test setting access policy."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="restricted_secret",
            value="value",
            secret_type="generic",
        )
        
        result = engine.set_access_policy(secret_id, ["admin", "service_account"])
        
        assert result is True
    
    def test_access_policy_enforcement(self):
        """Test access policy enforcement."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="restricted_secret",
            value="value",
            secret_type="generic",
        )
        
        engine.set_access_policy(secret_id, ["admin"])
        
        # Admin can access
        secret = engine.get_secret(secret_id, accessed_by="admin")
        assert secret is not None
        
        # Other user cannot access
        secret = engine.get_secret(secret_id, accessed_by="other_user")
        assert secret is None
    
    def test_expired_secret_inaccessible(self):
        """Test that expired secret is inaccessible."""
        engine = SecretManagerEngine()
        
        # Create expired secret
        expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        secret_id = engine.create_secret(
            name="expired_secret",
            value="value",
            secret_type="generic",
            expires_at=expires_at,
        )
        
        secret = engine.get_secret(secret_id)
        
        assert secret is None
    
    def test_inactive_secret_inaccessible(self):
        """Test that inactive secret is inaccessible."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="value",
            secret_type="generic",
        )
        
        engine._secrets[secret_id].status = SecretStatus.INACTIVE
        
        secret = engine.get_secret(secret_id)
        
        assert secret is None
    
    def test_get_secret_versions(self):
        """Test getting secret versions."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="versioned_secret",
            value="v1",
            secret_type="generic",
        )
        
        engine.update_secret(secret_id, "v2")
        engine.update_secret(secret_id, "v3")
        
        versions = engine.get_secret_versions(secret_id)
        
        assert len(versions) == 3
        
        # Check current version
        current = [v for v in versions if v["is_current"]]
        assert len(current) == 1
        assert current[0]["version_id"].startswith("v3_")
    
    def test_get_access_log(self):
        """Test getting access log."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="logged_secret",
            value="value",
            secret_type="generic",
        )
        
        engine.get_secret(secret_id, accessed_by="user1")
        engine.get_secret_value(secret_id, accessed_by="user2")
        engine.update_secret(secret_id, "new_value", updated_by="user1")
        
        logs = engine.get_access_log(secret_id=secret_id)
        
        assert len(logs) >= 3
    
    def test_get_access_log_filtered_by_action(self):
        """Test getting access log filtered by action."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="value",
            secret_type="generic",
        )
        
        engine.get_secret(secret_id)
        engine.update_secret(secret_id, "new_value")
        engine.rotate_secret(secret_id, "rotated_value")
        
        read_logs = engine.get_access_log(secret_id=secret_id, action="read")
        write_logs = engine.get_access_log(secret_id=secret_id, action="write")
        rotate_logs = engine.get_access_log(secret_id=secret_id, action="rotate")
        
        assert len(read_logs) >= 1
        assert len(write_logs) >= 1
        assert len(rotate_logs) >= 1
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = SecretManagerEngine()
        
        engine.create_secret("secret1", "value1", secret_type="password")
        engine.create_secret("secret2", "value2", secret_type="api_key")
        engine.create_secret("secret3", "value3", secret_type="token")
        
        engine.get_secret_value("secret1")
        engine.get_secret_value("secret2")
        
        stats = engine.get_statistics()
        
        assert stats["total_secrets"] == 3
        assert stats["total_accesses"] >= 2
        assert "password" in stats["by_type"]
        assert "api_key" in stats["by_type"]
    
    def test_list_secrets(self):
        """Test listing secrets."""
        engine = SecretManagerEngine()
        
        engine.create_secret("secret1", "value1", secret_type="password")
        engine.create_secret("secret2", "value2", secret_type="api_key")
        engine.create_secret("secret3", "value3", secret_type="password", tags=["prod"])
        
        secrets = engine.list_secrets()
        
        assert len(secrets) == 3
    
    def test_list_secrets_filtered_by_type(self):
        """Test listing secrets filtered by type."""
        engine = SecretManagerEngine()
        
        engine.create_secret("secret1", "value1", secret_type="password")
        engine.create_secret("secret2", "value2", secret_type="api_key")
        engine.create_secret("secret3", "value3", secret_type="password")
        
        passwords = engine.list_secrets(secret_type=SecretType.PASSWORD)
        
        assert len(passwords) == 2
        assert all(s["secret_type"] == "password" for s in passwords)
    
    def test_list_secrets_filtered_by_tag(self):
        """Test listing secrets filtered by tag."""
        engine = SecretManagerEngine()
        
        engine.create_secret("secret1", "value1", tags=["prod"])
        engine.create_secret("secret2", "value2", tags=["dev"])
        engine.create_secret("secret3", "value3", tags=["prod", "critical"])
        
        prod_secrets = engine.list_secrets(tag="prod")
        
        assert len(prod_secrets) == 2
    
    def test_list_secrets_filtered_by_status(self):
        """Test listing secrets filtered by status."""
        engine = SecretManagerEngine()
        
        secret1 = engine.create_secret("secret1", "value1")
        secret2 = engine.create_secret("secret2", "value2")
        
        engine.revoke_secret(secret2)
        
        active = engine.list_secrets(status=SecretStatus.ACTIVE)
        revoked = engine.list_secrets(status=SecretStatus.REVOKED)
        
        assert len(active) == 1
        assert len(revoked) == 1
    
    def test_register_rotation_callback(self):
        """Test registering rotation callback."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="rotating_secret",
            value="initial",
            secret_type="api_key",
            rotation_days=1,
        )
        
        def generate_new_value(sid):
            return "auto_generated_value"
        
        result = engine.register_rotation_callback(secret_id, generate_new_value)
        
        assert result is True
    
    def test_get_secrets_requiring_rotation(self):
        """Test getting secrets requiring rotation."""
        engine = SecretManagerEngine()
        
        # Create expired secret
        expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        secret_id = engine.create_secret(
            name="expired_secret",
            value="value",
            secret_type="api_key",
            rotation_days=30,
            expires_at=expires_at,
        )
        
        needs_rotation = engine.get_secrets_requiring_rotation()
        
        assert len(needs_rotation) == 1
        assert needs_rotation[0]["secret_id"] == secret_id
    
    def test_auto_rotate_secrets(self):
        """Test automatic secret rotation."""
        engine = SecretManagerEngine()
        
        # Create expired secret
        expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        secret_id = engine.create_secret(
            name="expired_secret",
            value="old_value",
            secret_type="api_key",
            rotation_days=30,
            expires_at=expires_at,
        )
        
        def generate_new_value(sid):
            return "auto_rotated_value"
        
        engine.register_rotation_callback(secret_id, generate_new_value)
        
        rotated_count = engine.auto_rotate_secrets()
        
        assert rotated_count == 1
        
        value = engine.get_secret_value(secret_id)
        assert value == "auto_rotated_value"
    
    def test_access_log_trimmed_to_max(self):
        """Test that access log is trimmed to max."""
        engine = SecretManagerEngine()
        engine._max_log_size = 100
        
        secret_id = engine.create_secret("test_secret", "value")
        
        for i in range(200):
            engine.get_secret(secret_id, accessed_by=f"user_{i}")
        
        assert len(engine._access_log) <= 100
    
    def test_secret_value_hashed_for_version(self):
        """Test that secret value is hashed for version tracking."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="test_value",
            secret_type="generic",
        )
        
        secret = engine._secrets[secret_id]
        version = secret.versions[0]
        
        # Value hash should be SHA256
        assert len(version.value_hash) == 64
    
    def test_secret_created_by_tracked(self):
        """Test that created_by is tracked."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="value",
            secret_type="generic",
            created_by="admin_user",
        )
        
        secret = engine.get_secret(secret_id)
        
        assert secret["created_by"] == "admin_user"
    
    def test_secret_updated_at_changes_on_update(self):
        """Test that updated_at changes on update."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="value",
            secret_type="generic",
        )
        
        import time
        time.sleep(0.01)
        
        engine.update_secret(secret_id, "new_value")
        
        secret = engine.get_secret(secret_id)
        
        assert secret["updated_at"] >= secret["created_at"]
    
    def test_access_count_incremented(self):
        """Test that access count is incremented."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="value",
            secret_type="generic",
        )
        
        for i in range(5):
            engine.get_secret_value(secret_id)
        
        secret = engine._secrets[secret_id]
        
        assert secret.access_count == 5
    
    def test_last_accessed_tracked(self):
        """Test that last_accessed is tracked."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="value",
            secret_type="generic",
        )
        
        engine.get_secret_value(secret_id)
        
        secret = engine._secrets[secret_id]
        
        assert secret.last_accessed is not None
    
    def test_statistics_track_failed_accesses(self):
        """Test that statistics track failed accesses."""
        engine = SecretManagerEngine()
        
        # Try to access non-existent secret
        for i in range(5):
            engine.get_secret("nonexistent", accessed_by="user")
        
        stats = engine.get_statistics()
        
        assert stats["failed_accesses"] == 5
    
    def test_statistics_track_rotations(self):
        """Test that statistics track rotations."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="value",
            secret_type="generic",
        )
        
        engine.rotate_secret(secret_id, "new_value")
        engine.rotate_secret(secret_id, "another_value")
        
        stats = engine.get_statistics()
        
        assert stats["rotations"] == 2
    
    def test_statistics_expiring_soon(self):
        """Test that statistics include expiring soon count."""
        engine = SecretManagerEngine()
        
        # Create secret expiring in 3 days
        expires_at = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        
        engine.create_secret(
            name="expiring_secret",
            value="value",
            secret_type="generic",
            expires_at=expires_at,
        )
        
        stats = engine.get_statistics()
        
        assert stats["expiring_soon"] >= 1
    
    def test_secret_type_enum_values(self):
        """Test secret type enum values."""
        assert SecretType.PASSWORD.value == "password"
        assert SecretType.API_KEY.value == "api_key"
        assert SecretType.TOKEN.value == "token"
        assert SecretType.CERTIFICATE.value == "certificate"
        assert SecretType.PRIVATE_KEY.value == "private_key"
        assert SecretType.CONNECTION_STRING.value == "connection_string"
        assert SecretType.GENERIC.value == "generic"
    
    def test_secret_status_enum_values(self):
        """Test secret status enum values."""
        assert SecretStatus.ACTIVE.value == "active"
        assert SecretStatus.INACTIVE.value == "inactive"
        assert SecretStatus.EXPIRED.value == "expired"
        assert SecretStatus.REVOKED.value == "revoked"
        assert SecretStatus.PENDING_ROTATION.value == "pending_rotation"
    
    def test_secret_to_dict_excludes_value_by_default(self):
        """Test that secret.to_dict excludes value by default."""
        secret = Secret(
            secret_id="secret_test",
            name="Test Secret",
            description="Test",
            secret_type=SecretType.PASSWORD,
            value="encrypted_value",
        )
        
        d = secret.to_dict()
        
        assert "value" not in d
    
    def test_secret_to_dict_includes_value_when_requested(self):
        """Test that secret.to_dict includes value when requested."""
        secret = Secret(
            secret_id="secret_test",
            name="Test Secret",
            description="Test",
            secret_type=SecretType.PASSWORD,
            value="encrypted_value",
        )
        
        d = secret.to_dict(include_value=True)
        
        assert "value" in d
        assert d["value"] == "encrypted_value"
    
    def test_secret_version_to_dict(self):
        """Test secret version serialization."""
        version = SecretVersion(
            version_id="v1_test",
            secret_id="secret_test",
            value_hash="abc123",
            created_at="2026-03-31T12:00:00Z",
            created_by="admin",
            is_current=True,
        )
        
        d = version.to_dict()
        
        assert d["version_id"] == "v1_test"
        assert d["is_current"] is True
    
    def test_secret_access_log_to_dict(self):
        """Test secret access log serialization."""
        log = SecretAccessLog(
            log_id="log_test",
            secret_id="secret_test",
            action="read",
            accessed_by="user",
            accessed_at="2026-03-31T12:00:00Z",
            success=True,
            reason="OK",
        )
        
        d = log.to_dict()
        
        assert d["log_id"] == "log_test"
        assert d["action"] == "read"
        assert d["success"] is True
    
    def test_encryption_key_customization(self):
        """Test custom encryption key."""
        engine = SecretManagerEngine(encryption_key="custom_key")
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="value",
            secret_type="generic",
        )
        
        value = engine.get_secret_value(secret_id)
        
        assert value == "value"
    
    def test_different_encryption_keys_produce_different_ciphertext(self):
        """Test that different keys produce different encrypted values."""
        engine1 = SecretManagerEngine(encryption_key="key1")
        engine2 = SecretManagerEngine(encryption_key="key2")
        
        secret_id1 = engine1.create_secret("test", "value", secret_type="generic")
        secret_id2 = engine2.create_secret("test", "value", secret_type="generic")
        
        # Encrypted values should be different
        assert engine1._secrets[secret_id1].value != engine2._secrets[secret_id2].value
        
        # But decrypted values should be the same
        assert engine1.get_secret_value(secret_id1) == engine2.get_secret_value(secret_id2)
    
    def test_access_log_sorted_newest_first(self):
        """Test that access log is sorted newest first."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("test_secret", "value")
        
        for i in range(5):
            engine.get_secret(secret_id, accessed_by=f"user_{i}")
        
        logs = engine.get_access_log(secret_id=secret_id)
        
        # Verify sorted (newest first)
        for i in range(len(logs) - 1):
            assert logs[i]["accessed_at"] >= logs[i + 1]["accessed_at"]
    
    def test_access_log_limit(self):
        """Test access log limit."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("test_secret", "value")
        
        for i in range(50):
            engine.get_secret(secret_id, accessed_by=f"user_{i}")
        
        logs = engine.get_access_log(secret_id=secret_id, limit=10)
        
        assert len(logs) == 10
    
    def test_revoke_reason_stored(self):
        """Test that revocation reason is stored."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="value",
            secret_type="generic",
        )
        
        engine.revoke_secret(secret_id, reason="Compromised credentials")
        
        secret = engine._secrets[secret_id]
        
        assert secret.metadata["revocation_reason"] == "Compromised credentials"
    
    def test_create_secret_generates_initial_version(self):
        """Test that creating secret generates initial version."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="value",
            secret_type="generic",
        )
        
        versions = engine.get_secret_versions(secret_id)
        
        assert len(versions) == 1
        assert versions[0]["is_current"] is True
    
    def test_rotate_secret_marks_old_versions_not_current(self):
        """Test that rotation marks old versions as not current."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="test_secret",
            value="v1",
            secret_type="generic",
        )
        
        engine.rotate_secret(secret_id, "v2")
        
        versions = engine.get_secret_versions(secret_id)
        
        v1 = [v for v in versions if v["version_id"].startswith("v1_")]
        v2 = [v for v in versions if v["version_id"].startswith("v2_")]
        
        assert v1[0]["is_current"] is False
        assert v2[0]["is_current"] is True
    
    def test_update_secret_value_not_found(self):
        """Test updating non-existent secret."""
        engine = SecretManagerEngine()
        
        result = engine.update_secret("unknown_secret", "value")
        
        assert result is False
    
    def test_rotate_secret_value_not_found(self):
        """Test rotating non-existent secret."""
        engine = SecretManagerEngine()
        
        result = engine.rotate_secret("unknown_secret", "value")
        
        assert result is False
    
    def test_revoke_secret_not_found(self):
        """Test revoking non-existent secret."""
        engine = SecretManagerEngine()
        
        result = engine.revoke_secret("unknown_secret")
        
        assert result is False
    
    def test_set_access_policy_not_found(self):
        """Test setting access policy for non-existent secret."""
        engine = SecretManagerEngine()
        
        result = engine.set_access_policy("unknown_secret", ["admin"])
        
        assert result is False
    
    def test_register_rotation_callback_not_found(self):
        """Test registering rotation callback for non-existent secret."""
        engine = SecretManagerEngine()
        
        def callback(sid):
            return "value"
        
        result = engine.register_rotation_callback("unknown_secret", callback)
        
        assert result is False
    
    def test_get_secret_versions_not_found(self):
        """Test getting versions for non-existent secret."""
        engine = SecretManagerEngine()
        
        versions = engine.get_secret_versions("unknown_secret")
        
        assert versions == []
    
    def test_list_secrets_empty(self):
        """Test listing secrets when empty."""
        engine = SecretManagerEngine()
        
        secrets = engine.list_secrets()
        
        assert secrets == []
    
    def test_statistics_empty_engine(self):
        """Test statistics with empty engine."""
        engine = SecretManagerEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_secrets"] == 0
        assert stats["total_accesses"] == 0
        assert stats["failed_accesses"] == 0
    
    def test_auto_rotate_secrets_with_failed_callback(self):
        """Test auto-rotation with failing callback."""
        engine = SecretManagerEngine()
        
        # Create expired secret
        expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        secret_id = engine.create_secret(
            name="expired_secret",
            value="value",
            secret_type="api_key",
            expires_at=expires_at,
        )
        
        def failing_callback(sid):
            raise Exception("Rotation failed")
        
        engine.register_rotation_callback(secret_id, failing_callback)
        
        # Should not raise, just log error
        rotated_count = engine.auto_rotate_secrets()
        
        assert rotated_count == 0
    
    def test_secret_with_all_fields(self):
        """Test creating secret with all fields."""
        expires_at = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
        
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret(
            name="complete_secret",
            value="super_secret_value",
            description="Complete test secret",
            secret_type="api_key",
            expires_at=expires_at,
            rotation_days=30,
            tags=["production", "critical"],
            metadata={"service": "api", "team": "platform"},
            created_by="admin",
        )
        
        secret = engine.get_secret(secret_id)
        
        assert secret["name"] == "complete_secret"
        assert secret["secret_type"] == "api_key"
        assert secret["expires_at"] == expires_at
        assert secret["rotation_days"] == 30
        assert len(secret["tags"]) == 2
        assert secret["metadata"]["service"] == "api"
        assert secret["created_by"] == "admin"
    
    def test_get_secret_updates_last_accessed(self):
        """Test that get_secret updates last_accessed."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("test_secret", "value", secret_type="generic")
        
        before = engine._secrets[secret_id].last_accessed
        
        import time
        time.sleep(0.01)
        
        engine.get_secret(secret_id, accessed_by="user")
        
        after = engine._secrets[secret_id].last_accessed
        
        assert after is not None
        assert after >= before
    
    def test_version_count_in_metadata(self):
        """Test that version count is in metadata."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("test_secret", "v1", secret_type="generic")
        
        engine.update_secret(secret_id, "v2")
        engine.update_secret(secret_id, "v3")
        
        secret = engine.get_secret(secret_id)
        
        assert secret["version_count"] == 3
    
    def test_access_log_action_types(self):
        """Test different access log action types."""
        engine = SecretManagerEngine()
        
        secret_id = engine.create_secret("test_secret", "value", secret_type="generic")
        
        engine.get_secret(secret_id)  # read
        engine.update_secret(secret_id, "new_value")  # write
        engine.rotate_secret(secret_id, "rotated")  # rotate
        engine.revoke_secret(secret_id)  # revoke
        engine.delete_secret(secret_id)  # delete
        
        logs = engine.get_access_log(secret_id=secret_id, limit=10)
        
        actions = [l["action"] for l in logs]
        
        assert "read" in actions
        assert "write" in actions
        assert "rotate" in actions
        assert "revoke" in actions
        assert "delete" in actions
