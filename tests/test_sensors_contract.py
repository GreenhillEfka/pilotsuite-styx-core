"""Sensor API Contract Tests — PilotSuite Core Slice 369+"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1 import sensors as sensors_api


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(sensors_api.bp)
    return app


def test_get_sensors_rejects_invalid_cache_param(monkeypatch):
    """GET /api/v1/sensors rejects invalid cache= query values."""
    monkeypatch.setattr(sensors_api, "_validate_token", lambda r: True)
    app = _make_app()
    client = app.test_client()

    for bad in ("yes", "no", "1", "0", "null", "   "):
        r = client.get(f"/api/v1/sensors?cache={bad}")
        assert r.status_code == 400, f"cache={bad!r} should be 400"
        payload = r.get_json()
        assert "cache" in payload.get("message", "").lower()


def test_get_sensors_accepts_valid_cache_true(monkeypatch):
    """GET /api/v1/sensors accepts cache=true."""
    monkeypatch.setattr(sensors_api, "_validate_token", lambda r: True)
    app = _make_app()
    client = app.test_client()
    r = client.get("/api/v1/sensors?cache=true")
    assert r.status_code == 200, f"cache=true should be 200, got {r.status_code}"


def test_get_sensors_accepts_valid_cache_false(monkeypatch):
    """GET /api/v1/sensors accepts cache=false."""
    monkeypatch.setattr(sensors_api, "_validate_token", lambda r: True)
    app = _make_app()
    client = app.test_client()
    r = client.get("/api/v1/sensors?cache=false")
    assert r.status_code == 200, f"cache=false should be 200, got {r.status_code}"


def test_get_sensor_rejects_whitespace_entity_id(monkeypatch):
    """GET /api/v1/sensors/<entity_id> rejects whitespace-only entity_id."""
    monkeypatch.setattr(sensors_api, "_validate_token", lambda r: True)
    app = _make_app()
    client = app.test_client()
    # Flask URL routing means truly blank paths go to 401; test whitespace-only that still matches route
    r = client.get("/api/v1/sensors/%20%20%20")
    assert r.status_code == 400, f"whitespace entity_id should be 400, got {r.status_code}"


def test_get_sensor_rejects_invalid_cache_param(monkeypatch):
    """GET /api/v1/sensors/<entity_id> rejects invalid cache= values."""
    monkeypatch.setattr(sensors_api, "_validate_token", lambda r: True)
    app = _make_app()
    client = app.test_client()

    for bad in ("yes", "no", "1"):
        r = client.get(f"/api/v1/sensors/sensor.wohnzimmer_temperature_1?cache={bad}")
        assert r.status_code == 400, f"cache={bad!r} should be 400"


def test_clear_cache_accepts_empty_body(monkeypatch):
    """POST /api/v1/sensors/cache/clear accepts empty body."""
    monkeypatch.setattr(sensors_api, "_validate_token", lambda r: True)
    app = _make_app()
    client = app.test_client()
    r = client.post("/api/v1/sensors/cache/clear", json={})
    assert r.status_code == 200, f"empty body should be 200, got {r.status_code}"


def test_clear_cache_rejects_non_object_body(monkeypatch):
    """POST /api/v1/sensors/cache/clear rejects non-object JSON bodies."""
    monkeypatch.setattr(sensors_api, "_validate_token", lambda r: True)
    app = _make_app()
    client = app.test_client()
    # Note: json=None sends no body (not a JSON null), treated as empty {}
    for bad, content in (
        ("string body", "application/json"),
        (["list"], "application/json"),
        (123, "application/json"),
    ):
        r = client.post(
            "/api/v1/sensors/cache/clear",
            data=str(bad).encode(),
            content_type=content,
        )
        assert r.status_code == 400, f"body={bad!r} should be 400, got {r.status_code}"
        payload = r.get_json()
        assert "object" in payload.get("message", "").lower()


def test_clear_cache_rejects_non_string_entity_id(monkeypatch):
    """POST /api/v1/sensors/cache/clear rejects non-string entity_id."""
    monkeypatch.setattr(sensors_api, "_validate_token", lambda r: True)
    app = _make_app()
    client = app.test_client()

    for bad in (123, ["entity"], {"key": "value"}):
        r = client.post("/api/v1/sensors/cache/clear", json={"entity_id": bad})
        assert r.status_code == 400, f"entity_id={bad!r} should be 400"
