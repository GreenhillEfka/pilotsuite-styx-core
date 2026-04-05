"""Integration Tests — Slice 193."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestIntegration(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_hacs_gate_to_discovery_flow(self):
        with self._app().test_client() as c:
            gate = json.loads(c.get("/api/v1/hacs/gate").data)
            self.assertTrue(gate.get("ok"))
            if gate.get("can_proceed"):
                discovery = json.loads(c.get("/api/hacs/discovery").data)
                self.assertTrue(discovery.get("ok"))
    def test_presence_to_energy_correlation(self):
        with self._app().test_client() as c:
            presence = json.loads(c.get("/api/v1/presence/state").data)
            energy = json.loads(c.get("/api/v1/energy/analytics/tariff").data)
            self.assertTrue(presence.get("ok"))
            self.assertTrue(energy.get("ok"))
    def test_vector_search_to_rag_flow(self):
        with self._app().test_client() as c:
            vector = json.loads(c.get("/api/v1/vector/collections").data)
            rag = json.loads(c.get("/api/v1/rag/search/analytics").data)
            self.assertTrue(vector.get("ok"))
            self.assertTrue(rag.get("ok"))
if __name__ == "__main__": unittest.main()
