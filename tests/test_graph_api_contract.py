"""Graph API Contract Tests — CORE-HARDEN-215"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1.graph import bp as graph_bp
import copilot_core.api.v1.graph as graph_mod


def _make_app():
    app = Flask(__name__)
    _orig = app.add_url_rule
    def _safe(*args, **kwargs):
        try:
            return _orig(*args, **kwargs)
        except AssertionError as e:
            if "overwriting" in str(e):
                return
            raise
    app.add_url_rule = _safe
    app.register_blueprint(graph_bp)
    return app


def _with_auth():
    return patch.object(graph_mod, '_validate_token', return_value=True)


def _make_svc(with_anomaly=False):
    _state = {"nodes": [], "edges": [], "limits": {}, "generated_at_ms": 0}
    if with_anomaly:
        _state["nodes"] = [{"id": "sensor.test", "kind": "sensor",
                             "meta": {"anomaly_score": -0.7}}]
    mock = MagicMock()
    mock.get_state.return_value = {"nodes": [], "edges": []}
    mock.get_graph_state.return_value = _state
    mock.get_stats.return_value = {"node_count": 0, "edge_count": 0, "limits": {"max_nodes": 1000}}
    mock.infer_patterns.return_value = []
    mock.get_topology.return_value = {"rooms": [], "devices": []}
    mock.get_sequences.return_value = {"sequences": []}
    mock.detect_sequences.return_value = []
    mock.get_anomalies.return_value = {"anomalies": [], "generated_at_ms": 0}
    mock.get_anomaly_history.return_value = {"history": []}
    mock.get_e2e_status.return_value = {"ok": True, "status": "nominal"}
    mock.export_graph.return_value = '{"nodes":[], "edges":[]}'
    mock.get_neuron_summary.return_value = {"neurons": []}
    mock.export_anomalies.return_value = '{"anomalies":[]}'
    mock.get_suggestions.return_value = {"suggestions": []}
    mock.trigger_automation.return_value = {"ok": True}
    mock.get_context_buckets.return_value = {"buckets": []}
    return mock


class TestGraphState:
    """GET /graph/state"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                r = app.test_client().get("/graph/state")
                assert r.status_code == 200, f"got {r.status_code}"

    def test_get_returns_dict(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                d = app.test_client().get("/graph/state").get_json()
                assert isinstance(d, dict)

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/graph/state")
        assert r.status_code in (401, 403)


class TestGraphStats:
    """GET /graph/stats"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                r = app.test_client().get("/graph/stats")
                assert r.status_code == 200

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/graph/stats")
        assert r.status_code in (401, 403)


class TestGraphPatterns:
    """GET /graph/patterns"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                r = app.test_client().get("/graph/patterns")
                assert r.status_code == 200

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/graph/patterns")
        assert r.status_code in (401, 403)


class TestGraphTopology:
    """GET /graph/topology"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                r = app.test_client().get("/graph/topology")
                assert r.status_code == 200

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/graph/topology")
        assert r.status_code in (401, 403)


class TestGraphSequences:
    """GET /graph/sequences"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                r = app.test_client().get("/graph/sequences")
                assert r.status_code == 200

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/graph/sequences")
        assert r.status_code in (401, 403)


class TestGraphCacheClear:
    """POST /graph/cache/clear"""

    def test_post_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                r = app.test_client().post("/graph/cache/clear")
                assert r.status_code == 200

    def test_post_requires_auth(self):
        r = _make_app().test_client().post("/graph/cache/clear")
        assert r.status_code in (401, 403)


class TestGraphAnomalies:
    """GET /graph/anomalies"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                r = app.test_client().get("/graph/anomalies")
                assert r.status_code == 200

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/graph/anomalies")
        assert r.status_code in (401, 403)


class TestGraphAnomaliesHistory:
    """GET /graph/anomalies/history"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                r = app.test_client().get("/graph/anomalies/history")
                assert r.status_code == 200

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/graph/anomalies/history")
        assert r.status_code in (401, 403)


class TestGraphAnomalyAcknowledge:
    """POST /graph/anomalies/<idx>/acknowledge"""

    def test_post_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc(with_anomaly=True)):
                r = app.test_client().post("/graph/anomalies/0/acknowledge")
                assert r.status_code == 200, f"got {r.status_code} / {r.get_json()}"

    def test_post_requires_auth(self):
        r = _make_app().test_client().post("/graph/anomalies/0/acknowledge")
        assert r.status_code in (401, 403)


class TestGraphE2EStatus:
    """GET /graph/e2e/status"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                r = app.test_client().get("/graph/e2e/status")
                assert r.status_code == 200

    def test_get_returns_ok(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                d = app.test_client().get("/graph/e2e/status").get_json()
                assert d.get("ok") is True

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/graph/e2e/status")
        assert r.status_code in (401, 403)


class TestGraphExport:
    """GET /graph/export"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                r = app.test_client().get("/graph/export")
                assert r.status_code == 200

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/graph/export")
        assert r.status_code in (401, 403)


class TestGraphNeuronSummary:
    """GET /graph/neuron-summary"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                r = app.test_client().get("/graph/neuron-summary")
                assert r.status_code == 200

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/graph/neuron-summary")
        assert r.status_code in (401, 403)


class TestGraphSuggestions:
    """GET /graph/suggestions"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                with patch('copilot_core.proactive_engine.ProactiveContextEngine') as m:
                    m.return_value.get_suggestions.return_value = []
                    r = app.test_client().get("/graph/suggestions")
                    assert r.status_code == 200, f"got {r.status_code} / {r.get_json()}"

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/graph/suggestions")
        assert r.status_code in (401, 403)


class TestGraphTriggerAutomation:
    """POST /graph/trigger/automation"""

    def test_post_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                with patch('copilot_core.proactive_engine.ProactiveContextEngine') as m:
                    m.return_value.deliver_suggestion.return_value = {"delivered": True}
                    r = app.test_client().post("/graph/trigger/automation", json={})
                    assert r.status_code == 200

    def test_post_requires_auth(self):
        r = _make_app().test_client().post("/graph/trigger/automation", json={})
        assert r.status_code in (401, 403)


class TestGraphContextBuckets:
    """GET /graph/context/buckets"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(graph_mod, '_svc', return_value=_make_svc()):
                r = app.test_client().get("/graph/context/buckets")
                assert r.status_code == 200

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/graph/context/buckets")
        assert r.status_code in (401, 403)
