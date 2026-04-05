"""Contract tests for HACS Gating API — Slice 179."""
import unittest
import tempfile
import json

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestHACSGateAPI(unittest.TestCase):
    """Test HACS gating endpoints."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _create_test_app(self):
        if not create_app:
            self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)

    def test_hacs_gate_returns_status(self):
        """GET /api/v1/hacs/gate returns gate status."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/hacs/gate")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("can_proceed", data)
            self.assertIn("checks", data)

    def test_hacs_gate_check_structure(self):
        """GET /api/v1/hacs/gate returns proper check structure."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/hacs/gate")
            data = json.loads(rv.data)
            checks = data.get("checks", {})
            self.assertIn("no_release_lock", checks)
            self.assertIn("system_healthy", checks)
            self.assertIn("version_parity", checks)

    def test_hacs_lock_endpoint_exists(self):
        """POST /api/v1/hacs/lock endpoint exists."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.post("/api/v1/hacs/lock", json={})
            # May return 401/403 if auth required, but endpoint should exist
            self.assertIn(rv.status_code, [200, 401, 403])


if __name__ == "__main__":
    unittest.main()
