"""Stress Tests — Slice 196."""
import unittest, tempfile, json, concurrent.futures
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestStress(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def _concurrent_requests(self, client, endpoint, count=50):
        def req(): return client.get(endpoint).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            results = list(ex.map(lambda _: req(), range(count)))
        return all(r == 200 for r in results)
    def test_health_endpoint_stress(self):
        with self._app().test_client() as c:
            self.assertTrue(self._concurrent_requests(c, "/api/v1/health"))
    def test_presence_endpoint_stress(self):
        with self._app().test_client() as c:
            self.assertTrue(self._concurrent_requests(c, "/api/v1/presence/state"))
    def test_vector_search_stress(self):
        with self._app().test_client() as c:
            self.assertTrue(self._concurrent_requests(c, "/api/v1/vector/search?q=test"))
if __name__ == "__main__": unittest.main()
