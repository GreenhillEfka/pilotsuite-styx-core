"""Batch Contract Tests Part 2 — Slices 151-165."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestBatchPart2(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_backup(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/backup/schedules").data)
            self.assertTrue(r.get("ok"))
    def test_reports(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/reports/templates").data)
            self.assertTrue(r.get("ok"))
    def test_webhooks(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/webhooks/triggers").data)
            self.assertTrue(r.get("ok"))
    def test_integrations(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/integrations/status").data)
            self.assertTrue(r.get("ok"))
    def test_automation(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/automation/templates").data)
            self.assertTrue(r.get("ok"))
    def test_jobs(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/jobs/queue").data)
            self.assertTrue(r.get("ok"))
    def test_cache(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/cache/keys").data)
            self.assertTrue(r.get("ok"))
    def test_search(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/search/advanced?q=test").data)
            self.assertTrue(r.get("ok"))
    def test_tags(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/tags/hierarchies").data)
            self.assertTrue(r.get("ok"))
    def test_media(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/media/albums").data)
            self.assertTrue(r.get("ok"))
if __name__ == "__main__": unittest.main()
