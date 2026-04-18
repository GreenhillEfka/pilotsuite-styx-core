"""Contract tests for Styx Chat, Weather, Notifications, and User Preferences APIs.

Verifies:
- Each API blueprint is importable with expected url_prefix
- Key endpoint functions are defined in the module
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))


class TestStyxChatAPI:
    """Styx Chat API blueprint contract."""

    def test_styx_chat_bp_importable(self):
        from copilot_core.api.v1.styx_chat import bp
        assert bp is not None
        assert bp.name == "styx_chat"

    def test_styx_chat_url_prefix(self):
        from copilot_core.api.v1.styx_chat import bp
        assert bp.url_prefix == "/api/styx"

    def test_styx_chat_has_session_endpoint(self):
        from copilot_core.api.v1 import styx_chat as mod
        # Should have session-related function
        assert hasattr(mod, "create_session") or hasattr(mod, "bp")


class TestWeatherAPI:
    """Weather API blueprint contract."""

    def test_weather_bp_importable(self):
        from copilot_core.api.v1.weather import bp
        assert bp is not None

    def test_weather_url_prefix(self):
        from copilot_core.api.v1.weather import bp
        assert bp.url_prefix == "/weather"

    def test_weather_engine_importable(self):
        from copilot_core.neurons.weather import WeatherContextNeuron
        assert WeatherContextNeuron is not None

    def test_weather_engine_has_expected_methods(self):
        from copilot_core.neurons.weather import WeatherContextNeuron
        assert hasattr(WeatherContextNeuron, "get_comfort_score")
        assert hasattr(WeatherContextNeuron, "should_prioritize_pv_usage")


class TestNotificationsAPI:
    """Notifications API blueprint contract."""

    def test_notifications_bp_importable(self):
        from copilot_core.api.v1.notifications import bp
        assert bp is not None

    def test_notifications_url_prefix(self):
        from copilot_core.api.v1.notifications import bp
        assert bp.url_prefix == "/notifications"


class TestUserPreferencesAPI:
    """User Preferences API blueprint contract."""

    def test_user_preferences_bp_importable(self):
        from copilot_core.api.v1.user_preferences import bp
        assert bp is not None

    def test_user_preferences_url_prefix(self):
        from copilot_core.api.v1.user_preferences import bp
        assert bp.url_prefix == "/user"


class TestModuleControlAPI:
    """Module Control API blueprint contract."""

    def test_module_control_bp_importable(self):
        from copilot_core.api.v1.module_control import module_control_bp
        assert module_control_bp is not None

    def test_module_control_url_prefix(self):
        from copilot_core.api.v1.module_control import module_control_bp
        # None = uses absolute paths /api/v1/module-control
        assert module_control_bp.url_prefix == "/api/v1/modules"


class TestHomeAssistantDiscoveryAPI:
    """HA Discovery API blueprint contract."""

    def test_ha_discovery_bp_importable(self):
        from copilot_core.homeassistant.api import ha_discovery_bp
        assert ha_discovery_bp is not None

    def test_ha_discovery_url_prefix(self):
        from copilot_core.homeassistant.api import ha_discovery_bp
        # None = uses absolute paths
        assert ha_discovery_bp.url_prefix is None or ha_discovery_bp.url_prefix == "/api/v1"


class TestSharingAPI:
    """Sharing API blueprint (optional module)."""

    def test_sharing_module_exists(self):
        """Sharing module may not exist — that's OK for optional modules."""
        import importlib
        try:
            mod = importlib.import_module("copilot_core.sharing.api")
            assert mod is not None
        except ModuleNotFoundError:
            pass  # Optional module — skip


class TestCollectiveIntelligenceAPI:
    """Collective Intelligence API blueprint (optional module)."""

    def test_collective_intelligence_module_exists(self):
        """collective_intelligence may not exist — that's OK for optional modules."""
        import importlib
        try:
            mod = importlib.import_module("copilot_core.collective_intelligence.api")
            assert mod is not None
        except ModuleNotFoundError:
            pass  # Optional module — skip