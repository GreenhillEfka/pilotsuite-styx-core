"""Contract tests for GET /api/v1/energy/reports/generate (F2.5-A)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Bypass auth before any app imports
mock_security = MagicMock()
mock_security.require_token = lambda f: f
sys.modules["copilot_core.api.security"] = mock_security

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from flask import Blueprint
import types


def _stub_shared_app_dependencies():
    mcp_stub = types.ModuleType("copilot_core.api.v1.mcp")
    mcp_stub.bp = Blueprint("mcp_stub", __name__, url_prefix="/api/v1/mcp")
    sys.modules["copilot_core.api.v1.mcp"] = mcp_stub

    tags_stub = types.ModuleType("copilot_core.tags")
    tags_stub.TagRegistry = type("TagRegistry", (), {})
    tags_stub.create_tag_service = lambda *a, **k: None
    sys.modules["copilot_core.tags"] = tags_stub

    tags_api_stub = types.ModuleType("copilot_core.tags.api")
    tags_api_stub.init_tags_api = lambda *a, **k: None
    sys.modules["copilot_core.tags.api"] = tags_api_stub


class TestEnergyReportGenerate:
    """Verify /reports/generate endpoint returns bounded JSON shape."""

    def test_returns_bounded_report_shape(self):
        import importlib

        _stub_shared_app_dependencies()
        sys.modules.pop("main", None)

        main = importlib.import_module("main")
        app = main.create_app(options={})

        client = app.test_client()
        response = client.get("/api/v1/energy/reports/generate")

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()

        assert payload.get("ok") is True
        assert payload.get("status") == "ready"
        assert "report" in payload

        report = payload["report"]
        assert isinstance(report, dict), f"report must be dict, got {type(report)}"
        # Top-level structure must be bounded
        required_fields = (
            "report_type",
            "period_start",
            "period_end",
            "consumption",
            "costs",
            "comparison",
            "recommendations",
            "highlights",
            "device_insights",
            "report_id",
            "generated_at",
        )
        for field in required_fields:
            assert field in report, f"report missing required field: {field}"

    def test_rejects_invalid_report_type(self):
        import importlib

        _stub_shared_app_dependencies()
        sys.modules.pop("main", None)

        main = importlib.import_module("main")
        app = main.create_app(options={})

        client = app.test_client()
        response = client.get("/api/v1/energy/reports/generate?report_type=invalid")

        assert response.status_code == 400, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()
        assert "error" in payload
        assert "report_type" in payload["error"]


class TestSolarSurplusStatus:
    """Verify GET /api/v1/energy/solar-surplus/status (F2.5-B)."""

    def test_returns_surplus_status_shape(self):
        import importlib

        _stub_shared_app_dependencies()
        sys.modules.pop("main", None)

        main = importlib.import_module("main")
        app = main.create_app(options={})

        client = app.test_client()
        response = client.get("/api/v1/energy/solar-surplus/status")

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()

        assert payload.get("ok") is True
        assert "surplus" in payload
        surplus = payload["surplus"]
        required_fields = (
            "generated_at",
            "horizon_hours",
            "total_slots",
            "total_candidates",
            "recommendations_count",
            "expected_self_consumption_gain_pct",
            "expected_savings_eur",
            "expected_grid_relief_kwh",
        )
        for field in required_fields:
            assert field in surplus, f"surplus missing required field: {field}"
