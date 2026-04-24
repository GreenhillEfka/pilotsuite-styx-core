"""RAG Multi Query 310 — bounded multi-query route contract.

Covers:
- route existence
- validation on malformed / oversized payloads
- bounded success behavior on the existing RAG family
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1.rag import bp as rag_bp
from copilot_core.rag import BM25Hit


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


class TestRAGMultiQueryRoute:
    def test_route_exists(self):
        app = _make_app()
        rules = {rule.rule for rule in app.url_map.iter_rules() if "/rag/" in rule.rule}
        assert "/api/v1/rag/search/multi" in rules


class TestRAGMultiQueryValidation:
    def test_queries_must_be_list(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post(
                "/api/v1/rag/search/multi",
                json={"queries": "not-a-list", "top_k": 3},
            )
            assert r.status_code == 400
            assert "queries must be a list" in r.get_json()["error"]

    def test_queries_must_not_be_blank(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post(
                "/api/v1/rag/search/multi",
                json={"queries": ["alpha", "   ", "beta"], "top_k": 3},
            )
            assert r.status_code == 400
            assert "queries must not contain blank values" in r.get_json()["error"]

    def test_queries_reject_oversized_lists(self):
        app = _make_app()
        too_many = [f"q{i}" for i in range(6)]
        with _auth_ok():
            r = app.test_client().post(
                "/api/v1/rag/search/multi",
                json={"queries": too_many, "top_k": 3},
            )
            assert r.status_code == 400
            assert "queries must contain between 1 and 5 items" in r.get_json()["error"]

    def test_requires_one_search_mode(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post(
                "/api/v1/rag/search/multi",
                json={
                    "queries": ["alpha", "beta"],
                    "use_lexical": False,
                    "use_semantic": False,
                },
            )
            assert r.status_code == 400
            assert "at least one of use_lexical/use_semantic must be true" in r.get_json()["error"]


class TestRAGMultiQuerySuccess:
    def test_bm25_multi_query_returns_bounded_results(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.side_effect = [
                        [BM25Hit(doc_id="doc-a", score=2.0, rank=1), BM25Hit(doc_id="doc-b", score=1.0, rank=2)],
                        [BM25Hit(doc_id="doc-a", score=1.5, rank=1), BM25Hit(doc_id="doc-c", score=1.0, rank=2)],
                    ]
                    mock_bm25.return_value.get_documents.return_value = {
                        "doc-a": {"text": "A", "metadata": {"kind": "x"}},
                        "doc-b": {"text": "B", "metadata": {"kind": "y"}},
                        "doc-c": {"text": "C", "metadata": {"kind": "z"}},
                    }

                    r = app.test_client().post(
                        "/api/v1/rag/search/multi",
                        json={
                            "queries": ["alpha", "beta"],
                            "top_k": 2,
                            "use_lexical": True,
                            "use_semantic": False,
                        },
                    )
                    assert r.status_code == 200, r.get_data(as_text=True)
                    d = r.get_json()
                    assert d["mode"] == "multi_bm25"
                    assert d["effective_mode"] == "multi_bm25"
                    assert d["query_count"] == 2
                    assert d["result_count"] <= 2
                    assert len(d["results"]) <= 2
                    assert d["results"][0]["id"] == "doc-a"
                    assert d["results"][0]["query_match_count"] == 2
                    assert d["results"][0]["matched_queries"] == ["alpha", "beta"]

    def test_duplicate_queries_are_deduped(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = [BM25Hit(doc_id="doc-a", score=1.0, rank=1)]
                    mock_bm25.return_value.get_documents.return_value = {
                        "doc-a": {"text": "A", "metadata": {}}
                    }
                    r = app.test_client().post(
                        "/api/v1/rag/search/multi",
                        json={"queries": ["alpha", "alpha", " alpha "], "top_k": 3},
                    )
                    assert r.status_code == 200
                    d = r.get_json()
                    assert d["queries"] == ["alpha"]
                    assert d["query_count"] == 1

    def test_semantic_degradation_stays_machine_checkable(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.search.return_value = [BM25Hit(doc_id="doc-a", score=1.0, rank=1)]
                mock_bm25.return_value.get_documents.return_value = {
                    "doc-a": {"text": "A", "metadata": {}}
                }
                with patch('copilot_core.api.v1.rag._semantic_search') as mock_semantic:
                    class Outcome:
                        hits = []
                        degraded = True
                        degraded_reason = "semantic_backend_unavailable"
                    mock_semantic.return_value = Outcome()
                    r = app.test_client().post(
                        "/api/v1/rag/search/multi",
                        json={
                            "queries": ["alpha", "beta"],
                            "use_lexical": True,
                            "use_semantic": True,
                            "top_k": 3,
                        },
                    )
                    assert r.status_code == 200
                    d = r.get_json()
                    assert d["degraded"] is True
                    assert d["degraded_reason"] == "semantic_backend_unavailable"
                    assert d["effective_mode"] == "multi_bm25"
