"""Tests for Embedding Pipeline Module.

Tests cover:
- EmbeddingCache dataclass
- BatchResult dataclass
- EmbeddingPipeline operations (embed, embed_batch)
- Caching functionality
- Statistics tracking
- Persistence (save/load cache)
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from copilot_core.rag.embedding_pipeline import (
    EmbeddingCache,
    BatchResult,
    EmbeddingPipeline,
    EmbeddingPipeline,
    set_embedding_function,
    init_embedding_pipeline,
    embed_text,
    embed_batch,
    default_embedding_pipeline,
    _default_embed_fn,
)


class TestEmbeddingCache(unittest.TestCase):
    """Test EmbeddingCache dataclass."""

    def test_create_cache_entry(self):
        """Test creating an EmbeddingCache entry."""
        cache = EmbeddingCache(
            text_hash="abc123",
            embedding=[0.1, 0.2, 0.3],
            model="test-model"
        )
        
        self.assertEqual(cache.text_hash, "abc123")
        self.assertEqual(cache.embedding, [0.1, 0.2, 0.3])
        self.assertEqual(cache.model, "test-model")
        self.assertEqual(cache.access_count, 0)
        self.assertGreater(cache.created_at, 0)

    def test_cache_with_access_count(self):
        """Test creating a cache entry with access count."""
        cache = EmbeddingCache(
            text_hash="def456",
            embedding=[0.4, 0.5, 0.6],
            model="test-model",
            created_at=1234567890.0,
            access_count=5
        )
        
        self.assertEqual(cache.access_count, 5)
        self.assertEqual(cache.created_at, 1234567890.0)


class TestBatchResult(unittest.TestCase):
    """Test BatchResult dataclass."""

    def test_create_batch_result(self):
        """Test creating a BatchResult."""
        result = BatchResult(
            total=10,
            successful=8,
            failed=2,
            cached=5,
            duration_ms=150.5,
            embeddings=[[0.1, 0.2], [0.3, 0.4]]
        )
        
        self.assertEqual(result.total, 10)
        self.assertEqual(result.successful, 8)
        self.assertEqual(result.failed, 2)
        self.assertEqual(result.cached, 5)
        self.assertEqual(result.duration_ms, 150.5)
        self.assertEqual(len(result.embeddings), 2)


class TestEmbeddingPipeline(unittest.TestCase):
    """Test EmbeddingPipeline class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.call_count = 0
        
        def mock_embed_fn(text):
            self.call_count += 1
            # Create deterministic embedding based on text
            return [float(ord(c)) for c in text[:384]] if len(text) >= 384 else [float(ord(c)) for c in text] + [0.0] * (384 - len(text))
        
        self.mock_embed_fn = mock_embed_fn
        self.pipeline = EmbeddingPipeline(
            embed_fn=mock_embed_fn,
            cache_dir=self.temp_dir,
            cache_size=100,
            batch_size=32
        )

    def tearDown(self):
        """Clean up test fixtures."""
        self.pipeline = None
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self):
        """Test EmbeddingPipeline initialization."""
        self.assertEqual(self.pipeline.cache_size, 100)
        self.assertEqual(self.pipeline.batch_size, 32)
        self.assertEqual(len(self.pipeline._cache), 0)
        self.assertEqual(self.pipeline._stats["total_requests"], 0)

    def test_embed_single_text(self):
        """Test embedding a single text."""
        result = self.pipeline.embed("Hello, World!")
        
        self.assertEqual(len(result), 384)
        self.assertEqual(self.call_count, 1)
        self.assertEqual(self.pipeline._stats["total_requests"], 1)
        self.assertEqual(self.pipeline._stats["cache_misses"], 1)

    def test_embed_caching(self):
        """Test that embeddings are cached."""
        text = "Test caching"
        
        # First call - cache miss
        result1 = self.pipeline.embed(text)
        self.assertEqual(self.call_count, 1)
        self.assertEqual(self.pipeline._stats["cache_misses"], 1)
        
        # Second call - cache hit
        result2 = self.pipeline.embed(text)
        self.assertEqual(self.call_count, 1)  # Should not call embed_fn again
        self.assertEqual(self.pipeline._stats["cache_hits"], 1)
        self.assertEqual(result1, result2)

    def test_embed_cache_access_count(self):
        """Test that cache access count is incremented."""
        text = "Test access count"
        
        # First call - should increment access count to 1
        self.pipeline.embed(text)
        text_hash = self.pipeline._hash_text(text)
        self.assertEqual(self.pipeline._cache[text_hash].access_count, 1)
        
        # Second call - should increment access count to 2
        self.pipeline.embed(text)
        self.assertEqual(self.pipeline._cache[text_hash].access_count, 2)
        
        # Third call - should increment access count to 3
        self.pipeline.embed(text)
        self.assertEqual(self.pipeline._cache[text_hash].access_count, 3)

    def test_embed_different_texts(self):
        """Test embedding different texts."""
        result1 = self.pipeline.embed("Text A")
        result2 = self.pipeline.embed("Text B")
        
        self.assertNotEqual(result1, result2)
        self.assertEqual(self.call_count, 2)
        self.assertEqual(self.pipeline._stats["total_requests"], 2)

    def test_embed_batch(self):
        """Test batch embedding."""
        texts = ["Text 1", "Text 2", "Text 3", "Text 4", "Text 5"]
        
        result = self.pipeline.embed_batch(texts)
        
        self.assertIsInstance(result, BatchResult)
        self.assertEqual(result.total, 5)
        self.assertEqual(result.successful, 5)
        self.assertEqual(result.failed, 0)
        self.assertEqual(len(result.embeddings), 5)
        self.assertEqual(self.call_count, 5)

    def test_embed_batch_partial_cache(self):
        """Test batch embedding with some cached results."""
        texts = ["Cached text", "New text 1", "New text 2"]
        
        # Pre-cache one text
        self.pipeline.embed("Cached text")
        self.call_count = 0  # Reset counter
        
        result = self.pipeline.embed_batch(texts)
        
        self.assertEqual(result.total, 3)
        self.assertEqual(result.successful, 3)
        # The cached count should be 1 (the first text was cached)
        self.assertEqual(result.cached, 1)
        # Only 2 new embeddings should be generated (the other 2 texts)
        self.assertEqual(self.call_count, 2)
        
        # Verify the cached text is in the cache and has been accessed
        text_hash = self.pipeline._hash_text("Cached text")
        self.assertIn(text_hash, self.pipeline._cache)
        self.assertEqual(self.pipeline._cache[text_hash].access_count, 1)

    def test_embed_batch_with_failures(self):
        """Test batch embedding with some failures."""
        def flaky_embed_fn(text):
            if "fail" in text:
                raise Exception("Simulated failure")
            return [0.1] * 384
        
        pipeline = EmbeddingPipeline(embed_fn=flaky_embed_fn)
        
        texts = ["good text", "fail text", "another good"]
        result = pipeline.embed_batch(texts)
        
        self.assertEqual(result.total, 3)
        self.assertEqual(result.successful, 2)
        self.assertEqual(result.failed, 1)
        self.assertEqual(len(result.embeddings), 3)
        # Failed embeddings should be zero vectors
        self.assertEqual(result.embeddings[1], [0.0] * 384)

    def test_hash_text(self):
        """Test text hashing."""
        hash1 = self.pipeline._hash_text("test")
        hash2 = self.pipeline._hash_text("test")
        hash3 = self.pipeline._hash_text("different")
        
        self.assertEqual(hash1, hash2)  # Same text = same hash
        self.assertNotEqual(hash1, hash3)  # Different text = different hash
        self.assertEqual(len(hash1), 16)  # Hash should be 16 chars

    def test_evict_oldest(self):
        """Test cache eviction."""
        # Create a pipeline with small cache
        pipeline = EmbeddingPipeline(embed_fn=self.mock_embed_fn, cache_size=3)
        
        # Fill cache
        pipeline.embed("Text 1")
        time.sleep(0.01)
        pipeline.embed("Text 2")
        time.sleep(0.01)
        pipeline.embed("Text 3")
        time.sleep(0.01)
        
        self.assertEqual(len(pipeline._cache), 3)
        
        # Add one more - should evict oldest
        pipeline.embed("Text 4")
        
        # Should still have 3 items
        self.assertEqual(len(pipeline._cache), 3)
        # "Text 1" should be evicted (oldest)
        hash1 = pipeline._hash_text("Text 1")
        self.assertNotIn(hash1, pipeline._cache)

    def test_get_stats(self):
        """Test getting pipeline statistics."""
        self.pipeline.embed("Text 1")
        self.pipeline.embed("Text 1")  # Cache hit
        self.pipeline.embed("Text 2")
        
        stats = self.pipeline.get_stats()
        
        self.assertEqual(stats["total_requests"], 3)
        self.assertEqual(stats["cache_hits"], 1)
        self.assertEqual(stats["cache_misses"], 2)
        self.assertEqual(stats["cache_size"], 2)
        self.assertIn("cache_hit_rate", stats)
        self.assertGreaterEqual(stats["cache_hit_rate"], 0.0)
        self.assertLessEqual(stats["cache_hit_rate"], 1.0)

    def test_clear_cache(self):
        """Test clearing the cache."""
        self.pipeline.embed("Text 1")
        self.pipeline.embed("Text 2")
        
        self.assertEqual(len(self.pipeline._cache), 2)
        
        self.pipeline.clear_cache()
        
        self.assertEqual(len(self.pipeline._cache), 0)

    def test_cache_persistence_save(self):
        """Test that cache is saved to disk."""
        self.pipeline.embed("Persistent text")
        self.pipeline._save_cache()
        
        cache_file = Path(self.temp_dir) / "embedding_cache.json"
        self.assertTrue(cache_file.exists())
        
        with open(cache_file, 'r') as f:
            data = json.load(f)
        
        self.assertGreater(len(data), 0)

    def test_cache_persistence_load(self):
        """Test that cache is loaded from disk on init."""
        # Create pipeline and add data
        pipeline1 = EmbeddingPipeline(
            embed_fn=self.mock_embed_fn,
            cache_dir=self.temp_dir,
            cache_size=100
        )
        pipeline1.embed("Persistent text")
        pipeline1._save_cache()
        
        # Create new pipeline with same cache dir
        pipeline2 = EmbeddingPipeline(
            embed_fn=self.mock_embed_fn,
            cache_dir=self.temp_dir,
            cache_size=100
        )
        
        # Should have loaded cached data
        self.assertEqual(len(pipeline2._cache), 1)

    def test_cache_load_nonexistent_file(self):
        """Test cache initialization when file doesn't exist."""
        new_dir = tempfile.mkdtemp()
        try:
            pipeline = EmbeddingPipeline(
                embed_fn=self.mock_embed_fn,
                cache_dir=new_dir,
                cache_size=100
            )
            # Should not raise an error
            self.assertEqual(len(pipeline._cache), 0)
        finally:
            shutil.rmtree(new_dir, ignore_errors=True)

    def test_cache_load_corrupted_file(self):
        """Test cache initialization with corrupted file."""
        new_dir = tempfile.mkdtemp()
        try:
            # Create corrupted cache file
            cache_file = Path(new_dir) / "embedding_cache.json"
            with open(cache_file, 'w') as f:
                f.write("not valid json {{{")
            
            pipeline = EmbeddingPipeline(
                embed_fn=self.mock_embed_fn,
                cache_dir=new_dir,
                cache_size=100
            )
            # Should not raise an error, just log it
            self.assertEqual(len(pipeline._cache), 0)
        finally:
            shutil.rmtree(new_dir, ignore_errors=True)

    def test_cache_save_error_handling(self):
        """Test cache save error handling."""
        with patch.object(self.pipeline, '_cache', side_effect=Exception("Simulated error")):
            # Should not raise an error
            self.pipeline._save_cache()


class TestGlobalFunctions(unittest.TestCase):
    """Test global embedding functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.original_embed_fn = None
        if '_default_embed_fn' in sys.modules.get('copilot_core.rag.embedding_pipeline', {}).__dict__:
            self.original_embed_fn = sys.modules['copilot_core.rag.embedding_pipeline']._default_embed_fn

    def tearDown(self):
        """Clean up."""
        from copilot_core.rag import embedding_pipeline
        embedding_pipeline._default_embed_fn = self.original_embed_fn
        embedding_pipeline.default_embedding_pipeline = None

    def test_set_embedding_function(self):
        """Test setting the global embedding function."""
        def custom_fn(text):
            return [1.0] * 384
        
        set_embedding_function(custom_fn)
        
        from copilot_core.rag.embedding_pipeline import _default_embed_fn
        self.assertIsNotNone(_default_embed_fn)

    def test_init_embedding_pipeline(self):
        """Test initializing the global embedding pipeline."""
        def custom_fn(text):
            return [0.5] * 384
        
        pipeline = init_embedding_pipeline(
            embed_fn=custom_fn,
            cache_size=50,
            batch_size=16
        )
        
        self.assertIsNotNone(pipeline)
        self.assertEqual(pipeline.cache_size, 50)
        
        from copilot_core.rag.embedding_pipeline import default_embedding_pipeline
        self.assertIsNotNone(default_embedding_pipeline)

    def test_embed_text_convenience(self):
        """Test the embed_text convenience function."""
        # Without initialized pipeline
        result = embed_text("test")
        self.assertEqual(result, [0.0] * 384)  # Default fallback
        
        # With initialized pipeline
        def custom_fn(text):
            return [1.0] * 384
        
        init_embedding_pipeline(embed_fn=custom_fn)
        result = embed_text("test")
        self.assertEqual(result, [1.0] * 384)

    def test_embed_batch_convenience(self):
        """Test the embed_batch convenience function."""
        # Without initialized pipeline
        result = embed_batch(["test1", "test2"])
        self.assertEqual(result, [[0.0] * 384, [0.0] * 384])
        
        # With initialized pipeline
        def custom_fn(text):
            return [1.0] * 384
        
        init_embedding_pipeline(embed_fn=custom_fn)
        result = embed_batch(["test1", "test2"])
        self.assertEqual(result, [[1.0] * 384, [1.0] * 384])


if __name__ == "__main__":
    unittest.main()
