import pytest
from flask import Flask


def test_sensor_modules_returns_flat_structure(monkeypatch) -> None:
    """Sensor modules endpoint returns flat, HA-compatible structure."""
    from copilot_core.api.v1.sensors import sensors_bp, ModuleRegistry
    
    # Mock registry
    class MockRegistry:
        def get_all_states(self):
            return {"presence": "active", "light": "learning"}
    
    monkeypatch.setattr(ModuleRegistry, "get_instance", MockRegistry)
    
    app = Flask(__name__)
    app.register_blueprint(sensors_bp)
    client = app.test_client()
    
    response = client.get("/api/v1/sensors/modules")
    
    assert response.status_code == 200
    data = response.get_json()
    assert "sensors" in data
    assert data["count"] == 2
    
    sensors_by_id = {s["attributes"]["module_id"]: s for s in data["sensors"]}
    assert "presence" in sensors_by_id
    assert sensors_by_id["presence"]["state"] == "active"
    assert sensors_by_id["presence"]["unique_id"] == "pilotsuite_module_presence"


def test_sensor_modules_empty_registry(monkeypatch) -> None:
    """Sensor modules handles empty registry gracefully."""
    from copilot_core.api.v1.sensors import sensors_bp, ModuleRegistry
    
    class MockRegistry:
        def get_all_states(self):
            return {}
    
    monkeypatch.setattr(ModuleRegistry, "get_instance", MockRegistry)
    
    app = Flask(__name__)
    app.register_blueprint(sensors_bp)
    client = app.test_client()
    
    response = client.get("/api/v1/sensors/modules")
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["sensors"] == []
    assert data["count"] == 0


def test_sensor_system_returns_503_without_monitor(monkeypatch) -> None:
    """Sensor system returns 503 when SystemHealthMonitor unavailable."""
    from copilot_core.api.v1.sensors import sensors_bp
    
    # Import fails -> 503
    monkeypatch.setattr("copilot_core.api.v1.sensors.SystemHealthMonitor", None)
    
    app = Flask(__name__)
    app.register_blueprint(sensors_bp)
    client = app.test_client()
    
    response = client.get("/api/v1/sensors/system")
    
    # Should return 503 when service unavailable
    assert response.status_code == 503
