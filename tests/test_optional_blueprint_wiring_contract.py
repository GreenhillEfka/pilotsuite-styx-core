"""Startup wiring coverage for optional-dependency-hardened blueprints."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.core_setup import register_blueprints  # noqa: E402


EXPECTED_OPTIONAL_ROUTES = {
    "/api/v1/anomaly/model/status",
    "/api/v1/calendar",
    "/api/v1/entity-assignment/suggestions",
    "/api/v1/homekit/status",
    "/api/v1/mcp/status",
    "/api/v1/onyx/status",
    "/api/v1/scenes",
    "/api/v1/synapse/feed",
    "/api/v1/styx/stt",
    "/api/v1/styx/voice/status",
    "/api/v1/weather/",
    "/api/v1/zone/health",
}


def test_optional_dependency_hardened_blueprints_remain_wired_in_core_setup() -> None:
    app = Flask(__name__)
    register_blueprints(app, {})

    rules = {str(rule) for rule in app.url_map.iter_rules()}
    missing = sorted(route for route in EXPECTED_OPTIONAL_ROUTES if route not in rules)

    assert not missing, "Missing optional blueprint routes: " + ", ".join(missing)
