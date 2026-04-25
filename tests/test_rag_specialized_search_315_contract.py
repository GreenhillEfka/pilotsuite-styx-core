"""RAG Specialized Search 315 — focused contract coverage for /search/bm25 and /search/semantic."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    with patch("copilot_core.api.v1.rag.validate_token", return_value=True):
        yield


class TestRAGSpecializedSearch315:
    def test_bm25_rejects_invalid_namespace(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post(
                "/api/v1/rag/search/bm25",
                json={"namespace": "../bad", "query": "lights"},
            )
            assert r.status_code == 400
            assert r.get_json()["error"] == "invalid namespace format"

    def test_bm25_response_shape_is_bounded_and_explicit(self):
        app = _make_app()
        with _auth_ok():
            with patch("copilot_core.api.v1.rag._get_bm25") as mock_bm25:
                mock_bm25.return_value.search.return_value = [
                    BM25Hit(doc_id="doc-1", score=1.25, rank=1),
                ]
                r = app.test_client().post(
                    "/api/v1/rag/search/bm25",
                    json={
                        "namespace": "notes",
                        "query": "lights",
                        "include_text": False,
                        "include_metadata": False,
                        "top_k": 3,
                    },
                )
                assert r.status_code == 200, r.get_data(as_text=True)
                d = r.get_json()
                assert d["mode"] == "bm25"
                assert d["effective_mode"] == "bm25"
                assert d["degraded"] is False
                assert d["degraded_reason"] is None
                assert d["namespace"] == "notes"
                assert d["result_count"] == 1
                assert d["results"] == [{"id": "doc-1", "score": 1.25, "rank": 1}]

    def test_semantic_response_shape_is_machine_checkable_when_healthy(self):
        app = _make_app()
        with _auth_ok():
            with patch("copilot_core.api.v1.rag._load_semantic_backend") as mock_load:
                backend = MagicMock()
                backend.search_fn.return_value = [{"id": "doc-1", "score": 0.95}]
                mock_load.return_value = backend
                with patch("copilot_core.api.v1.rag._get_bm25") as mock_bm25:
                    mock_bm25.return_value.get_documents.return_value = {
                        "doc-1": {"text": "hello", "metadata": {"kind": "note"}}
                    }
                    r = app.test_client().post(
                        "/api/v1/rag/search/semantic",
                        json={"namespace": "notes", "query": "hello", "top_k": 3},
                    )
                    assert r.status_code == 200, r.get_data(as_text=True)
                    d = r.get_json()
                    assert d["mode"] == "semantic"
                    assert d["effective_mode"] == "semantic"
                    assert d["degraded"] is False
                    assert d["degraded_reason"] is None
                    assert d["warnings"] == []
                    assert d["result_count"] == 1
                    assert d["results"][0]["id"] == "doc-1"
                    assert d["results"][0]["semantic_score"] == 0.95

    def test_semantic_degradation_is_machine_checkable_when_backend_missing(self):
        app = _make_app()
        with _auth_ok():
            with patch("copilot_core.api.v1.rag._load_semantic_backend", return_value=None):
                with patch("copilot_core.api.v1.rag._get_bm25") as mock_bm25:
                    r = app.test_client().post(
                        "/api/v1/rag/search/semantic",
                        json={"namespace": "notes", "query": "hello", "top_k": 3},
                    )
                    assert r.status_code == 200, r.get_data(as_text=True)
                    d = r.get_json()
                    assert d["mode"] == "semantic"
                    assert d["effective_mode"] == "semantic"
                    assert d["degraded"] is True
                    assert d["degraded_reason"] == "semantic_backend_unavailable"
                    assert d["result_count"] == 0
                    assert any("semantic" in warning.lower() for warning in d["warnings"])
                    mock_bm25.assert_not_called()

    def test_semantic_degradation_is_machine_checkable_when_backend_fails(self):
        app = _make_app()
        with _auth_ok():
            with patch("copilot_core.api.v1.rag._load_semantic_backend") as mock_load:
                backend = MagicMock()
                backend.search_fn.side_effect = RuntimeError("vector store unreachable")
                mock_load.return_value = backend
                with patch("copilot_core.api.v1.rag._get_bm25") as mock_bm25:
                    r = app.test_client().post(
                        "/api/v1/rag/search/semantic",
                        json={"namespace": "notes", "query": "hello", "top_k": 3},
                    )
                    assert r.status_code == 200, r.get_data(as_text=True)
                    d = r.get_json()
                    assert d["mode"] == "semantic"
                    assert d["effective_mode"] == "semantic"
                    assert d["degraded"] is True
                    assert d["degraded_reason"] == "semantic_backend_failed"
                    assert d["result_count"] == 0
                    assert any("semantic" in warning.lower() for warning in d["warnings"])
                    mock_bm25.assert_not_called()
