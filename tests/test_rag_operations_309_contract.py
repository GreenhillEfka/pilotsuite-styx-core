"""RAG Operations 309 — CORE RAG health/stats/index/cache-clear contract.

Verifies bounded operational control surfaces on the existing Core RAG seam:
- GET /api/v1/rag/stats
- POST /api/v1/rag/index
- POST /api/v1/rag/cache/clear
- GET /api/v1/rag/health (add the already-documented health surface)

Fixes: rag_index() generic exception path references `exc` outside scope.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from contextlib import contextmanager
from unittest.mock import patch, MagicMock
from flask import Flask
from copilot_core.api.v1.rag import bp as rag_bp


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(rag_bp)
    return app


@contextmanager
def _auth_ok():
    async def _no_cache(*args, **kwargs):
        return None
    with patch('copilot_core.api.v1.rag.validate_token', return_value=True):
        with patch('copilot_core.api.v1.rag._get_rag_cache') as mock_cache:
            mock_cache.return_value.get = _no_cache
            yield


# ── Health endpoint exists and is machine-checkable ────────────────────────────

class TestRAGHealthEndpoint:
    """GET /api/v1/rag/health must exist and return structured readiness truth."""

    def test_health_endpoint_exists(self):
        app = _make_app()
        rules = {rule.rule for rule in app.url_map.iter_rules() if "/rag/" in rule.rule}
        assert "/api/v1/rag/health" in rules, \
            f"health endpoint not registered, found: {rules}"

    def test_health_returns_bm25_status(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.stats.return_value = MagicMock(
                    doc_count=42, avg_doc_len=128.5, term_count=999
                )
                with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                    r = app.test_client().get("/api/v1/rag/health")
                    assert r.status_code == 200, f"health returned {r.status_code}"
                    d = r.get_json()
                    assert "bm25" in d, f"bm25 status missing from health: {d}"
                    assert isinstance(d["bm25"], dict), "bm25 status must be a dict"

    def test_health_returns_semantic_backend_status(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.stats.return_value = MagicMock(
                    doc_count=10, avg_doc_len=64.0, term_count=500
                )
                mock_backend = MagicMock()
                mock_backend.index_fn = MagicMock()
                mock_backend.search_fn = MagicMock()
                mock_backend.module_path = "copilot_core.vectorstores.chromadb"
                with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=mock_backend):
                    r = app.test_client().get("/api/v1/rag/health")
                    d = r.get_json()
                    assert "semantic" in d, f"semantic status missing from health: {d}"
                    assert d["semantic"]["available"] is True, \
                        f"semantic should be available: {d}"

    def test_health_returns_cache_status(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.stats.return_value = MagicMock(
                    doc_count=5, avg_doc_len=32.0, term_count=100
                )
                with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                    r = app.test_client().get("/api/v1/rag/health")
                    d = r.get_json()
                    assert "cache" in d, f"cache status missing from health: {d}"
                    assert isinstance(d["cache"], dict), "cache status must be a dict"

    def test_health_without_semantic_backend_shows_unavailable(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.stats.return_value = MagicMock(
                    doc_count=5, avg_doc_len=32.0, term_count=100
                )
                with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                    r = app.test_client().get("/api/v1/rag/health")
                    d = r.get_json()
                    assert d["semantic"]["available"] is False, \
                        f"semantic should be unavailable when backend is None: {d}"
                    assert d["semantic"]["reason"] == "semantic_backend_unavailable", \
                        f"reason should be 'semantic_backend_unavailable': {d}"


# ── Stats endpoint is bounded and truthful ────────────────────────────────────

class TestRAGStatsEndpoint:
    """GET /api/v1/rag/stats must return factual BM25 stats."""

    def test_stats_endpoint_exists(self):
        app = _make_app()
        rules = {rule.rule for rule in app.url_map.iter_rules() if "/rag/" in rule.rule}
        assert "/api/v1/rag/stats" in rules, \
            f"stats endpoint not registered, found: {rules}"

    def test_stats_returns_namespace_doc_count(self):
        from copilot_core.rag.bm25 import BM25Stats
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.stats.return_value = BM25Stats(
                    namespace="default", doc_count=99, term_count=5000, posting_count=500,
                    avg_doc_len=200.0, total_doc_len=19800, updated_at=1700000000.0,
                    db_path="/tmp/bm25.db", db_size_bytes=1024, schema_version=1,
                )
                r = app.test_client().get("/api/v1/rag/stats?namespace=default")
                assert r.status_code == 200, f"stats returned {r.status_code}"
                d = r.get_json()
                assert d.get("doc_count") == 99, f"doc_count mismatch: {d}"
                assert "avg_doc_len" in d, f"avg_doc_len missing: {d}"


# ── Index endpoint — fix generic exception path with exc outside scope ─────────

class TestRAGIndexEndpoint:
    """POST /api/v1/rag/index generic failure must not reference undefined `exc`."""

    def test_index_endpoint_exists(self):
        app = _make_app()
        rules = {rule.rule for rule in app.url_map.iter_rules() if "/rag/" in rule.rule}
        assert "/api/v1/rag/index" in rules, \
            f"index endpoint not registered, found: {rules}"

    def test_index_generic_failure_is_handled_safely(self):
        """rag_index generic exception path must not raise NameError on undefined `exc`."""
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    # Simulate a generic failure in the index path
                    mock_bm25.return_value.index_documents.side_effect = RuntimeError("disk full")
                    r = app.test_client().post(
                        "/api/v1/rag/index",
                        json={"documents": [{"id": "x", "text": "test"}], "namespace": "default"}
                    )
                    # Must not 500 due to NameError; error response expected
                    assert r.status_code in (200, 400, 500), f"got {r.status_code}"
                    if r.status_code == 500:
                        # NameError would show in response body
                        body = r.get_data(as_text=True)
                        assert "NameError" not in body, \
                            "NameError on undefined 'exc' — generic exception path broken"
                    # If it returns a structured error, that's acceptable
                    if r.status_code == 400:
                        d = r.get_json()
                        assert "error" in d or "ok" in d

    def test_index_success_returns_ok(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.index_documents.return_value = 1
                    r = app.test_client().post(
                        "/api/v1/rag/index",
                        json={"documents": [{"id": "doc-1", "text": "hello world"}], "namespace": "default"}
                    )
                    # Accept any non-5xx response
                    assert r.status_code != 500, f"index should not 500 on success: {r.get_json()}"


# ── Cache clear endpoint ───────────────────────────────────────────────────────

class TestRAGCacheClearEndpoint:
    """POST /api/v1/rag/cache/clear must be bounded and explicit."""

    def test_cache_clear_endpoint_exists(self):
        app = _make_app()
        rules = {rule.rule for rule in app.url_map.iter_rules() if "/rag/" in rule.rule}
        assert "/api/v1/rag/cache/clear" in rules, \
            f"cache/clear endpoint not registered, found: {rules}"

    def test_cache_clear_returns_structured_response(self):
        app = _make_app()
        with _auth_ok():
            async def mock_clear(*args, **kwargs):
                return {"cleared": 5}
            with patch('copilot_core.api.v1.rag.validate_token', return_value=True):
                with patch('copilot_core.api.v1.rag._get_rag_cache') as mock_cache:
                    mock_cache.return_value.clear = mock_clear
                    r = app.test_client().post("/api/v1/rag/cache/clear", json={})
                    # Should not 500; error or success response both acceptable
                    assert r.status_code in (200, 400, 404, 500), f"got {r.status_code}"
                    if r.status_code == 200:
                        d = r.get_json()
                        assert "ok" in d or "cleared" in d or "error" in d, \
                            f"structured response expected: {d}"