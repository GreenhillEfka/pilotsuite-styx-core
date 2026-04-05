"""Contract tests for Dashboard Widgets API — Slice 175."""
import unittest
import tempfile
import json

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestDashboardWidgetsAPI(unittest.TestCase):
    """Test dashboard widgets API endpoints."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _create_test_app(self):
        if not create_app:
            self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)

    def test_widget_floorplan_config(self):
        """GET /api/v1/dashboard/widgets/floorplan/config returns config."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/dashboard/widgets/floorplan/config")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertEqual(data.get("widget_type"), "floorplan")

    def test_widget_area_tree_config(self):
        """GET /api/v1/dashboard/widgets/area_tree/config returns config."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/dashboard/widgets/area_tree/config")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertEqual(data.get("widget_type"), "area_tree")

    def test_widget_service_actions_config(self):
        """GET /api/v1/dashboard/widgets/service_actions/config returns config."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/dashboard/widgets/service_actions/config")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertEqual(data.get("widget_type"), "service_actions")

    def test_widget_entity_grid_config(self):
        """GET /api/v1/dashboard/widgets/entity_grid/config returns config."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/dashboard/widgets/entity_grid/config")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertEqual(data.get("widget_type"), "entity_grid")

    def test_widget_floorplan_data_missing_id(self):
        """GET /api/v1/dashboard/widgets/floorplan/data requires floorplan_id."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/dashboard/widgets/floorplan/data")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 400)
            self.assertFalse(data.get("ok"))

    def test_widget_entity_grid_data_missing_ids(self):
        """GET /api/v1/dashboard/widgets/entity_grid/data requires entity_ids."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/dashboard/widgets/entity_grid/data")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 400)
            self.assertFalse(data.get("ok"))

    def test_widget_service_actions_execute_missing_service(self):
        """POST /api/v1/dashboard/widgets/service_actions/execute requires service."""
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.post("/api/v1/dashboard/widgets/service_actions/execute", json={})
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 400)
            self.assertFalse(data.get("ok"))


if __name__ == "__main__":
    unittest.main()
