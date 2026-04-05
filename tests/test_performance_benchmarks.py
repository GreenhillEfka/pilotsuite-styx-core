"""Performance Benchmarks — Slice 191."""
import unittest, tempfile, json, time
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestPerformanceBenchmarks(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def _benchmark(self, client, endpoint, iterations=10):
        latencies = []
        for _ in range(iterations):
            start = time.perf_counter()
            client.get(endpoint)
            latencies.append((time.perf_counter() - start) * 1000)
        latencies.sort()
        return {"p50": latencies[len(latencies)//2], "p95": latencies[int(len(latencies)*0.95)], "p99": latencies[int(len(latencies)*0.99)]}
    def test_hacs_gate_latency(self):
        with self._app().test_client() as c:
            metrics = self._benchmark(c, "/api/v1/hacs/gate")
            self.assertLess(metrics["p95"], 100)  # <100ms p95
    def test_hacs_discovery_latency(self):
        with self._app().test_client() as c:
            metrics = self._benchmark(c, "/api/hacs/discovery")
            self.assertLess(metrics["p95"], 100)
    def test_energy_analytics_latency(self):
        with self._app().test_client() as c:
            metrics = self._benchmark(c, "/api/v1/energy/analytics/tariff")
            self.assertLess(metrics["p95"], 150)
    def test_presence_latency(self):
        with self._app().test_client() as c:
            metrics = self._benchmark(c, "/api/v1/presence/state")
            self.assertLess(metrics["p95"], 50)
    def test_vector_search_latency(self):
        with self._app().test_client() as c:
            metrics = self._benchmark(c, "/api/v1/vector/search?q=test")
            self.assertLess(metrics["p95"], 200)
if __name__ == "__main__": unittest.main()
