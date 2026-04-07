"""Tests for RAG Hybrid Search API (Flask Blueprint).

Covers all 6 endpoints:
  POST /api/v1/rag/search          – Hybrid Search
  POST /api/v1/rag/search/bm25     – BM25-only
  POST /api/v1/rag/search/semantic  – Semantic-only
  POST /api/v1/rag/rerank          – RRF Reranking
  GET  /api/v1/rag/stats           – Index Stats
  POST /api/v1/rag/index           – Document Indexing
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from flask import Flask

@pytest.fixture(autouse=True)
def _disable_auth_for_rag_tests(monkeypatch):
    """Disable auth for RAG tests without polluting other test modules."""
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
    import copilot_core.api.security as sec
    sec._token_cache = ("", 0.0)


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset module-level singletons between tests."""
    import copilot_core.api.v1.rag as rag_mod
    rag_mod._bm25_index = None
    rag_mod._semantic_backend = None
    rag_mod._metrics = rag_mod._Metrics()
    rag_mod._rag_cache = None
    # Reset rate limiter to avoid cross-test rate limit pollution
    try:
        from copilot_core.security.rate_limiter import get_rate_limiter
        get_rate_limiter().reset()
    except Exception:
        pass
    yield


@pytest.fixture()
def app(tmp_path):
    """Create a minimal Flask app with the RAG blueprint registered."""
    db_path = str(tmp_path / "test_rag.sqlite3")
    with patch.dict(os.environ, {"COPILOT_CORE_RAG_DB_PATH": db_path}):
        # Re-import to pick up new env
        import importlib
        import copilot_core.api.v1.rag as rag_mod
        importlib.reload(rag_mod)
        rag_mod._bm25_index = None
        rag_mod._semantic_backend = None

        flask_app = Flask(__name__)
        flask_app.config["TESTING"] = True
        flask_app.register_blueprint(rag_mod.bp)
        yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


def _index_sample_docs(client, namespace: str = "default") -> Any:
    """Helper: index sample documents for search tests."""
    docs = [
        {"id": "doc1", "text": "Python is a great programming language", "metadata": {"lang": "en"}},
        {"id": "doc2", "text": "Flask is a Python web framework", "metadata": {"lang": "en"}},
        {"id": "doc3", "text": "Machine learning uses Python extensively", "metadata": {"topic": "ml"}},
        {"id": "doc4", "text": "JavaScript is used for frontend development"},
        {"id": "doc5", "text": "Home Assistant automates your smart home"},
    ]
    resp = client.post(
        "/api/v1/rag/index",
        json={"namespace": namespace, "documents": docs, "index_semantic": False},
    )
    return resp


# ── Endpoint 6: POST /api/v1/rag/index ────────────────────────────────────

class TestRagIndex:
    def test_index_documents_success(self, client):
        resp = _index_sample_docs(client)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["bm25_indexed"] == 5
        assert data["namespace"] == "default"
        assert isinstance(data["took_ms"], (int, float))

    def test_index_empty_documents_returns_400(self, client):
        resp = client.post("/api/v1/rag/index", json={"documents": []})
        assert resp.status_code == 400
        assert "documents required" in resp.get_json()["error"]

    def test_index_missing_doc_id_returns_400(self, client):
        resp = client.post(
            "/api/v1/rag/index",
            json={"documents": [{"text": "some text"}]},
        )
        assert resp.status_code == 400
        assert "id required" in resp.get_json()["error"]

    def test_index_missing_text_returns_400(self, client):
        resp = client.post(
            "/api/v1/rag/index",
            json={"documents": [{"id": "d1", "text": ""}]},
        )
        assert resp.status_code == 400
        assert "text required" in resp.get_json()["error"]

    def test_index_too_many_documents_returns_400(self, client):
        docs = [{"id": f"d{i}", "text": f"text {i}"} for i in range(2001)]
        resp = client.post("/api/v1/rag/index", json={"documents": docs})
        assert resp.status_code == 400
        assert "max" in resp.get_json()["error"].lower()

    def test_index_custom_namespace(self, client):
        resp = client.post(
            "/api/v1/rag/index",
            json={
                "namespace": "test_ns",
                "documents": [{"id": "d1", "text": "Hello world"}],
                "index_semantic": False,
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()["namespace"] == "test_ns"

    def test_index_with_metadata(self, client):
        resp = client.post(
            "/api/v1/rag/index",
            json={
                "documents": [{"id": "m1", "text": "metadata test", "metadata": {"key": "value"}}],
                "index_semantic": False,
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()["bm25_indexed"] == 1


# ── Endpoint 5: GET /api/v1/rag/stats ─────────────────────────────────────

class TestRagStats:
    def test_stats_empty_index(self, client):
        resp = client.get("/api/v1/rag/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["doc_count"] == 0
        assert data["namespace"] == "default"
        assert "metrics" in data

    def test_stats_after_indexing(self, client):
        _index_sample_docs(client)
        resp = client.get("/api/v1/rag/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["doc_count"] == 5
        assert data["term_count"] > 0

    def test_stats_custom_namespace(self, client):
        resp = client.get("/api/v1/rag/stats?namespace=nonexistent")
        assert resp.status_code == 200
        assert resp.get_json()["doc_count"] == 0

    def test_stats_includes_metrics(self, client):
        resp = client.get("/api/v1/rag/stats")
        data = resp.get_json()
        metrics = data["metrics"]
        assert "search_requests" in metrics
        assert "index_requests" in metrics
        assert "rerank_requests" in metrics
        assert "errors" in metrics


# ── Endpoint 1: POST /api/v1/rag/search (Hybrid) ──────────────────────────

class TestRagHybridSearch:
    def test_search_missing_query_returns_400(self, client):
        resp = client.post("/api/v1/rag/search", json={})
        assert resp.status_code == 400
        assert "query required" in resp.get_json()["error"]

    def test_search_bm25_only_mode(self, client):
        _index_sample_docs(client)
        resp = client.post(
            "/api/v1/rag/search",
            json={"query": "Python", "use_semantic": False},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["mode"] == "bm25"
        assert data["result_count"] > 0
        assert data["results"][0]["id"] in ("doc1", "doc2", "doc3")

    def test_search_hybrid_mode_fallback_to_bm25(self, client):
        """Without semantic backend, hybrid falls back to BM25-only results."""
        _index_sample_docs(client)
        resp = client.post(
            "/api/v1/rag/search",
            json={"query": "Python", "use_lexical": True, "use_semantic": True},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        # Mode is hybrid_rrf but results come only from BM25
        assert data["mode"] == "hybrid_rrf"

    def test_search_neither_mode_returns_400(self, client):
        resp = client.post(
            "/api/v1/rag/search",
            json={"query": "test", "use_lexical": False, "use_semantic": False},
        )
        assert resp.status_code == 400

    def test_search_includes_text_and_metadata(self, client):
        _index_sample_docs(client)
        resp = client.post(
            "/api/v1/rag/search",
            json={"query": "Python", "use_semantic": False, "include_text": True, "include_metadata": True},
        )
        data = resp.get_json()
        assert data["result_count"] > 0
        first = data["results"][0]
        assert "text" in first
        assert first["text"] is not None

    def test_search_excludes_text_when_disabled(self, client):
        _index_sample_docs(client)
        resp = client.post(
            "/api/v1/rag/search",
            json={"query": "Python", "use_semantic": False, "include_text": False, "include_metadata": False},
        )
        data = resp.get_json()
        first = data["results"][0]
        assert "text" not in first
        assert "metadata" not in first

    def test_search_top_k_limits_results(self, client):
        _index_sample_docs(client)
        resp = client.post(
            "/api/v1/rag/search",
            json={"query": "Python", "use_semantic": False, "top_k": 2},
        )
        data = resp.get_json()
        assert data["result_count"] <= 2

    def test_search_returns_took_ms(self, client):
        _index_sample_docs(client)
        resp = client.post(
            "/api/v1/rag/search",
            json={"query": "Python", "use_semantic": False},
        )
        data = resp.get_json()
        assert "took_ms" in data
        assert data["took_ms"] >= 0

    def test_search_no_results_for_unknown_term(self, client):
        _index_sample_docs(client)
        resp = client.post(
            "/api/v1/rag/search",
            json={"query": "xyznonexistent", "use_semantic": False},
        )
        data = resp.get_json()
        assert data["result_count"] == 0


# ── Endpoint 2: POST /api/v1/rag/search/bm25 ──────────────────────────────

class TestRagBM25Search:
    def test_bm25_search_basic(self, client):
        _index_sample_docs(client)
        resp = client.post("/api/v1/rag/search/bm25", json={"query": "Flask"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["mode"] == "bm25"
        assert data["result_count"] > 0
        assert data["results"][0]["id"] == "doc2"

    def test_bm25_search_missing_query(self, client):
        resp = client.post("/api/v1/rag/search/bm25", json={"query": ""})
        assert resp.status_code == 400

    def test_bm25_search_with_namespace(self, client):
        client.post(
            "/api/v1/rag/index",
            json={
                "namespace": "ns1",
                "documents": [{"id": "x1", "text": "unique namespace doc"}],
                "index_semantic": False,
            },
        )
        resp = client.post(
            "/api/v1/rag/search/bm25",
            json={"query": "unique", "namespace": "ns1"},
        )
        data = resp.get_json()
        assert data["result_count"] == 1
        assert data["results"][0]["id"] == "x1"

    def test_bm25_search_ranking_order(self, client):
        _index_sample_docs(client)
        resp = client.post(
            "/api/v1/rag/search/bm25",
            json={"query": "Python programming"},
        )
        data = resp.get_json()
        # doc1 has both "Python" and "programming" -> should rank highest
        assert data["results"][0]["id"] == "doc1"
        # Scores should be descending
        scores = [r["score"] for r in data["results"]]
        assert scores == sorted(scores, reverse=True)


# ── Endpoint 3: POST /api/v1/rag/search/semantic ──────────────────────────

class TestRagSemanticSearch:
    def test_semantic_search_no_backend(self, client):
        _index_sample_docs(client)
        resp = client.post(
            "/api/v1/rag/search/semantic",
            json={"query": "Python"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["mode"] == "semantic"
        assert data["result_count"] == 0

    def test_semantic_search_missing_query(self, client):
        resp = client.post("/api/v1/rag/search/semantic", json={})
        assert resp.status_code == 400


# ── Endpoint 4: POST /api/v1/rag/rerank ───────────────────────────────────

class TestRagRerank:
    def test_rerank_basic(self, client):
        resp = client.post(
            "/api/v1/rag/rerank",
            json={
                "lexical_hits": [
                    {"id": "a", "score": 5.0, "rank": 1},
                    {"id": "b", "score": 3.0, "rank": 2},
                    {"id": "c", "score": 1.0, "rank": 3},
                ],
                "semantic_hits": [
                    {"id": "b", "score": 0.9, "rank": 1},
                    {"id": "d", "score": 0.8, "rank": 2},
                    {"id": "a", "score": 0.7, "rank": 3},
                ],
                "top_k": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["result_count"] > 0
        # "a" and "b" appear in both lists -> should have highest fused scores
        ids = [r["id"] for r in data["results"]]
        assert "a" in ids
        assert "b" in ids

    def test_rerank_empty_lists_returns_400(self, client):
        resp = client.post(
            "/api/v1/rag/rerank",
            json={"lexical_hits": [], "semantic_hits": []},
        )
        assert resp.status_code == 400

    def test_rerank_single_list(self, client):
        resp = client.post(
            "/api/v1/rag/rerank",
            json={
                "lexical_hits": [
                    {"id": "x", "score": 1.0, "rank": 1},
                ],
                "semantic_hits": [],
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["result_count"] == 1
        assert data["results"][0]["id"] == "x"

    def test_rerank_respects_weights(self, client):
        resp = client.post(
            "/api/v1/rag/rerank",
            json={
                "lexical_hits": [
                    {"id": "a", "score": 5.0, "rank": 1},
                ],
                "semantic_hits": [
                    {"id": "b", "score": 0.9, "rank": 1},
                ],
                "lexical_weight": 2.0,
                "semantic_weight": 0.5,
                "top_k": 2,
            },
        )
        data = resp.get_json()
        # With higher lexical weight, "a" should score higher
        assert data["results"][0]["id"] == "a"

    def test_rerank_includes_fusion_metadata(self, client):
        resp = client.post(
            "/api/v1/rag/rerank",
            json={
                "lexical_hits": [{"id": "a", "score": 5.0, "rank": 1}],
                "semantic_hits": [{"id": "a", "score": 0.9, "rank": 1}],
                "top_k": 1,
            },
        )
        data = resp.get_json()
        result = data["results"][0]
        assert "fused_score" in result
        assert result["lexical_rank"] is not None
        assert result["semantic_rank"] is not None
        assert result["fused_score"] > 0

    def test_rerank_took_ms(self, client):
        resp = client.post(
            "/api/v1/rag/rerank",
            json={
                "lexical_hits": [{"id": "a", "score": 1.0, "rank": 1}],
                "semantic_hits": [],
            },
        )
        data = resp.get_json()
        assert "took_ms" in data
        assert data["took_ms"] >= 0


# ── Auth ────────────────────────────────────────────────────────────────

class TestRagAuth:
    def test_auth_required_when_enabled(self, tmp_path):
        """When auth is required, requests without token get 401."""
        db_path = str(tmp_path / "auth_test.sqlite3")

        with patch.dict(os.environ, {
            "COPILOT_AUTH_REQUIRED": "true",
            "COPILOT_AUTH_TOKEN": "secret-token-123",
            "COPILOT_CORE_RAG_DB_PATH": db_path,
        }):
            import importlib
            import copilot_core.api.v1.rag as rag_mod
            import copilot_core.api.security as sec_mod
            importlib.reload(sec_mod)
            importlib.reload(rag_mod)
            rag_mod._bm25_index = None

            flask_app = Flask(__name__)
            flask_app.config["TESTING"] = True
            flask_app.register_blueprint(rag_mod.bp)
            c = flask_app.test_client()

            # Reset security cache
            sec_mod._token_cache = ("", 0.0)

            resp = c.get("/api/v1/rag/stats")
            assert resp.status_code == 401

    def test_auth_passes_with_valid_token(self, tmp_path):
        db_path = str(tmp_path / "auth_pass.sqlite3")

        with patch.dict(os.environ, {
            "COPILOT_AUTH_REQUIRED": "true",
            "COPILOT_AUTH_TOKEN": "secret-token-123",
            "COPILOT_CORE_RAG_DB_PATH": db_path,
        }):
            import importlib
            import copilot_core.api.v1.rag as rag_mod
            import copilot_core.api.security as sec_mod
            importlib.reload(sec_mod)
            importlib.reload(rag_mod)
            rag_mod._bm25_index = None

            flask_app = Flask(__name__)
            flask_app.config["TESTING"] = True
            flask_app.register_blueprint(rag_mod.bp)
            c = flask_app.test_client()

            sec_mod._token_cache = ("", 0.0)

            resp = c.get(
                "/api/v1/rag/stats",
                headers={"X-Auth-Token": "secret-token-123"},
            )
            assert resp.status_code == 200


# ── Metrics ─────────────────────────────────────────────────────────────

class TestMetrics:
    def test_metrics_track_search_requests(self, client):
        _index_sample_docs(client)
        client.post("/api/v1/rag/search/bm25", json={"query": "Python"})
        client.post("/api/v1/rag/search/bm25", json={"query": "Flask"})

        resp = client.get("/api/v1/rag/stats")
        data = resp.get_json()
        # 2 BM25 searches
        assert data["metrics"]["search_requests"] == 2

    def test_metrics_track_index_requests(self, client):
        _index_sample_docs(client)
        resp = client.get("/api/v1/rag/stats")
        data = resp.get_json()
        assert data["metrics"]["index_requests"] == 1

    def test_metrics_track_rerank_requests(self, client):
        client.post(
            "/api/v1/rag/rerank",
            json={
                "lexical_hits": [{"id": "a", "score": 1.0, "rank": 1}],
                "semantic_hits": [],
            },
        )
        resp = client.get("/api/v1/rag/stats")
        data = resp.get_json()
        assert data["metrics"]["rerank_requests"] == 1


# ── Edge Cases ──────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_no_json_body_returns_400(self, client):
        resp = client.post("/api/v1/rag/search", data="not json", content_type="text/plain")
        assert resp.status_code == 400

    def test_upsert_updates_existing_doc(self, client):
        client.post(
            "/api/v1/rag/index",
            json={
                "documents": [{"id": "u1", "text": "original text"}],
                "index_semantic": False,
            },
        )
        client.post(
            "/api/v1/rag/index",
            json={
                "documents": [{"id": "u1", "text": "updated content with new terms"}],
                "index_semantic": False,
            },
        )
        resp = client.post("/api/v1/rag/search/bm25", json={"query": "updated"})
        data = resp.get_json()
        assert data["result_count"] == 1
        assert data["results"][0]["id"] == "u1"

    def test_large_top_k_clamped(self, client):
        _index_sample_docs(client)
        resp = client.post(
            "/api/v1/rag/search/bm25",
            json={"query": "Python", "top_k": 99999},
        )
        # Should succeed (clamped to _MAX_TOP_K)
        assert resp.status_code == 200
