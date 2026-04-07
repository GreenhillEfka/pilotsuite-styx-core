"""Unit Tests for RAG Hybrid Search - BM25 and RRF (No FastAPI deps).

Core algorithm tests that don't require FastAPI or HTTP client.
"""

import os
import pytest
import tempfile
from typing import List

from copilot_core.rag.bm25 import (
    BM25Config,
    BM25Document,
    BM25SqliteIndex,
    _bm25_idf,
    _bm25_term_score,
    _term_frequencies,
    default_tokenize,
)
from copilot_core.rag.hybrid_search import (
    FusedHit,
    RankedHit,
    reciprocal_rank_fusion,
)


# ============================================================================
# BM25 Tokenization Tests
# ============================================================================

class TestTokenization:
    """Test tokenization functions."""
    
    def test_default_tokenize_simple(self):
        """Test tokenization of simple text."""
        tokens = default_tokenize("Hello world")
        assert tokens == ["hello", "world"]
    
    def test_default_tokenize_mixed_case(self):
        """Test case normalization."""
        tokens = default_tokenize("Hello WORLD Test")
        assert tokens == ["hello", "world", "test"]
    
    def test_default_tokenize_with_numbers(self):
        """Test tokenization with numbers."""
        tokens = default_tokenize("Test123 and 456test")
        assert "test123" in tokens
        assert "456test" in tokens
    
    def test_default_tokenize_special_chars(self):
        """Test that special characters are removed."""
        tokens = default_tokenize("Hello-world! Test@email.com")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens
        assert "email" in tokens
        assert "com" in tokens
    
    def test_default_tokenize_empty(self):
        """Test empty string."""
        assert default_tokenize("") == []
        assert default_tokenize("   ") == []
    
    def test_term_frequencies(self):
        """Test term frequency calculation."""
        tokens = ["hello", "world", "hello", "test", "hello"]
        tf = _term_frequencies(tokens)
        assert tf["hello"] == 3
        assert tf["world"] == 1
        assert tf["test"] == 1
    
    def test_term_frequencies_empty(self):
        """Test empty token list."""
        assert _term_frequencies([]) == {}


# ============================================================================
# BM25 Scoring Tests
# ============================================================================

class TestBM25Scoring:
    """Test BM25 scoring functions."""
    
    def test_idf_basic(self):
        """Test IDF calculation."""
        idf = _bm25_idf(n=100, df=10)
        assert idf > 0
    
    def test_idf_all_docs(self):
        """Test IDF when term is in all docs."""
        idf = _bm25_idf(n=100, df=100)
        assert idf > 0
    
    def test_idf_no_docs(self):
        """Test IDF with zero docs."""
        idf = _bm25_idf(n=0, df=0)
        assert idf == 0.0
    
    def test_idf_no_df(self):
        """Test IDF with zero document frequency."""
        idf = _bm25_idf(n=100, df=0)
        assert idf >= 0  # IDF can be 0 when term doesn't exist
    
    def test_term_score_basic(self):
        """Test term score calculation."""
        score = _bm25_term_score(
            idf=2.0,
            tf=3,
            doc_len=100,
            avg_doc_len=100.0,
            k1=1.5,
            b=0.75,
        )
        assert score > 0
    
    def test_term_score_zero_tf(self):
        """Test term score with zero term frequency."""
        score = _bm25_term_score(
            idf=2.0,
            tf=0,
            doc_len=100,
            avg_doc_len=100.0,
            k1=1.5,
            b=0.75,
        )
        assert score == 0.0
    
    def test_term_score_doc_len_effect(self):
        """Test that longer docs get penalized."""
        score_short = _bm25_term_score(
            idf=2.0,
            tf=3,
            doc_len=50,
            avg_doc_len=100.0,
            k1=1.5,
            b=0.75,
        )
        score_long = _bm25_term_score(
            idf=2.0,
            tf=3,
            doc_len=200,
            avg_doc_len=100.0,
            k1=1.5,
            b=0.75,
        )
        assert score_short > score_long


# ============================================================================
# BM25 Index Tests
# ============================================================================

class TestBM25Index:
    """Test BM25 index operations."""
    
    @pytest.fixture
    def index(self):
        """Create temporary BM25 index."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
            db_path = f.name
        config = BM25Config(db_path=db_path, persist=True)
        idx = BM25SqliteIndex(config)
        yield idx
        idx.close()
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    def test_upsert_single_document(self, index):
        """Test indexing a single document."""
        doc = BM25Document(doc_id="doc1", text="Hello world test")
        success, errors = index.upsert_documents(namespace="test", documents=[doc])
        
        assert success == 1
        assert len(errors) == 0
    
    def test_upsert_multiple_documents(self, index):
        """Test indexing multiple documents."""
        docs = [
            BM25Document(doc_id="doc1", text="Hello world"),
            BM25Document(doc_id="doc2", text="World peace"),
            BM25Document(doc_id="doc3", text="Hello peace"),
        ]
        success, errors = index.upsert_documents(namespace="test", documents=docs)
        
        assert success == 3
        assert len(errors) == 0
    
    def test_upsert_with_metadata(self, index):
        """Test indexing with metadata."""
        doc = BM25Document(
            doc_id="doc1",
            text="Test content",
            metadata={"author": "test", "year": 2024}
        )
        success, errors = index.upsert_documents(namespace="test", documents=[doc])
        
        assert success == 1
        docs = index.get_documents(namespace="test", doc_ids=["doc1"])
        assert docs["doc1"]["metadata"]["author"] == "test"
    
    def test_upsert_empty_doc_id(self, index):
        """Test that empty doc_id raises error."""
        doc = BM25Document(doc_id="", text="Test")
        success, errors = index.upsert_documents(namespace="test", documents=[doc])
        
        assert success == 0
        assert len(errors) == 1
    
    def test_upsert_empty_text(self, index):
        """Test that empty text raises error."""
        doc = BM25Document(doc_id="doc1", text="")
        success, errors = index.upsert_documents(namespace="test", documents=[doc])
        
        assert success == 0
        assert len(errors) == 1
    
    def test_upsert_update_document(self, index):
        """Test updating an existing document."""
        doc1 = BM25Document(doc_id="doc1", text="Original text")
        index.upsert_documents(namespace="test", documents=[doc1])
        
        doc2 = BM25Document(doc_id="doc1", text="Updated text")
        success, errors = index.upsert_documents(namespace="test", documents=[doc2])
        
        assert success == 1
        docs = index.get_documents(namespace="test", doc_ids=["doc1"])
        assert docs["doc1"]["text"] == "Updated text"
    
    def test_search_basic(self, index):
        """Test basic search."""
        docs = [
            BM25Document(doc_id="doc1", text="Python programming language"),
            BM25Document(doc_id="doc2", text="Java programming language"),
            BM25Document(doc_id="doc3", text="Python snake"),
        ]
        index.upsert_documents(namespace="test", documents=docs)
        
        hits = index.search(namespace="test", query="Python programming", top_k=2)
        
        assert len(hits) >= 1
        assert hits[0].doc_id in ["doc1", "doc2", "doc3"]
    
    def test_search_with_text(self, index):
        """Test search with text inclusion."""
        doc = BM25Document(doc_id="doc1", text="Test content for search")
        index.upsert_documents(namespace="test", documents=[doc])
        
        hits = index.search(namespace="test", query="test", top_k=1, include_text=True)
        
        assert len(hits) == 1
        assert hits[0].text == "Test content for search"
    
    def test_search_with_metadata(self, index):
        """Test search with metadata inclusion."""
        doc = BM25Document(
            doc_id="doc1",
            text="Test content",
            metadata={"key": "value"}
        )
        index.upsert_documents(namespace="test", documents=[doc])
        
        hits = index.search(namespace="test", query="test", top_k=1, include_metadata=True)
        
        assert len(hits) == 1
        assert hits[0].metadata["key"] == "value"
    
    def test_search_empty_namespace(self, index):
        """Test search in empty namespace."""
        hits = index.search(namespace="empty", query="test", top_k=10)
        assert hits == []
    
    def test_search_empty_query(self, index):
        """Test search with empty query."""
        doc = BM25Document(doc_id="doc1", text="Test content")
        index.upsert_documents(namespace="test", documents=[doc])
        
        hits = index.search(namespace="test", query="", top_k=10)
        assert hits == []
    
    def test_get_documents(self, index):
        """Test getting documents by IDs."""
        docs = [
            BM25Document(doc_id="doc1", text="First"),
            BM25Document(doc_id="doc2", text="Second"),
        ]
        index.upsert_documents(namespace="test", documents=docs)
        
        result = index.get_documents(namespace="test", doc_ids=["doc1", "doc2"])
        
        assert len(result) == 2
        assert result["doc1"]["text"] == "First"
        assert result["doc2"]["text"] == "Second"
    
    def test_get_documents_not_found(self, index):
        """Test getting non-existent documents."""
        result = index.get_documents(namespace="test", doc_ids=["nonexistent"])
        assert result == {}
    
    def test_stats(self, index):
        """Test index statistics."""
        docs = [
            BM25Document(doc_id="doc1", text="Hello world"),
            BM25Document(doc_id="doc2", text="Test content"),
        ]
        index.upsert_documents(namespace="test", documents=docs)
        
        stats = index.stats(namespace="test")
        
        assert stats.namespace == "test"
        assert stats.doc_count == 2
        assert stats.term_count > 0
        assert stats.posting_count > 0
        assert stats.avg_doc_len > 0
    
    def test_stats_empty_namespace(self, index):
        """Test stats for empty namespace."""
        stats = index.stats(namespace="empty")
        
        assert stats.doc_count == 0
        assert stats.term_count == 0
    
    def test_namespace_isolation(self, index):
        """Test that namespaces are isolated."""
        doc1 = BM25Document(doc_id="doc1", text="Namespace A")
        doc2 = BM25Document(doc_id="doc1", text="Namespace B")
        
        index.upsert_documents(namespace="ns_a", documents=[doc1])
        index.upsert_documents(namespace="ns_b", documents=[doc2])
        
        hits_a = index.search(namespace="ns_a", query="namespace", top_k=10, include_text=True)
        hits_b = index.search(namespace="ns_b", query="namespace", top_k=10, include_text=True)
        
        assert len(hits_a) == 1
        assert len(hits_b) == 1
        assert hits_a[0].text == "Namespace A"
        assert hits_b[0].text == "Namespace B"


# ============================================================================
# Hybrid Search (RRF) Tests
# ============================================================================

class TestReciprocalRankFusion:
    """Test RRF fusion algorithm."""
    
    def test_rrf_basic(self):
        """Test basic RRF fusion."""
        lexical = [
            RankedHit(doc_id="doc1", score=0.9, rank=1),
            RankedHit(doc_id="doc2", score=0.8, rank=2),
        ]
        semantic = [
            RankedHit(doc_id="doc2", score=0.95, rank=1),
            RankedHit(doc_id="doc3", score=0.85, rank=2),
        ]
        
        fused = reciprocal_rank_fusion(
            lexical_hits=lexical,
            semantic_hits=semantic,
            top_k=3,
        )
        
        assert len(fused) == 3
        assert fused[0].doc_id == "doc2"  # Should be ranked highest
    
    def test_rrf_empty_lexical(self):
        """Test RRF with empty lexical results."""
        lexical: List[RankedHit] = []
        semantic = [
            RankedHit(doc_id="doc1", score=0.9, rank=1),
        ]
        
        fused = reciprocal_rank_fusion(
            lexical_hits=lexical,
            semantic_hits=semantic,
            top_k=5,
        )
        
        assert len(fused) == 1
        assert fused[0].doc_id == "doc1"
    
    def test_rrf_empty_semantic(self):
        """Test RRF with empty semantic results."""
        lexical = [
            RankedHit(doc_id="doc1", score=0.9, rank=1),
        ]
        semantic: List[RankedHit] = []
        
        fused = reciprocal_rank_fusion(
            lexical_hits=lexical,
            semantic_hits=semantic,
            top_k=5,
        )
        
        assert len(fused) == 1
        assert fused[0].doc_id == "doc1"
    
    def test_rrf_both_empty(self):
        """Test RRF with both empty."""
        fused = reciprocal_rank_fusion(
            lexical_hits=[],
            semantic_hits=[],
            top_k=10,
        )
        assert fused == []
    
    def test_rrf_top_k_limit(self):
        """Test that top_k limits results."""
        lexical = [RankedHit(doc_id=f"doc{i}", score=1.0, rank=i) for i in range(1, 11)]
        semantic = [RankedHit(doc_id=f"doc{i}", score=1.0, rank=i) for i in range(11, 21)]
        
        fused = reciprocal_rank_fusion(
            lexical_hits=lexical,
            semantic_hits=semantic,
            top_k=5,
        )
        
        assert len(fused) == 5
    
    def test_rrf_weights(self):
        """Test weighted RRF."""
        lexical = [RankedHit(doc_id="doc1", score=0.9, rank=1)]
        semantic = [RankedHit(doc_id="doc2", score=0.9, rank=1)]
        
        # Higher lexical weight should favor doc1
        fused = reciprocal_rank_fusion(
            lexical_hits=lexical,
            semantic_hits=semantic,
            top_k=2,
            lexical_weight=10.0,
            semantic_weight=1.0,
        )
        
        assert fused[0].doc_id == "doc1"
    
    def test_rrf_k_parameter(self):
        """Test RRF k parameter effect."""
        lexical = [RankedHit(doc_id="doc1", score=0.9, rank=1)]
        semantic = [RankedHit(doc_id="doc1", score=0.9, rank=1)]
        
        fused = reciprocal_rank_fusion(
            lexical_hits=lexical,
            semantic_hits=semantic,
            top_k=1,
            k=60,
        )
        
        assert len(fused) == 1
        assert fused[0].fused_score > 0
    
    def test_rrf_preserves_metadata(self):
        """Test that RRF preserves rank and score metadata."""
        lexical = [RankedHit(doc_id="doc1", score=0.8, rank=2)]
        semantic = [RankedHit(doc_id="doc1", score=0.9, rank=1)]
        
        fused = reciprocal_rank_fusion(
            lexical_hits=lexical,
            semantic_hits=semantic,
            top_k=1,
        )
        
        assert fused[0].lexical_rank == 2
        assert fused[0].semantic_rank == 1
        assert fused[0].lexical_score == 0.8
        assert fused[0].semantic_score == 0.9


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_rrf_invalid_rank(self):
        """Test RRF with invalid rank values."""
        lexical = [RankedHit(doc_id="doc1", score=0.9, rank=0)]
        semantic: List[RankedHit] = []
        
        fused = reciprocal_rank_fusion(
            lexical_hits=lexical,
            semantic_hits=semantic,
            top_k=1,
        )
        
        assert len(fused) == 1
    
    def test_rrf_duplicate_docs(self):
        """Test RRF with same doc in both lists."""
        lexical = [RankedHit(doc_id="doc1", score=0.9, rank=1)]
        semantic = [RankedHit(doc_id="doc1", score=0.95, rank=1)]
        
        fused = reciprocal_rank_fusion(
            lexical_hits=lexical,
            semantic_hits=semantic,
            top_k=1,
        )
        
        assert len(fused) == 1
        assert fused[0].doc_id == "doc1"
        assert fused[0].fused_score > 0
    
    def test_bm25_special_characters_in_query(self):
        """Test BM25 search with special characters."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
            db_path = f.name
        try:
            index = BM25SqliteIndex(BM25Config(db_path=db_path))
            
            doc = BM25Document(doc_id="doc1", text="Email: test@example.com")
            index.upsert_documents(namespace="test", documents=[doc])
            
            hits = index.search(namespace="test", query="email test", top_k=10)
            assert len(hits) > 0
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_bm25_very_long_document(self):
        """Test BM25 with very long document."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
            db_path = f.name
        try:
            index = BM25SqliteIndex(BM25Config(db_path=db_path))
            
            long_text = "word " * 10000
            doc = BM25Document(doc_id="doc1", text=long_text)
            index.upsert_documents(namespace="test", documents=[doc])
            
            hits = index.search(namespace="test", query="word", top_k=10)
            assert len(hits) == 1
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_bm25_unicode_text(self):
        """Test BM25 with unicode text."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
            db_path = f.name
        try:
            index = BM25SqliteIndex(BM25Config(db_path=db_path))
            
            doc = BM25Document(doc_id="doc1", text="Hello 世界 🌍")
            index.upsert_documents(namespace="test", documents=[doc])
            
            hits = index.search(namespace="test", query="hello", top_k=10)
            assert len(hits) == 1
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
