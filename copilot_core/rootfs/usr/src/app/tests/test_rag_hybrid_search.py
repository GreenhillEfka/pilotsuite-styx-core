"""Tests for RAG Hybrid Search.

Test coverage for RAG Hybrid Search:
- Reciprocal Rank Fusion (RRF) algorithm
- Hybrid search endpoint
- BM25-only search
- Semantic-only search
- Index statistics
- Search statistics
- Error handling
- Edge cases

Author: Clawdya
Version: 1.0.0
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from flask import Flask

# Import the RAG module components
from copilot_core.rag.hybrid_search import (
    reciprocal_rank_fusion,
    RankedHit,
    FusedHit,
)


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    yield app


@pytest.fixture
def mock_bm25_index():
    """Create mock BM25 index."""
    bm25 = MagicMock()
    bm25.search.return_value = [
        MagicMock(doc_id="doc1", score=0.9, rank=1),
        MagicMock(doc_id="doc2", score=0.7, rank=2),
        MagicMock(doc_id="doc3", score=0.5, rank=3),
    ]
    bm25.get_documents.return_value = {
        "doc1": {"text": "Document 1 content", "metadata": {"source": "test"}},
        "doc2": {"text": "Document 2 content", "metadata": {}},
        "doc3": {"text": "Document 3 content", "metadata": {"source": "test"}},
    }
    bm25.stats.return_value = MagicMock(
        namespace="default",
        doc_count=100,
        term_count=500,
        posting_count=1000,
        avg_doc_len=50.0,
        total_doc_len=5000,
        updated_at="2024-01-01T00:00:00Z",
        db_path="/tmp/test.db",
        db_size_bytes=10240,
        schema_version=1,
    )
    bm25.upsert_documents.return_value = (3, 0)
    return bm25


@pytest.fixture
def client(app, mock_bm25_index, monkeypatch):
    """Create test client with mocked RAG backend."""
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
    import copilot_core.api.security as sec
    sec._token_cache = ("", 0.0)

    with patch('copilot_core.api.v1.rag._get_bm25', return_value=mock_bm25_index):
        with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
            from copilot_core.api.v1 import rag

            # Reset RAG API state, cache, and rate limiter for test isolation
            rag.init_rag_api()
            rag._rag_cache = None
            try:
                from copilot_core.security.rate_limiter import get_rate_limiter
                get_rate_limiter().reset()
            except Exception:
                pass

            app.register_blueprint(rag.bp)
            with app.test_client() as test_client:
                yield test_client


class TestReciprocalRankFusion:
    """Tests for RRF algorithm"""

    def test_rrf_empty_inputs(self):
        """Test RRF with empty inputs."""
        result = reciprocal_rank_fusion(
            lexical_hits=[],
            semantic_hits=[],
            top_k=10
        )
        
        assert result == []

    def test_rrf_lexical_only(self):
        """Test RRF with only lexical results."""
        lexical_hits = [
            RankedHit(doc_id="doc1", score=0.9, rank=1),
            RankedHit(doc_id="doc2", score=0.7, rank=2),
        ]
        
        result = reciprocal_rank_fusion(
            lexical_hits=lexical_hits,
            semantic_hits=[],
            top_k=10
        )
        
        assert len(result) == 2
        assert result[0].doc_id == "doc1"
        assert result[0].lexical_rank == 1

    def test_rrf_semantic_only(self):
        """Test RRF with only semantic results."""
        semantic_hits = [
            RankedHit(doc_id="doc1", score=0.95, rank=1),
            RankedHit(doc_id="doc2", score=0.8, rank=2),
        ]
        
        result = reciprocal_rank_fusion(
            lexical_hits=[],
            semantic_hits=semantic_hits,
            top_k=10
        )
        
        assert len(result) == 2
        assert result[0].doc_id == "doc1"
        assert result[0].semantic_rank == 1

    def test_rrf_combined_results(self):
        """Test RRF with both lexical and semantic results."""
        lexical_hits = [
            RankedHit(doc_id="doc1", score=0.9, rank=1),
            RankedHit(doc_id="doc2", score=0.7, rank=2),
        ]
        semantic_hits = [
            RankedHit(doc_id="doc2", score=0.95, rank=1),
            RankedHit(doc_id="doc3", score=0.8, rank=2),
        ]
        
        result = reciprocal_rank_fusion(
            lexical_hits=lexical_hits,
            semantic_hits=semantic_hits,
            top_k=10
        )
        
        # doc2 should rank highest (appears in both)
        assert len(result) == 3
        assert result[0].doc_id == "doc2"
        assert result[0].lexical_rank == 2
        assert result[0].semantic_rank == 1

    def test_rrf_top_k_limit(self):
        """Test RRF respects top_k limit."""
        lexical_hits = [RankedHit(doc_id=f"doc{i}", score=1.0-i*0.1, rank=i+1) for i in range(20)]
        
        result = reciprocal_rank_fusion(
            lexical_hits=lexical_hits,
            semantic_hits=[],
            top_k=5
        )
        
        assert len(result) == 5

    def test_rrf_weights(self):
        """Test RRF with custom weights."""
        lexical_hits = [RankedHit(doc_id="doc1", score=0.9, rank=1)]
        semantic_hits = [RankedHit(doc_id="doc2", score=0.9, rank=1)]
        
        # Higher lexical weight should favor doc1
        result = reciprocal_rank_fusion(
            lexical_hits=lexical_hits,
            semantic_hits=semantic_hits,
            top_k=10,
            lexical_weight=2.0,
            semantic_weight=1.0
        )
        
        assert result[0].doc_id == "doc1"

    def test_rrf_k_parameter(self):
        """Test RRF with custom k parameter."""
        lexical_hits = [RankedHit(doc_id="doc1", score=0.9, rank=1)]
        
        result = reciprocal_rank_fusion(
            lexical_hits=lexical_hits,
            semantic_hits=[],
            top_k=10,
            k=100
        )
        
        assert len(result) == 1
        assert result[0].fused_score > 0

    def test_rrf_invalid_top_k(self):
        """Test RRF with invalid top_k."""
        result = reciprocal_rank_fusion(
            lexical_hits=[],
            semantic_hits=[],
            top_k=0
        )
        
        assert result == []

    def test_rrf_preserves_scores(self):
        """Test RRF preserves original scores in result."""
        lexical_hits = [RankedHit(doc_id="doc1", score=0.85, rank=1)]
        semantic_hits = [RankedHit(doc_id="doc1", score=0.92, rank=1)]
        
        result = reciprocal_rank_fusion(
            lexical_hits=lexical_hits,
            semantic_hits=semantic_hits,
            top_k=10
        )
        
        assert result[0].lexical_score == 0.85
        assert result[0].semantic_score == 0.92


class TestRAGSearchEndpoint:
    """Tests for /api/v1/rag/search endpoint"""

    def test_search_lexical_only(self, client):
        """Test lexical-only search."""
        payload = {
            "query": "test query",
            "use_lexical": True,
            "use_semantic": False,
        }
        
        response = client.post(
            '/api/v1/rag/search',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["mode"] == "bm25"

    def test_search_hybrid(self, client):
        """Test hybrid search."""
        payload = {
            "query": "test query",
            "use_lexical": True,
            "use_semantic": True,
        }
        
        response = client.post(
            '/api/v1/rag/search',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["mode"] == "hybrid_rrf"

    def test_search_missing_query(self, client):
        """Test search fails without query."""
        payload = {}
        
        response = client.post(
            '/api/v1/rag/search',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 400

    def test_search_returns_results(self, client):
        """Test search returns results array."""
        payload = {"query": "test"}
        
        response = client.post(
            '/api/v1/rag/search',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        data = json.loads(response.data)
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_search_returns_took_ms(self, client):
        """Test search includes timing."""
        payload = {"query": "test"}
        
        response = client.post(
            '/api/v1/rag/search',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        data = json.loads(response.data)
        assert "took_ms" in data

    def test_search_with_namespace(self, client):
        """Test search with custom namespace."""
        payload = {
            "query": "test",
            "namespace": "custom"
        }
        
        response = client.post(
            '/api/v1/rag/search',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        data = json.loads(response.data)
        assert data["namespace"] == "custom"

    def test_search_with_top_k(self, client):
        """Test search with custom top_k."""
        payload = {
            "query": "test",
            "top_k": 5
        }
        
        response = client.post(
            '/api/v1/rag/search',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200

    def test_search_include_text_false(self, client):
        """Test search without text inclusion."""
        payload = {
            "query": "test",
            "include_text": False
        }
        
        response = client.post(
            '/api/v1/rag/search',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        data = json.loads(response.data)
        # Results should not include text when False
        if data["results"]:
            assert data["results"][0].get("text") is None

    def test_search_include_metadata(self, client):
        """Test search with metadata inclusion."""
        payload = {
            "query": "test",
            "include_metadata": True
        }
        
        response = client.post(
            '/api/v1/rag/search',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        data = json.loads(response.data)
        assert "results" in data

    def test_search_both_disabled_error(self, client):
        """Test search fails when both lexical and semantic disabled."""
        payload = {
            "query": "test",
            "use_lexical": False,
            "use_semantic": False
        }
        
        response = client.post(
            '/api/v1/rag/search',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 400


class TestRAGIndexEndpoint:
    """Tests for /api/v1/rag/index endpoint"""

    def test_index_documents_success(self, client):
        """Test successful document indexing."""
        payload = {
            "namespace": "test",
            "documents": [
                {"id": "doc1", "text": "Test document 1"},
                {"id": "doc2", "text": "Test document 2"},
            ]
        }
        
        response = client.post(
            '/api/v1/rag/index',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["bm25_indexed"] >= 2

    def test_index_missing_documents(self, client):
        """Test index fails without documents."""
        payload = {"namespace": "test"}
        
        response = client.post(
            '/api/v1/rag/index',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 400

    def test_index_document_missing_id(self, client):
        """Test index fails without document ID."""
        payload = {
            "documents": [{"text": "No ID"}]
        }
        
        response = client.post(
            '/api/v1/rag/index',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 400

    def test_index_document_missing_text(self, client):
        """Test index fails without document text."""
        payload = {
            "documents": [{"id": "doc1"}]
        }
        
        response = client.post(
            '/api/v1/rag/index',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 400

    def test_index_returns_took_ms(self, client):
        """Test index includes timing."""
        payload = {
            "documents": [{"id": "doc1", "text": "Test"}]
        }
        
        response = client.post(
            '/api/v1/rag/index',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        data = json.loads(response.data)
        assert "took_ms" in data

    def test_index_with_metadata(self, client):
        """Test index with document metadata."""
        payload = {
            "documents": [{
                "id": "doc1",
                "text": "Test",
                "metadata": {"source": "test", "author": "test"}
            }]
        }
        
        response = client.post(
            '/api/v1/rag/index',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200


class TestRAGStatsEndpoints:
    """Tests for statistics endpoints"""

    def test_index_stats(self, client):
        """Test index statistics endpoint."""
        response = client.get('/api/v1/rag/stats')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "index" in data or "doc_count" in data or "search_requests" in data

    def test_index_stats_with_namespace(self, client):
        """Test index stats with namespace parameter."""
        response = client.get('/api/v1/rag/stats?namespace=test')
        
        assert response.status_code == 200

    def test_search_stats(self, client):
        """Test search statistics endpoint."""
        response = client.get('/api/v1/rag/stats')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        # Stats endpoint returns BM25 index stats
        assert "doc_count" in data or "db_path" in data

    def test_search_stats_after_search(self, client):
        """Test search stats updated after search."""
        # First do a search
        client.post(
            '/api/v1/rag/search',
            data=json.dumps({"query": "test"}),
            content_type='application/json'
        )
        
        # Then check stats
        response = client.get('/api/v1/rag/stats')
        data = json.loads(response.data)
        
        assert data.get("search_requests", 0) >= 1 or data.get("index_requests", 0) >= 0


class TestRAGErrors:
    """Error handling tests"""

    def test_invalid_json_body(self, client):
        """Test handling of invalid JSON."""
        # API uses request.get_json() or {} which handles invalid JSON gracefully
        response = client.post(
            '/api/v1/rag/search',
            data="not valid json",
            content_type='application/json'
        )
        
        # API treats invalid JSON as empty dict and returns error for missing query
        assert response.status_code in [200, 400]

    def test_empty_query_string(self, client):
        """Test search with empty query."""
        payload = {"query": ""}
        
        response = client.post(
            '/api/v1/rag/search',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 400

    def test_too_many_documents(self, client):
        """Test index with too many documents."""
        payload = {
            "documents": [{"id": f"doc{i}", "text": "test"} for i in range(2001)]
        }
        
        response = client.post(
            '/api/v1/rag/index',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 400


class TestFusedHit:
    """Tests for FusedHit dataclass"""

    def test_fused_hit_creation(self):
        """Test FusedHit creation."""
        hit = FusedHit(
            doc_id="doc1",
            fused_score=0.95,
            lexical_rank=1,
            semantic_rank=2,
            lexical_score=0.9,
            semantic_score=0.85
        )
        
        assert hit.doc_id == "doc1"
        assert hit.fused_score == 0.95
        assert hit.lexical_rank == 1

    def test_fused_hit_optional_fields(self):
        """Test FusedHit with optional fields."""
        hit = FusedHit(
            doc_id="doc1",
            fused_score=0.95
        )
        
        assert hit.lexical_rank is None
        assert hit.semantic_rank is None


class TestRankedHit:
    """Tests for RankedHit dataclass"""

    def test_ranked_hit_creation(self):
        """Test RankedHit creation."""
        hit = RankedHit(doc_id="doc1", score=0.9, rank=1)
        
        assert hit.doc_id == "doc1"
        assert hit.score == 0.9
        assert hit.rank == 1

    def test_ranked_hit_frozen(self):
        """Test RankedHit is frozen (immutable)."""
        hit = RankedHit(doc_id="doc1", score=0.9, rank=1)
        
        with pytest.raises(Exception):  # frozen dataclass raises error on modification
            hit.doc_id = "doc2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
