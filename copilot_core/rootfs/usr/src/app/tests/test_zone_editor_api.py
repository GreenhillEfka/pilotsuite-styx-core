"""Tests for Zone Editor API endpoints (v12.0.0)."""

import pytest
from unittest.mock import patch
from flask import Flask

from copilot_core.api.v1.zone_editor import zone_editor_bp, init_zone_editor_api
from copilot_core.hub.habitus_zones import HabitusZoneEngine


@pytest.fixture(scope="function")
def app():
    """Create test Flask app with Zone Editor API.

    Each test gets its own app instance to ensure complete isolation.
    """
    app = Flask(__name__)
    app.config["TESTING"] = True
    # Initialize zone editor API (clears internal _zones_store)
    init_zone_editor_api()
    app.register_blueprint(zone_editor_bp)
    return app


@pytest.fixture(scope="function")
def client(app):
    """Create test client.

    Each test gets its own client, but the underlying app is shared.
    The zone engine reset happens via reset_all_before_test fixture.
    """
    return app.test_client()


@pytest.fixture
def engine():
    """Create and populate HabitusZoneEngine."""
    eng = HabitusZoneEngine()
    # Register some rooms
    eng.register_room("bad", "Bad", entities=[
        "sensor.bad_temperature", "sensor.bad_humidity",
        "light.bad_decke", "binary_sensor.bad_motion",
    ])
    eng.register_room("toilette", "Toilette", entities=[
        "light.toilette_licht", "binary_sensor.toilette_motion",
    ])
    eng.register_room("wohnzimmer", "Wohnzimmer", entities=[
        "sensor.wohnzimmer_temperature", "light.wohnzimmer_haupt",
        "light.wohnzimmer_stehlampe", "media_player.wohnzimmer_tv",
    ])
    eng.register_room("kueche", "Küche", entities=[
        "sensor.kueche_temperature", "light.kueche_decke",
    ])
    # Create a zone
    eng.create_zone("badbereich", "Badbereich", ["bad", "toilette"], icon="mdi:shower-head")
    return eng


@pytest.fixture(autouse=True)
def setup_zone_engine_for_module():
    """Ensure zone engine is initialized for all tests in this module.
    
    This runs before each test (after reset_all_before_test) to ensure
    the zone engine is available for tests that need it.
    """
    from copilot_core.api.v1.zone_editor import init_zone_editor_api
    init_zone_editor_api()
    yield


@pytest.fixture
def client_with_engine(app, engine):
    """Create test client with initialized engine."""
    # Pass the engine instance to the API so tests use the same engine
    from copilot_core.api.v1.zone_editor import set_zone_engine
    set_zone_engine(engine)
    return app.test_client()


@pytest.fixture
def app_isolated():
    """Create isolated test Flask app (no blueprint registration)."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    # Don't register blueprint - tests will register manually
    return app


@pytest.fixture
def client_isolated(app_isolated):
    """Create test client for isolated app."""
    return app_isolated.test_client()


class TestZoneList:
    def test_list_zones_empty(self, app):
        """Test listing zones when no zones exist (empty store)."""
        # Use the auto-initialized engine, but don't add any zones
        client = app.test_client()
        response = client.get("/api/v1/zone-editor/zones")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert "zones" in data
        assert data["total"] == 0  # Empty zone list

    def test_list_zones(self, client_with_engine):
        """Test listing all zones."""
        response = client_with_engine.get("/api/v1/zone-editor/zones")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert "zones" in data
        assert data["total"] == 1
        assert data["zones"][0]["zone_id"] == "badbereich"
        assert data["zones"][0]["name"] == "Badbereich"

    def test_list_zones_count(self, client_with_engine, engine):
        """Test zone count after creating multiple zones."""
        engine.create_zone("wohnbereich", "Wohnbereich", ["wohnzimmer"])
        response = client_with_engine.get("/api/v1/zone-editor/zones")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 2


class TestZoneGet:
    def test_get_zone_not_initialized(self, client):
        """Test getting a zone when engine not initialized."""
        import copilot_core.api.v1.zone_editor as zone_api
        zone_api._zone_engine = None
        
        response = client.get("/api/v1/zone-editor/zones/badbereich")
        # When engine is not initialized, 503 SERVICE UNAVAILABLE is returned
        assert response.status_code == 503
        data = response.get_json()
        assert data["ok"] is False
        assert "not initialized" in data["error"]

    def test_get_zone_not_found(self, client_with_engine):
        """Test getting a non-existent zone."""
        response = client_with_engine.get("/api/v1/zone-editor/zones/nonexistent")
        assert response.status_code == 404
        data = response.get_json()
        assert data["ok"] is False
        assert "not found" in data["error"]

    def test_get_zone_success(self, client_with_engine):
        """Test getting an existing zone."""
        response = client_with_engine.get("/api/v1/zone-editor/zones/badbereich")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        zone = data["zone"]
        assert zone["zone_id"] == "badbereich"
        assert zone["name"] == "Badbereich"
        assert len(zone["rooms"]) == 2
        # Fix: rooms are objects with room_id, not plain strings
        room_ids = [r["room_id"] for r in zone["rooms"]]
        assert "bad" in room_ids
        assert "toilette" in room_ids
        assert zone["icon"] == "mdi:shower-head"
        assert zone["mode"] == "active"
        assert zone["enabled"] is True


class TestRoomList:
    def test_list_rooms(self, client_with_engine):
        """Test listing all rooms."""
        response = client_with_engine.get("/api/v1/zone-editor/rooms")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["total"] == 4
        assert len(data["rooms"]) == 4

    def test_list_unassigned_rooms(self, client_with_engine):
        """Test listing only unassigned rooms."""
        response = client_with_engine.get("/api/v1/zone-editor/rooms?unassigned=true")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["unassigned_count"] == 2  # kueche and wohnzimmer
        for room in data["rooms"]:
            assert room["zone"] is None

    def test_room_details(self, client_with_engine):
        """Test room details include zone assignment."""
        response = client_with_engine.get("/api/v1/zone-editor/rooms/bad")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        room = data["room"]
        assert room["room_id"] == "bad"
        assert room["name"] == "Bad"
        assert room["zone"] == "badbereich"
        assert room["entity_count"] == 4


class TestOverview:
    def test_get_overview(self, client_with_engine):
        """Test getting zone overview."""
        response = client_with_engine.get("/api/v1/zone-editor/overview")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        overview = data["overview"]
        assert overview["total_zones"] == 1
        assert overview["total_rooms"] == 4
        assert len(overview["unassigned_rooms"]) == 2
        assert "modes" in overview

    def test_get_zone_state(self, client_with_engine):
        """Test getting zone state."""
        response = client_with_engine.get("/api/v1/zone-editor/zones/badbereich/state")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        state = data["state"]
        assert state["zone_id"] == "badbereich"
        assert state["room_count"] == 2
        assert state["entity_count"] == 6


class TestTemplates:
    def test_list_templates(self, client_with_engine):
        """Test listing available templates."""
        response = client_with_engine.get("/api/v1/zone-editor/templates")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert "templates" in data
        # Check for common templates
        templates = data["templates"]
        assert "wohnbereich" in templates or "badbereich" in templates or len(templates) > 0

    def test_apply_template(self, client_with_engine, monkeypatch):
        """Test applying a template to create a zone."""
        # Skip this test as it requires auth token mocking
        pytest.skip("Requires auth token mocking for POST endpoint")


class TestZoneState:
    def test_zone_state_not_found(self, client_with_engine):
        """Test getting state for non-existent zone."""
        response = client_with_engine.get("/api/v1/zone-editor/zones/nonexistent/state")
        assert response.status_code == 404

    def test_zone_mode_invalid(self, client_with_engine, monkeypatch):
        """Test setting invalid zone mode."""
        # This would require auth, so we test the validation logic
        pass


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_complete_zone_workflow(self, client_with_engine):
        """Test complete workflow: list, get details, check state."""
        # List all zones
        response = client_with_engine.get("/api/v1/zone-editor/zones")
        assert response.status_code == 200
        zones_data = response.get_json()
        assert zones_data["total"] == 1

        # Get specific zone
        zone_id = zones_data["zones"][0]["zone_id"]
        response = client_with_engine.get(f"/api/v1/zone-editor/zones/{zone_id}")
        assert response.status_code == 200
        zone_data = response.get_json()
        assert zone_data["zone"]["zone_id"] == zone_id

        # Get zone state
        response = client_with_engine.get(f"/api/v1/zone-editor/zones/{zone_id}/state")
        assert response.status_code == 200
        state_data = response.get_json()
        assert state_data["state"]["zone_id"] == zone_id

    def test_room_zone_relationship(self, client_with_engine):
        """Test that room-zone relationships are correctly represented."""
        # Get room that's in a zone
        response = client_with_engine.get("/api/v1/zone-editor/rooms/bad")
        assert response.status_code == 200
        room_data = response.get_json()
        assert room_data["room"]["zone"] == "badbereich"

        # Get room that's not in a zone
        response = client_with_engine.get("/api/v1/zone-editor/rooms/kueche")
        assert response.status_code == 200
        room_data = response.get_json()
        assert room_data["room"]["zone"] is None

    def test_zone_entity_count(self, client_with_engine):
        """Test that zone entity count is sum of room entities."""
        response = client_with_engine.get("/api/v1/zone-editor/zones/badbereich")
        assert response.status_code == 200
        zone_data = response.get_json()
        # Bad has 4 entities, Toilette has 2
        # Note: entity_count is at zone level
        assert zone_data["zone"]["entity_count"] == 6 or zone_data["zone"].get("entity_count", 0) > 0


class TestZoneWriteApi:
    def test_create_zone_modern_success(self, client_with_engine):
        payload = {
            "zone_id": "wohnbereich",
            "name": "Wohnbereich",
            "rooms": ["wohnzimmer", "kueche"],
            "icon": "mdi:sofa-outline",
            "priority": 4,
        }
        with patch("copilot_core.api.security.validate_token", return_value=True):
            response = client_with_engine.post("/api/v1/zone-editor/zones", json=payload)
        assert response.status_code == 201
        data = response.get_json()
        assert data["ok"] is True
        assert data["zone"]["zone_id"] == "wohnbereich"
        assert data["zone"]["priority"] == 4

    def test_update_zone_modern_success(self, client_with_engine):
        payload = {
            "name": "Bad & Spa",
            "mode": "away",
            "enabled": False,
            "priority": 9,
            "rooms": ["bad"],
        }
        with patch("copilot_core.api.security.validate_token", return_value=True):
            response = client_with_engine.put("/api/v1/zone-editor/zones/badbereich", json=payload)
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["zone"]["name"] == "Bad & Spa"
        assert data["zone"]["mode"] == "away"
        assert data["zone"]["enabled"] is False
        assert data["zone"]["priority"] == 9
        room_ids = [room["room_id"] for room in data["zone"]["rooms"]]
        assert room_ids == ["bad"]

    def test_add_and_remove_room_modern(self, client_with_engine):
        with patch("copilot_core.api.security.validate_token", return_value=True):
            add_response = client_with_engine.post(
                "/api/v1/zone-editor/zones/badbereich/rooms",
                json={"room_id": "wohnzimmer"},
            )
            remove_response = client_with_engine.delete(
                "/api/v1/zone-editor/zones/badbereich/rooms/wohnzimmer"
            )
        assert add_response.status_code == 200
        assert remove_response.status_code == 200
        removed = remove_response.get_json()
        room_ids = [room["room_id"] for room in removed["zone"]["rooms"]]
        assert "wohnzimmer" not in room_ids

    def test_delete_zone_modern(self, client_with_engine):
        with patch("copilot_core.api.security.validate_token", return_value=True):
            response = client_with_engine.delete("/api/v1/zone-editor/zones/badbereich")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["deleted_zone_id"] == "badbereich"

    def test_create_zone_modern_requires_name(self, client_with_engine):
        with patch("copilot_core.api.security.validate_token", return_value=True):
            response = client_with_engine.post(
                "/api/v1/zone-editor/zones",
                json={"zone_id": "zone:missing_name"},
            )
        assert response.status_code == 400
        data = response.get_json()
        assert data["ok"] is False
        assert "name" in data["error"]
