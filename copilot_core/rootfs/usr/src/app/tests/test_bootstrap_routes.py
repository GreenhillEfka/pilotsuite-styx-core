"""Bootstrap route regression tests for main/core_setup wiring."""

from __future__ import annotations

import importlib

from flask import Flask

from copilot_core.core_setup import register_blueprints


def test_register_blueprints_keeps_core_and_hub_routes_available():
    """Regression: register_blueprints must not fail on local-shadowed names."""
    app = Flask(__name__)
    register_blueprints(app, {"config": {}})

    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/v1/modules/" in routes
    assert "/api/v1/hub/zones" in routes
    assert "/chat/status" in routes
    assert "/v1/models" in routes


def test_main_exposes_status_and_capabilities_compat_endpoints():
    """HA integration expects /api/v1/status and /api/v1/capabilities."""
    main = importlib.import_module("main")
    client = main.app.test_client()

    status = client.get("/api/v1/status")
    assert status.status_code == 200
    status_json = status.get_json()
    assert status_json["ok"] is True
    assert "version" in status_json

    caps = client.get("/api/v1/capabilities")
    assert caps.status_code == 200
    caps_json = caps.get_json()
    assert caps_json["ok"] is True
    assert isinstance(caps_json.get("modules"), dict)
