"""Tests for /api/v1/capabilities endpoint."""

import tempfile
import unittest

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestCapabilitiesEndpoint(unittest.TestCase):
    """Test /api/v1/capabilities endpoint functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        """Clean up test fixtures."""
        self.tmpdir.cleanup()

    def _create_test_app(self):
        """Create a test Flask app with temp paths."""
        app = create_app()
        from dataclasses import replace

        cfg = app.config["COPILOT_CFG"]
        app.config["COPILOT_CFG"] = replace(
            cfg,
            data_dir=self.tmpdir.name,
            brain_graph_json_path=f"{self.tmpdir.name}/brain_graph.db",
            events_jsonl_path=f"{self.tmpdir.name}/events.jsonl",
            candidates_json_path=f"{self.tmpdir.name}/candidates.json",
            brain_graph_nodes_max=500,
            brain_graph_edges_max=1500,
            brain_graph_persist=True,
        )
        return app

    def test_capabilities_endpoint_returns_200(self):
        """Test /api/v1/capabilities returns HTTP 200."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        self.assertEqual(r.status_code, 200)

    def test_capabilities_endpoint_returns_ok_true(self):
        """Test /api/v1/capabilities returns ok: true."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_capabilities_endpoint_returns_version(self):
        """Test /api/v1/capabilities returns version field."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        self.assertIn("version", j)

    def test_capabilities_endpoint_returns_modules(self):
        """Test /api/v1/capabilities returns modules field."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        self.assertIn("modules", j)
        self.assertIsInstance(j["modules"], dict)

    def test_capabilities_endpoint_has_events_module(self):
        """Test /api/v1/capabilities has events module."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        self.assertIn("events", j["modules"])
        
        events = j["modules"]["events"]
        self.assertIn("enabled", events)
        self.assertIsInstance(events["enabled"], bool)

    def test_capabilities_endpoint_events_has_persist(self):
        """Test events module has persist field."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        events = j["modules"]["events"]
        self.assertIn("persist", events)
        self.assertIsInstance(events["persist"], bool)

    def test_capabilities_endpoint_events_has_cache_max(self):
        """Test events module has cache_max field."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        events = j["modules"]["events"]
        self.assertIn("cache_max", events)
        self.assertIsInstance(events["cache_max"], int)

    def test_capabilities_endpoint_has_candidates_module(self):
        """Test /api/v1/capabilities has candidates module."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        self.assertIn("candidates", j["modules"])
        
        candidates = j["modules"]["candidates"]
        self.assertIn("enabled", candidates)
        self.assertIn("max", candidates)

    def test_capabilities_endpoint_has_mood_module(self):
        """Test /api/v1/capabilities has mood module."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        self.assertIn("mood", j["modules"])
        
        mood = j["modules"]["mood"]
        self.assertIn("enabled", mood)
        self.assertIn("window_seconds", mood)

    def test_capabilities_endpoint_has_brain_graph_module(self):
        """Test /api/v1/capabilities has brain_graph module."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        self.assertIn("brain_graph", j["modules"])
        
        brain_graph = j["modules"]["brain_graph"]
        self.assertIn("enabled", brain_graph)
        self.assertIn("persist", brain_graph)
        self.assertIn("nodes_max", brain_graph)
        self.assertIn("edges_max", brain_graph)

    def test_capabilities_endpoint_has_vector_store_module(self):
        """Test /api/v1/capabilities has vector_store module."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        self.assertIn("vector_store", j["modules"])
        
        vector_store = j["modules"]["vector_store"]
        self.assertIn("enabled", vector_store)
        self.assertIn("version", vector_store)

    def test_capabilities_endpoint_has_dashboard_module(self):
        """Test /api/v1/capabilities has dashboard module."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        self.assertIn("dashboard", j["modules"])
        
        dashboard = j["modules"]["dashboard"]
        self.assertIn("enabled", dashboard)
        self.assertIn("version", dashboard)

    def test_capabilities_endpoint_events_idempotency(self):
        """Test events module has idempotency configuration."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        
        events = j["modules"]["events"]
        self.assertIn("idempotency", events)
        
        idempotency = events["idempotency"]
        self.assertIn("supported", idempotency)
        self.assertIn("ttl_seconds", idempotency)
        self.assertIn("lru_max", idempotency)
        self.assertIn("key_sources", idempotency)
        self.assertIsInstance(idempotency["key_sources"], list)

    def test_capabilities_endpoint_key_sources_present(self):
        """Test idempotency key sources include expected values."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        
        events = j["modules"]["events"]
        key_sources = events["idempotency"]["key_sources"]
        
        expected_sources = [
            "Idempotency-Key header",
            "idempotency_key payload field",
            "event_id payload field",
            "id payload field",
        ]
        for source in expected_sources:
            self.assertIn(source, key_sources)

    def test_capabilities_endpoint_brain_graph_persistence(self):
        """Test brain_graph module has persistence configuration."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        
        brain_graph = j["modules"]["brain_graph"]
        self.assertIn("json_path", brain_graph)
        self.assertIn("feeding_enabled", brain_graph)

    def test_capabilities_endpoint_content_type_json(self):
        """Test /api/v1/capabilities returns application/json content type."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        self.assertIn("application/json", r.content_type)


class TestCapabilitiesEndpointIntegration(unittest.TestCase):
    """Integration tests for capabilities endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        """Clean up test fixtures."""
        self.tmpdir.cleanup()

    def _create_test_app(self):
        """Create a test Flask app with temp paths."""
        app = create_app()
        from dataclasses import replace

        cfg = app.config["COPILOT_CFG"]
        app.config["COPILOT_CFG"] = replace(
            cfg,
            data_dir=self.tmpdir.name,
            brain_graph_json_path=f"{self.tmpdir.name}/brain_graph.db",
            events_jsonl_path=f"{self.tmpdir.name}/events.jsonl",
            candidates_json_path=f"{self.tmpdir.name}/candidates.json",
            brain_graph_nodes_max=500,
            brain_graph_edges_max=1500,
            brain_graph_persist=True,
        )
        return app

    def test_capabilities_endpoint_all_modules_present(self):
        """Test all expected modules are present in capabilities."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        
        expected_modules = [
            "events",
            "candidates",
            "mood",
            "brain_graph",
            "vector_store",
            "dashboard",
        ]
        
        modules = j["modules"]
        for module in expected_modules:
            self.assertIn(module, modules, f"Missing module: {module}")

    def test_capabilities_endpoint_module_structure(self):
        """Test each module has expected structure."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        
        modules = j["modules"]
        
        # Events structure
        events = modules.get("events", {})
        self.assertIn("enabled", events)
        self.assertIn("persist", events)
        self.assertIn("cache_max", events)
        
        # Candidates structure
        candidates = modules.get("candidates", {})
        self.assertIn("enabled", candidates)
        self.assertIn("persist", candidates)
        self.assertIn("max", candidates)
        
        # Mood structure
        mood = modules.get("mood", {})
        self.assertIn("enabled", mood)
        self.assertIn("window_seconds", mood)
        
        # Brain graph structure
        brain_graph = modules.get("brain_graph", {})
        self.assertIn("enabled", brain_graph)
        self.assertIn("persist", brain_graph)
        self.assertIn("nodes_max", brain_graph)
        self.assertIn("edges_max", brain_graph)


if __name__ == "__main__":
    unittest.main()
