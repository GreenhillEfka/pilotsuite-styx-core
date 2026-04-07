"""Tests for Context Retrieval Engine Module.

Tests cover:
- RetrievalStage enum
- RetrievalResult and RetrievalConfig dataclasses
- ContextRetrievalEngine operations (retrieve, stats)
- Multi-stage pipeline (initial, re-rank, filter, select)
- Metadata filtering
- Top-k selection and thresholding
"""

import time
import unittest
from typing import Any, Dict, List, Tuple
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from copilot_core.rag.retrieval_engine import (
    RetrievalStage,
    RetrievalResult,
    RetrievalConfig,
    ContextRetrievalEngine,
    init_retrieval_engine,
    retrieve_context,
    default_retrieval_engine,
)


class MockDocument:
    """Mock document for testing."""
    def __init__(self, id: str, text: str, metadata: Dict[str, Any] = None):
        self.id = id
        self.text = text
        self.metadata = metadata or {}


class TestRetrievalDataclasses(unittest.TestCase):
    """Test retrieval dataclasses."""

    def test_create_retrieval_result(self):
        """Test creating a RetrievalResult."""
        doc = MockDocument("doc1", "text1")
        result = RetrievalResult(
            stage=RetrievalStage.FINAL,
            documents=[doc],
            scores=[0.9],
            latency_ms=10.5,
            metadata={"query": "test"}
        )

        self.assertEqual(result.stage, RetrievalStage.FINAL)
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(result.scores, [0.9])
        self.assertEqual(result.latency_ms, 10.5)
        self.assertEqual(result.metadata["query"], "test")

    def test_create_retrieval_config(self):
        """Test creating a RetrievalConfig."""
        config = RetrievalConfig(
            initial_k=100,
            final_k=5,
            min_score_threshold=0.5
        )

        self.assertEqual(config.initial_k, 100)
        self.assertEqual(config.final_k, 5)
        self.assertEqual(config.min_score_threshold, 0.5)


class TestContextRetrievalEngine(unittest.TestCase):
    """Test ContextRetrievalEngine class."""

    def setUp(self):
        """Set up test fixtures."""
        self.docs = [
            MockDocument("doc1", "apple", {"type": "fruit"}),
            MockDocument("doc2", "banana", {"type": "fruit"}),
            MockDocument("doc3", "carrot", {"type": "vegetable"}),
        ]

        def mock_vector_search(query, k):
            # Return docs in order for doc1, doc2, doc3 with scores 0.9, 0.8, 0.7
            return [
                (self.docs[0], 0.9),
                (self.docs[1], 0.8),
                (self.docs[2], 0.7),
            ][:k]

        self.mock_vector_search = mock_vector_search
        self.engine = ContextRetrievalEngine(vector_search_fn=mock_vector_search)

    def test_init(self):
        """Test ContextRetrievalEngine initialization."""
        self.assertIsNotNone(self.engine.vector_search_fn)
        self.assertIsNone(self.engine.re_rank_fn)
        self.assertIsNotNone(self.engine.config)
        self.assertEqual(self.engine._stats["total_queries"], 0)

    def test_retrieve_basic(self):
        """Test basic retrieval."""
        result = self.engine.retrieve("test query")

        self.assertIsInstance(result, RetrievalResult)
        self.assertEqual(len(result.documents), 3)
        self.assertEqual(result.documents[0].id, "doc1")
        self.assertEqual(result.scores[0], 0.9)
        self.assertEqual(self.engine._stats["total_queries"], 1)

    def test_retrieve_limit_k(self):
        """Test retrieval with k limit."""
        result = self.engine.retrieve("test query", k=2)

        self.assertEqual(len(result.documents), 2)
        self.assertEqual(result.documents[0].id, "doc1")
        self.assertEqual(result.documents[1].id, "doc2")

    def test_retrieve_with_filters(self):
        """Test retrieval with metadata filters."""
        result = self.engine.retrieve("test query", filters={"type": "fruit"})

        # Should only return doc1 and doc2
        self.assertEqual(len(result.documents), 2)
        self.assertTrue(all(d.metadata["type"] == "fruit" for d in result.documents))
        self.assertEqual(result.documents[0].id, "doc1")
        self.assertEqual(result.documents[1].id, "doc2")

    def test_retrieve_with_re_ranking(self):
        """Test retrieval with re-ranking stage."""
        def mock_re_rank(query, documents):
            # Reverse the order
            return [(doc, 1.0 - (i * 0.1)) for i, doc in enumerate(reversed(documents))]

        engine = ContextRetrievalEngine(
            vector_search_fn=self.mock_vector_search,
            re_rank_fn=mock_re_rank,
            config=RetrievalConfig(re_rank_enabled=True)
        )

        result = engine.retrieve("test query")

        # Order should be changed by re-ranker (reversed doc1, doc2, doc3)
        self.assertEqual(result.documents[0].id, "doc3")
        self.assertEqual(engine._stats["re_rank_applied"], 1)

    def test_retrieve_thresholding(self):
        """Test score thresholding."""
        self.engine.config.min_score_threshold = 0.85

        result = self.engine.retrieve("test query")

        # Only doc1 has score >= 0.85
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(result.documents[0].id, "doc1")

    def test_matches_filters(self):
        """Test internal _matches_filters method."""
        doc = MockDocument("doc1", "text", {"color": "red", "size": "large"})

        self.assertTrue(self.engine._matches_filters(doc, {"color": "red"}))
        self.assertTrue(self.engine._matches_filters(doc, {"color": "red", "size": "large"}))
        self.assertFalse(self.engine._matches_filters(doc, {"color": "blue"}))
        self.assertFalse(self.engine._matches_filters(doc, {"type": "unknown"}))

    def test_select_top_k_sorting(self):
        """Test that _select_top_k sorts documents by score."""
        # Unsorted input
        initial_result = RetrievalResult(
            stage=RetrievalStage.INITIAL,
            documents=[self.docs[2], self.docs[0], self.docs[1]],
            scores=[0.7, 0.9, 0.8],
            latency_ms=1.0
        )

        final_result = self.engine._select_top_k(initial_result, k=10)

        # Should be sorted: doc1 (0.9), doc2 (0.8), doc3 (0.7)
        self.assertEqual(final_result.documents[0].id, "doc1")
        self.assertEqual(final_result.documents[1].id, "doc2")
        self.assertEqual(final_result.documents[2].id, "doc3")

    def test_get_stats(self):
        """Test getting engine statistics."""
        self.engine.retrieve("query 1")
        self.engine.retrieve("query 2")

        stats = self.engine.get_stats()

        self.assertEqual(stats["total_queries"], 2)
        self.assertIn("avg_latency_ms", stats)
        self.assertGreaterEqual(stats["avg_latency_ms"], 0.0)

    def test_error_handling_in_stages(self):
        """Test stage error handling (should log warning and continue)."""
        # Vector search fails
        def failing_search(q, k):
            raise Exception("Search failed")
            
        engine = ContextRetrievalEngine(vector_search_fn=failing_search)
        result = engine.retrieve("test")
        
        self.assertEqual(result.documents, [])
        self.assertEqual(result.scores, [])
        
        # Re-ranker fails
        def failing_rerank(q, docs):
            raise Exception("Re-rank failed")
            
        engine = ContextRetrievalEngine(
            vector_search_fn=self.mock_vector_search,
            re_rank_fn=failing_rerank
        )
        result = engine.retrieve("test")
        
        # Should still have results from initial stage
        self.assertEqual(len(result.documents), 3)
        self.assertEqual(len(result.scores), 3)
        
        # Verify the metadata includes the query
        self.assertIn("query", result.metadata)
        self.assertEqual(result.metadata["query"], "test")


class TestGlobalRetrievalFunctions(unittest.TestCase):
    """Test global retrieval functions."""

    def setUp(self):
        """Set up."""
        self.original_engine = None
        if 'default_retrieval_engine' in sys.modules.get('copilot_core.rag.retrieval_engine', {}).__dict__:
            self.original_engine = sys.modules['copilot_core.rag.retrieval_engine'].default_retrieval_engine

    def tearDown(self):
        """Clean up."""
        from copilot_core.rag import retrieval_engine
        retrieval_engine.default_retrieval_engine = self.original_engine

    def test_init_retrieval_engine(self):
        """Test initializing the global retrieval engine."""
        mock_fn = MagicMock()
        engine = init_retrieval_engine(vector_search_fn=mock_fn)

        self.assertIsNotNone(engine)
        from copilot_core.rag.retrieval_engine import default_retrieval_engine
        self.assertEqual(default_retrieval_engine, engine)

    def test_retrieve_context_convenience(self):
        """Test the retrieve_context convenience function."""
        # Without initialized engine
        result = retrieve_context("test")
        self.assertEqual(result.documents, [])

        # With initialized engine
        doc = MockDocument("doc1", "text")
        mock_fn = MagicMock(return_value=[(doc, 0.9)])
        init_retrieval_engine(vector_search_fn=mock_fn)

        result = retrieve_context("test")
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(result.documents[0].id, "doc1")


if __name__ == "__main__":
    unittest.main()
