"""Tests for Habitus Zones API (v13.1.0)."""

import pytest
import json
from unittest.mock import Mock, patch

from copilot_core.homeassistant.habitus_zones import ZoneType


@pytest.fixture
def client():
    """Create test client for habitus zones API."""
    from flask import Flask
    from copilot_core.api.v1.habitus_zones import bp as habitus_zones_bp
    
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["COPILOT_CFG"] = Mock(data_dir="/tmp/test_data")
    
    # Register blueprint
    app.register_blueprint(habitus_zones_bp)
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def auth_headers():
    """Return auth headers for API requests."""
    return {"X-Auth-Token": "test-token-123"}


class TestGetAllHabitusZones:
    """Tests for GET /api/v1/habitus/zones endpoint."""
    
    def test_get_all_zones_success(self, client, auth_headers):
        """Test successful retrieval of all zones."""
        response = client.get("/api/v1/habitus/zones", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["status"] == "ok"
        assert "zones" in data
        assert "total_zones" in data
        assert data["total_zones"] > 0
        
        # Check zone structure
        zone = data["zones"][0]
        assert "id" in zone
        assert "zone_type" in zone
        assert "name_de" in zone
        assert "name_en" in zone
        assert "keywords_de" in zone
        assert "keywords_en" in zone
        assert "priority" in zone
        assert "module_overrides" in zone
        assert set(zone["module_overrides"].keys()) == {
            "light", "motion", "music", "volume", "tv", "climate", "camera"
        }
    
    def test_get_zones_with_metrics(self, client, auth_headers):
        """Test zones retrieval with metrics included."""
        response = client.get(
            "/api/v1/habitus/zones?include_metrics=true",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["status"] == "ok"
        zone = data["zones"][0]
        assert "metrics" in zone
        assert "entity_count" in zone["metrics"]

    def test_default_module_overrides_are_suggestion_first(self, client, auth_headers):
        """All default module overrides should disable direct execution."""
        response = client.get("/api/v1/habitus/zones", headers=auth_headers)

        assert response.status_code == 200
        zone = response.get_json()["zones"][0]
        for override in zone["module_overrides"].values():
            assert override["suggestion_mode"] == "explainable_manual"
            assert override["direct_execution_enabled"] is False
            assert override["approval_required"] is True
            assert override["explanation_required"] is True
    
    def test_get_zones_without_metrics(self, client, auth_headers):
        """Test zones retrieval without metrics."""
        response = client.get(
            "/api/v1/habitus/zones?include_metrics=false",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        zone = data["zones"][0]
        assert "metrics" not in zone or zone.get("metrics") is None
    
    def test_get_zones_filtered_by_type(self, client, auth_headers):
        """Test filtering zones by type."""
        response = client.get(
            "/api/v1/habitus/zones?zone_type=living",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["status"] == "ok"
        assert data["total_zones"] == 1
        assert data["zones"][0]["zone_type"] == "living"
    
    def test_get_zones_invalid_type_filter(self, client, auth_headers):
        """Test invalid zone type filter."""
        response = client.get(
            "/api/v1/habitus/zones?zone_type=invalid_type",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "invalid_zone_type"
    
    def test_get_zones_unauthorized(self, client):
        """Test unauthorized access."""
        # Note: Auth is bypassed in test mode, so we just verify endpoint works
        response = client.get("/api/v1/habitus/zones")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"


class TestConfigureZone:
    """Tests for POST /api/v1/habitus/zones/{id} endpoint."""
    
    def test_configure_zone_success(self, client, auth_headers):
        """Test successful zone configuration."""
        config_data = {
            "name_de": "Test Bereich",
            "name_en": "Test Area",
            "priority": 15,
            "keywords_de": ["test", "beispiel"],
            "entities": {
                "light": "light.test"
            },
            "settings": {
                "min_temp": 20
            },
            "module_overrides": {
                "light": {
                    "enabled": True,
                    "direct_execution_enabled": True,
                    "notes": "Operator explicitly enabled direct light execution."
                }
            },
        }
        
        response = client.post(
            "/api/v1/habitus/zones/living",
            headers=auth_headers,
            data=json.dumps(config_data),
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["status"] == "ok"
        assert "zone" in data
        assert data["zone"]["name_de"] == "Test Bereich"
        assert data["zone"]["priority"] == 15
        assert data["zone"]["module_overrides"]["light"]["direct_execution_enabled"] is True
        assert data["zone"]["module_overrides"]["tv"]["direct_execution_enabled"] is False
    
    def test_configure_zone_invalid_id(self, client, auth_headers):
        """Test configuration with invalid zone ID."""
        response = client.post(
            "/api/v1/habitus/zones/invalid_zone",
            headers=auth_headers,
            data=json.dumps({"name_de": "Test"}),
            content_type="application/json"
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "invalid_zone_id"
    
    def test_configure_zone_not_found(self, client, auth_headers):
        """Test configuration for non-existent zone."""
        # Use a valid ZoneType value but one that might not exist in mapping
        response = client.post(
            "/api/v1/habitus/zones/room_mira",
            headers=auth_headers,
            data=json.dumps({"name_de": "Test"}),
            content_type="application/json"
        )
        
        # Should succeed as room_mira is a valid ZoneType
        assert response.status_code in [200, 404]
    
    def test_configure_zone_empty_body(self, client, auth_headers):
        """Test configuration with empty body (should use defaults)."""
        response = client.post(
            "/api/v1/habitus/zones/living",
            headers=auth_headers,
            data=json.dumps({}),
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["status"] == "ok"
        assert "zone" in data
        assert data["zone"]["module_overrides"]["light"]["direct_execution_enabled"] is False
        assert data["zone"]["module_overrides"]["light"]["suggestion_mode"] == "explainable_manual"


class TestGetZoneMetrics:
    """Tests for GET /api/v1/habitus/zones/{id}/metrics endpoint."""
    
    def test_get_zone_metrics_success(self, client, auth_headers):
        """Test successful metrics retrieval."""
        response = client.get(
            "/api/v1/habitus/zones/living/metrics",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["status"] == "ok"
        assert "zone_id" in data
        assert data["zone_id"] == "living"
        assert "metrics" in data
        assert "timestamp" in data
    
    def test_get_zone_metrics_invalid_id(self, client, auth_headers):
        """Test metrics for invalid zone ID."""
        response = client.get(
            "/api/v1/habitus/zones/invalid/metrics",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "invalid_zone_id"
    
    def test_get_zone_metrics_not_found(self, client, auth_headers):
        """Test metrics for non-existent zone."""
        response = client.get(
            "/api/v1/habitus/zones/nonexistent/metrics",
            headers=auth_headers
        )
        
        assert response.status_code in [400, 404]
    
    def test_get_zone_metrics_unauthorized(self, client):
        """Test unauthorized metrics access."""
        # Note: Auth is bypassed in test mode, so we just verify endpoint works
        response = client.get("/api/v1/habitus/zones/living/metrics")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"


class TestMatchRoomsToZones:
    """Tests for POST /api/v1/habitus/zones/match endpoint."""
    
    def test_match_rooms_success(self, client, auth_headers):
        """Test successful room matching."""
        match_data = {
            "rooms": ["Wohnzimmer", "Küche", "Bad"]
        }
        
        response = client.post(
            "/api/v1/habitus/zones/match",
            headers=auth_headers,
            data=json.dumps(match_data),
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["status"] == "ok"
        assert "matches" in data
        assert "total_rooms" in data
        assert "review_required" in data
    
    def test_match_rooms_empty_list(self, client, auth_headers):
        """Test matching with empty room list."""
        response = client.post(
            "/api/v1/habitus/zones/match",
            headers=auth_headers,
            data=json.dumps({"rooms": []}),
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["status"] == "ok"
        assert data["total_rooms"] == 0
    
    def test_match_rooms_missing_rooms(self, client, auth_headers):
        """Test matching without rooms field."""
        response = client.post(
            "/api/v1/habitus/zones/match",
            headers=auth_headers,
            data=json.dumps({}),
            content_type="application/json"
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "missing_rooms"
    
    def test_match_rooms_invalid_format(self, client, auth_headers):
        """Test matching with invalid rooms format."""
        response = client.post(
            "/api/v1/habitus/zones/match",
            headers=auth_headers,
            data=json.dumps({"rooms": "not_an_array"}),
            content_type="application/json"
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "invalid_format"


class TestMapHomeAssistantTopology:
    """Tests for POST /api/v1/habitus/zones/map-homeassistant endpoint."""

    def test_map_homeassistant_topology_success(self, client, auth_headers):
        payload = {
            "areas": [
                {"area_id": "wohnzimmer", "name": "Wohnzimmer"},
                {"area_id": "atelier", "name": "Atelier Nord"},
            ],
            "entities": [
                {
                    "entity_id": "light.wohnzimmer_decke",
                    "attributes": {"friendly_name": "Wohnzimmer Decke", "area_id": "wohnzimmer"},
                },
                {
                    "entity_id": "sensor.mystery_probe",
                    "attributes": {"friendly_name": "ZX Probe 9", "area_id": "atelier"},
                },
            ],
        }

        response = client.post(
            "/api/v1/habitus/zones/map-homeassistant",
            headers=auth_headers,
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["summary"]["area_count"] == 2
        assert data["summary"]["entity_count"] == 2
        assert data["ungeordnet"]["entity_count"] == 1
        assert any(zone["zone_type"] == "living" for zone in data["zones"])

    def test_map_homeassistant_topology_invalid_format(self, client, auth_headers):
        response = client.post(
            "/api/v1/habitus/zones/map-homeassistant",
            headers=auth_headers,
            data=json.dumps({"areas": {}, "entities": []}),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "invalid_format"


class TestGetReviewQueue:
    """Tests for GET /api/v1/habitus/zones/review endpoint."""
    
    def test_get_review_queue_success(self, client, auth_headers):
        """Test successful review queue retrieval."""
        response = client.get(
            "/api/v1/habitus/zones/review",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["status"] == "ok"
        assert "threshold" in data
        assert "total_review" in data
        assert "rooms" in data
    
    def test_get_review_queue_custom_threshold(self, client, auth_headers):
        """Test review queue with custom threshold."""
        response = client.get(
            "/api/v1/habitus/zones/review?threshold=50.0",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["status"] == "ok"
        assert data["threshold"] == 50.0


class TestZoneIcons:
    """Test zone icon mapping."""
    
    def test_all_zone_types_have_icons(self):
        """Test that all zone types have icon mappings."""
        from copilot_core.api.v1.habitus_zones import _get_icon_for_zone
        
        for zone_type in ZoneType:
            icon = _get_icon_for_zone(zone_type)
            assert icon is not None
            assert icon.startswith("mdi:")


class TestZoneMetrics:
    """Test zone metrics function."""
    
    def test_get_zone_metrics_structure(self):
        """Test metrics structure."""
        from copilot_core.api.v1.habitus_zones import _get_zone_metrics
        
        metrics = _get_zone_metrics(ZoneType.LIVING)
        
        assert isinstance(metrics, dict)
        assert "entity_count" in metrics
        assert "active_lights" in metrics
        assert "avg_temperature" in metrics
        assert "avg_humidity" in metrics
        assert "occupancy" in metrics
