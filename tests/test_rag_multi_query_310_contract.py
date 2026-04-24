"""RAG Multi Query 310 — CORE RAG /search/multi contract.

Verifies the already-documented multi-query search seam is real, bounded,
and fused through the existing Core RAG helpers only.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from contextlib import contextmanager
from unittest.mock import patch

from flask import Flask

from copilot_core.api.v1.rag import bp as rag_bp
from copilot_core.api.v1.rag import _SemanticSearchOutcome
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


class TestRAGMultiQueryEndpoint:
    """POST /api/v1/rag/search/multi must exist and stay bounded."""

    def test_multi_query_endpoint_exists(self):
        app = _make_app()
        rules = {rule.rule for rule in app.url_map.iter_rules() if "/rag/" in rule.rule}
        assert "/api/v1/rag/search/multi" in rules, \
            f"/api/v1/rag/search/multi not found in {rules}"

    def test_multi_query_requires_query_list(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post("/api/v1/rag/search/multi", json={})
            assert r.status_code == 400, f"expected 400, got {r.status_code}"
            d = r.get_json()
            assert d["error"] == "queries must be a list"

    def test_multi_query_rejects_oversized_query_list(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post(
                "/api/v1/rag/search/multi",
                json={"queries": ["q1", "q2", "q3", "q4", "q5", "q6"]},
            )
            assert r.status_code == 400, f"expected 400, got {r.status_code}"
            d = r.get_json()
            assert "between 1 and 5" in d["error"], f"unexpected error: {d}"

    def test_multi_query_rejects_blank_values(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post(
                "/api/v1/rag/search/multi",
                json={"queries": ["living room", "   "]},
            )
            assert r.status_code == 400, f"expected 400, got {r.status_code}"
            d = r.get_json()
            assert d["error"] == "queries must not contain blank values"

    def test_multi_query_returns_fused_bounded_results(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.search.side_effect = [
                    [
                        BM25Hit(doc_id="doc-1", score=1.0, rank=1),
                        BM25Hit(doc_id="doc-2", score=0.5, rank=2),
                    ],
                    [
                        BM25Hit(doc_id="doc-1", score=0.8, rank=1),
                    ],
                ]
                with patch('copilot_core.api.v1.rag._semantic_search') as mock_semantic:
                    mock_semantic.side_effect = [
                        _SemanticSearchOutcome(
                            hits=[RankedHit(doc_id="doc-2", score=0.9, rank=1)]
                        ),
                        _SemanticSearchOutcome(
                            hits=[RankedHit(doc_id="doc-1", score=0.95, rank=1)]
                        ),
                    ]
                    with patch('copilot_core.api.v1.rag._enrich_results', return_value={
                        "doc-1": {"text": "alpha", "metadata": {"room": "living"}},
                        "doc-2": {"text": "beta", "metadata": {"room": "living"}},
                    }):
                        r = app.test_client().post(
                            "/api/v1/rag/search/multi",
                            json={
                                "namespace": "default",
                                "queries": ["living room lights", "lighting living room"],
                                "top_k": 2,
                            },
                        )

        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.get_data(as_text=True)}"
        d = r.get_json()
        assert d["mode"] == "multi_hybrid_rrf", f"unexpected mode: {d}"
        assert d["query_count"] == 2, f"unexpected query_count: {d}"
        assert d["result_count"] == 2, f"unexpected result_count: {d}"
        assert d["results"][0]["id"] == "doc-1", f"unexpected rank order: {d['results']}"
        assert d["results"][0]["query_match_count"] == 2, f"missing query fusion truth: {d['results'][0]}"
        assert d["results"][0]["matched_queries"] == [
            "living room lights",
            "lighting living room",
        ], f"unexpected matched_queries: {d['results'][0]}"
        assert "fused_score" in d["results"][0], f"missing fused_score: {d['results'][0]}"

    def test_multi_query_degraded_truth_is_machine_checkable(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.search.side_effect = [
                    [BM25Hit(doc_id="doc-1", score=1.0, rank=1)],
                    [BM25Hit(doc_id="doc-1", score=1.0, rank=1)],
                ]
                with patch('copilot_core.api.v1.rag._semantic_search') as mock_semantic:
                    mock_semantic.side_effect = [
                        _SemanticSearchOutcome(
                            hits=[],
                            degraded=True,
                            degraded_reason="semantic_backend_unavailable",
                        ),
                        _SemanticSearchOutcome(
                            hits=[],
                            degraded=True,
                            degraded_reason="semantic_backend_unavailable",
                        ),
                    ]
                    with patch('copilot_core.api.v1.rag._enrich_results', return_value={"doc-1": {}}):
                        r = app.test_client().post(
                            "/api/v1/rag/search/multi",
                            json={"queries": ["one", "two"], "top_k": 1},
                        )

        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.get_data(as_text=True)}"
        d = r.get_json()
        assert d["degraded"] is True, f"expected degraded truth: {d}"
        assert d["degraded_reason"] == "semantic_backend_unavailable", f"unexpected degraded_reason: {d}"
        assert d["effective_mode"] == "multi_bm25", f"unexpected effective_mode: {d}"
