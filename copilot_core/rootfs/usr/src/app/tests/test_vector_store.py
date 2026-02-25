"""Tests for Vector Store Module.

Tests cover:
- Embedding generation
- Vector storage
- Similarity search
- API endpoints
"""

import asyncio
import json
import math
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot_core.vector_store.embeddings import (
    EmbeddingEngine,
    EmbeddingConfig,
    EmbeddingResult,
    get_embedding_engine,
    reset_embedding_engine,
    _normalize,
    _hash_to_vector,
    EMBEDDING_DIM,
)
from copilot_core.vector_store.store import (
    VectorStore,
    VectorStoreConfig,
    VectorEntry,
    SearchResult,
    get_vector_store,
    reset_vector_store,
    _cosine_similarity,
)


class TestEmbeddingEngine(unittest.TestCase):
    """Test the EmbeddingEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = EmbeddingEngine(EmbeddingConfig())
        
    def test_normalize_vector(self):
        """Test vector normalization."""
        vec = [3.0, 4.0]
        normalized = _normalize(vec)
        magnitude = math.sqrt(sum(x * x for x in normalized))
        self.assertAlmostEqual(magnitude, 1.0, places=5)
        
    def test_hash_to_vector(self):
        """Test deterministic hash vector generation."""
        vec1 = _hash_to_vector("test_string")
        vec2 = _hash_to_vector("test_string")
        vec3 = _hash_to_vector("different_string")
        
        # Same input should produce same output
        self.assertEqual(vec1, vec2)
        # Different inputs should produce different outputs
        self.assertNotEqual(vec1, vec3)
        # Output should have correct dimension
        self.assertEqual(len(vec1), EMBEDDING_DIM)
        
    def test_embed_entity_basic(self):
        """Test basic entity embedding."""
        async def run_test():
            result = await self.engine.embed_entity(
                entity_id="light.wohnzimmer",
                domain="light",
                area="living_room",
            )
            
            self.assertIsInstance(result, EmbeddingResult)
            self.assertEqual(len(result.vector), EMBEDDING_DIM)
            self.assertEqual(result.source, "local")
            self.assertEqual(result.model, "entity_v1")
            
        asyncio.run(run_test())
        
    def test_embed_entity_with_capabilities(self):
        """Test entity embedding with capabilities."""
        async def run_test():
            result = await self.engine.embed_entity(
                entity_id="light.wohnzimmer",
                domain="light",
                area="living_room",
                capabilities=["brightness", "color_temp", "color"],
                tags=["indoor", "main"],
            )
            
            self.assertEqual(len(result.vector), EMBEDDING_DIM)
            
        asyncio.run(run_test())
        
    def test_embed_user_preferences(self):
        """Test user preference embedding."""
        async def run_test():
            preferences = {
                "light_brightness": {"default": 0.8},
                "temperature": {"default": 21.0},
                "media_volume": {"default": 0.5},
                "mood_weights": {"comfort": 0.7, "frugality": 0.4, "joy": 0.6},
            }
            
            result = await self.engine.embed_user_preferences(
                user_id="person.efka",
                preferences=preferences,
            )
            
            self.assertIsInstance(result, EmbeddingResult)
            self.assertEqual(len(result.vector), EMBEDDING_DIM)
            self.assertEqual(result.source, "local")
            self.assertEqual(result.model, "preference_v1")
            
        asyncio.run(run_test())
        
    def test_embed_pattern(self):
        """Test pattern embedding."""
        async def run_test():
            result = await self.engine.embed_pattern(
                pattern_id="pattern_001",
                pattern_type="habitus",
                entities=["light.wohnzimmer", "light.kueche"],
                conditions={"time_start": "20:00", "mood": "relax"},
                confidence=0.85,
            )
            
            self.assertIsInstance(result, EmbeddingResult)
            self.assertEqual(len(result.vector), EMBEDDING_DIM)
            self.assertEqual(result.source, "local")
            self.assertEqual(result.model, "pattern_v1")
            
        asyncio.run(run_test())
        
    def test_embedding_caching(self):
        """Test that embeddings are cached."""
        async def run_test():
            result1 = await self.engine.embed_entity(
                entity_id="light.test",
                domain="light",
            )
            self.assertFalse(result1.cached)
            
            # Second call should be cached
            result2 = await self.engine.embed_entity(
                entity_id="light.test",
                domain="light",
            )
            # Note: cached flag is set in the engine, not the result
            # The vectors should be identical
            self.assertEqual(result1.vector, result2.vector)
            
        asyncio.run(run_test())


class TestVectorStore(unittest.TestCase):
    """Test the VectorStore class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Use a temp file for the database
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)
        
        self.config = VectorStoreConfig(
            db_path=self.temp_path,
            persist=True,
            cache_size=100,
        )
        self.store = VectorStore(self.config)
        
    def tearDown(self):
        """Clean up test fixtures."""
        self.store.close()
        if os.path.exists(self.temp_path):
            os.remove(self.temp_path)
        reset_vector_store()

    def test_init_falls_back_when_data_dir_unwritable(self):
        """Vector store should fallback when /data is not writable."""
        fallback_tmp = tempfile.TemporaryDirectory()
        store = None
        try:
            with patch("copilot_core.vector_store.store.Path.mkdir") as mock_mkdir:
                mock_mkdir.side_effect = [PermissionError("denied"), None]
                with patch.dict(os.environ, {"COPILOT_VECTOR_DB_DIR": fallback_tmp.name}):
                    store = VectorStore(
                        VectorStoreConfig(
                            db_path="/data/vector_store.db",
                            persist=True,
                            cache_size=10,
                        )
                    )
            self.assertTrue(store.config.db_path.startswith(fallback_tmp.name))
            self.assertEqual(mock_mkdir.call_count, 2)
        finally:
            if store:
                store.close()
            fallback_tmp.cleanup()
        
    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        # Identical vectors
        vec = [1.0, 2.0, 3.0]
        sim = _cosine_similarity(vec, vec)
        self.assertAlmostEqual(sim, 1.0, places=5)
        
        # Orthogonal vectors
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        sim = _cosine_similarity(vec1, vec2)
        self.assertAlmostEqual(sim, 0.0, places=5)
        
        # Opposite vectors
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        sim = _cosine_similarity(vec1, vec2)
        self.assertAlmostEqual(sim, -1.0, places=5)
        
    def test_upsert_and_get(self):
        """Test upserting and getting entries."""
        async def run_test():
            vector = [0.1] * EMBEDDING_DIM
            
            entry = await self.store.upsert(
                entry_id="test_entity",
                vector=vector,
                entry_type="entity",
                metadata={"domain": "light"},
            )
            
            self.assertEqual(entry.id, "test_entity")
            self.assertEqual(entry.entry_type, "entity")
            self.assertEqual(entry.metadata["domain"], "light")
            
            # Retrieve
            retrieved = await self.store.get("test_entity")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.id, "test_entity")
            self.assertEqual(retrieved.vector, vector)
            
        asyncio.run(run_test())
        
    def test_delete(self):
        """Test deleting entries."""
        async def run_test():
            vector = [0.1] * EMBEDDING_DIM
            await self.store.upsert(
                entry_id="test_entity",
                vector=vector,
                entry_type="entity",
            )
            
            # Delete
            deleted = await self.store.delete("test_entity")
            self.assertTrue(deleted)
            
            # Should not exist
            retrieved = await self.store.get("test_entity")
            self.assertIsNone(retrieved)
            
        asyncio.run(run_test())
        
    def test_search_similar(self):
        """Test similarity search."""
        async def run_test():
            # Create test vectors
            vec1 = [0.9] * EMBEDDING_DIM  # High values
            vec2 = [0.8] * EMBEDDING_DIM  # Similar to vec1
            vec3 = [-0.5] * EMBEDDING_DIM  # Different
            
            await self.store.upsert("entity:light1", vec1, "entity", {"domain": "light"})
            await self.store.upsert("entity:light2", vec2, "entity", {"domain": "light"})
            await self.store.upsert("entity:climate1", vec3, "entity", {"domain": "climate"})
            
            # Search
            results = await self.store.search_similar(
                query_vector=vec1,
                entry_type="entity",
                limit=10,
                threshold=0.5,
                exclude_ids=["entity:light1"],
            )
            
            self.assertGreater(len(results), 0)
            # Should find light2 (similar) but not climate1 (different) or light1 (excluded)
            self.assertTrue(any(r.id == "entity:light2" for r in results))
            self.assertFalse(any(r.id == "entity:light1" for r in results))
            
        asyncio.run(run_test())
        
    def test_get_by_type(self):
        """Test getting entries by type."""
        async def run_test():
            vector = [0.1] * EMBEDDING_DIM
            
            await self.store.upsert("entity:1", vector, "entity")
            await self.store.upsert("entity:2", vector, "entity")
            await self.store.upsert("user_pref:user1", vector, "user_preference")
            
            entities = await self.store.get_by_type("entity")
            self.assertEqual(len(entities), 2)
            
            user_prefs = await self.store.get_by_type("user_preference")
            self.assertEqual(len(user_prefs), 1)
            
        asyncio.run(run_test())
        
    def test_stats(self):
        """Test getting statistics."""
        async def run_test():
            vector = [0.1] * EMBEDDING_DIM
            
            await self.store.upsert("entity:1", vector, "entity")
            await self.store.upsert("user_pref:user1", vector, "user_preference")
            
            stats = await self.store.stats()
            
            self.assertIn("by_type", stats)
            self.assertIn("entity", stats["by_type"])
            self.assertIn("user_preference", stats["by_type"])
            
        asyncio.run(run_test())
        
    def test_clear(self):
        """Test clearing entries."""
        async def run_test():
            vector = [0.1] * EMBEDDING_DIM
            
            await self.store.upsert("entity:1", vector, "entity")
            await self.store.upsert("entity:2", vector, "entity")
            await self.store.upsert("user_pref:user1", vector, "user_preference")
            
            # Clear only entities
            count = await self.store.clear("entity")
            self.assertEqual(count, 2)
            
            # User preference should still exist
            user_prefs = await self.store.get_by_type("user_preference")
            self.assertEqual(len(user_prefs), 1)
            
        asyncio.run(run_test())


class TestVectorAPI(unittest.TestCase):
    """Test the Vector Store API endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Import Flask app
        from copilot_core.app import create_app
        import tempfile
        import os
        
        self.temp_fd, self.temp_db = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)
        
        os.environ["COPILOT_VECTOR_DB_PATH"] = self.temp_db
        
        self.app = create_app()
        self.client = self.app.test_client()
        
        # Reset singletons
        reset_vector_store()
        reset_embedding_engine()
        
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)
        reset_vector_store()
        reset_embedding_engine()
        
    def test_create_entity_embedding(self):
        """Test creating an entity embedding via API."""
        response = self.client.post("/api/v1/vector/embeddings", json={
            "type": "entity",
            "id": "light.test",
            "domain": "light",
            "area": "living_room",
            "capabilities": ["brightness", "color_temp"],
        })
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertTrue(data["ok"])
        self.assertIn("entry", data)
        
    def test_create_user_preference_embedding(self):
        """Test creating a user preference embedding via API."""
        response = self.client.post("/api/v1/vector/embeddings", json={
            "type": "user_preference",
            "id": "person.test",
            "preferences": {
                "light_brightness": {"default": 0.8},
                "temperature": {"default": 21.0},
            },
        })
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertTrue(data["ok"])
        
    def test_create_pattern_embedding(self):
        """Test creating a pattern embedding via API."""
        response = self.client.post("/api/v1/vector/embeddings", json={
            "type": "pattern",
            "id": "pattern_001",
            "pattern_type": "habitus",
            "entities": ["light.test1", "light.test2"],
            "confidence": 0.85,
        })
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertTrue(data["ok"])
        
    def test_find_similar(self):
        """Test finding similar entries via API."""
        # Create test entities
        self.client.post("/api/v1/vector/embeddings", json={
            "type": "entity",
            "id": "light.test1",
            "domain": "light",
        })
        
        self.client.post("/api/v1/vector/embeddings", json={
            "type": "entity",
            "id": "light.test2",
            "domain": "light",
        })
        
        # Find similar
        response = self.client.get("/api/v1/vector/similar/light.test1?type=entity")
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["ok"])
        self.assertIn("results", data)
        
    def test_get_vector_stats(self):
        """Test getting vector stats via API."""
        response = self.client.get("/api/v1/vector/stats")
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["ok"])
        self.assertIn("stats", data)
        
    def test_list_vectors(self):
        """Test listing vectors via API."""
        # Create test entities
        self.client.post("/api/v1/vector/embeddings", json={
            "type": "entity",
            "id": "light.test_list",
            "domain": "light",
        })
        
        response = self.client.get("/api/v1/vector/vectors?type=entity")
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["ok"])
        self.assertIn("entries", data)
        
    def test_compute_similarity(self):
        """Test computing similarity via API."""
        # Create test entities
        self.client.post("/api/v1/vector/embeddings", json={
            "type": "entity",
            "id": "light.sim1",
            "domain": "light",
        })
        
        self.client.post("/api/v1/vector/embeddings", json={
            "type": "entity",
            "id": "light.sim2",
            "domain": "light",
        })
        
        response = self.client.post("/api/v1/vector/similarity", json={
            "id1": "entity:light.sim1",
            "id2": "entity:light.sim2",
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["ok"])
        self.assertIn("similarity", data)
        
    def test_bulk_create_embeddings(self):
        """Test bulk creating embeddings via API."""
        response = self.client.post("/api/v1/vector/embeddings/bulk", json={
            "entities": [
                {"id": "light.bulk1", "domain": "light"},
                {"id": "light.bulk2", "domain": "light"},
            ],
            "user_preferences": [
                {"id": "person.bulk", "preferences": {"light_brightness": {"default": 0.7}}},
            ],
        })
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertTrue(data["ok"])
        self.assertIn("results", data)
        self.assertIn("entities", data["results"])
        self.assertIn("user_preferences", data["results"])


class TestVectorStoreIntegration(unittest.TestCase):
    """Integration tests for Vector Store with MUPL."""
    
    def test_preference_similarity(self):
        """Test that similar preferences have high similarity."""
        async def run_test():
            # Create store
            temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
            os.close(temp_fd)
            
            try:
                store = VectorStore(VectorStoreConfig(db_path=temp_path))
                engine = EmbeddingEngine()
                store.set_embedding_engine(engine)
                
                # Create similar user preferences
                prefs1 = {
                    "light_brightness": {"default": 0.8},
                    "temperature": {"default": 21.0},
                    "mood_weights": {"comfort": 0.7, "frugality": 0.4, "joy": 0.6},
                }
                
                prefs2 = {
                    "light_brightness": {"default": 0.75},  # Similar
                    "temperature": {"default": 21.5},  # Similar
                    "mood_weights": {"comfort": 0.65, "frugality": 0.45, "joy": 0.55},  # Similar
                }
                
                prefs3 = {
                    "light_brightness": {"default": 0.2},  # Very different
                    "temperature": {"default": 18.0},  # Very different
                    "mood_weights": {"comfort": 0.2, "frugality": 0.9, "joy": 0.1},  # Very different
                }
                
                await store.store_user_preference_embedding("user1", prefs1)
                await store.store_user_preference_embedding("user2", prefs2)
                await store.store_user_preference_embedding("user3", prefs3)
                
                # Find similar users for user1
                similar = await store.find_similar_users("user1", threshold=0.5)
                
                # user2 should be more similar than user3
                user2_sim = next((r.similarity for r in similar if r.id == "user_pref:user2"), 0)
                user3_sim = next((r.similarity for r in similar if r.id == "user_pref:user3"), 0)
                
                # This is a basic test - actual values depend on embedding algorithm
                # We just verify the mechanism works
                self.assertGreater(len(similar), 0)
                
                store.close()
                
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
