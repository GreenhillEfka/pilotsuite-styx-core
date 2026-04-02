"""API contract tests for Zone Presence Hold / Release Surface (Slice 39).

Tests verify:
1. POST /presence/zones/<zone_id>/hold - set hold
2. GET /presence/zones/<zone_id>/hold - get hold
3. DELETE /presence/zones/<zone_id>/hold - release hold
4. GET /presence/zones/<zone_id>/state - get effective hold state
5. GET /presence/zones/holds - get summary
6. GET /presence/zones/holds/<hold_id> - get single hold
"""
import pytest
import json

from flask import Flask
from copilot_core.core.zone_presence_hold import get_zone_presence_hold_store, ZoneHoldState
from copilot_core.api.v1.zone_presence_hold import zone_presence_hold_bp


@pytest.fixture(autouse=True)
def clear_store():
    """Clear hold store before each test."""
    store = get_zone_presence_hold_store()
    store.clear()
    yield


@pytest.fixture
def app():
    """Create test app with zone presence hold blueprint."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(zone_presence_hold_bp)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestZonePresenceHoldAPI:
    """Test zone presence hold API endpoints."""
    
    def test_set_hold_force_on(self, client):
        """Test POST /presence/zones/<zone_id>/hold with force_on."""
        response = client.post(
            "/presence/zones/zone:living/hold",
            data=json.dumps({
                "hold_state": "force_on",
                "reason": "manual",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["contract"] == "ZonePresenceHoldV1"
        assert data["zone_id"] == "zone:living"
        assert data["hold_state"] == "force_on"
        assert data["reason"] == "manual"
        assert data["is_active"] is True
    
    def test_set_hold_force_off(self, client):
        """Test POST /presence/zones/<zone_id>/hold with force_off."""
        response = client.post(
            "/presence/zones/zone:bedroom/hold",
            data=json.dumps({
                "hold_state": "force_off",
                "reason": "testing",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["hold_state"] == "force_off"
        assert data["reason"] == "testing"
    
    def test_set_hold_auto(self, client):
        """Test POST /presence/zones/<zone_id>/hold with auto."""
        response = client.post(
            "/presence/zones/zone:kitchen/hold",
            data=json.dumps({
                "hold_state": "auto",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["hold_state"] == "auto"
    
    def test_set_hold_with_duration(self, client):
        """Test POST /presence/zones/<zone_id>/hold with duration_seconds."""
        response = client.post(
            "/presence/zones/zone:living/hold",
            data=json.dumps({
                "hold_state": "force_on",
                "duration_seconds": 3600,
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["expires_at"] is not None
        assert data["is_expired"] is False
    
    def test_set_hold_invalid_state(self, client):
        """Test POST /presence/zones/<zone_id>/hold with invalid state."""
        response = client.post(
            "/presence/zones/zone:living/hold",
            data=json.dumps({
                "hold_state": "invalid_state",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_set_hold_missing_zone(self, client):
        """Test POST /presence/zones/<zone_id>/hold without zone in path."""
        response = client.post(
            "/presence/zones//hold",
            data=json.dumps({
                "hold_state": "force_on",
            }),
            content_type="application/json",
        )
        
        # Flask will handle this as 404 for missing route param
        assert response.status_code in [400, 404]
    
    def test_get_hold(self, client):
        """Test GET /presence/zones/<zone_id>/hold."""
        # Set hold first
        client.post(
            "/presence/zones/zone:living/hold",
            data=json.dumps({
                "hold_state": "force_on",
            }),
            content_type="application/json",
        )
        
        # Get hold
        response = client.get("/presence/zones/zone:living/hold")
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["contract"] == "ZonePresenceHoldV1"
        assert data["zone_id"] == "zone:living"
        assert data["hold_state"] == "force_on"
    
    def test_get_hold_not_found(self, client):
        """Test GET /presence/zones/<zone_id>/hold for zone without hold."""
        response = client.get("/presence/zones/zone:nonexistent/hold")
        
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
    
    def test_release_hold(self, client):
        """Test DELETE /presence/zones/<zone_id>/hold."""
        # Set hold first
        client.post(
            "/presence/zones/zone:bedroom/hold",
            data=json.dumps({
                "hold_state": "force_on",
            }),
            content_type="application/json",
        )
        
        # Release hold
        response = client.delete("/presence/zones/zone:bedroom/hold")
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["released"] is True
        assert data["zone_id"] == "zone:bedroom"
    
    def test_release_nonexistent_hold(self, client):
        """Test DELETE /presence/zones/<zone_id>/hold for zone without hold."""
        response = client.delete("/presence/zones/zone:nonexistent/hold")
        
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
    
    def test_get_hold_state(self, client):
        """Test GET /presence/zones/<zone_id>/state."""
        # Set hold first
        client.post(
            "/presence/zones/zone:living/hold",
            data=json.dumps({
                "hold_state": "force_on",
            }),
            content_type="application/json",
        )
        
        # Get state
        response = client.get("/presence/zones/zone:living/state")
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["zone_id"] == "zone:living"
        assert data["hold_state"] == "force_on"
        assert data["is_enforced"] is True
    
    def test_get_hold_state_no_hold(self, client):
        """Test GET /presence/zones/<zone_id>/state without hold."""
        response = client.get("/presence/zones/zone:empty/state")
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["zone_id"] == "zone:empty"
        assert data["hold_state"] == "auto"
        assert data["is_enforced"] is False
    
    def test_get_holds_summary(self, client):
        """Test GET /presence/zones/holds."""
        # Create multiple holds
        client.post(
            "/presence/zones/zone:living/hold",
            data=json.dumps({"hold_state": "force_on"}),
            content_type="application/json",
        )
        client.post(
            "/presence/zones/zone:bedroom/hold",
            data=json.dumps({"hold_state": "force_off"}),
            content_type="application/json",
        )
        
        response = client.get("/presence/zones/holds")
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["contract"] == "ZonePresenceHoldSummaryV1"
        assert data["total_holds"] == 2
        assert data["active_holds"] == 2
        assert data["force_on_holds"] == 1
        assert data["force_off_holds"] == 1
    
    def test_get_holds_with_zone_filter(self, client):
        """Test GET /presence/zones/holds?zone_id=..."""
        client.post(
            "/presence/zones/zone:living/hold",
            data=json.dumps({"hold_state": "force_on"}),
            content_type="application/json",
        )
        client.post(
            "/presence/zones/zone:bedroom/hold",
            data=json.dumps({"hold_state": "force_off"}),
            content_type="application/json",
        )
        
        response = client.get("/presence/zones/holds?zone_id=zone:living")
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["total_holds"] == 1
        assert data["by_zone"]["zone:living"] == "force_on"
    
    def test_get_holds_with_revision_delta(self, client):
        """Test GET /presence/zones/holds?since_revision=..."""
        # Initial state
        client.post(
            "/presence/zones/zone:living/hold",
            data=json.dumps({"hold_state": "force_on"}),
            content_type="application/json",
        )
        
        response1 = client.get("/presence/zones/holds")
        data1 = response1.get_json()
        rev1 = data1["hold_revision"]
        
        # No changes
        response2 = client.get(f"/presence/zones/holds?since_revision={rev1}")
        data2 = response2.get_json()
        assert data2["has_changes"] is False
        
        # New hold
        client.post(
            "/presence/zones/zone:bedroom/hold",
            data=json.dumps({"hold_state": "force_off"}),
            content_type="application/json",
        )
        
        response3 = client.get(f"/presence/zones/holds?since_revision={rev1}")
        data3 = response3.get_json()
        assert data3["has_changes"] is True
    
    def test_get_hold_by_id(self, client):
        """Test GET /presence/zones/holds/<hold_id>."""
        # Set hold first
        response = client.post(
            "/presence/zones/zone:living/hold",
            data=json.dumps({"hold_state": "force_on"}),
            content_type="application/json",
        )
        hold_id = response.get_json()["hold_id"]
        
        # Get by ID
        response = client.get(f"/presence/zones/holds/{hold_id}")
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["hold_id"] == hold_id
        assert data["zone_id"] == "zone:living"
    
    def test_get_hold_by_id_not_found(self, client):
        """Test GET /presence/zones/holds/<hold_id> for nonexistent hold."""
        response = client.get("/presence/zones/holds/hold_nonexistent")
        
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
    
    def test_update_existing_hold(self, client):
        """Test updating an existing hold."""
        # Initial hold
        client.post(
            "/presence/zones/zone:kitchen/hold",
            data=json.dumps({
                "hold_state": "force_on",
                "reason": "initial",
            }),
            content_type="application/json",
        )
        
        # Update hold
        response = client.post(
            "/presence/zones/zone:kitchen/hold",
            data=json.dumps({
                "hold_state": "force_off",
                "reason": "updated",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["hold_state"] == "force_off"
        assert data["reason"] == "updated"
    
    def test_release_hold_with_reason(self, client):
        """Test DELETE /presence/zones/<zone_id>/hold?reason=..."""
        # Set hold first
        client.post(
            "/presence/zones/zone:living/hold",
            data=json.dumps({"hold_state": "force_on"}),
            content_type="application/json",
        )
        
        # Release with custom reason
        response = client.delete("/presence/zones/zone:living/hold?reason=test_release")
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["released"] is True
        
        # Verify hold shows released reason
        response = client.get("/presence/zones/zone:living/hold")
        hold_data = response.get_json()
        assert hold_data["released"] is True
        assert hold_data["released_reason"] == "test_release"
