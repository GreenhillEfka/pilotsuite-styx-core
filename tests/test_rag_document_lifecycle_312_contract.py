"""RAG Document Lifecycle 312 — documented create/delete seam contract."""
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
    async def _no_cache(*args, **kwargs):
        return None
    with patch('copilot_core.api.v1.rag.validate_token', return_value=True):
        with patch('copilot_core.api.v1.rag._get_rag_cache') as mock_cache:
            mock_cache.return_value.get = _no_cache
            mock_cache.return_value.invalidate_pattern.return_value = None
            yield


class TestRAGDocumentRoutes:
    def test_routes_exist(self):
        app = _make_app()
        rules = {rule.rule for rule in app.url_map.iter_rules() if "/rag/" in rule.rule}
        assert "/api/v1/rag/documents" in rules
        assert "/api/v1/rag/documents/<doc_id>" in rules


class TestRAGDocumentCreate:
    def test_requires_doc_id(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post("/api/v1/rag/documents", json={"content": "hello"})
            assert r.status_code == 400
            assert "doc_id required" in r.get_json()["error"]

    def test_requires_content(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post("/api/v1/rag/documents", json={"doc_id": "doc-1"})
            assert r.status_code == 400
            assert "content required" in r.get_json()["error"]

    def test_create_success_with_explicit_semantic_warning(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.upsert_documents.return_value = (1, [])
                with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                    r = app.test_client().post(
                        "/api/v1/rag/documents",
                        json={"doc_id": "doc-1", "content": "hello world", "metadata": {"kind": "note"}},
                    )
                    assert r.status_code == 200, r.get_data(as_text=True)
                    d = r.get_json()
                    assert d["created"] is True
                    assert d["bm25_indexed"] is True
                    assert d["semantic_indexed"] is False
                    assert d["degraded"] is True
                    assert d["degraded_reason"] == "semantic_backend_unavailable_or_failed"
                    assert isinstance(d["warnings"], list)


class TestRAGDocumentDelete:
    def test_delete_missing_doc_is_honest_404(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.delete_document.return_value = False
                r = app.test_client().delete("/api/v1/rag/documents/missing-doc")
                assert r.status_code == 404
                d = r.get_json()
                assert d["deleted"] is False
                assert d["doc_id"] == "missing-doc"
                assert d["error"] == "document not found"

    def test_delete_success_with_explicit_semantic_truth(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.delete_document.return_value = True
                r = app.test_client().delete("/api/v1/rag/documents/doc-1")
                assert r.status_code == 200, r.get_data(as_text=True)
                d = r.get_json()
                assert d["deleted"] is True
                assert d["semantic_deleted"] is False
                assert d["degraded"] is True
                assert d["degraded_reason"] == "semantic_delete_unavailable"
                assert "semantic delete unavailable" in d["warnings"][0]


class TestBM25DeleteContract:
    def test_bm25_delete_called_with_namespace_and_doc_id(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.delete_document.return_value = True
                app.test_client().delete("/api/v1/rag/documents/doc-xyz?namespace=memory")
                mock_bm25.return_value.delete_document.assert_called_once_with(
                    namespace="memory", doc_id="doc-xyz"
                )
