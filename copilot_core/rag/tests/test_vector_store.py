"""Vector Store Tests — Comprehensive test suite for RAG vector storage."""
from __future__ import annotations

import pytest
import numpy as np
from typing import List, Dict, Any
import tempfile
import shutil
from pathlib import Path


class TestVectorStore:
    """Test vector store CRUD operations."""

    @pytest.fixture
    def vector_store(self):
        """Create test vector store."""
        from copilot_core.rag.vector_store import VectorStore
        temp_dir = tempfile.mkdtemp()
        store = VectorStore(data_dir=temp_dir, dimension=384)
        yield store
        shutil.rmtree(temp_dir)

    def test_add_vector(self, vector_store):
        """Test adding vector to store."""
        vector = np.random.rand(384).astype(np.float32)
        entry_id = "test_entry_1"
        metadata = {"type": "test", "source": "unit_test"}
        
        result = vector_store.add_vector(entry_id, vector, metadata)
        
        assert result is True
        assert entry_id in vector_store._vectors

    def test_get_vector(self, vector_store):
        """Test retrieving vector from store."""
        vector = np.random.rand(384).astype(np.float32)
        entry_id = "test_entry_2"
        
        vector_store.add_vector(entry_id, vector, {"type": "test"})
        retrieved = vector_store.get_vector(entry_id)
        
        assert retrieved is not None
        assert np.allclose(retrieved["vector"], vector)
        assert retrieved["metadata"]["type"] == "test"

    def test_delete_vector(self, vector_store):
        """Test deleting vector from store."""
        vector = np.random.rand(384).astype(np.float32)
        entry_id = "test_entry_3"
        
        vector_store.add_vector(entry_id, vector)
        result = vector_store.delete_vector(entry_id)
        
        assert result is True
        assert entry_id not in vector_store._vectors

    def test_similarity_search(self, vector_store):
        """Test similarity search."""
        # Add known vectors
        for i in range(10):
            vector = np.zeros(384, dtype=np.float32)
            vector[i % 384] = 1.0  # One-hot encoding
            vector_store.add_vector(f"entry_{i}", vector, {"index": i})
        
        # Query with similar vector
        query = np.zeros(384, dtype=np.float32)
        query[0] = 0.9  # Similar to entry_0
        
        results = vector_store.similarity_search(query, k=3)
        
        assert len(results) == 3
        assert results[0]["entry_id"] == "entry_0"

    def test_bulk_add(self, vector_store):
        """Test bulk vector addition."""
        vectors = np.random.rand(100, 384).astype(np.float32)
        entry_ids = [f"bulk_{i}" for i in range(100)]
        metadata = [{"index": i} for i in range(100)]
        
        result = vector_store.bulk_add(entry_ids, vectors, metadata)
        
        assert result["success"] is True
        assert result["added_count"] == 100

    def test_persistence(self, vector_store):
        """Test vector store persistence."""
        vector = np.random.rand(384).astype(np.float32)
        entry_id = "persistent_test"
        
        vector_store.add_vector(entry_id, vector, {"test": "value"})
        vector_store.save()
        
        # Create new instance with same directory
        new_store = type(vector_store)(data_dir=vector_store._data_dir, dimension=384)
        new_store.load()
        
        retrieved = new_store.get_vector(entry_id)
        assert retrieved is not None
        assert retrieved["metadata"]["test"] == "value"

    def test_vector_stats(self, vector_store):
        """Test vector store statistics."""
        for i in range(50):
            vector = np.random.rand(384).astype(np.float32)
            vector_store.add_vector(f"stat_{i}", vector)
        
        stats = vector_store.get_stats()
        
        assert stats["vector_count"] == 50
        assert stats["dimension"] == 384
        assert "memory_usage_mb" in stats

    def test_dimension_mismatch(self, vector_store):
        """Test handling of dimension mismatch."""
        wrong_vector = np.random.rand(256).astype(np.float32)  # Wrong dimension
        
        with pytest.raises(ValueError):
            vector_store.add_vector("wrong_dim", wrong_vector)

    def test_concurrent_access(self, vector_store):
        """Test concurrent read/write access."""
        import threading
        
        errors = []
        
        def writer():
            try:
                for i in range(20):
                    vector = np.random.rand(384).astype(np.float32)
                    vector_store.add_vector(f"concurrent_{i}", vector)
            except Exception as e:
                errors.append(e)
        
        def reader():
            try:
                for i in range(20):
                    vector_store.get_vector(f"concurrent_{i}")
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Concurrent access errors: {errors}"

    def test_export_import(self, vector_store):
        """Test vector store export/import."""
        for i in range(10):
            vector = np.random.rand(384).astype(np.float32)
            vector_store.add_vector(f"export_{i}", vector, {"i": i})
        
        # Export
        export_path = vector_store._data_dir / "export.json"
        vector_store.export_to_json(str(export_path))
        
        assert export_path.exists()
        
        # Import to new store
        temp_dir = tempfile.mkdtemp()
        try:
            new_store = type(vector_store)(data_dir=temp_dir, dimension=384)
            new_store.import_from_json(str(export_path))
            
            assert new_store.get_stats()["vector_count"] == 10
        finally:
            shutil.rmtree(temp_dir)


class TestEmbeddingPipeline:
    """Test embedding pipeline operations."""

    @pytest.fixture
    def embedding_pipeline(self):
        """Create test embedding pipeline."""
        from copilot_core.rag.embedding_pipeline import EmbeddingPipeline
        return EmbeddingPipeline(model_name="sentence-transformers/all-MiniLM-L6-v2")

    def test_create_embedding(self, embedding_pipeline):
        """Test creating single embedding."""
        text = "This is a test sentence for embedding."
        
        embedding = embedding_pipeline.create_embedding(text)
        
        assert embedding is not None
        assert len(embedding) == 384  # all-MiniLM-L6-v2 dimension
        assert isinstance(embedding, np.ndarray)

    def test_batch_embeddings(self, embedding_pipeline):
        """Test creating batch embeddings."""
        texts = [
            "First test sentence",
            "Second test sentence",
            "Third test sentence",
        ]
        
        embeddings = embedding_pipeline.create_batch_embeddings(texts)
        
        assert len(embeddings) == 3
        assert all(len(e) == 384 for e in embeddings)

    def test_normalize_embeddings(self, embedding_pipeline):
        """Test embedding normalization."""
        embedding = np.random.rand(384).astype(np.float32)
        
        normalized = embedding_pipeline.normalize_embedding(embedding)
        
        assert np.isclose(np.linalg.norm(normalized), 1.0)

    def test_embedding_cache(self, embedding_pipeline):
        """Test embedding cache."""
        text = "Cached embedding test"
        
        # First call (cache miss)
        emb1 = embedding_pipeline.create_embedding(text)
        
        # Second call (cache hit)
        emb2 = embedding_pipeline.create_embedding(text)
        
        assert np.allclose(emb1, emb2)


class TestRetrievalEngine:
    """Test retrieval engine operations."""

    @pytest.fixture
    def retrieval_engine(self):
        """Create test retrieval engine."""
        from copilot_core.rag.retrieval_engine import RetrievalEngine
        from copilot_core.rag.vector_store import VectorStore
        import tempfile
        
        temp_dir = tempfile.mkdtemp()
        vector_store = VectorStore(data_dir=temp_dir, dimension=384)
        engine = RetrievalEngine(vector_store=vector_store)
        yield engine
        shutil.rmtree(temp_dir)

    def test_retrieve_similar(self, retrieval_engine):
        """Test retrieving similar documents."""
        # Add documents
        for i in range(20):
            vector = np.random.rand(384).astype(np.float32)
            retrieval_engine._vector_store.add_vector(
                f"doc_{i}", vector, {"text": f"Document {i}", "category": "test"}
            )
        
        # Query
        query_vector = np.random.rand(384).astype(np.float32)
        results = retrieval_engine.retrieve_similar(query_vector, k=5)
        
        assert len(results) == 5
        assert all("entry_id" in r for r in results)
        assert all("metadata" in r for r in results)

    def test_filtered_retrieval(self, retrieval_engine):
        """Test retrieval with filters."""
        # Add documents with categories
        for cat in ["A", "B", "C"]:
            for i in range(10):
                vector = np.random.rand(384).astype(np.float32)
                retrieval_engine._vector_store.add_vector(
                    f"doc_{cat}_{i}", vector, {"category": cat}
                )
        
        # Query with filter
        query_vector = np.random.rand(384).astype(np.float32)
        results = retrieval_engine.retrieve_similar(
            query_vector, k=5, filters={"category": "A"}
        )
        
        assert len(results) == 5
        assert all(r["metadata"]["category"] == "A" for r in results)

    def test_hybrid_retrieval(self, retrieval_engine):
        """Test hybrid retrieval (vector + keyword)."""
        # Add documents
        for i in range(20):
            vector = np.random.rand(384).astype(np.float32)
            retrieval_engine._vector_store.add_vector(
                f"doc_{i}", vector, {"text": f"Test document {i} about topic {i % 3}"}
            )
        
        # Hybrid query
        query_vector = np.random.rand(384).astype(np.float32)
        results = retrieval_engine.hybrid_retrieve(
            query_vector, 
            keyword="topic",
            k=10,
            alpha=0.5  # Equal weight vector + keyword
        )
        
        assert len(results) == 10


class TestRAGAPI:
    """Test RAG API endpoints."""

    @pytest.fixture
    def rag_api(self):
        """Create test RAG API."""
        from copilot_core.rag.rag_api import RAGAPI
        return RAGAPI()

    def test_add_document_api(self, rag_api):
        """Test add document via API."""
        response = rag_api.add_document({
            "id": "api_test_doc",
            "text": "Test document content",
            "metadata": {"source": "api_test"}
        })
        
        assert response["success"] is True
        assert response["document_id"] == "api_test_doc"

    def test_query_api(self, rag_api):
        """Test query via API."""
        # Add document first
        rag_api.add_document({
            "id": "query_test",
            "text": "Test content for query",
            "metadata": {}
        })
        
        response = rag_api.query({
            "query": "test content",
            "k": 5
        })
        
        assert response["success"] is True
        assert "results" in response
        assert len(response["results"]) > 0

    def test_bulk_import_api(self, rag_api):
        """Test bulk import via API."""
        documents = [
            {"id": f"bulk_{i}", "text": f"Bulk document {i}", "metadata": {}}
            for i in range(10)
        ]
        
        response = rag_api.bulk_import({"documents": documents})
        
        assert response["success"] is True
        assert response["imported_count"] == 10


# Run with: pytest copilot_core/rag/tests/test_vector_store.py -v
