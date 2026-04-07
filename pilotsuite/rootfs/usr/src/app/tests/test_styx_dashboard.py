"""Tests for Styx Dashboard API (styx_dashboard.py).

Tests the unified dashboard endpoints:
  - GET /api/v1/styx/dashboard       (full payload)
  - GET /api/v1/styx/dashboard/compact (lightweight polling)
  - GET /api/v1/styx/config           (system configuration)

Uses a real Flask test client with mocked services.
"""

import json
import pytest
from unittest.mock import Mock, patch
from flask import Flask


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def mock_services():
    """Create a full set of mock services."""
    neuron_mgr = Mock()
    neuron_mgr.get_mood_summary.return_value = {
        "dominant_mood": "calm",
        "confidence": 0.82,
        "emotions": {"calm": 0.82, "focused": 0.15},
    }
    neuron_mgr.get_neuron_summary.return_value = {
        "total_count": 12,
        "active_count": 8,
        "layers": {"context": 4, "state": 4, "mood": 4},
    }

    brain_svc = Mock()
    brain_svc.get_graph_state.return_value = {
        "nodes": [
            {"id": "n1", "kind": "entity", "score": 0.9},
            {"id": "n2", "kind": "pattern", "score": 0.5},
            {"id": "n3", "kind": "entity", "score": 0.3},
        ],
        "edges": [
            {"source": "n1", "target": "n2", "weight": 0.7},
        ],
    }

    bus = Mock()
    bus.get_stats.return_value = {
        "events_published": 142,
        "events_delivered": 138,
        "errors": 2,
        "subscribers": 5,
    }
    bus.get_dead_letters.return_value = [
        {"event": "test.failed", "error": "timeout", "ts": "2026-03-04T10:00:00Z"},
    ]

    registry = Mock()
    registry.get_all_states.return_value = {
        "mood_engine": "active",
        "habitus_miner": "learning",
        "brain_graph": "active",
    }
    registry.should_collect_data.side_effect = lambda mid: mid != "off_module"
    registry.should_suggest.side_effect = lambda mid: mid in (
        "mood_engine", "habitus_miner", "brain_graph",
        "neuron_pipeline", "integration_bus", "hebbian_learning",
        "proactive_engine", "energy_service", "voice_context",
        "anomaly_detection",
    )

    habitus_svc = Mock()
    habitus_svc.get_pattern_stats.return_value = {
        "total_patterns": 23,
        "active_patterns": 15,
    }

    hebbian = Mock()
    hebbian.get_all_weights.return_value = {"s1": 0.5, "s2": 0.3, "s3": 0.8}
    hebbian.get_drift.return_value = {"s1": 0.02, "s2": -0.05, "s3": 0.01}

    candidates = Mock()
    candidates.list.return_value = [
        {"id": "c1", "text": "Turn off lights", "score": 0.9},
        {"id": "c2", "text": "Lower blinds", "score": 0.7},
    ]

    return {
        "neuron_manager": neuron_mgr,
        "brain_graph_service": brain_svc,
        "integration_bus": bus,
        "module_registry": registry,
        "habitus_service": habitus_svc,
        "hebbian_learning": hebbian,
        "candidate_store": candidates,
        "startup_time_ms": 123.4,
    }


def _make_app(services):
    """Create a Flask app with the styx_dashboard blueprint and auth bypassed."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    from copilot_core.api.v1.styx_dashboard import styx_dashboard_bp, init_styx_dashboard_api
    init_styx_dashboard_api(services)
    app.register_blueprint(styx_dashboard_bp)
    return app


@pytest.fixture
def client(mock_services):
    """Flask test client with auth bypassed."""
    with patch("copilot_core.api.v1.styx_dashboard.validate_token", return_value=True):
        app = _make_app(mock_services)
        with app.test_client() as c:
            yield c


# ── Full Dashboard Tests ─────────────────────────────────────────────

class TestFullDashboard:
    """Tests for GET /api/v1/styx/dashboard."""

    def test_full_dashboard_ok(self, client):
        resp = client.get("/api/v1/styx/dashboard")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert "timestamp" in data
        assert "render_ms" in data

    def test_full_dashboard_mood(self, client):
        resp = client.get("/api/v1/styx/dashboard")
        data = json.loads(resp.data)
        assert data["mood"]["dominant_mood"] == "calm"
        assert data["mood"]["confidence"] == 0.82

    def test_full_dashboard_neurons(self, client):
        resp = client.get("/api/v1/styx/dashboard")
        data = json.loads(resp.data)
        assert data["neurons"]["total_count"] == 12
        assert "summary" in data["neurons"]

    def test_full_dashboard_graph(self, client):
        resp = client.get("/api/v1/styx/dashboard")
        data = json.loads(resp.data)
        graph = data["graph"]
        assert graph["total_nodes"] == 3
        assert graph["total_edges"] == 1
        assert graph["nodes_by_kind"]["entity"] == 2
        assert graph["nodes_by_kind"]["pattern"] == 1
        # Sorted by score descending
        assert graph["top_nodes"][0]["id"] == "n1"

    def test_full_dashboard_bus_with_dead_letters(self, client):
        resp = client.get("/api/v1/styx/dashboard")
        data = json.loads(resp.data)
        bus = data["bus"]
        assert bus["events_published"] == 142
        assert bus["dead_letter_count"] == 1
        assert len(bus["recent_dead_letters"]) == 1

    def test_full_dashboard_modules(self, client):
        resp = client.get("/api/v1/styx/dashboard")
        data = json.loads(resp.data)
        assert data["modules"]["mood_engine"] == "active"
        assert data["modules"]["habitus_miner"] == "learning"

    def test_full_dashboard_habitus(self, client):
        resp = client.get("/api/v1/styx/dashboard")
        data = json.loads(resp.data)
        assert data["habitus"]["total_patterns"] == 23

    def test_full_dashboard_learning(self, client):
        resp = client.get("/api/v1/styx/dashboard")
        data = json.loads(resp.data)
        learning = data["learning"]
        assert learning["total_synapses"] == 3
        assert len(learning["top_drifts"]) == 3
        # Sorted by drift descending
        assert learning["top_drifts"][0]["synapse"] == "s2"
        assert learning["top_drifts"][0]["drift"] == 0.05

    def test_full_dashboard_candidates(self, client):
        resp = client.get("/api/v1/styx/dashboard")
        data = json.loads(resp.data)
        assert len(data["candidates"]) == 2
        assert data["candidates"][0]["id"] == "c1"


# ── Compact Dashboard Tests ──────────────────────────────────────────

class TestCompactDashboard:
    """Tests for GET /api/v1/styx/dashboard/compact."""

    def test_compact_ok(self, client):
        resp = client.get("/api/v1/styx/dashboard/compact")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True

    def test_compact_has_mood(self, client):
        resp = client.get("/api/v1/styx/dashboard/compact")
        data = json.loads(resp.data)
        assert data["mood"]["dominant_mood"] == "calm"

    def test_compact_bus_subset(self, client):
        """Compact endpoint only returns bus counters, not full stats."""
        resp = client.get("/api/v1/styx/dashboard/compact")
        data = json.loads(resp.data)
        bus = data["bus"]
        assert "events_published" in bus
        assert "events_delivered" in bus
        assert "errors" in bus
        assert "subscribers" not in bus

    def test_compact_has_modules(self, client):
        resp = client.get("/api/v1/styx/dashboard/compact")
        data = json.loads(resp.data)
        assert "mood_engine" in data["modules"]


# ── Config Endpoint Tests ────────────────────────────────────────────

class TestSystemConfig:
    """Tests for GET /api/v1/styx/config."""

    def test_config_ok(self, client):
        resp = client.get("/api/v1/styx/config")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True

    def test_config_has_modules(self, client):
        resp = client.get("/api/v1/styx/config")
        data = json.loads(resp.data)
        modules = data["modules"]
        assert len(modules) == 10
        ids = [m["id"] for m in modules]
        assert "mood_engine" in ids
        assert "brain_graph" in ids
        assert "anomaly_detection" in ids

    def test_config_module_structure(self, client):
        resp = client.get("/api/v1/styx/config")
        data = json.loads(resp.data)
        mod = data["modules"][0]
        assert "id" in mod
        assert "label" in mod
        assert "icon" in mod
        assert "description" in mod
        assert "state" in mod
        assert "collects_data" in mod
        assert "generates_suggestions" in mod

    def test_config_module_states_from_registry(self, client):
        """Modules with explicit states get them from registry."""
        resp = client.get("/api/v1/styx/config")
        data = json.loads(resp.data)
        modules = {m["id"]: m for m in data["modules"]}
        assert modules["mood_engine"]["state"] == "active"
        assert modules["habitus_miner"]["state"] == "learning"

    def test_config_default_state(self, client):
        """Modules without explicit state default to 'active'."""
        resp = client.get("/api/v1/styx/config")
        data = json.loads(resp.data)
        modules = {m["id"]: m for m in data["modules"]}
        assert modules["anomaly_detection"]["state"] == "active"

    def test_config_valid_states(self, client):
        resp = client.get("/api/v1/styx/config")
        data = json.loads(resp.data)
        assert set(data["valid_module_states"]) == {"active", "learning", "off"}

    def test_config_habitus_zones(self, client):
        resp = client.get("/api/v1/styx/config")
        data = json.loads(resp.data)
        assert "habitus_zones" in data
        assert isinstance(data["habitus_zones"], list)

    def test_config_service_health(self, client):
        resp = client.get("/api/v1/styx/config")
        data = json.loads(resp.data)
        health = data["service_health"]
        assert health["neuron_manager"] is True
        assert health["brain_graph_service"] is True
        assert health["integration_bus"] is True

    def test_config_startup_time(self, client):
        resp = client.get("/api/v1/styx/config")
        data = json.loads(resp.data)
        assert data["startup_time_ms"] == 123.4


# ── Resilience Tests ─────────────────────────────────────────────────

class TestDashboardResilience:
    """Test graceful degradation when services are missing/broken."""

    def test_dashboard_with_no_services(self):
        """Dashboard works even with empty services dict."""
        with patch("copilot_core.api.v1.styx_dashboard.validate_token", return_value=True):
            app = _make_app({})
            with app.test_client() as c:
                resp = c.get("/api/v1/styx/dashboard")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True
                assert data["mood"] == {}
                assert data["modules"] == {}

    def test_compact_with_no_services(self):
        """Compact endpoint works with empty services."""
        with patch("copilot_core.api.v1.styx_dashboard.validate_token", return_value=True):
            app = _make_app({})
            with app.test_client() as c:
                resp = c.get("/api/v1/styx/dashboard/compact")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True

    def test_dashboard_with_broken_service(self):
        """Dashboard survives a service that throws on every call."""
        broken = Mock()
        broken.get_mood_summary.side_effect = RuntimeError("boom")
        broken.get_neuron_summary.side_effect = RuntimeError("boom")

        with patch("copilot_core.api.v1.styx_dashboard.validate_token", return_value=True):
            app = _make_app({"neuron_manager": broken})
            with app.test_client() as c:
                resp = c.get("/api/v1/styx/dashboard")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True
                assert data["mood"] == {}

    def test_config_with_broken_registry(self):
        """Config endpoint works when registry throws."""
        broken_reg = Mock()
        broken_reg.get_all_states.side_effect = RuntimeError("db locked")
        broken_reg.should_collect_data.side_effect = RuntimeError("db locked")
        broken_reg.should_suggest.side_effect = RuntimeError("db locked")

        with patch("copilot_core.api.v1.styx_dashboard.validate_token", return_value=True):
            app = _make_app({"module_registry": broken_reg})
            with app.test_client() as c:
                resp = c.get("/api/v1/styx/config")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True
                assert len(data["modules"]) == 10
