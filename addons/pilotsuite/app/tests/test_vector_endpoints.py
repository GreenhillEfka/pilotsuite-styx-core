"""Tests for /api/v1/vector/* endpoints."""

import tempfile
import unittest

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestVectorEndpoints(unittest.TestCase):
    """Test /api/v1/vector/* endpoint functionality."""

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
        
        # Reset lazy singletons
        from copilot_core.brain_graph import provider
        from copilot_core.api.v1 import vector as vector_api
        
        provider._STORE = None
        provider._SVC = None
        vector_api._STORE = None
        
        return app

    def test_vector_post_embeddings_returns_200(self):
        """Test POST /api/v1/vector/embeddings returns HTTP 200."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        payload = {
            "type": "entity",
            "id": "light.test",
            "domain": "light",
            "area": "living_room",
            "capabilities": ["brightness", "color_temp"],
            "tags": ["indoor"],
            "state": {"state": "on"},
        }
        r = client.post("/api/v1/vector/embeddings", json=payload)
        self.assertIn(r.status_code, [200, 201])

    def test_vector_post_embeddings_returns_ok(self):
        """Test POST /api/v1/vector/embeddings returns ok: true."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        payload = {
            "type": "entity",
            "id": "light.test",
            "domain": "light",
        }
        r = client.post("/api/v1/vector/embeddings", json=payload)
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_vector_post_embeddings_missing_type(self):
        """Test POST /api/v1/vector/embeddings with missing type returns 400."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        payload = {"id": "light.test"}
        r = client.post("/api/v1/vector/embeddings", json=payload)
        self.assertEqual(r.status_code, 400)

    def test_vector_post_embeddings_missing_id(self):
        """Test POST /api/v1/vector/embeddings with missing id returns 400."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        payload = {"type": "entity"}
        r = client.post("/api/v1/vector/embeddings", json=payload)
        self.assertEqual(r.status_code, 400)

    def test_vector_post_embeddings_invalid_type(self):
        """Test POST /api/v1/vector/embeddings with invalid type returns 400."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        payload = {
            "type": "invalid_type",
            "id": "test",
        }
        r = client.post("/api/v1/vector/embeddings", json=payload)
        self.assertEqual(r.status_code, 400)

    def test_vector_get_vectors_returns_200(self):
        """Test GET /api/v1/vector/vectors returns HTTP 200."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/vector/vectors")
        self.assertEqual(r.status_code, 200)

    def test_vector_get_vectors_returns_ok(self):
        """Test GET /api/v1/vector/vectors returns ok: true."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/vector/vectors")
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_vector_get_vectors_returns_entries(self):
        """Test GET /api/v1/vector/vectors returns entries list."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/vector/vectors")
        j = r.get_json()
        self.assertIn("entries", j)
        self.assertIsInstance(j["entries"], list)

    def test_vector_get_vectors_limit_param(self):
        """Test GET /api/v1/vector/vectors with limit parameter."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/vector/vectors?limit=5")
        self.assertEqual(r.status_code, 200)

    def test_vector_get_vectors_type_filter(self):
        """Test GET /api/v1/vector/vectors with type filter."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/vector/vectors?type=entity")
        self.assertEqual(r.status_code, 200)

    def test_vector_post_embeddings_entity(self):
        """Test POST /api/v1/vector/embeddings with entity type."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        payload = {
            "type": "entity",
            "id": "light.living_room",
            "domain": "light",
            "area": "living_room",
            "capabilities": ["brightness"],
        }
        r = client.post("/api/v1/vector/embeddings", json=payload)
        self.assertIn(r.status_code, [200, 201])
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertIn("entry", j)

    def test_vector_post_embeddings_user_preference(self):
        """Test POST /api/v1/vector/embeddings with user_preference type."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        payload = {
            "type": "user_preference",
            "id": "user_1",
            "preferences": {
                "preferred_temperature": 22,
                "preferred_lighting": "warm",
            },
        }
        r = client.post("/api/v1/vector/embeddings", json=payload)
        self.assertIn(r.status_code, [200, 201])

    def test_vector_post_embeddings_pattern(self):
        """Test POST /api/v1/vector/embeddings with pattern type."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        payload = {
            "type": "pattern",
            "id": "pattern_1",
            "pattern_type": "habitus",
            "entities": ["light.1", "light.2"],
        }
        r = client.post("/api/v1/vector/embeddings", json=payload)
        self.assertIn(r.status_code, [200, 201])

    def test_vector_post_embeddings_bulk(self):
        """Test POST /api/v1/vector/embeddings/bulk."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        payload = {
            "entities": [
                {"id": "light.test1", "domain": "light"},
                {"id": "light.test2", "domain": "light"},
            ],
            "user_preferences": [
                {"id": "user_1", "preferences": {"temp": 22}},
            ],
            "patterns": [
                {"id": "pattern_1", "pattern_type": "test", "entities": ["e1"]},
            ],
        }
        r = client.post("/api/v1/vector/embeddings/bulk", json=payload)
        self.assertEqual(r.status_code, 201)
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_vector_stats_endpoint(self):
        """Test GET /api/v1/vector/stats."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/vector/stats")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertIn("stats", j)

    def test_vector_clear_vectors(self):
        """Test DELETE /api/v1/vector/vectors."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.delete("/api/v1/vector/vectors")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_vector_clear_vectors_type_filter(self):
        """Test DELETE /api/v1/vector/vectors with type filter."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.delete("/api/v1/vector/vectors?type=entity")
        self.assertEqual(r.status_code, 200)

    def test_vector_similar_endpoint(self):
        """Test GET /api/v1/vector/similar/<id>."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # First create an entry
        client.post("/api/v1/vector/embeddings", json={
            "type": "entity",
            "id": "light.test",
            "domain": "light",
        })
        
        # Then get similar
        r = client.get("/api/v1/vector/similar/light.test")
        self.assertEqual(r.status_code, 200)

    def test_vector_similar_with_params(self):
        """Test GET /api/v1/vector/similar with query params."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # First create an entry
        client.post("/api/v1/vector/embeddings", json={
            "type": "entity",
            "id": "light.test",
            "domain": "light",
        })
        
        r = client.get("/api/v1/vector/similar/light.test?limit=5&threshold=0.5")
        self.assertEqual(r.status_code, 200)

    def test_vector_get_specific_vector(self):
        """Test GET /api/v1/vector/vectors/<id>."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # First create an entry
        r = client.post("/api/v1/vector/embeddings", json={
            "type": "entity",
            "id": "light.test",
            "domain": "light",
        })
        self.assertIn(r.status_code, [200, 201])
        j = r.get_json()
        entry_id = j["entry"]["id"]
        
        # Then get specific vector
        r = client.get(f"/api/v1/vector/vectors/{entry_id}")
        self.assertEqual(r.status_code, 200)

    def test_vector_delete_vector(self):
        """Test DELETE /api/v1/vector/vectors/<id>."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # First create an entry
        r = client.post("/api/v1/vector/embeddings", json={
            "type": "entity",
            "id": "light.test",
            "domain": "light",
        })
        
        # Then delete it
        r = client.delete("/api/v1/vector/vectors/entity:light.test")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_vector_similarity_post(self):
        """Test POST /api/v1/vector/similarity."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # Create two entries first
        r1 = client.post("/api/v1/vector/embeddings", json={
            "type": "entity",
            "id": "light.test1",
            "domain": "light",
        })
        r2 = client.post("/api/v1/vector/embeddings", json={
            "type": "entity",
            "id": "light.test2",
            "domain": "light",
        })
        
        # Then compute similarity
        j1 = r1.get_json()
        j2 = r2.get_json()
        id1 = j1["entry"]["id"]
        id2 = j2["entry"]["id"]
        
        payload = {"id1": id1, "id2": id2}
        r = client.post("/api/v1/vector/similarity", json=payload)
        self.assertEqual(r.status_code, 200)


class TestVectorEndpointsIntegration(unittest.TestCase):
    """Integration tests for vector endpoints."""

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
        
        # Reset lazy singletons
        from copilot_core.brain_graph import provider
        from copilot_core.api.v1 import vector as vector_api
        
        provider._STORE = None
        provider._SVC = None
        vector_api._STORE = None
        
        return app

    def test_vector_full_workflow(self):
        """Test complete vector workflow: create, list, get, delete."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # 1. Create embedding
        r = client.post("/api/v1/vector/embeddings", json={
            "type": "entity",
            "id": "light.living_room",
            "domain": "light",
        })
        self.assertIn(r.status_code, [200, 201])
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        
        # 2. List vectors
        r = client.get("/api/v1/vector/vectors")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertGreater(len(j["entries"]), 0)
        
        # 3. Get stats
        r = client.get("/api/v1/vector/stats")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        
        # 4. Clear all vectors
        r = client.delete("/api/v1/vector/vectors")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
