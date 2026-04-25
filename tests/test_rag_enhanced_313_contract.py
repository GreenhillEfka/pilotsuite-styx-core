"""RAG Enhanced 313 — focused contract coverage for /search/enhanced."""
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
from copilot_core.rag.query_router import QueryType


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


def _classification(query_type: QueryType, *, use_web_search: bool) -> SimpleNamespace:
    return SimpleNamespace(
        query_type=query_type,
        use_web_search=use_web_search,
        confidence=0.99,
        web_keywords_found=[],
        local_keywords_found=[],
        reasoning="contract-test",
    )


class TestRAGEnhancedContract:
    def test_rejects_missing_query(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post("/api/v1/rag/search/enhanced", json={})
            assert r.status_code == 400
            assert r.get_json()["error"] == "query required"

    def test_local_only_bm25_mode_is_machine_checkable(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag.classify_query', return_value=_classification(QueryType.LOCAL, use_web_search=False)):
                with patch('copilot_core.api.v1.rag._semantic_search') as mock_semantic:
                    mock_semantic.return_value = SimpleNamespace(hits=[], degraded=True, degraded_reason='semantic_backend_unavailable')
                    with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                        mock_bm25.return_value.search.return_value = [BM25Hit(doc_id='doc-1', score=2.0, rank=1)]
                        mock_bm25.return_value.get_documents.return_value = {'doc-1': {'text': 'A', 'metadata': {'kind': 'note'}}}
                        r = app.test_client().post('/api/v1/rag/search/enhanced', json={'query': 'local status', 'top_k': 3})
                        assert r.status_code == 200, r.get_data(as_text=True)
                        d = r.get_json()
                        assert d['mode'] == 'local'
                        assert d['effective_mode'] == 'local_bm25'
                        assert d['degraded'] is True
                        assert d['degraded_reason'] == 'semantic_backend_unavailable'
                        assert d['sources_used'] == {'local_bm25': True, 'semantic': False, 'web_searxng': False}
                        assert d['results'][0]['id'] == 'doc-1'

    def test_web_only_mode_keeps_source_provenance_explicit(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag.classify_query', return_value=_classification(QueryType.WEB, use_web_search=True)):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = []
                    mock_bm25.return_value.get_documents.return_value = {}
                    with patch('copilot_core.api.v1.rag._semantic_search') as mock_semantic:
                        mock_semantic.return_value = SimpleNamespace(hits=[], degraded=False, degraded_reason=None)
                        with patch('copilot_core.api.v1.rag._searxng_search_sync') as mock_web:
                            mock_web.return_value = [
                                SimpleNamespace(
                                    title='Example',
                                    url='https://example.com',
                                    content='snippet',
                                    score=0.9,
                                    category='general',
                                    engine='searxng',
                                )
                            ]
                            r = app.test_client().post('/api/v1/rag/search/enhanced', json={'query': 'latest news', 'top_k': 3})
                            assert r.status_code == 200
                            d = r.get_json()
                            assert d['mode'] == 'web'
                            assert d['effective_mode'] == 'web'
                            assert d['degraded'] is False
                            assert d['sources_used'] == {'local_bm25': False, 'semantic': False, 'web_searxng': True}
                            assert d['results'][0]['source'] == 'searxng'
                            assert d['results'][0]['url'] == 'https://example.com'

    def test_hybrid_mode_keeps_local_and_web_truth_explicit(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag.classify_query', return_value=_classification(QueryType.LOCAL, use_web_search=False)):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = [BM25Hit(doc_id='doc-1', score=1.0, rank=1)]
                    mock_bm25.return_value.get_documents.return_value = {'doc-1': {'text': 'A', 'metadata': {}}}
                    with patch('copilot_core.api.v1.rag._semantic_search') as mock_semantic:
                        mock_semantic.return_value = SimpleNamespace(
                            hits=[RankedHit(doc_id='doc-1', score=0.8, rank=1)],
                            degraded=False,
                            degraded_reason=None,
                        )
                        with patch('copilot_core.api.v1.rag._searxng_search_sync') as mock_web:
                            mock_web.return_value = [
                                SimpleNamespace(
                                    title='Web Result',
                                    url='https://example.com/web',
                                    content='web snippet',
                                    score=0.7,
                                    category='general',
                                    engine='searxng',
                                )
                            ]
                            r = app.test_client().post('/api/v1/rag/search/enhanced', json={'query': 'need local and web', 'use_web': True, 'top_k': 3})
                            assert r.status_code == 200, r.get_data(as_text=True)
                            d = r.get_json()
                            assert d['mode'] == 'hybrid'
                            assert d['effective_mode'] == 'hybrid_local_web'
                            assert d['degraded'] is False
                            assert d['sources_used'] == {'local_bm25': True, 'semantic': True, 'web_searxng': True}
                            sources = {item['source'] for item in d['results']}
                            assert 'local' in sources
                            assert 'searxng' in sources

    def test_hybrid_degradation_stays_machine_checkable(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag.classify_query', return_value=_classification(QueryType.LOCAL, use_web_search=False)):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = [BM25Hit(doc_id='doc-1', score=1.0, rank=1)]
                    with patch('copilot_core.api.v1.rag._semantic_search') as mock_semantic:
                        mock_semantic.return_value = SimpleNamespace(hits=[], degraded=True, degraded_reason='semantic_backend_failed')
                        with patch('copilot_core.api.v1.rag._searxng_search_sync') as mock_web:
                            mock_web.return_value = [
                                SimpleNamespace(
                                    title='Web Result',
                                    url='https://example.com/web',
                                    content='web snippet',
                                    score=0.7,
                                    category='general',
                                    engine='searxng',
                                )
                            ]
                            r = app.test_client().post('/api/v1/rag/search/enhanced', json={'query': 'need local and web', 'use_web': True, 'top_k': 3})
                            assert r.status_code == 200
                            d = r.get_json()
                            assert d['mode'] == 'hybrid'
                            assert d['effective_mode'] == 'hybrid_bm25_web'
                            assert d['degraded'] is True
                            assert d['degraded_reason'] == 'semantic_backend_failed'
