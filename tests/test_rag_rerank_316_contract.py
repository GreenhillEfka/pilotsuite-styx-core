"""RAG Rerank 316 — focused contract coverage for /rerank."""
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


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(rag_bp)
    return app


@contextmanager
def _auth_ok():
    with patch("copilot_core.api.v1.rag.validate_token", return_value=True):
        yield


class TestRAGRerankRoute:
    def test_route_exists(self):
        app = _make_app()
        rules = {rule.rule for rule in app.url_map.iter_rules() if "/rag/" in rule.rule}
        assert "/api/v1/rag/rerank" in rules


class TestRAGRerankValidation:
    def test_rejects_empty_hit_lists(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post("/api/v1/rag/rerank", json={})
            assert r.status_code == 400
            assert r.get_json()["error"] == "at least one of lexical_hits/semantic_hits required"

    def test_rejects_non_list_hit_payloads(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post(
                "/api/v1/rag/rerank",
                json={"lexical_hits": {"id": "doc-1"}},
            )
            assert r.status_code == 400
            assert r.get_json()["error"] == "lexical_hits must be a list"

    def test_rejects_effectively_empty_hit_lists_after_parsing(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post(
                "/api/v1/rag/rerank",
                json={
                    "lexical_hits": [{"id": "   ", "score": 1.0, "rank": 1}],
                    "semantic_hits": [],
                },
            )
            assert r.status_code == 400
            assert r.get_json()["error"] == "at least one of lexical_hits/semantic_hits required"


class TestRAGRerankSuccess:
    def test_returns_bounded_fused_result_truth(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post(
                "/api/v1/rag/rerank",
                json={
                    "top_k": 2,
                    "lexical_hits": [
                        {"id": "doc-a", "score": 5.0, "rank": 1},
                        {"id": "doc-b", "score": 3.0, "rank": 2},
                    ],
                    "semantic_hits": [
                        {"id": "doc-b", "score": 0.91, "rank": 1},
                        {"id": "doc-c", "score": 0.82, "rank": 2},
                    ],
                },
            )
            assert r.status_code == 200, r.get_data(as_text=True)
            d = r.get_json()
            assert d["mode"] == "rerank_rrf"
            assert d["effective_mode"] == "rerank_rrf"
            assert d["degraded"] is False
            assert d["degraded_reason"] is None
            assert d["top_k"] == 2
            assert d["result_count"] == 2
            assert len(d["results"]) == 2
            assert d["results"][0]["id"] == "doc-b"
            assert d["results"][0]["rank"] == 1
            assert d["results"][0]["score"] == d["results"][0]["fused_score"]
            assert d["results"][0]["lexical_rank"] == 2
            assert d["results"][0]["semantic_rank"] == 1
            assert d["results"][1]["id"] == "doc-a"
