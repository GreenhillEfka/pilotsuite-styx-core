"""Tests for User Management & RBAC — Slice 26."""
import pytest
from copilot_core.users.engine import (
    UserManagementEngine,
    Permission,
    RoleType,
    create_user_management_engine,
)


class TestUserManagementEngine:
    """Test user management engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_user_management_engine()
        assert engine is not None
    
    def test_default_roles_created(self):
        """Test that default roles are created."""
        engine = UserManagementEngine()
        
        roles = engine.get_all_roles()
        
        assert len(roles) >= 4  # admin, power_user, user, guest
        
        role_names = [r["name"] for r in roles]
        assert "Administrator" in role_names
        assert "Power User" in role_names
        assert "User" in role_names
        assert "Guest" in role_names
    
    def test_create_user(self):
        """Test user creation."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="securepassword123",
        )
        
        assert user_id is not None
        assert user_id.startswith("user_")
        assert user_id in engine._users
        
        user = engine._users[user_id]
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password_hash != ""
        assert user.enabled is True
    
    def test_create_user_with_custom_roles(self):
        """Test user creation with custom roles."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="adminuser",
            email="admin@example.com",
            password="password",
            roles=["role_admin"],
        )
        
        user = engine._users[user_id]
        assert "role_admin" in user.roles
    
    def test_authenticate_user_valid(self):
        """Test authenticating valid user."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
        )
        
        user = engine.authenticate_user("testuser", "password123")
        
        assert user is not None
        assert user.user_id == user_id
        assert user.last_login is not None
    
    def test_authenticate_user_invalid_password(self):
        """Test authenticating with invalid password."""
        engine = UserManagementEngine()
        
        engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
        )
        
        user = engine.authenticate_user("testuser", "wrongpassword")
        
        assert user is None
    
    def test_authenticate_user_unknown(self):
        """Test authenticating unknown user."""
        engine = UserManagementEngine()
        
        user = engine.authenticate_user("unknown_user", "password")
        
        assert user is None
    
    def test_authenticate_disabled_user(self):
        """Test authenticating disabled user."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password",
        )
        
        engine.disable_user(user_id)
        
        user = engine.authenticate_user("testuser", "password")
        
        assert user is None
    
    def test_assign_role(self):
        """Test assigning role to user."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password",
        )
        
        result = engine.assign_role(user_id, "role_admin")
        
        assert result is True
        assert "role_admin" in engine._users[user_id].roles
    
    def test_assign_unknown_role(self):
        """Test assigning unknown role."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password",
        )
        
        result = engine.assign_role(user_id, "unknown_role")
        
        assert result is False
    
    def test_assign_to_unknown_user(self):
        """Test assigning role to unknown user."""
        engine = UserManagementEngine()
        
        result = engine.assign_role("unknown_user", "role_admin")
        
        assert result is False
    
    def test_revoke_role(self):
        """Test revoking role from user."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password",
            roles=["role_admin"],
        )
        
        result = engine.revoke_role(user_id, "role_admin")
        
        assert result is True
        assert "role_admin" not in engine._users[user_id].roles
    
    def test_check_permission_admin(self):
        """Test permission check for admin."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="admin",
            email="admin@example.com",
            password="password",
            roles=["role_admin"],
        )
        
        has_perm = engine.check_permission(user_id, Permission.SYSTEM_ADMIN)
        
        assert has_perm is True
    
    def test_check_permission_guest(self):
        """Test permission check for guest."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="guest",
            email="guest@example.com",
            password="password",
            roles=["role_guest"],
        )
        
        # Guest should have read permissions
        has_read = engine.check_permission(user_id, Permission.ZONE_READ)
        
        # Guest should NOT have write permissions
        has_write = engine.check_permission(user_id, Permission.ZONE_WRITE)
        
        assert has_read is True
        assert has_write is False
    
    def test_check_permission_unknown_user(self):
        """Test permission check for unknown user."""
        engine = UserManagementEngine()
        
        has_perm = engine.check_permission("unknown_user", Permission.SYSTEM_READ)
        
        assert has_perm is False
    
    def test_check_permission_disabled_user(self):
        """Test permission check for disabled user."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password",
            roles=["role_admin"],
        )
        
        engine.disable_user(user_id)
        
        has_perm = engine.check_permission(user_id, Permission.SYSTEM_ADMIN)
        
        assert has_perm is False
    
    def test_create_custom_role(self):
        """Test creating custom role."""
        engine = UserManagementEngine()
        
        role_id = engine.create_role(
            name="Custom Role",
            description="Custom permissions",
            permissions=[Permission.ZONE_READ, Permission.MODULE_READ],
        )
        
        assert role_id is not None
        assert role_id.startswith("role_custom_")
        assert role_id in engine._roles
        
        role = engine._roles[role_id]
        assert role.name == "Custom Role"
        assert role.is_system is False
    
    def test_delete_custom_role(self):
        """Test deleting custom role."""
        engine = UserManagementEngine()
        
        role_id = engine.create_role(
            name="Temp Role",
            description="Temporary",
            permissions=[Permission.ZONE_READ],
        )
        
        result = engine.delete_role(role_id)
        
        assert result is True
        assert role_id not in engine._roles
    
    def test_delete_system_role(self):
        """Test deleting system role (should fail)."""
        engine = UserManagementEngine()
        
        result = engine.delete_role("role_admin")
        
        assert result is False
        assert "role_admin" in engine._roles
    
    def test_get_user(self):
        """Test getting user details."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password",
        )
        
        user = engine.get_user(user_id)
        
        assert user is not None
        assert user["username"] == "testuser"
        assert user["email"] == "test@example.com"
        assert "password_hash" not in user  # Should not expose hash
    
    def test_get_user_by_username(self):
        """Test getting user by username."""
        engine = UserManagementEngine()
        
        engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password",
        )
        
        user = engine.get_user_by_username("testuser")
        
        assert user is not None
        assert user["username"] == "testuser"
    
    def test_get_all_users(self):
        """Test getting all users."""
        engine = UserManagementEngine()
        
        for i in range(5):
            engine.create_user(f"user{i}", f"user{i}@example.com", "password")
        
        users = engine.get_all_users(limit=10)
        
        assert len(users) == 5
    
    def test_get_all_roles(self):
        """Test getting all roles."""
        engine = UserManagementEngine()
        
        # Create custom roles
        engine.create_role("Role 1", "Desc 1", [Permission.ZONE_READ])
        engine.create_role("Role 2", "Desc 2", [Permission.MODULE_READ])
        
        roles = engine.get_all_roles()
        
        assert len(roles) >= 6  # 4 default + 2 custom
    
    def test_get_user_permissions(self):
        """Test getting user permissions."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password",
            roles=["role_admin"],
        )
        
        perms = engine.get_user_permissions(user_id)
        
        assert len(perms) > 0
        assert "system:admin" in perms
    
    def test_get_user_permissions_multiple_roles(self):
        """Test getting permissions from multiple roles."""
        engine = UserManagementEngine()
        
        # Create custom role
        role_id = engine.create_role(
            "Special Role",
            "Special permissions",
            [Permission.ZONE_DELETE, Permission.MODULE_DELETE],
        )
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password",
            roles=["role_user", role_id],
        )
        
        perms = engine.get_user_permissions(user_id)
        
        # Should have permissions from both roles
        assert "zone:write" in perms  # from role_user
        assert "zone:delete" in perms  # from special role
    
    def test_get_audit_logs(self):
        """Test getting audit logs."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password",
        )
        
        # Generate some audit logs
        engine.check_permission(user_id, Permission.ZONE_READ, "zone", "zone_1")
        engine.check_permission(user_id, Permission.SYSTEM_ADMIN, "system", "")
        
        logs = engine.get_audit_logs(limit=10)
        
        assert len(logs) >= 2
    
    def test_get_audit_logs_filtered_by_user(self):
        """Test getting audit logs filtered by user."""
        engine = UserManagementEngine()
        
        user_a = engine.create_user("user_a", "a@example.com", "password")
        user_b = engine.create_user("user_b", "b@example.com", "password")
        
        engine.check_permission(user_a, Permission.ZONE_READ, "zone", "zone_1")
        engine.check_permission(user_b, Permission.ZONE_READ, "zone", "zone_1")
        
        logs_a = engine.get_audit_logs(user_id=user_a)
        logs_b = engine.get_audit_logs(user_id=user_b)
        
        assert len(logs_a) >= 1
        assert len(logs_b) >= 1
        assert all(l["user_id"] == user_a for l in logs_a)
        assert all(l["user_id"] == user_b for l in logs_b)
    
    def test_get_audit_logs_filtered_by_allowed(self):
        """Test getting audit logs filtered by allowed status."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password",
            roles=["role_guest"],
        )
        
        # Allowed check
        engine.check_permission(user_id, Permission.ZONE_READ, "zone", "zone_1")
        
        # Denied check
        engine.check_permission(user_id, Permission.ZONE_WRITE, "zone", "zone_1")
        
        denied_logs = engine.get_audit_logs(allowed=False)
        
        assert len(denied_logs) >= 1
    
    def test_enable_user(self):
        """Test enabling user."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password",
        )
        
        engine.disable_user(user_id)
        result = engine.enable_user(user_id)
        
        assert result is True
        assert engine._users[user_id].enabled is True
    
    def test_disable_user(self):
        """Test disabling user."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user(
            username="testuser",
            email="test@example.com",
            password="password",
        )
        
        result = engine.disable_user(user_id)
        
        assert result is True
        assert engine._users[user_id].enabled is False
    
    def test_get_user_management_summary(self):
        """Test user management summary."""
        engine = UserManagementEngine()
        
        # Create users
        engine.create_user("user1", "u1@example.com", "password")
        engine.create_user("user2", "u2@example.com", "password")
        
        # Disable one
        users = engine.get_all_users()
        engine.disable_user(users[0]["user_id"])
        
        summary = engine.get_user_management_summary()
        
        assert summary["total_users"] == 2
        assert summary["enabled_users"] == 1
        assert summary["system_roles"] >= 4
    
    def test_audit_logs_sorted_newest_first(self):
        """Test that audit logs are sorted newest first."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user("testuser", "test@example.com", "password")
        
        for i in range(5):
            engine.check_permission(user_id, Permission.ZONE_READ, "zone", f"zone_{i}")
        
        logs = engine.get_audit_logs(limit=10)
        
        # Verify sorted by timestamp (newest first)
        for i in range(len(logs) - 1):
            assert logs[i]["timestamp"] >= logs[i + 1]["timestamp"]
    
    def test_audit_logs_trimmed_to_max(self):
        """Test that audit logs are trimmed to max size."""
        engine = UserManagementEngine()
        
        user_id = engine.create_user("testuser", "test@example.com", "password")
        
        # Create more than max logs
        for i in range(10050):
            engine.check_permission(user_id, Permission.ZONE_READ, "zone", f"zone_{i}")
        
        assert len(engine._audit_logs) <= 10000
    
    def test_role_to_dict(self):
        """Test role serialization."""
        from copilot_core.users.engine import Role
        
        role = Role(
            role_id="role_test",
            name="Test Role",
            description="Test description",
            role_type=RoleType.USER,
            permissions={Permission.ZONE_READ, Permission.ZONE_WRITE},
        )
        
        d = role.to_dict()
        
        assert d["role_id"] == "role_test"
        assert d["name"] == "Test Role"
        assert d["role_type"] == "user"
        assert "zone:read" in d["permissions"]
        assert "zone:write" in d["permissions"]
    
    def test_user_to_dict(self):
        """Test user serialization."""
        from copilot_core.users.engine import User
        
        user = User(
            user_id="user_test",
            username="testuser",
            email="test@example.com",
            password_hash="abc123",
            enabled=True,
            roles=["role_user"],
        )
        
        d = user.to_dict()
        
        assert d["user_id"] == "user_test"
        assert d["username"] == "testuser"
        assert d["password_hash"] not in d  # Should not be exposed
        assert d["enabled"] is True
    
    def test_audit_log_to_dict(self):
        """Test audit log serialization."""
        from copilot_core.users.engine import AccessAuditLog
        
        log = AccessAuditLog(
            log_id="audit_test",
            timestamp="2026-03-31T12:00:00Z",
            user_id="user_test",
            action="zone:read",
            resource="zone",
            resource_id="zone_1",
            allowed=True,
            reason="Permission granted",
        )
        
        d = log.to_dict()
        
        assert d["log_id"] == "audit_test"
        assert d["allowed"] is True
        assert d["reason"] == "Permission granted"
    
    def test_permission_enum_values(self):
        """Test permission enum values."""
        assert Permission.ZONE_READ.value == "zone:read"
        assert Permission.ZONE_WRITE.value == "zone:write"
        assert Permission.SYSTEM_ADMIN.value == "system:admin"
        assert Permission.USER_ADMIN.value == "user:admin"
    
    def test_role_type_enum_values(self):
        """Test role type enum values."""
        assert RoleType.ADMIN.value == "admin"
        assert RoleType.POWER_USER.value == "power_user"
        assert RoleType.USER.value == "user"
        assert RoleType.GUEST.value == "guest"
