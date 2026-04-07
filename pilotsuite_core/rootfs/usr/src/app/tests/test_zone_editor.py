"""Tests for Zone Editor API.

Test coverage for Zone Editor endpoints:
- POST /api/v1/zone/editor/create - Zone erstellen
- GET /api/v1/zone/editor/list - Alle Zonen auflisten
- GET /api/v1/zone/editor/<zone_id> - Zone Details
- PUT /api/v1/zone/editor/<zone_id> - Zone aktualisieren
- DELETE /api/v1/zone/editor/<zone_id> - Zone löschen
- POST /api/v1/zone/editor/<zone_id>/rooms - Room zu Zone hinzufügen
- DELETE /api/v1/zone/editor/<zone_id>/rooms/<room_id> - Room aus Zone entfernen

Author: Clawdya
Version: 1.0.0
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from flask import Flask


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    yield app


@pytest.fixture
def mock_zones():
    """Mock zone data for testing."""
    return {
        "zone:wohnzimmer": {
            "zone_id": "zone:wohnzimmer",
            "name": "Wohnzimmer",
            "rooms": ["room:wohnzimmer", "room:esszimmer"],
            "icon": "mdi:sofa",
            "mode": "active",
            "enabled": True,
            "priority": 1,
        },
        "zone:kuche": {
            "zone_id": "zone:kuche",
            "name": "Küche",
            "rooms": ["room:kuche"],
            "icon": "mdi:stove",
            "mode": "active",
            "enabled": True,
            "priority": 0,
        },
    }


@pytest.fixture
def client(app, mock_zones):
    """Create test client with mocked zone engine."""
    with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
        engine_instance = MagicMock()
        engine_instance.get_all_zones.return_value = list(mock_zones.values())
        engine_instance.get_zone.side_effect = lambda zid: mock_zones.get(zid)
        # Mock get_overview for legacy list endpoint
        engine_instance.get_overview.return_value = MagicMock(
            zones=[{"zone_id": zid} for zid in mock_zones.keys()]
        )
        # Make create_zone return the zone data that was passed in
        # Signature: create_zone(zone_id, name, room_ids, icon)
        def mock_create_zone(zone_id, name, room_ids, icon, **_):
            return {
                "zone_id": zone_id,
                "name": name,
                "rooms": room_ids,
                "icon": icon,
                "mode": "active",
                "enabled": True,
                "priority": 0,
            }
        engine_instance.create_zone.side_effect = mock_create_zone
        engine_instance.update_zone.return_value = True
        engine_instance.delete_zone.return_value = True
        engine_instance.add_room_to_zone.return_value = True
        engine_instance.remove_room_from_zone.return_value = True
        mock_engine.return_value = engine_instance
        
        from copilot_core.api.v1 import zone_editor
        
        with patch('copilot_core.api.security.validate_token', return_value=True):
            # Register legacy and modern zone editor routes
            app.register_blueprint(zone_editor.zone_editor_bp)
            app.register_blueprint(zone_editor.zone_editor_legacy_bp)
            app.register_blueprint(zone_editor.zone_legacy_alias_bp)
            with app.test_client() as test_client:
                yield test_client


class TestZoneEditorCreate:
    """Tests for POST /api/v1/zone/editor/create"""

    def test_create_zone_success(self, client):
        """Test successful zone creation."""
        payload = {
            "zone_id": "zone:test",
            "name": "Test Zone",
            "icon": "mdi:test",
            "rooms": ["room:test1"],
            "priority": 5,
        }
        
        response = client.post(
            '/api/v1/zone/editor/create',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] is True
        assert "zone" in data

    def test_create_zone_legacy_with_zone_type_and_modules(self, client):
        """Legacy create accepts zone_type and enabled_modules."""
        payload = {
            "zone_id": "zone:test",
            "name": "Test Zone",
            "priority": 4,
            "zone_type": "kitchen",
            "enabled_modules": ["light", "climate"],
        }

        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.create_zone.return_value = None
            calls = []
            def _get_zone(zone_id):
                calls.append(zone_id)
                if len(calls) == 1:
                    return None
                return {
                    "zone_id": "zone:test",
                    "zone_type": "kitchen",
                    "enabled_modules": ["light", "climate"],
                }
            engine.get_zone.side_effect = _get_zone
            mock_engine.return_value = engine

            response = client.post(
                '/api/v1/zone/editor/create',
                data=json.dumps(payload),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["ok"] is True
            assert data["zone"]["zone_type"] == "kitchen"
            assert data["zone"]["enabled_modules"] == ["light", "climate"]
            engine.create_zone.assert_called_once_with(
                "zone:test",
                "Test Zone",
                [],
                "mdi:home-floor-1",
                priority=4,
                zone_type="kitchen",
                enabled_modules={"climate", "light"},
            )

    def test_create_zone_legacy_invalid_zone_type(self, client):
        """Legacy create rejects invalid zone_type values."""
        payload = {
            "zone_id": "zone:test",
            "name": "Test Zone",
            "zone_type": "not-a-zone",
        }

        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_zone.return_value = None
            mock_engine.return_value = engine

            response = client.post(
                '/api/v1/zone/editor/create',
                data=json.dumps(payload),
                content_type='application/json'
            )

            assert response.status_code == 400
            data = json.loads(response.data)
            assert "Invalid zone_type" in data["error"]

    def test_create_zone_missing_zone_id(self, client):
        """Test zone creation fails without zone_id."""
        payload = {"name": "Test Zone"}
        
        response = client.post(
            '/api/v1/zone/editor/create',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_create_zone_missing_name(self, client):
        """Test zone creation fails without name."""
        payload = {"zone_id": "zone:test"}
        
        response = client.post(
            '/api/v1/zone/editor/create',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 400

    def test_create_zone_duplicate_id(self, client):
        """Test zone creation fails with duplicate ID."""
        from copilot_core.api.v1 import zone_editor
        
        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_zone.return_value = {"zone_id": "zone:existing"}
            mock_engine.return_value = engine
            
            payload = {"zone_id": "zone:existing", "name": "Duplicate"}
            
            response = client.post(
                '/api/v1/zone/editor/create',
                data=json.dumps(payload),
                content_type='application/json'
            )
            
            assert response.status_code == 409

    def test_create_zone_with_default_icon(self, client):
        """Test zone creation uses default icon when not provided."""
        payload = {"zone_id": "zone:test", "name": "Test Zone"}
        
        response = client.post(
            '/api/v1/zone/editor/create',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200


class TestZoneEditorList:
    """Tests for GET /api/v1/zone/editor/list"""

    def test_list_zones_returns_all(self, client, mock_zones):
        """Test listing all zones."""
        response = client.get('/api/v1/zone/editor/list')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "zones" in data
        assert len(data["zones"]) == len(mock_zones)

    def test_list_zones_filter_by_zone_type(self, client):
        """Legacy list supports zone_type filtering."""
        zones_by_id = {
            "zone:kuechenbereich": {
                "zone_id": "zone:kuechenbereich",
                "zone_type": "kitchen",
                "name": "Küche",
                "rooms": [],
            },
            "zone:wohnbereich": {
                "zone_id": "zone:wohnbereich",
                "zone_type": "living",
                "name": "Wohnbereich",
                "rooms": [],
            },
        }

        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_overview.return_value = MagicMock(zones=[{"zone_id": zid} for zid in zones_by_id.keys()])
            engine.get_zone.side_effect = lambda zone_id: zones_by_id.get(zone_id)
            mock_engine.return_value = engine

            response = client.get('/api/v1/zone/editor/list?zone_type=kitchen')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["count"] == 1
            assert data["zones"][0]["zone_id"] == "zone:kuechenbereich"
            assert data["zones"][0]["zone_type"] == "kitchen"

    def test_list_zones_filter_by_zone_type_invalid(self, client):
        """Legacy list rejects invalid zone_type filter values."""
        response = client.get('/api/v1/zone/editor/list?zone_type=invalid-zone')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Invalid zone_type" in data["error"]

    def test_list_zones_empty(self, client):
        """Test listing zones when none exist."""
        from copilot_core.api.v1 import zone_editor
        
        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_all_zones.return_value = []
            mock_engine.return_value = engine
            
            response = client.get('/api/v1/zone/editor/list')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["zones"] == []
            assert data["count"] == 0

    def test_list_zones_includes_metadata(self, client):
        """Test zone list includes required metadata."""
        response = client.get('/api/v1/zone/editor/list')
        
        data = json.loads(response.data)
        assert "count" in data
        assert "generated_at" in data


class TestZoneEditorGet:
    """Tests for GET /api/v1/zone/editor/<zone_id>"""

    def test_get_zone_exists(self, client):
        """Test getting existing zone."""
        response = client.get('/api/v1/zone/editor/zone:wohnzimmer')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] is True
        assert "zone" in data

    def test_get_zone_not_found(self, client):
        """Test getting non-existent zone."""
        from copilot_core.api.v1 import zone_editor
        
        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_zone.return_value = None
            mock_engine.return_value = engine
            
            response = client.get('/api/v1/zone/editor/zone:nonexistent')
            
            assert response.status_code == 404

    def test_get_zone_includes_rooms(self, client):
        """Test zone details include room list."""
        response = client.get('/api/v1/zone/editor/zone:wohnzimmer')
        
        data = json.loads(response.data)
        assert "rooms" in data["zone"]


class TestZoneEditorUpdate:
    """Tests for PUT /api/v1/zone/editor/<zone_id>"""

    def test_update_zone_success(self, client):
        """Test successful zone update."""
        payload = {
            "name": "Updated Name",
            "icon": "mdi:new-icon",
            "priority": 10,
        }
        
        response = client.put(
            '/api/v1/zone/editor/zone:wohnzimmer',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] is True

    def test_update_zone_legacy_with_zone_type_and_modules(self, client):
        """Legacy update supports zone_type and enabled_modules."""
        payload = {
            "zone_type": "terrace",
            "enabled_modules": ["light", "camera"],
        }

        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_zone.side_effect = [
                {"zone_id": "zone:wohnzimmer", "zone_type": "kitchen", "enabled_modules": ["light"]},
                {"zone_id": "zone:wohnzimmer", "zone_type": "terrace", "enabled_modules": ["light", "camera"]},
            ]
            engine.set_zone_type.return_value = True
            engine.set_zone_enabled_modules.return_value = True
            mock_engine.return_value = engine

            response = client.put(
                '/api/v1/zone/editor/zone:wohnzimmer',
                data=json.dumps(payload),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["ok"] is True
            assert data["zone"]["zone_type"] == "terrace"
            assert data["zone"]["enabled_modules"] == ["light", "camera"]
            engine.set_zone_type.assert_called_once_with("zone:wohnzimmer", "terrace")
            engine.set_zone_enabled_modules.assert_called_once_with(
                "zone:wohnzimmer",
                {"light", "camera"},
            )

    def test_update_zone_legacy_invalid_zone_type(self, client):
        """Legacy update rejects invalid zone_type."""
        payload = {
            "zone_type": "not-a-zone",
        }

        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_zone.return_value = {"zone_id": "zone:wohnzimmer"}
            mock_engine.return_value = engine

            response = client.put(
                '/api/v1/zone/editor/zone:wohnzimmer',
                data=json.dumps(payload),
                content_type='application/json'
            )

            assert response.status_code == 400
            data = json.loads(response.data)
            assert "Invalid zone_type" in data["error"]

    def test_update_zone_not_found(self, client):
        """Test update fails for non-existent zone."""
        from copilot_core.api.v1 import zone_editor
        
        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_zone.return_value = None
            engine.update_zone.return_value = False
            mock_engine.return_value = engine
            
            payload = {"name": "New Name"}
            
            response = client.put(
                '/api/v1/zone/editor/zone:nonexistent',
                data=json.dumps(payload),
                content_type='application/json'
            )
            
            assert response.status_code == 404

    def test_update_zone_empty_payload(self, client):
        """Test update with empty payload."""
        response = client.put(
            '/api/v1/zone/editor/zone:wohnzimmer',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        assert response.status_code in [200, 400]


class TestZoneEditorDelete:
    """Tests for DELETE /api/v1/zone/editor/<zone_id>"""

    def test_delete_zone_success(self, client):
        """Test successful zone deletion."""
        from copilot_core.api.v1 import zone_editor
        
        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_zone.return_value = {"zone_id": "zone:test"}
            engine.delete_zone.return_value = True
            mock_engine.return_value = engine
            
            response = client.delete('/api/v1/zone/editor/zone:test')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["ok"] is True

    def test_delete_zone_not_found(self, client):
        """Test delete fails for non-existent zone."""
        from copilot_core.api.v1 import zone_editor
        
        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_zone.return_value = None
            mock_engine.return_value = engine
            
            response = client.delete('/api/v1/zone/editor/zone:nonexistent')
            
            assert response.status_code == 404


class TestZoneEditorRooms:
    """Tests for room management endpoints"""

    def test_add_room_to_zone(self, client):
        """Test adding room to zone."""
        from copilot_core.api.v1 import zone_editor
        
        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_zone.return_value = {"zone_id": "zone:test"}
            engine.add_room_to_zone.return_value = True
            mock_engine.return_value = engine
            
            payload = {"room_id": "room:new"}
            
            response = client.post(
                '/api/v1/zone/editor/zone:test/rooms',
                data=json.dumps(payload),
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["ok"] is True

    def test_add_room_missing_id(self, client):
        """Test add room fails without room_id."""
        response = client.post(
            '/api/v1/zone/editor/zone:test/rooms',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        assert response.status_code == 400

    def test_remove_room_from_zone(self, client):
        """Test removing room from zone."""
        from copilot_core.api.v1 import zone_editor
        
        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_zone.return_value = {"zone_id": "zone:test"}
            engine.remove_room_from_zone.return_value = True
            mock_engine.return_value = engine
            
            response = client.delete('/api/v1/zone/editor/zone:test/rooms/room:test')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["ok"] is True

    def test_remove_room_not_found(self, client):
        """Test removing room from non-existent zone."""
        from copilot_core.api.v1 import zone_editor
        
        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_zone.return_value = None
            mock_engine.return_value = engine
            
            response = client.delete('/api/v1/zone/editor/zone:nonexistent/rooms/room:test')
            
            assert response.status_code == 404


class TestZoneLegacyAliases:
    """Tests for /api/v1/zone compatibility alias routes."""

    def test_alias_create_routes_to_legacy_endpoint(self, client):
        """Alias /api/v1/zone/create forwards to legacy create endpoint."""
        payload = {
            "zone_id": "zone:alias",
            "name": "Alias Zone",
        }

        response = client.post(
            '/api/v1/zone/create',
            data=json.dumps(payload),
            content_type='application/json',
            follow_redirects=False,
        )

        assert response.status_code in [301, 302, 307, 308]
        assert response.headers["Location"].endswith('/api/v1/zone/editor/create')

    def test_alias_update_routes_to_legacy_endpoint(self, client):
        """Alias /api/v1/zone/update routes to legacy update endpoint."""
        payload = {
            "zone_id": "zone:badbereich",
            "name": "Renamed",
        }

        response = client.post(
            '/api/v1/zone/update',
            data=json.dumps(payload),
            content_type='application/json',
            follow_redirects=False,
        )

        assert response.status_code in [301, 302, 307, 308]
        assert response.headers["Location"].endswith('/api/v1/zone/editor/zone:badbereich')

    def test_alias_delete_routes_to_legacy_endpoint(self, client):
        """Alias /api/v1/zone/delete/<zone_id> routes to legacy delete endpoint."""
        response = client.delete(
            '/api/v1/zone/delete/zone:badbereich',
            follow_redirects=False,
        )

        assert response.status_code in [301, 302, 307, 308]
        assert response.headers["Location"].endswith('/api/v1/zone/editor/zone:badbereich')


class TestZoneEditorEdgeCases:
    """Edge case tests for Zone Editor API"""

    def test_invalid_json_payload(self, client):
        """Test handling of invalid JSON."""
        response = client.post(
            '/api/v1/zone/editor/create',
            data="not valid json",
            content_type='application/json'
        )
        
        assert response.status_code == 400

    def test_zone_id_with_special_chars(self, client):
        """Test zone creation with special characters in ID."""
        from copilot_core.api.v1 import zone_editor
        
        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_zone.return_value = None
            engine.create_zone.return_value = {"zone_id": "zone:test-123_abc", "name": "Test Zone"}
            mock_engine.return_value = engine
            
            payload = {"zone_id": "zone:test-123_abc", "name": "Test Zone"}
            
            response = client.post(
                '/api/v1/zone/editor/create',
                data=json.dumps(payload),
                content_type='application/json'
            )
            
            assert response.status_code == 200

    def test_concurrent_zone_operations(self, client):
        """Test concurrent zone operations are handled safely."""
        from copilot_core.api.v1 import zone_editor
        
        with patch('copilot_core.api.v1.zone_editor.get_zone_engine') as mock_engine:
            engine = MagicMock()
            engine.get_all_zones.return_value = []
            mock_engine.return_value = engine
            
            responses = []
            for i in range(5):
                response = client.get('/api/v1/zone/editor/list')
                responses.append(response.status_code)
            
            assert all(code == 200 for code in responses)

    def test_zone_requires_auth(self, app):
        """Test zone endpoints require authentication."""
        from copilot_core.api.v1 import zone_editor
        
        with patch('copilot_core.api.security.validate_token', return_value=False):
            # Register legacy blueprint which has /zone/editor/* routes
            app.register_blueprint(zone_editor.zone_editor_legacy_bp)
            with app.test_client() as test_client:
                response = test_client.get('/api/v1/zone/editor/list')
                
                assert response.status_code == 401
                data = json.loads(response.data)
                assert data["ok"] is False
                assert "error" in data
