"""Contract tests for the Calendar API.

Verifies:
- calendar_bp is importable and has expected routes
- Module gracefully handles missing HA (no crash, returns empty/informative result)
- All endpoints are registered on the blueprint
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))


class TestCalendarModuleImport:
    """Calendar module is importable and has correct structure."""

    def test_calendar_bp_importable(self):
        from copilot_core.api.v1.calendar import calendar_bp
        assert calendar_bp is not None
        assert calendar_bp.name == "calendar"

    def test_bp_url_prefix(self):
        from copilot_core.api.v1.calendar import calendar_bp
        assert calendar_bp.url_prefix == "/api/v1/calendar"


class TestCalendarRoutes:
    """Calendar blueprint has the expected route handlers."""

    def test_has_list_calendars_route(self):
        from copilot_core.api.v1.calendar import calendar_bp
        routes = [str(r) for r in calendar_bp.url_map.iter_rules()] if hasattr(calendar_bp, 'url_map') else []
        # Routes are defined via decorators, check endpoint names
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(calendar_bp)
        route_paths = [str(r) for r in app.url_map.iter_rules()]
        assert "/api/v1/calendar" in route_paths

    def test_has_today_route(self):
        from flask import Flask
        from copilot_core.api.v1.calendar import calendar_bp
        app = Flask(__name__)
        app.register_blueprint(calendar_bp)
        route_paths = [str(r) for r in app.url_map.iter_rules()]
        assert "/api/v1/calendar/today" in route_paths

    def test_has_upcoming_route(self):
        from flask import Flask
        from copilot_core.api.v1.calendar import calendar_bp
        app = Flask(__name__)
        app.register_blueprint(calendar_bp)
        route_paths = [str(r) for r in app.url_map.iter_rules()]
        assert "/api/v1/calendar/upcoming" in route_paths

    def test_today_and_upcoming_are_get_routes(self):
        from flask import Flask
        from copilot_core.api.v1.calendar import calendar_bp
        app = Flask(__name__)
        app.register_blueprint(calendar_bp)
        rules = {str(r): r.methods for r in app.url_map.iter_rules()
                 if str(r) in ("/api/v1/calendar/today", "/api/v1/calendar/upcoming")}
        for path, methods in rules.items():
            assert "GET" in methods, f"{path} should accept GET"


class TestCalendarBackendGracefulDegradation:
    """Calendar module handles missing HA gracefully."""

    def test_get_ha_headers_returns_tuple(self):
        from copilot_core.api.v1.calendar import _get_ha_headers
        result = _get_ha_headers()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_fetch_calendar_entities_returns_list_on_error(self):
        """When HA is unavailable, _fetch_calendar_entities returns empty list."""
        from copilot_core.api.v1.calendar import _fetch_calendar_entities
        result = _fetch_calendar_entities()
        # Should return a list even when HA is unavailable (no crash)
        assert isinstance(result, list)

    def test_event_cache_is_dict(self):
        from copilot_core.api.v1.calendar import _event_cache
        assert isinstance(_event_cache, dict)

    def test_cache_ttl_is_positive_int(self):
        from copilot_core.api.v1.calendar import CACHE_TTL
        assert isinstance(CACHE_TTL, int)
        assert CACHE_TTL > 0