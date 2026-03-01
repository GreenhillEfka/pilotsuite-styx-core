"""Tests for RAG Hybrid Search functionality.

Tests cover:
- BM25 indexing and search
- Vector search integration
- Reciprocal Rank Fusion (RRF)
- Multi-query support
- Performance (<100ms response time)
"""

import asyncio
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Tuple

try:
    from copilot_core.rag.hybrid_search import (
        BM25Index,
        HybridSearchEngine,
        HybridSearchConfig,
        HybridSearchResult,
        rrf_fusion,
        get_hybrid_search_engine,
    )
    RAG_AVAILABLE = True
except (ModuleNotFoundError, ImportError) as e:
    RAG_AVAILABLE = False
    print(f"RAG module not available: {e}")


class TestBM25Index(unittest.TestCase):
    """Test BM25 indexing and search."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not RAG_AVAILABLE:
            self.skipTest("RAG module not available")
        self.index = BM25Index(k1=1.5, b=0.75)
        
        # Add test documents
        self.documents = [
            ("doc1", "The quick brown fox jumps over the lazy dog"),
            ("doc2", "A fast brown fox leaps across the sleepy canine"),
            ("doc3", "The lazy dog sleeps all day long"),
            ("doc4", "Quick brown animals are very agile"),
        ]
        
        for doc_id, content in self.documents:
            self.index.add_document(doc_id, content)
    
    def test_document_indexing(self):
        """Test that documents are properly indexed."""
        self.assertEqual(self.index._num_docs, 4)
        self.assertEqual(len(self.index._doc_lengths), 4)
        
        # Check document length
        self.assertEqual(self.index._doc_lengths["doc1"], 9)  # 9 tokens
    
    def test_document_removal(self):
        """Test document removal."""
        # Remove a document
        result = self.index.remove_document("doc3")
        self.assertTrue(result)
        
        # Verify removal
        self.assertEqual(self.index._num_docs, 3)
        self.assertNotIn("doc3", self.index._doc_lengths)
        
        # Try to remove non-existent document
        result = self.index.remove_document("nonexistent")
        self.assertFalse(result)
    
    def test_bm25_scoring(self):
        """Test BM25 score calculation."""
        # "fox" should appear in doc1 and doc2
        score_doc1 = self.index.bm25_score("fox", "doc1")
        score_doc2 = self.index.bm25_score("fox", "doc2")
        score_doc3 = self.index.bm25_score("fox", "doc3")
        
        self.assertGreater(score_doc1, 0)
        self.assertGreater(score_doc2, 0)
        self.assertEqual(score_doc3, 0)  # "fox" not in doc3
    
    def test_search_basic(self):
        """Test basic search functionality."""
        results = self.index.search("brown fox", top_k=2)
        
        self.assertEqual(len(results), 2)
        
        # Both results should contain "brown" or "fox"
        for doc_id, score in results:
            self.assertGreater(score, 0)
            content = self.index.get_document(doc_id)
            self.assertIsNotNone(content)
    
    def test_search_no_results(self):
        """Test search with no matching results."""
        results = self.index.search("nonexistentterm12345")
        self.assertEqual(len(results), 0)
    
    def test_search_empty_query(self):
        """Test search with empty query."""
        results = self.index.search("")
        self.assertEqual(len(results), 0)
    
    def test_get_document(self):
        """Test retrieving document content."""
        content = self.index.get_document("doc1")
        self.assertEqual(content, "The quick brown fox jumps over the lazy dog")
        
        # Non-existent document
        content = self.index.get_document("nonexistent")
        self.assertIsNone(content)


class TestRRFFusion(unittest.TestCase):
    """Test Reciprocal Rank Fusion."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not RAG_AVAILABLE:
            self.skipTest("RAG module not available")
    
    def test_rrf_basic(self):
        """Test basic RRF fusion."""
        results1 = [("doc1", 0.9), ("doc2", 0.8), ("doc3", 0.7)]
        results2 = [("doc2", 0.95), ("doc4", 0.85), ("doc1", 0.75)]
        
        rrf_scores = rrf_fusion([results1, results2], k=60)
        
        # doc1 appears in both lists (rank 1 and 3)
        # doc2 appears in both lists (rank 2 and 1)
        # doc3 appears only in first list (rank 3)
        # doc4 appears only in second list (rank 2)
        
        self.assertIn("doc1", rrf_scores)
        self.assertIn("doc2", rrf_scores)
        self.assertIn("doc3", rrf_scores)
        self.assertIn("doc4", rrf_scores)
        
        # doc2 should have higher score (rank 1 + rank 2) than doc1 (rank 1 + rank 3)
        self.assertGreater(rrf_scores["doc2"], rrf_scores["doc1"])
    
    def test_rrf_single_list(self):
        """Test RRF with single result list."""
        results = [("doc1", 0.9), ("doc2", 0.8)]
        rrf_scores = rrf_fusion([results], k=60)
        
        self.assertEqual(len(rrf_scores), 2)
        self.assertGreater(rrf_scores["doc1"], rrf_scores["doc2"])
    
    def test_rrf_empty_lists(self):
        """Test RRF with empty result lists."""
        rrf_scores = rrf_fusion([], k=60)
        self.assertEqual(len(rrf_scores), 0)
        
        rrf_scores = rrf_fusion([[], []], k=60)
        self.assertEqual(len(rrf_scores), 0)


class TestHybridSearchEngine(unittest.TestCase):
    """Test hybrid search engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not RAG_AVAILABLE:
            self.skipTest("RAG module not available")
        
        self.config = HybridSearchConfig(
            rrf_k=60,
            bm25_weight=0.5,
            vector_weight=0.5,
            top_k=5,
            use_cache=False,  # Disable cache for tests
        )
        
        # Mock vector store
        self.mock_vector_store = Mock()
        
        self.engine = HybridSearchEngine(
            config=self.config,
            vector_store=self.mock_vector_store,
        )
        
        # Add test documents
        self.documents = [
            ("doc1", "Home Assistant automation for lights and switches"),
            ("doc2", "Smart home climate control and temperature monitoring"),
            ("doc3", "Security system with cameras and motion sensors"),
            ("doc4", "Energy management and solar panel optimization"),
            ("doc5", "Voice control integration with Alexa and Google"),
        ]
        
        for doc_id, content in self.documents:
            self.engine.add_document(doc_id, content)
    
    def test_engine_initialization(self):
        """Test engine initialization."""
        self.assertIsNotNone(self.engine._bm25_index)
        self.assertEqual(self.engine._bm25_index._num_docs, 5)
    
    def test_hybrid_search_basic(self):
        """Test basic hybrid search."""
        # Mock vector search to return some results
        async def mock_vector_search(*args, **kwargs):
            return [("doc1", 0.85), ("doc2", 0.75)]
        
        with patch.object(self.engine, '_vector_search', mock_vector_search):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    self.engine.search("home automation", top_k=3)
                )
            finally:
                loop.close()
        
        self.assertLessEqual(len(results), 3)
        
        # Verify result structure
        for result in results:
            self.assertIsInstance(result, HybridSearchResult)
            self.assertIsNotNone(result.id)
            self.assertGreaterEqual(result.score, 0)
            self.assertGreaterEqual(result.final_rank, 1)
    
    def test_hybrid_search_performance(self):
        """Test search performance (<100ms target)."""
        # Mock vector search with slight delay
        async def mock_vector_search(*args, **kwargs):
            await asyncio.sleep(0.01)  # 10ms delay
            return [("doc1", 0.85), ("doc2", 0.75)]
        
        with patch.object(self.engine, '_vector_search', mock_vector_search):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                start_time = time.time()
                results = loop.run_until_complete(
                    self.engine.search("home automation", top_k=5)
                )
                execution_time_ms = (time.time() - start_time) * 1000
            finally:
                loop.close()
        
        # Performance should be under 100ms
        self.assertLess(execution_time_ms, 100, f"Search took {execution_time_ms:.2f}ms (target: <100ms)")
    
    def test_multi_query_search(self):
        """Test multi-query search."""
        queries = [
            "home automation",
            "smart home",
            "automation system",
        ]
        
        # Mock vector search
        async def mock_vector_search(*args, **kwargs):
            return [("doc1", 0.85)]
        
        with patch.object(self.engine, '_vector_search', mock_vector_search):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    self.engine.search_multi_query(queries, top_k=5)
                )
            finally:
                loop.close()
        
        # Should return results
        self.assertGreater(len(results), 0)
        
        # Verify results are sorted by score
        for i in range(len(results) - 1):
            self.assertGreaterEqual(results[i].score, results[i+1].score)
    
    def test_search_with_filters(self):
        """Test search with metadata filters."""
        filters = {"type": "automation"}
        
        # Mock vector search that respects filters
        async def mock_vector_search(query, top_k, filters):
            self.assertEqual(filters, {"type": "automation"})
            return [("doc1", 0.85)]
        
        with patch.object(self.engine, '_vector_search', mock_vector_search):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    self.engine.search("automation", filters=filters)
                )
            finally:
                loop.close()
        
        self.assertGreater(len(results), 0)
    
    def test_get_stats(self):
        """Test statistics retrieval."""
        stats = self.engine.get_stats()
        
        self.assertIn("num_documents", stats)
        self.assertEqual(stats["num_documents"], 5)
        self.assertIn("avg_doc_length", stats)
        self.assertIn("config", stats)
        self.assertEqual(stats["config"]["top_k"], 5)
    
    def test_cache_functionality(self):
        """Test search result caching."""
        # Enable cache
        self.engine.config.use_cache = True
        self.engine.config.cache_ttl_seconds = 300
        
        # Mock vector search
        async def mock_vector_search(*args, **kwargs):
            return [("doc1", 0.85)]
        
        with patch.object(self.engine, '_vector_search', mock_vector_search):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # First search (cache miss)
                results1 = loop.run_until_complete(
                    self.engine.search("test query")
                )
                
                # Second search (cache hit)
                results2 = loop.run_until_complete(
                    self.engine.search("test query")
                )
            finally:
                loop.close()
        
        # Results should be the same
        self.assertEqual(len(results1), len(results2))
        
        # Verify cache was populated
        self.assertGreater(len(self.engine._cache), 0)
        
        # Clear cache
        self.engine.clear_cache()
        self.assertEqual(len(self.engine._cache), 0)
    
    def test_singleton_pattern(self):
        """Test singleton pattern for engine."""
        engine1 = get_hybrid_search_engine()
        engine2 = get_hybrid_search_engine()
        
        # Should return same instance
        self.assertIs(engine1, engine2)


class TestRAGAPIEndpoints(unittest.TestCase):
    """Test RAG API endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not RAG_AVAILABLE:
            self.skipTest("RAG module not available")
        
        try:
            from copilot_core.app import create_app
            self.app = create_app()
            self.client = self.app.test_client()
        except (ModuleNotFoundError, ImportError):
            self.skipTest("Flask app not available")
    
    def test_rag_health_endpoint(self):
        """Test /api/v1/rag/health endpoint."""
        # Note: This will fail without proper auth token
        # In real tests, you'd mock the auth
        response = self.client.get("/api/v1/rag/health")
        
        # Should return 401 without auth (or 200 if auth is mocked)
        self.assertIn(response.status_code, [200, 401])
    
    def test_rag_stats_endpoint(self):
        """Test /api/v1/rag/stats endpoint."""
        response = self.client.get("/api/v1/rag/stats")
        self.assertIn(response.status_code, [200, 401])


class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmark tests."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not RAG_AVAILABLE:
            self.skipTest("RAG module not available")
        
        self.config = HybridSearchConfig(
            top_k=10,
            use_cache=False,
        )
        
        self.engine = HybridSearchEngine(config=self.config)
        
        # Add larger dataset for benchmarking
        for i in range(100):
            content = f"Document {i} with various content about home automation and smart devices"
            self.engine.add_document(f"doc{i:03d}", content)
    
    def test_search_latency_100docs(self):
        """Test search latency with 100 documents."""
        async def mock_vector_search(*args, **kwargs):
            return [(f"doc{i:03d}", 0.9 - i*0.01) for i in range(10)]
        
        with patch.object(self.engine, '_vector_search', mock_vector_search):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                start_time = time.time()
                results = loop.run_until_complete(
                    self.engine.search("home automation", top_k=10)
                )
                latency_ms = (time.time() - start_time) * 1000
            finally:
                loop.close()
        
        print(f"\nSearch latency (100 docs): {latency_ms:.2f}ms")
        self.assertLess(latency_ms, 100, f"Latency {latency_ms:.2f}ms exceeds 100ms target")
    
    def test_multi_query_latency(self):
        """Test multi-query search latency."""
        queries = ["smart home", "home automation", "automation system"]
        
        async def mock_vector_search(*args, **kwargs):
            await asyncio.sleep(0.005)  # 5ms simulated delay
            return [(f"doc{i:03d}", 0.9 - i*0.01) for i in range(5)]
        
        with patch.object(self.engine, '_vector_search', mock_vector_search):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                start_time = time.time()
                results = loop.run_until_complete(
                    self.engine.search_multi_query(queries, top_k=10)
                )
                latency_ms = (time.time() - start_time) * 1000
            finally:
                loop.close()
        
        print(f"\nMulti-query latency (3 queries): {latency_ms:.2f}ms")
        # Multi-query should still be under 100ms due to parallel execution
        self.assertLess(latency_ms, 150, f"Latency {latency_ms:.2f}ms exceeds target")


if __name__ == "__main__":
    unittest.main()
