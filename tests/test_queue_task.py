"""Queue & Task Tests — Slice 286 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestQueueTask(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_queue_status(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/queue/status")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_enqueue_task(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/tasks/enqueue", json={"type": "process"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_tasks_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/tasks/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_cancel_task(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/tasks/cancel", json={"task_id": "t1"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
