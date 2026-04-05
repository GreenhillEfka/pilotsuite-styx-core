"""Contract tests for Areas/Floorplan Integration — Slice 174."""
import unittest
import tempfile
import json

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestAreasFloorplanIntegration(unittest.TestCase):
    """Test areas/floorplan integration endpoints."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _create_test_app(self):
        if not create_app:
            self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)

    def test_areas_get_floorplan_missing(self):
        """GET /api/v1/areas/<id>/floorplan returns 404 if not associated."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/areas/test-area/floorplan")
            self.assertEqual(rv.status_code, 404)

    def test_areas_set_floorplan_missing_id(self):
        """PUT /api/v1/areas/<id>/floorplan requires floorplan_id."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.put("/api/v1/areas/test-area/floorplan", json={})
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 400)
            self.assertFalse(data.get("ok"))

    def test_floorplan_zones_resolve(self):
        """GET /api/v1/floorplan/<id>/zones/resolve returns zone mapping."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/floorplan/fp1/zones/resolve")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("zone_resolution", data)

    def test_floorplan_navigation(self):
        """GET /api/v1/floorplan/<id>/navigation returns nav data."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/floorplan/fp1/navigation")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("navigation", data)


if __name__ == "__main__":
    unittest.main()
