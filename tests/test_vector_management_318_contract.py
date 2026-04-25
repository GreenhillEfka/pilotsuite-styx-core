"""Vector Management 318 — focused contract coverage for live vector management routes."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1.vector import bp as vector_bp


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(vector_bp)
    return app


@contextmanager
def _auth_ok():
    with patch('copilot_core.api.v1.vector._validate_token', return_value=True):
        yield


def _entry(entry_id: str, entry_type: str = 'entity', metadata: dict | None = None):
    return SimpleNamespace(
        id=entry_id,
        entry_type=entry_type,
        vector=[0.1, 0.2, 0.3],
        created_at='2026-04-25T10:00:00Z',
        updated_at='2026-04-25T10:05:00Z',
        metadata=metadata or {},
    )


class TestVectorManagementRoutes:
    def test_routes_exist(self):
        app = _make_app()
        rules = {rule.rule for rule in app.url_map.iter_rules() if '/vector' in rule.rule}
        assert '/vector/vectors' in rules
        assert '/vector/vectors/<path:entry_id>' in rules
        assert '/vector/stats' in rules


class TestVectorListContract:
    def test_list_vectors_is_bounded(self):
        app = _make_app()
        store = MagicMock()
        store.get_by_type.side_effect = [
            [_entry('entity:1')],
            [_entry('user_pref:2', 'user_preference')],
            [_entry('pattern:3', 'pattern')],
        ]
        with _auth_ok(), patch('copilot_core.api.v1.vector._store', return_value=store), patch('copilot_core.api.v1.vector._run_async', side_effect=lambda x: x):
            r = app.test_client().get('/vector/vectors?limit=2')
            assert r.status_code == 200, r.get_data(as_text=True)
            d = r.get_json()
            assert d['ok'] is True
            assert d['count'] == 2
            assert len(d['entries']) == 2

    def test_list_vectors_filters_by_type(self):
        app = _make_app()
        store = MagicMock()
        store.get_by_type.return_value = [_entry('user_pref:2', 'user_preference')]
        with _auth_ok(), patch('copilot_core.api.v1.vector._store', return_value=store), patch('copilot_core.api.v1.vector._run_async', side_effect=lambda x: x):
            r = app.test_client().get('/vector/vectors?type=user_preference&limit=5')
            assert r.status_code == 200
            d = r.get_json()
            assert d['count'] == 1
            assert d['entries'][0]['id'] == 'user_pref:2'
            store.get_by_type.assert_called_once_with('user_preference', 5)


class TestVectorGetContract:
    def test_get_vector_resolves_normalized_entry_id(self):
        app = _make_app()
        store = MagicMock()
        store.get.side_effect = [None, _entry('user_pref:abc', 'user_preference')]
        with _auth_ok(), patch('copilot_core.api.v1.vector._store', return_value=store), patch('copilot_core.api.v1.vector._run_async', side_effect=lambda x: x):
            r = app.test_client().get('/vector/vectors/abc')
            assert r.status_code == 200, r.get_data(as_text=True)
            d = r.get_json()
            assert d['found'] is True
            assert d['requested_id'] == 'abc'
            assert d['lookup_id'] == 'user_pref:abc'
            assert d['entry']['id'] == 'user_pref:abc'

    def test_get_vector_missing_is_honest(self):
        app = _make_app()
        store = MagicMock()
        store.get.side_effect = [None, None, None]
        with _auth_ok(), patch('copilot_core.api.v1.vector._store', return_value=store), patch('copilot_core.api.v1.vector._run_async', side_effect=lambda x: x):
            r = app.test_client().get('/vector/vectors/missing-id')
            assert r.status_code == 404
            d = r.get_json()
            assert d['found'] is False
            assert d['requested_id'] == 'missing-id'
            assert d['attempted_ids'] == ['entity:missing-id', 'user_pref:missing-id', 'pattern:missing-id']


class TestVectorDeleteAndClearContract:
    def test_delete_vector_missing_is_honest(self):
        app = _make_app()
        store = MagicMock()
        store.delete.side_effect = [False, False, False]
        with _auth_ok(), patch('copilot_core.api.v1.vector._store', return_value=store), patch('copilot_core.api.v1.vector._run_async', side_effect=lambda x: x):
            r = app.test_client().delete('/vector/vectors/missing-id')
            assert r.status_code == 404
            d = r.get_json()
            assert d['found'] is False
            assert d['deleted_count'] == 0
            assert d['deleted'] is None

    def test_delete_vector_returns_deleted_truth(self):
        app = _make_app()
        store = MagicMock()
        store.delete.side_effect = [False, True]
        with _auth_ok(), patch('copilot_core.api.v1.vector._store', return_value=store), patch('copilot_core.api.v1.vector._run_async', side_effect=lambda x: x):
            r = app.test_client().delete('/vector/vectors/abc')
            assert r.status_code == 200
            d = r.get_json()
            assert d['found'] is True
            assert d['deleted'] == 'user_pref:abc'
            assert d['deleted_count'] == 1

    def test_stats_shape_is_machine_checkable(self):
        app = _make_app()
        store = MagicMock()
        store.stats.return_value = {'total_vectors': 3, 'by_type': {'entity': 2, 'pattern': 1}}
        with _auth_ok(), patch('copilot_core.api.v1.vector._store', return_value=store), patch('copilot_core.api.v1.vector._run_async', side_effect=lambda x: x):
            r = app.test_client().get('/vector/stats')
            assert r.status_code == 200
            d = r.get_json()
            assert d == {'ok': True, 'stats': {'total_vectors': 3, 'by_type': {'entity': 2, 'pattern': 1}}}

    def test_clear_vectors_reports_deleted_count_and_scope(self):
        app = _make_app()
        store = MagicMock()
        store.clear.return_value = 4
        with _auth_ok(), patch('copilot_core.api.v1.vector._store', return_value=store), patch('copilot_core.api.v1.vector._run_async', side_effect=lambda x: x):
            r = app.test_client().delete('/vector/vectors?type=pattern')
            assert r.status_code == 200
            d = r.get_json()
            assert d == {'ok': True, 'deleted_count': 4, 'type': 'pattern'}
            store.clear.assert_called_once_with('pattern')
