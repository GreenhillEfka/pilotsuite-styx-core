"""Contract tests for Hub API + Presence API.

Verifies:
- hub_bp initializes, routes are registered
- Presence API endpoints are reachable without crashing
- Hub energy endpoints handle missing energy_advisor gracefully
- PresenceIntelligenceEngine is importable with expected methods
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))


class TestHubAPIImport:
    """Hub API module is importable."""

    def test_hub_api_importable(self):
        from copilot_core.hub.api import hub_bp
        assert hub_bp is not None
        assert hub_bp.name == "hub"


class TestHubEnergyEndpoints:
    """Hub energy endpoints handle missing energy_advisor gracefully."""

    def test_energy_dashboard_handles_missing_advisor(self, monkeypatch):
        """GET /api/v1/hub/energy should not crash when advisor is None."""
        from flask import Flask
        from copilot_core.hub.api import hub_bp

        app = Flask(__name__)
        app.config["COPILOT_AUTH_REQUIRED"] = False
        app.register_blueprint(hub_bp)
        client = app.test_client()

        # Simulate uninitialized energy_advisor
        import copilot_core.hub.api as hub_module
        monkeypatch.setattr(hub_module, "_energy_advisor", None)

        response = client.get("/api/v1/hub/energy")
        # 503 = graceful (advisor not set up), 200 = happy path
        assert response.status_code in (200, 401, 503), f"Expected 200 or 503, got {response.status_code}"

    def test_eco_score_handles_missing_advisor(self, monkeypatch):
        """GET /api/v1/hub/energy/eco-score should not crash when advisor is None."""
        from flask import Flask
        from copilot_core.hub.api import hub_bp

        app = Flask(__name__)
        app.config["COPILOT_AUTH_REQUIRED"] = False
        app.register_blueprint(hub_bp)
        client = app.test_client()

        import copilot_core.hub.api as hub_module
        monkeypatch.setattr(hub_module, "_energy_advisor", None)

        response = client.get("/api/v1/hub/energy/eco-score")
        assert response.status_code in (200, 401, 503), f"Expected 200 or 503, got {response.status_code}"


class TestPresenceAPIImport:
    """Presence API module is importable and has expected structure."""

    def test_presence_bp_importable(self):
        from copilot_core.api.v1.presence import presence_bp
        assert presence_bp is not None

    def test_presence_bp_url_prefix(self):
        from copilot_core.api.v1.presence import presence_bp
        assert "/api/v1/presence" in presence_bp.url_prefix


class TestPresenceEngineImport:
    """Presence engine modules are importable."""

    def test_presence_intelligence_engine_importable(self):
        from copilot_core.hub.presence_intelligence import PresenceIntelligenceEngine
        assert PresenceIntelligenceEngine is not None

    def test_presence_intelligence_engine_has_get_dashboard(self):
        from copilot_core.hub.presence_intelligence import PresenceIntelligenceEngine
        engine = PresenceIntelligenceEngine()
        assert hasattr(engine, "get_dashboard")

    def test_presence_intelligence_engine_has_get_heatmap(self):
        from copilot_core.hub.presence_intelligence import PresenceIntelligenceEngine
        engine = PresenceIntelligenceEngine()
        assert hasattr(engine, "get_heatmap")

    def test_presence_intelligence_engine_has_get_triggers(self):
        from copilot_core.hub.presence_intelligence import PresenceIntelligenceEngine
        engine = PresenceIntelligenceEngine()
        assert hasattr(engine, "get_triggers")