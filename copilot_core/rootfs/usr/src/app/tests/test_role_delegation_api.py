"""Tests for Role Inference + Delegation API endpoints (v4.3.0).

Covers:
- GET /user/<id>/role
- GET /user/roles
- POST /user/<id>/device/<id>
- GET /user/<id>/access/<id>
- POST /user/<id>/delegate
- DELETE /user/<id>/delegate
- GET /user/delegations
"""

import json
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

try:
    from flask import Flask
    from copilot_core.api.v1.user_preferences import bp as user_prefs_bp
    from copilot_core.neurons.mupl import (
        MultiUserPreferenceLearning,
        UserRole,
        create_mupl_module,
    )
    from copilot_core.storage.user_preferences import (
        UserPreferenceStore,
        init_user_preference_store,
    )
except ImportError:
    Flask = None


def _build_app(store, mupl):
    """Create a minimal Flask app with the user_preferences blueprint."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    # Provide a fake auth token so _require_auth passes
    app.config["AUTH_TOKEN"] = "test_token"

    # Attach MUPL + config
    cfg = MagicMock()
    cfg.mupl = mupl
    app.config["COPILOT_CFG"] = cfg

    app.register_blueprint(user_prefs_bp, url_prefix="/user")
    return app


class TestRoleAPI(unittest.TestCase):
    """Test role inference endpoints."""

    def setUp(self):
        if Flask is None:
            self.skipTest("Flask not available")

        self._tmp = tempfile.mkdtemp()
        self.store = init_user_preference_store(data_dir=self._tmp, persist=True)
        self.mupl = create_mupl_module()
        self.app = _build_app(self.store, self.mupl)
        self.client = self.app.test_client()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _auth(self):
        return {"X-Auth-Token": "test_token"}

    # ---------- GET /user/<id>/role ----------

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_unknown_user_returns_unknown_role(self, _mock_auth):
        resp = self.client.get("/user/person.nobody/role", headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["role"], "unknown")
        self.assertEqual(data["confidence"], 0.0)

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_device_manager_role(self, _mock_auth):
        # Register enough devices + automations
        for i in range(6):
            self.mupl.register_device_control("person.admin", f"light.room_{i}")
        for i in range(4):
            self.mupl.register_automation_created("person.admin", {"id": f"auto_{i}"})

        resp = self.client.get("/user/person.admin/role", headers=self._auth())
        data = resp.get_json()
        self.assertEqual(data["role"], "device_manager")
        self.assertEqual(data["device_count"], 6)
        self.assertEqual(data["automation_count"], 4)

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_everyday_user_role(self, _mock_auth):
        self.mupl.register_device_control("person.bob", "light.a")
        self.mupl.register_device_control("person.bob", "light.b")

        resp = self.client.get("/user/person.bob/role", headers=self._auth())
        data = resp.get_json()
        self.assertEqual(data["role"], "everyday_user")

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_restricted_user_role(self, _mock_auth):
        self.mupl.register_device_control("person.child", "light.bedroom")

        resp = self.client.get("/user/person.child/role", headers=self._auth())
        data = resp.get_json()
        self.assertEqual(data["role"], "restricted_user")

    # ---------- GET /user/roles ----------

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_get_all_roles(self, _mock_auth):
        self.mupl.register_device_control("person.a", "l.1")
        self.mupl.register_device_control("person.a", "l.2")
        self.mupl.register_device_control("person.b", "l.3")

        resp = self.client.get("/user/roles", headers=self._auth())
        data = resp.get_json()
        self.assertEqual(data["count"], 2)
        self.assertIn("person.a", data["roles"])
        self.assertIn("person.b", data["roles"])

    # ---------- POST /user/<id>/device/<id> ----------

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_register_device_usage(self, _mock_auth):
        resp = self.client.post(
            "/user/person.x/device/light.kitchen",
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "ok")

        # Verify device is tracked in MUPL
        profile = self.mupl.get_user_profile("person.x")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.device_count, 1)

    # ---------- GET /user/<id>/access/<id> ----------

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_rbac_access_check(self, _mock_auth):
        self.mupl.register_device_control("person.u", "light.a")

        # Has access to registered device
        resp = self.client.get("/user/person.u/access/light.a", headers=self._auth())
        data = resp.get_json()
        self.assertTrue(data["allowed"])

        # No access to unregistered device
        resp = self.client.get("/user/person.u/access/light.z", headers=self._auth())
        data = resp.get_json()
        self.assertFalse(data["allowed"])


class TestDelegationAPI(unittest.TestCase):
    """Test delegation workflow endpoints."""

    def setUp(self):
        if Flask is None:
            self.skipTest("Flask not available")

        self._tmp = tempfile.mkdtemp()
        self.store = init_user_preference_store(data_dir=self._tmp, persist=True)
        self.mupl = create_mupl_module()

        # Make person.admin a device manager
        for i in range(6):
            self.mupl.register_device_control("person.admin", f"light.room_{i}")
        for i in range(4):
            self.mupl.register_automation_created("person.admin", {"id": f"a_{i}"})

        self.app = _build_app(self.store, self.mupl)
        self.client = self.app.test_client()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _auth(self):
        return {
            "X-Auth-Token": "test_token",
            "Content-Type": "application/json",
        }

    # ---------- POST /user/<id>/delegate ----------

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_delegate_device_success(self, _mock_auth):
        resp = self.client.post(
            "/user/person.admin/delegate",
            headers=self._auth(),
            data=json.dumps({
                "target_user_id": "person.guest",
                "device_id": "light.room_0",
                "expires_hours": 2,
            }),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "delegated")
        self.assertEqual(data["to"], "person.guest")
        self.assertIsNotNone(data["expires_at"])

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_delegate_requires_device_manager(self, _mock_auth):
        # person.nobody has no devices — not a device manager
        resp = self.client.post(
            "/user/person.nobody/delegate",
            headers=self._auth(),
            data=json.dumps({
                "target_user_id": "person.guest",
                "device_id": "light.x",
            }),
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertEqual(data["error"], "only_device_managers_can_delegate")

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_delegate_missing_fields_returns_400(self, _mock_auth):
        resp = self.client.post(
            "/user/person.admin/delegate",
            headers=self._auth(),
            data=json.dumps({"target_user_id": "person.guest"}),
        )
        self.assertEqual(resp.status_code, 400)

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_delegate_permanent(self, _mock_auth):
        resp = self.client.post(
            "/user/person.admin/delegate",
            headers=self._auth(),
            data=json.dumps({
                "target_user_id": "person.member",
                "device_id": "light.room_1",
                "expires_hours": 0,
            }),
        )
        data = resp.get_json()
        self.assertEqual(data["status"], "delegated")
        self.assertIsNone(data["expires_at"])

    # ---------- DELETE /user/<id>/delegate ----------

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_revoke_delegation(self, _mock_auth):
        # First delegate
        self.client.post(
            "/user/person.admin/delegate",
            headers=self._auth(),
            data=json.dumps({
                "target_user_id": "person.guest",
                "device_id": "light.room_0",
            }),
        )

        # Then revoke
        resp = self.client.delete(
            "/user/person.admin/delegate",
            headers=self._auth(),
            data=json.dumps({
                "target_user_id": "person.guest",
                "device_id": "light.room_0",
            }),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "revoked")
        self.assertEqual(data["removed"], 1)

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_revoke_nonexistent_removes_zero(self, _mock_auth):
        resp = self.client.delete(
            "/user/person.admin/delegate",
            headers=self._auth(),
            data=json.dumps({
                "target_user_id": "person.ghost",
                "device_id": "light.none",
            }),
        )
        data = resp.get_json()
        self.assertEqual(data["removed"], 0)

    # ---------- GET /user/delegations ----------

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_list_delegations(self, _mock_auth):
        # Create two delegations
        for i in range(2):
            self.client.post(
                "/user/person.admin/delegate",
                headers=self._auth(),
                data=json.dumps({
                    "target_user_id": f"person.user_{i}",
                    "device_id": f"light.room_{i}",
                }),
            )

        resp = self.client.get("/user/delegations", headers=self._auth())
        data = resp.get_json()
        self.assertEqual(data["count"], 2)

    @patch("copilot_core.api.v1.user_preferences._validate_token", return_value=True)
    def test_expired_delegations_filtered(self, _mock_auth):
        # Create a delegation that's already expired
        self.store._save_extra("delegations", [
            {
                "from": "person.admin",
                "to": "person.old",
                "device_id": "light.x",
                "created_at": time.time() - 100000,
                "expires_at": time.time() - 1,  # expired
            },
            {
                "from": "person.admin",
                "to": "person.current",
                "device_id": "light.y",
                "created_at": time.time(),
                "expires_at": None,  # permanent
            },
        ])

        resp = self.client.get("/user/delegations", headers=self._auth())
        data = resp.get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["delegations"][0]["to"], "person.current")


class TestExtraStorage(unittest.TestCase):
    """Test _load_extra / _save_extra helpers."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.store = UserPreferenceStore(data_dir=self._tmp, persist=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_roundtrip(self):
        payload = {"key": "value", "list": [1, 2, 3]}
        self.store._save_extra("test_blob", payload)
        loaded = self.store._load_extra("test_blob")
        self.assertEqual(loaded, payload)

    def test_load_missing_returns_none(self):
        self.assertIsNone(self.store._load_extra("nonexistent"))

    def test_save_disabled_when_persist_false(self):
        store = UserPreferenceStore(data_dir=self._tmp, persist=False)
        store._save_extra("should_not_write", {"x": 1})
        self.assertIsNone(store._load_extra("should_not_write"))


if __name__ == "__main__":
    unittest.main()
