"""Contract tests for HACS Discovery API — Slice 180."""
import unittest
import tempfile
import json

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestHACSDiscoveryAPI(unittest.TestCase):
    """Test HACS discovery endpoints."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _create_test_app(self):
        if not create_app:
            self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)

    def test_hacs_discovery_returns_metadata(self):
        """GET /api/hacs/discovery returns repository metadata."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/hacs/discovery")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("name", data)
            self.assertIn("version", data)
            self.assertIn("manifest", data)

    def test_hacs_versions_returns_list(self):
        """GET /api/hacs/versions returns version list."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/hacs/versions")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("versions", data)
            self.assertIn("latest", data)


if __name__ == "__main__":
    unittest.main()
