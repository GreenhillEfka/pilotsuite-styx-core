"""Update & Firmware Tests — Slice 272 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestUpdateFirmware(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_updates_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/updates/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_install_update(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/updates/install", json={"update_id": "v1.0.1"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_firmware_state(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/firmware/state")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_firmware_update(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/firmware/update")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
