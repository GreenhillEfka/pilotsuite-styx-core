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
    async def _no_cache(*args, **kwargs):
        return None
    with patch('copilot_core.api.v1.rag.validate_token', return_value=True):
        with patch('copilot_core.api.v1.rag._get_rag_cache') as mock_cache:
            mock_cache.return_value.get = _no_cache
            yield


class TestRAGRerankRouteRegistration:
    def test_route_exists(self):
        app = _make_app()
        rules = {rule.rule for rule in app.url_map.iter_rules() if '/rag/' in rule.rule}
        assert '/api/v1/rag/rerank' in rules


class TestRAGRerankValidation:
    def test_rejects_empty_hit_lists(self):
        app = _make_app()
        with _auth_ok():
            r = app.test_client().post('/api/v1/rag/rerank', json={})
            assert r.status_code == 400
            assert r.get_json()['error'] == 'at least one of lexical_hits/semantic_hits required'

    def test_rejects_oversized_hit_lists(self):
        app = _make_app()
        oversized = [{'id': f'doc-{i}', 'score': 1.0, 'rank': i + 1} for i in range(1001)]
        with _auth_ok():
            r = app.test_client().post('/api/v1/rag/rerank', json={'lexical_hits': oversized})
            assert r.status_code == 400
            assert r.get_json()['error'] == 'max 1000 hits per list'


class TestRAGRerankResultTruth:
    def test_fused_results_are_bounded_and_machine_checkable(self):
        app = _make_app()
        with _auth_ok():
            payload = {
                'lexical_hits': [
                    {'id': 'doc-a', 'score': 2.0, 'rank': 1},
                    {'id': 'doc-b', 'score': 1.0, 'rank': 2},
                ],
                'semantic_hits': [
                    {'id': 'doc-b', 'score': 0.95, 'rank': 1},
                    {'id': 'doc-a', 'score': 0.80, 'rank': 2},
                ],
                'top_k': 1,
            }
            r = app.test_client().post('/api/v1/rag/rerank', json=payload)
            assert r.status_code == 200, r.get_data(as_text=True)
            d = r.get_json()
            assert d['mode'] == 'rerank_rrf'
            assert d['result_count'] == 1
            assert len(d['results']) == 1
            result = d['results'][0]
            assert result['id'] in {'doc-a', 'doc-b'}
            assert isinstance(result['fused_score'], float)
            assert 'lexical_rank' in result
            assert 'semantic_rank' in result

    def test_accepts_single_input_list_without_widening_route(self):
        app = _make_app()
        with _auth_ok():
            payload = {
                'semantic_hits': [
                    {'id': 'doc-s', 'score': 0.9, 'rank': 1},
                    {'id': 'doc-t', 'score': 0.7, 'rank': 2},
                ],
                'top_k': 2,
            }
            r = app.test_client().post('/api/v1/rag/rerank', json=payload)
            assert r.status_code == 200, r.get_data(as_text=True)
            d = r.get_json()
            assert d['mode'] == 'rerank_rrf'
            assert d['result_count'] == 2
            assert len(d['results']) == 2
            assert d['results'][0]['semantic_rank'] == 1
            assert d['results'][0]['lexical_rank'] is None

    def test_skips_blank_ids_and_keeps_valid_hits(self):
        app = _make_app()
        with _auth_ok():
            payload = {
                'lexical_hits': [
                    {'id': '   ', 'score': 3.0, 'rank': 1},
                    {'id': 'doc-a', 'score': 2.0, 'rank': 2},
                ],
                'top_k': 5,
            }
            r = app.test_client().post('/api/v1/rag/rerank', json=payload)
            assert r.status_code == 200, r.get_data(as_text=True)
            d = r.get_json()
            assert d['result_count'] == 1
            assert d['results'][0]['id'] == 'doc-a'
