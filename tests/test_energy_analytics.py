"""Contract tests for Energy Analytics API — Slice 135/181."""
import unittest
import tempfile
import json

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestEnergyAnalyticsAPI(unittest.TestCase):
    """Test energy analytics endpoints."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _create_test_app(self):
        if not create_app:
            self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)

    def test_energy_tariff_analytics(self):
        """GET /api/v1/energy/analytics/tariff returns tariff data."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/energy/analytics/tariff")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("tariff", data)

    def test_energy_battery_analytics(self):
        """GET /api/v1/energy/analytics/battery returns battery data."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/energy/analytics/battery")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("battery", data)

    def test_energy_consumption_patterns(self):
        """GET /api/v1/energy/consumption/patterns returns patterns."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/energy/consumption/patterns")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("patterns", data)


if __name__ == "__main__":
    unittest.main()
