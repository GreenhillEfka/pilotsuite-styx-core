"""Contract tests for Predictive Analytics API — Slice 136/182."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestPredictiveAnalyticsAPI(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _create_test_app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_predictive_suggestions(self):
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/predictive/suggestions")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("suggestions", data)
    def test_predictive_anomalies(self):
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/predictive/anomalies")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("anomalies", data)
    def test_predictive_learning_progress(self):
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/predictive/learning-progress")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("progress", data)
if __name__ == "__main__": unittest.main()
