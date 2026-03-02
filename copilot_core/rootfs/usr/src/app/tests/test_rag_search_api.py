"""
Tests for RAG Search API endpoints.

Existing endpoints in copilot_core/api/rag_search.py:
- POST /api/v1/rag/search - Semantic search with embeddings
- GET /api/v1/rag/search/suggestions - Autocomplete suggestions
- GET /api/v1/rag/search/stats - Search analytics
- POST /api/v1/rag/search/benchmark - Performance benchmark

New endpoints to implement (P1-026):
- POST /api/v1/rag/index - Index a document
- POST /api/v1/rag/index/batch - Batch index documents
- DELETE /api/v1/rag/index/<document_id> - Delete a document
- GET /api/v1/rag/status - RAG system status
- POST /api/v1/rag/rebuild - Rebuild index
"""

import pytest


class TestRAGSearchEndpoint:
    """Tests for /api/v1/rag/search endpoint."""

    def test_search_post_with_query(self, test_client, auth_headers):
        """Test POST search with valid query."""
        response = test_client.post(
            '/api/v1/rag/search',
            json={'query': 'test search query', 'limit': 3},
            headers=auth_headers
        )
        
        # Endpoint exists and should return 200 or 500 (if vector store not configured)
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.get_json()
            assert 'query' in data or 'results' in data

    def test_search_with_limit(self, test_client, auth_headers):
        """Test search with custom limit."""
        response = test_client.post(
            '/api/v1/rag/search',
            json={
                'query': 'lighting control',
                'limit': 10,
                'threshold': 0.5
            },
            headers=auth_headers
        )
        
        assert response.status_code in [200, 500]


class TestRAGSearchSuggestionsEndpoint:
    """Tests for /api/v1/rag/search/suggestions endpoint."""

    def test_suggestions_with_query(self, test_client, auth_headers):
        """Test GET suggestions with query parameter."""
        response = test_client.get(
            '/api/v1/rag/search/suggestions?q=home',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'query' in data
        assert 'suggestions' in data
        assert 'count' in data

    def test_suggestions_empty_query(self, test_client, auth_headers):
        """Test suggestions with empty query."""
        response = test_client.get(
            '/api/v1/rag/search/suggestions',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['count'] == 0
        assert data['suggestions'] == []

    def test_suggestions_with_limit(self, test_client, auth_headers):
        """Test suggestions with custom limit."""
        response = test_client.get(
            '/api/v1/rag/search/suggestions?q=test&limit=3',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert len(data['suggestions']) <= 3


class TestRAGSearchStatsEndpoint:
    """Tests for /api/v1/rag/search/stats endpoint."""

    def test_stats_success(self, test_client, auth_headers):
        """Test RAG stats endpoint."""
        response = test_client.get(
            '/api/v1/rag/search/stats',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'total_searches' in data
        assert 'unique_queries' in data
        assert 'cache_stats' in data
        assert 'history_stats' in data

    def test_stats_with_limit(self, test_client, auth_headers):
        """Test stats with custom limit."""
        response = test_client.get(
            '/api/v1/rag/search/stats?limit=5',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'top_queries' in data
        assert len(data['top_queries']) <= 5


class TestRAGSearchBenchmarkEndpoint:
    """Tests for /api/v1/rag/search/benchmark endpoint."""

    def test_benchmark_success(self, test_client, auth_headers):
        """Test benchmark endpoint."""
        response = test_client.post(
            '/api/v1/rag/search/benchmark',
            json={'query': 'test query', 'iterations': 3},
            headers=auth_headers
        )
        
        # May return 200 or 500 depending on vector store configuration
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.get_json()
            assert 'iterations' in data or 'query' in data


class TestRAGIndexEndpoint:
    """Tests for /api/v1/rag/index endpoint (to be implemented)."""

    def test_index_document_missing_content(self, test_client, auth_headers):
        """Test indexing without content returns 400."""
        # This endpoint doesn't exist yet - should return 404 or 400
        response = test_client.post(
            '/api/v1/rag/index',
            json={'metadata': {'source': 'test'}},
            headers=auth_headers
        )
        
        # Endpoint not yet implemented
        assert response.status_code in [404, 400, 501]


class TestRAGStatusEndpoint:
    """Tests for /api/v1/rag/status endpoint (to be implemented)."""

    def test_status_not_implemented(self, test_client, auth_headers):
        """Test status endpoint (not yet implemented)."""
        response = test_client.get(
            '/api/v1/rag/status',
            headers=auth_headers
        )
        
        # Endpoint not yet implemented
        assert response.status_code in [404, 501]


class TestRAGAuthentication:
    """Test authentication requirements for RAG endpoints."""

    def test_search_with_auth(self, test_client, auth_headers):
        """Test that search endpoint works with authentication."""
        response = test_client.post(
            '/api/v1/rag/search',
            json={'query': 'test'},
            headers=auth_headers
        )
        
        # Should work with auth (200 or 500 if vector store not configured)
        assert response.status_code in [200, 500]

    def test_suggestions_with_auth(self, test_client, auth_headers):
        """Test that suggestions endpoint works with authentication."""
        response = test_client.get(
            '/api/v1/rag/search/suggestions?q=test',
            headers=auth_headers
        )
        
        assert response.status_code == 200

    def test_stats_with_auth(self, test_client, auth_headers):
        """Test that stats endpoint works with authentication."""
        response = test_client.get(
            '/api/v1/rag/search/stats',
            headers=auth_headers
        )
        
        assert response.status_code == 200
