"""RAG Resilience 307 — CORE RAG degraded fallback contract.

Verifies that semantic retrieval degradation is explicit and machine-checkable
on the existing Core RAG search seam without widening the API family.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

import uuid
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
from flask import Flask
from copilot_core.api.v1.rag import bp as rag_bp
from copilot_core.rag import BM25Hit, RankedHit


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


# ── Degraded truth helpers ─────────────────────────────────────────────────────

def _assert_degraded(response_json: dict, expected_reason: str) -> None:
    assert response_json.get("degraded") is True, \
        f"expected degraded=True, got {response_json.get('degraded')}"
    assert response_json.get("degraded_reason") == expected_reason, \
        f"expected degraded_reason={expected_reason!r}, got {response_json.get('degraded_reason')!r}"
    assert "effective_mode" in response_json


def _assert_not_degraded(response_json: dict) -> None:
    val = response_json.get("degraded")
    assert val is False or val is None, \
        f"expected degraded=False/None, got {val}"


# ── Semantic backend unavailable ───────────────────────────────────────────────

class TestSemanticBackendUnavailable:
    """When semantic backend is not configured, hybrid returns BM25 with explicit degraded truth."""

    def test_hybrid_search_without_semantic_backend_is_degraded(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = []
                    r = app.test_client().post(
                        "/api/v1/rag/search",
                        json={"query": "test query", "use_lexical": True, "use_semantic": True}
                    )
                    d = r.get_json()
                    _assert_degraded(d, "semantic_backend_unavailable")

    def test_semantic_only_without_backend_is_degraded(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = []
                    r = app.test_client().post(
                        "/api/v1/rag/search",
                        json={"query": "test query", "use_lexical": False, "use_semantic": True}
                    )
                    d = r.get_json()
                    _assert_degraded(d, "semantic_backend_unavailable")

    def test_degraded_does_not_widen_to_undocumented_mode(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = []
                    r = app.test_client().post(
                        "/api/v1/rag/search",
                        json={"query": "test query", "use_lexical": True, "use_semantic": True}
                    )
                    d = r.get_json()
                    assert d.get("effective_mode") in ("bm25", "hybrid_rrf"), \
                        f"effective_mode={d.get('effective_mode')} not documented"


# ── Semantic backend exception ───────────────────────────────────────────────────

class TestSemanticBackendFailed:
    """When semantic backend raises, hybrid falls back to BM25 with explicit degraded truth."""

    def test_semantic_exception_causes_degraded(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend') as mock_load:
                mock_backend = MagicMock()
                mock_backend.search_fn.side_effect = RuntimeError("vector store unreachable")
                mock_load.return_value = mock_backend
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = []
                    r = app.test_client().post(
                        "/api/v1/rag/search",
                        json={"query": "test query", "use_lexical": True, "use_semantic": True}
                    )
                    d = r.get_json()
                    _assert_degraded(d, "semantic_backend_failed")

    def test_degraded_with_results_still_returned(self):
        app = _make_app()
        token = str(uuid.uuid4())[:8]
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend') as mock_load:
                mock_backend = MagicMock()
                mock_backend.search_fn.side_effect = RuntimeError("vector store down")
                mock_load.return_value = mock_backend
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = [
                        BM25Hit(doc_id=f"doc-{token}-1", score=1.5, rank=1),
                        BM25Hit(doc_id=f"doc-{token}-2", score=0.8, rank=2),
                    ]
                    with patch('copilot_core.api.v1.rag._enrich_results', return_value={}):
                        r = app.test_client().post(
                            "/api/v1/rag/search",
                            json={"query": "test query", "use_lexical": True, "use_semantic": True}
                        )
                        d = r.get_json()
                        _assert_degraded(d, "semantic_backend_failed")
                        assert d.get("result_count", 0) > 0, \
                            "degraded mode must still return BM25 results"

    def test_warning_still_appended_for_human_diagnosis(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend') as mock_load:
                mock_backend = MagicMock()
                mock_backend.search_fn.side_effect = RuntimeError("connection refused")
                mock_load.return_value = mock_backend
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = []
                    r = app.test_client().post(
                        "/api/v1/rag/search",
                        json={"query": "test query", "use_semantic": True, "use_lexical": True}
                    )
                    d = r.get_json()
                    _assert_degraded(d, "semantic_backend_failed")
                    warning_texts = [w.lower() for w in d.get("warnings", [])]
                    assert any("semantic" in w for w in warning_texts), \
                        f"expected semantic warning for humans, got {d.get('warnings')}"


# ── Healthy hybrid remains non-degraded ─────────────────────────────────────

class TestHealthyHybrid:
    """When semantic backend is healthy, hybrid search must not be marked degraded."""

    def test_healthy_hybrid_is_not_degraded(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend') as mock_load:
                mock_backend = MagicMock()
                mock_backend.search_fn.return_value = [{"id": "sem-doc-1", "score": 0.95}]
                mock_load.return_value = mock_backend
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = [
                        RankedHit(doc_id="bm25-doc-1", score=1.2, rank=1),
                    ]
                    with patch('copilot_core.api.v1.rag._enrich_results', return_value={}):
                        r = app.test_client().post(
                            "/api/v1/rag/search",
                            json={"query": "test query", "use_lexical": True, "use_semantic": True}
                        )
                        d = r.get_json()
                        _assert_not_degraded(d)
                        assert d.get("effective_mode") == "hybrid_rrf"

    def test_bm25_only_never_degraded(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.search.return_value = [
                    BM25Hit(doc_id="doc-1", score=1.0, rank=1),
                ]
                with patch('copilot_core.api.v1.rag._enrich_results', return_value={}):
                    r = app.test_client().post(
                        "/api/v1/rag/search",
                        json={"query": "test query", "use_lexical": True, "use_semantic": False}
                    )
                    d = r.get_json()
                    _assert_not_degraded(d)
                    assert d.get("effective_mode") == "bm25"


# ── Semantic-only stays bounded ─────────────────────────────────────────────

class TestSemanticOnlyStaysBounded:
    """Semantic-only requests must not silently widen into a different contract."""

    def test_semantic_only_mode_is_preserved(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend') as mock_load:
                mock_backend = MagicMock()
                mock_backend.search_fn.return_value = [{"id": "sdoc-1", "score": 0.9}]
                mock_load.return_value = mock_backend
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = [
                        RankedHit(doc_id="sdoc-1", score=0.9, rank=1),
                    ]
                    with patch('copilot_core.api.v1.rag._enrich_results', return_value={}):
                        r = app.test_client().post(
                            "/api/v1/rag/search",
                            json={"query": "test query", "use_lexical": False, "use_semantic": True}
                        )
                        d = r.get_json()
                        assert d.get("mode") == "semantic", \
                            f"mode must be 'semantic', got {d.get('mode')}"
                        assert d.get("effective_mode") == "semantic", \
                            f"effective_mode must be 'semantic', got {d.get('effective_mode')}"

    def test_semantic_only_with_backend_exception_degrades_honestly(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend') as mock_load:
                mock_backend = MagicMock()
                mock_backend.search_fn.side_effect = RuntimeError("timeout")
                mock_load.return_value = mock_backend
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = []
                    r = app.test_client().post(
                        "/api/v1/rag/search",
                        json={"query": "test query", "use_lexical": False, "use_semantic": True}
                    )
                    d = r.get_json()
                    _assert_degraded(d, "semantic_backend_failed")
                    assert d.get("effective_mode") == "semantic", \
                        "effective_mode must stay 'semantic' even when degraded"


# ── No new endpoint family ─────────────────────────────────────────────────

class TestNoNewEndpointFamily:
    def test_rag_search_endpoint_exists(self):
        """The /api/v1/rag/search endpoint must exist."""
        app = _make_app()
        rules = {rule.rule for rule in app.url_map.iter_rules() if "/rag/" in rule.rule}
        assert "/api/v1/rag/search" in rules, \
            f"/api/v1/rag/search not found in {rules}"
