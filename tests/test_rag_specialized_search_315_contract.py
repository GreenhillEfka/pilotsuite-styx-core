"""RAG Specialized Search 315 — focused contract coverage for bm25 and semantic routes."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

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


class TestRAGSpecializedRouteRegistration:
    def test_routes_exist(self):
        app = _make_app()
        rules = {rule.rule for rule in app.url_map.iter_rules() if '/rag/' in rule.rule}
        assert '/api/v1/rag/search/bm25' in rules
        assert '/api/v1/rag/search/semantic' in rules


class TestBM25SpecializedContract:
    def test_bm25_requires_query(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post('/api/v1/rag/search/bm25', json={})
            assert r.status_code == 400
            assert r.get_json()['error'] == 'query required'

    def test_bm25_rejects_invalid_namespace(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post('/api/v1/rag/search/bm25', json={'query': 'alpha', 'namespace': '../bad'})
            assert r.status_code == 400
            assert r.get_json()['error'] == 'invalid namespace format'

    def test_bm25_returns_bounded_explicit_results(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                mock_bm25.return_value.search.return_value = [
                    BM25Hit(doc_id='doc-1', score=2.0, rank=1),
                    BM25Hit(doc_id='doc-2', score=1.0, rank=2),
                    BM25Hit(doc_id='doc-3', score=0.5, rank=3),
                ]
                mock_bm25.return_value.get_documents.return_value = {
                    'doc-1': {'text': 'A', 'metadata': {'kind': 'x'}},
                    'doc-2': {'text': 'B', 'metadata': {'kind': 'y'}},
                }
                r = app.test_client().post('/api/v1/rag/search/bm25', json={'query': 'alpha', 'top_k': 2})
                assert r.status_code == 200, r.get_data(as_text=True)
                d = r.get_json()
                assert d['mode'] == 'bm25'
                assert d['effective_mode'] == 'bm25'
                assert d['degraded'] is False
                assert d['degraded_reason'] is None
                assert d['result_count'] == 2
                assert len(d['results']) == 2
                assert d['results'][0]['id'] == 'doc-1'
                assert d['results'][0]['lexical_rank'] == 1


class TestSemanticSpecializedContract:
    def test_semantic_requires_query(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post('/api/v1/rag/search/semantic', json={})
            assert r.status_code == 400
            assert r.get_json()['error'] == 'query required'

    def test_semantic_returns_machine_checkable_degradation(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._semantic_search') as mock_semantic:
                mock_semantic.return_value = SimpleNamespace(
                    hits=[],
                    degraded=True,
                    degraded_reason='semantic_backend_unavailable',
                )
                r = app.test_client().post('/api/v1/rag/search/semantic', json={'query': 'alpha', 'top_k': 2})
                assert r.status_code == 200, r.get_data(as_text=True)
                d = r.get_json()
                assert d['mode'] == 'semantic'
                assert d['effective_mode'] == 'semantic'
                assert d['degraded'] is True
                assert d['degraded_reason'] == 'semantic_backend_unavailable'
                assert d['result_count'] == 0
                assert isinstance(d['warnings'], list)

    def test_semantic_stays_semantic_only(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._semantic_search') as mock_semantic:
                mock_semantic.return_value = SimpleNamespace(
                    hits=[RankedHit(doc_id='doc-s', score=0.9, rank=1)],
                    degraded=False,
                    degraded_reason=None,
                )
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.get_documents.return_value = {
                        'doc-s': {'text': 'semantic doc', 'metadata': {'kind': 'semantic'}}
                    }
                    r = app.test_client().post('/api/v1/rag/search/semantic', json={'query': 'alpha', 'top_k': 3})
                    assert r.status_code == 200, r.get_data(as_text=True)
                    d = r.get_json()
                    assert d['mode'] == 'semantic'
                    assert d['effective_mode'] == 'semantic'
                    assert d['degraded'] is False
                    assert d['results'][0]['id'] == 'doc-s'
                    assert d['results'][0]['semantic_rank'] == 1
                    assert 'lexical_rank' not in d['results'][0] or d['results'][0]['lexical_rank'] is None
