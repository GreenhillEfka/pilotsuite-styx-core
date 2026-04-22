"""Sensors API Contract Tests — CORE-HARDEN-208"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1 import sensors
from unittest.mock import patch, MagicMock, AsyncMock
import copilot_core.api.security as security


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(sensors.bp)
    return app


def _make_mock_service():
    """Return a mock SensorService with all needed return values."""
    mock = MagicMock()
    # All SensorService methods are async and called via asyncio.run() in endpoints
    # Use AsyncMock so asyncio.run() gets a real coroutine
    async def mock_all_sensors(*args, **kwargs):
        return [
            {
                "entity_id": "sensor.wohnzimmer_temperature_1",
                "name": "Wohnzimmer Temperatur",
                "state": "21.5",
                "attributes": {"unit_of_measurement": "°C", "device_class": "temperature", "room": "wohnzimmer"},
                "last_updated": "2026-04-22T20:00:00+00:00",
            }
        ]
    async def mock_get_sensor(entity_id, *args, **kwargs):
        if "unknown" in entity_id:
            return None
        return {
            "entity_id": "sensor.wohnzimmer_temperature_1",
            "name": "Wohnzimmer Temperatur",
            "state": "21.5",
            "attributes": {"unit_of_measurement": "°C", "device_class": "temperature", "room": "wohnzimmer"},
            "last_updated": "2026-04-22T20:00:00+00:00",
        }
    async def mock_by_type(*args, **kwargs):
        return []
    async def mock_by_room(*args, **kwargs):
        return []
    mock.get_all_sensors = AsyncMock(side_effect=mock_all_sensors)
    mock.get_sensor = AsyncMock(side_effect=mock_get_sensor)
    mock.get_sensors_by_type = AsyncMock(side_effect=mock_by_type)
    mock.get_sensors_by_room = AsyncMock(side_effect=mock_by_room)
    return mock


def _make_mock_cache():
    """"Return a mock sensor cache with async methods."""
    mock = MagicMock()
    async def mock_get_stats(*args, **kwargs):
        return {"hits": 42, "misses": 7, "size": 49}
    async def mock_invalidate(*args, **kwargs):
        return None
    mock.get_stats = AsyncMock(side_effect=mock_get_stats)
    mock.invalidate_all = AsyncMock(side_effect=mock_invalidate)
    return mock


def _patch_auth():
    # sensors.bp imports validate_token as _validate_token via `from ... security import validate_token as _validate_token`
    return patch.object(sensors, '_validate_token', return_value=True)


# Real routes (Flask URL map confirmed):
# GET  /api/v1/sensors
# GET  /api/v1/sensors/<entity_id>
# GET  /api/v1/sensors/rooms
# GET  /api/v1/sensors/types
# GET  /api/v1/sensors/cache/stats
# POST /api/v1/sensors/cache/clear

# Real response shapes:
# GET /sensors → {status, count, cached, sensors[]}
# GET /sensors/<id> → {status, cached, sensor} or 404
# GET /rooms → {status, rooms: {room: {count, sensors[]}}}
# GET /types → {status, types: {type: {count, sensors[]}}}
# GET /cache/stats → {status, cache_type, ttl_seconds, stats}
# POST /cache/clear → {status, message}


class TestSensorsList:
    def test_get_sensors_returns_200(self):
        app = _make_app()
        with _patch_auth():
            mock_service = _make_mock_service()
            with patch.object(sensors, '_get_service', return_value=mock_service):
                client = app.test_client()
                r = client.get("/api/v1/sensors")
                assert r.status_code == 200, f"expected 200, got {r.status_code}, body={r.get_json()}"

    def test_get_sensors_returns_correct_shape(self):
        app = _make_app()
        with _patch_auth():
            mock_service = _make_mock_service()
            with patch.object(sensors, '_get_service', return_value=mock_service):
                client = app.test_client()
                r = client.get("/api/v1/sensors")
                data = r.get_json()
                assert r.status_code == 200
                assert data["status"] == "ok"
                assert "sensors" in data
                assert "count" in data

    def test_get_sensors_rejects_invalid_cache_param(self):
        app = _make_app()
        with _patch_auth():
            mock_service = _make_mock_service()
            with patch.object(sensors, '_get_service', return_value=mock_service):
                client = app.test_client()
                r = client.get("/api/v1/sensors?cache=maybe")
                assert r.status_code == 400, f"expected 400, got {r.status_code}"

    def test_get_sensors_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/sensors")
        assert r.status_code in (401, 403)


class TestSensorsSingle:
    def test_get_sensor_returns_200(self):
        app = _make_app()
        with _patch_auth():
            mock_service = _make_mock_service()
            with patch.object(sensors, '_get_service', return_value=mock_service):
                client = app.test_client()
                r = client.get("/api/v1/sensors/sensor.wohnzimmer_temperature_1")
                assert r.status_code == 200, f"expected 200, got {r.status_code}, body={r.get_json()}"

    def test_get_sensor_not_found_returns_404(self):
        app = _make_app()
        with _patch_auth():
            mock_service = _make_mock_service()
            mock_service.get_sensor.return_value = None
            with patch.object(sensors, '_get_service', return_value=mock_service):
                client = app.test_client()
                r = client.get("/api/v1/sensors/sensor.unknown_entity")
                assert r.status_code == 404, f"expected 404, got {r.status_code}"

    def test_get_sensor_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/sensors/sensor.wohnzimmer_temperature_1")
        assert r.status_code in (401, 403)


class TestSensorsRooms:
    def test_get_rooms_returns_200(self):
        app = _make_app()
        with _patch_auth():
            mock_service = _make_mock_service()
            with patch.object(sensors, '_get_service', return_value=mock_service):
                client = app.test_client()
                r = client.get("/api/v1/sensors/rooms")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_rooms_returns_correct_shape(self):
        app = _make_app()
        with _patch_auth():
            mock_service = _make_mock_service()
            with patch.object(sensors, '_get_service', return_value=mock_service):
                client = app.test_client()
                r = client.get("/api/v1/sensors/rooms")
                data = r.get_json()
                assert r.status_code == 200
                assert data["status"] == "ok"
                assert "rooms" in data

    def test_get_rooms_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/sensors/rooms")
        assert r.status_code in (401, 403)


class TestSensorsTypes:
    def test_get_types_returns_200(self):
        app = _make_app()
        with _patch_auth():
            mock_service = _make_mock_service()
            with patch.object(sensors, '_get_service', return_value=mock_service):
                client = app.test_client()
                r = client.get("/api/v1/sensors/types")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_types_returns_correct_shape(self):
        app = _make_app()
        with _patch_auth():
            mock_service = _make_mock_service()
            with patch.object(sensors, '_get_service', return_value=mock_service):
                client = app.test_client()
                r = client.get("/api/v1/sensors/types")
                data = r.get_json()
                assert r.status_code == 200
                assert data["status"] == "ok"
                assert "types" in data

    def test_get_types_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/sensors/types")
        assert r.status_code in (401, 403)


class TestSensorsCacheStats:
    def test_get_cache_stats_returns_200(self):
        app = _make_app()
        with _patch_auth():
            with patch.object(sensors, 'get_sensor_cache', return_value=_make_mock_cache()):
                client = app.test_client()
                r = client.get("/api/v1/sensors/cache/stats")
                assert r.status_code == 200, f"expected 200, got {r.status_code}, body={r.get_json()}"

    def test_get_cache_stats_returns_correct_shape(self):
        app = _make_app()
        with _patch_auth():
            with patch.object(sensors, 'get_sensor_cache', return_value=_make_mock_cache()):
                client = app.test_client()
                r = client.get("/api/v1/sensors/cache/stats")
                data = r.get_json()
                assert r.status_code == 200
                assert data["status"] == "ok"
                assert data["cache_type"] == "sensor"
                assert "ttl_seconds" in data

    def test_get_cache_stats_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/sensors/cache/stats")
        assert r.status_code in (401, 403)


class TestSensorsCacheClear:
    def test_post_cache_clear_returns_200(self):
        app = _make_app()
        with _patch_auth():
            with patch.object(sensors, 'get_sensor_cache', return_value=_make_mock_cache()):
                client = app.test_client()
                r = client.post("/api/v1/sensors/cache/clear")
                assert r.status_code == 200, f"expected 200, got {r.status_code}, body={r.get_json()}"

    def test_post_cache_clear_with_entity_id(self):
        app = _make_app()
        with _patch_auth():
            with patch.object(sensors, 'get_sensor_cache', return_value=_make_mock_cache()):
                client = app.test_client()
                r = client.post("/api/v1/sensors/cache/clear", json={"entity_id": "sensor.wohnzimmer_temperature_1"})
                assert r.status_code == 200

    def test_post_cache_clear_rejects_non_object_body(self):
        app = _make_app()
        with _patch_auth():
            with patch.object(sensors, 'get_sensor_cache', return_value=_make_mock_cache()):
                client = app.test_client()
                r = client.post("/api/v1/sensors/cache/clear", json=["not", "a", "dict"])
                assert r.status_code == 400

    def test_post_cache_clear_rejects_non_string_entity_id(self):
        app = _make_app()
        with _patch_auth():
            with patch.object(sensors, 'get_sensor_cache', return_value=_make_mock_cache()):
                client = app.test_client()
                r = client.post("/api/v1/sensors/cache/clear", json={"entity_id": 123})
                assert r.status_code == 400

    def test_post_cache_clear_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/sensors/cache/clear")
        assert r.status_code in (401, 403)


class TestSensorsAllAuth:
    def test_all_endpoints_require_authorization(self):
        app = _make_app()
        client = app.test_client()
        endpoints = [
            ("GET", "/api/v1/sensors"),
            ("GET", "/api/v1/sensors/sensor.wohnzimmer_temperature_1"),
            ("GET", "/api/v1/sensors/rooms"),
            ("GET", "/api/v1/sensors/types"),
            ("GET", "/api/v1/sensors/cache/stats"),
            ("POST", "/api/v1/sensors/cache/clear"),
        ]
        for method, path, *rest in endpoints:
            body = rest[0] if rest else None
            r = client.open(path, method=method, json=body)
            assert r.status_code in (401, 403), f"{method} {path}: expected 401/403, got {r.status_code}"
