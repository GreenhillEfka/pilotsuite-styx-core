"""Contract tests for Auth, Alarm, Sensors, Search, Candidates APIs.

Verifies key API blueprints are importable and have valid url_prefix.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))


class TestAuthAPI:
    """Auth API blueprint contract."""

    def test_auth_bp_importable(self):
        from copilot_core.api.v1.auth import auth_bp
        assert auth_bp is not None

    def test_auth_url_prefix(self):
        from copilot_core.api.v1.auth import auth_bp
        assert auth_bp.url_prefix == "/api/v1/auth"


class TestAlarmAPI:
    """Alarm API blueprint contract."""

    def test_alarm_bp_importable(self):
        from copilot_core.api.v1.alarm import alarm_bp
        assert alarm_bp is not None

    def test_alarm_url_prefix(self):
        from copilot_core.api.v1.alarm import alarm_bp
        assert alarm_bp.url_prefix == "/api/v1/alarm"


class TestSensorsAPI:
    """Sensors API blueprint contract."""

    def test_sensors_bp_importable(self):
        from copilot_core.api.v1.sensors import bp as sensors_bp
        assert sensors_bp is not None

    def test_sensors_url_prefix(self):
        from copilot_core.api.v1.sensors import bp as sensors_bp
        assert sensors_bp.url_prefix == "/api/v1/sensors"


class TestCandidatesAPI:
    """Candidates API blueprint contract."""

    def test_candidates_bp_importable(self):
        from copilot_core.api.v1.candidates import bp as candidates_bp
        assert candidates_bp is not None

    def test_candidates_url_prefix(self):
        from copilot_core.api.v1.candidates import bp as candidates_bp
        # /candidates (relative — core_setup prepends /api/v1)
        assert candidates_bp.url_prefix == "/candidates"


class TestSearchAPI:
    """Search API blueprint contract."""

    def test_search_bp_importable(self):
        from copilot_core.api.v1.search import bp as search_bp
        assert search_bp is not None

    def test_search_url_prefix(self):
        from copilot_core.api.v1.search import bp as search_bp
        # /search (relative — core_setup prepends /api/v1)
        assert search_bp.url_prefix == "/search"


class TestMetricsAPI:
    """Metrics API blueprint contract."""

    def test_metrics_bp_importable(self):
        from copilot_core.api.v1.metrics import metrics_bp
        assert metrics_bp is not None

    def test_metrics_url_prefix(self):
        from copilot_core.api.v1.metrics import metrics_bp
        # None or /api/v1 — both acceptable
        assert metrics_bp.url_prefix is None or metrics_bp.url_prefix == "/api/v1"


class TestHomeKitAPI:
    """HomeKit API blueprint contract."""

    def test_homekit_bp_importable(self):
        from copilot_core.api.v1.homekit import homekit_bp
        assert homekit_bp is not None

    def test_homekit_url_prefix(self):
        from copilot_core.api.v1.homekit import homekit_bp
        assert homekit_bp.url_prefix is not None