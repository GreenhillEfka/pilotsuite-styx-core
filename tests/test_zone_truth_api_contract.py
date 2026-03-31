"""Contract tests for Zone Truth Store API endpoints."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import os

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)

from flask import Flask

from copilot_core.api.v1.zone_automation import (
    init_zone_automation_api,
    get_zone_truth_zones,
    get_zone_truth_zone,
    get_zone_truth_entities,
    get_zone_truth_revision,
    get_zone_truth_archetypes,
)
from copilot_core.hub.habitus_zones import HabitusZoneEngine
from copilot_core.hub.zone_automation import ZoneAutomationController
from copilot_core.storage.zone_truth import ZoneTruthStore, reset_zone_truth_store


def _make_test_app(controller, zone_engine):
    """Create test Flask app with zone automation blueprint."""
    init_zone_automation_api(controller, zone_engine)
    
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(
        __import__("copilot_core.api.v1.zone_automation", fromlist=["zone_automation_bp"]).zone_automation_bp
    )
    return app


class TestZoneTruthApi:
    """Tests for Zone Truth Store API endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        reset_zone_truth_store()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_path = os.path.join(self.temp_dir.name, "zone_truth.json")
        
        self.controller = ZoneAutomationController()
        self.zone_engine = HabitusZoneEngine()
        self.store = ZoneTruthStore(persist=True, storage_path=self.storage_path)
        
        # Pre-populate store with test data
        self.store.create_zone(
            zone_id="wohnzimmer",
            name="Wohnzimmer",
            zone_type="living",
            icon="mdi:sofa",
            priority=10,
            enabled_modules={"light", "motion"},
        )
        self.store.add_entity("wohnzimmer", "light.wohnzimmer_hauptlicht", "lights")
        self.store.add_entity("wohnzimmer", "sensor.wohnzimmer_temp", "sensors")
        
        self.store.create_zone(
            zone_id="kitchen",
            name="Küche",
            zone_type="kitchen",
            enabled_modules={"light", "climate"},
        )
        self.store.add_entity("kitchen", "light.kitchen_ceiling", "lights")
        
        self.app = _make_test_app(self.controller, self.zone_engine)

    def teardown_method(self):
        """Clean up test fixtures."""
        reset_zone_truth_store()
        self.temp_dir.cleanup()

    def test_get_zone_truth_zones_returns_all_zones(self) -> None:
        """Test GET /api/v1/zone-automation/truth/zones returns all zones."""
        with self.app.test_client() as client:
            response = client.get("/api/v1/zone-automation/truth/zones")
            data = response.get_json()
            
            assert response.status_code == 200
            assert data["ok"] is True
            assert "zones" in data
            assert data["summary"]["zone_count"] == 2
            assert data["summary"]["entity_count"] == 3

    def test_get_zone_truth_zones_compact_mode(self) -> None:
        """Test compact mode omits entity details."""
        with self.app.test_client() as client:
            response = client.get("/api/v1/zone-automation/truth/zones?compact=true")
            data = response.get_json()
            
            assert response.status_code == 200
            assert data["summary"]["compact"] is True
            for zone in data["zones"]:
                assert "entities" not in zone
                assert "entity_count" in zone

    def test_get_zone_truth_zones_delta_query(self) -> None:
        """Test delta query returns only changed zones."""
        with self.app.test_client() as client:
            # Get initial state
            response = client.get("/api/v1/zone-automation/truth/zones")
            initial = response.get_json()
            initial_revision = initial["summary"]["revision"]
            
            # Make a change
            self.store.add_entity("wohnzimmer", "light.wohnzimmer_stehlampe", "lights")
            
            # Query deltas
            response = client.get(
                f"/api/v1/zone-automation/truth/zones?since={initial_revision}&deltas=true"
            )
            data = response.get_json()
            
            assert response.status_code == 200
            assert len(data["zones"]) == 1
            assert data["delta"]["enabled"] is True

    def test_get_zone_truth_zone_returns_single_zone(self) -> None:
        """Test GET /api/v1/zone-automation/truth/zones/<zone_id>."""
        with self.app.test_client() as client:
            response = client.get("/api/v1/zone-automation/truth/zones/wohnzimmer")
            data = response.get_json()
            
            assert response.status_code == 200
            assert data["ok"] is True
            assert "zone" in data
            assert data["zone"]["zone_id"] == "wohnzimmer"
            assert data["zone"]["name"] == "Wohnzimmer"
            assert data["zone"]["zone_type"] == "living"

    def test_get_zone_truth_zone_not_found(self) -> None:
        """Test 404 for non-existent zone."""
        with self.app.test_client() as client:
            response = client.get("/api/v1/zone-automation/truth/zones/nonexistent")
            data = response.get_json()
            
            assert response.status_code == 404
            assert data["ok"] is False
            assert "error" in data

    def test_get_zone_truth_entities_groups_by_role(self) -> None:
        """Test GET /api/v1/zone-automation/truth/zones/<zone_id>/entities."""
        with self.app.test_client() as client:
            response = client.get("/api/v1/zone-automation/truth/zones/wohnzimmer/entities")
            data = response.get_json()
            
            assert response.status_code == 200
            assert data["ok"] is True
            assert "entities_by_role" in data
            assert "lights" in data["entities_by_role"]
            assert "sensors" in data["entities_by_role"]
            assert len(data["entities_by_role"]["lights"]) == 1
            assert len(data["entities_by_role"]["sensors"]) == 1

    def test_get_zone_truth_revision_returns_history(self) -> None:
        """Test GET /api/v1/zone-automation/truth/revision."""
        with self.app.test_client() as client:
            response = client.get("/api/v1/zone-automation/truth/revision")
            data = response.get_json()
            
            assert response.status_code == 200
            assert data["ok"] is True
            assert "current_revision" in data
            assert "history" in data
            assert len(data["history"]) > 0
            assert data["history"][0]["revision"] >= 1

    def test_get_zone_truth_revision_filtered_by_zone(self) -> None:
        """Test revision history filtered by zone_id."""
        with self.app.test_client() as client:
            response = client.get("/api/v1/zone-automation/truth/revision?zone_id=wohnzimmer")
            data = response.get_json()
            
            assert response.status_code == 200
            # Should only have revisions for wohnzimmer
            for rev in data["history"]:
                assert rev["zone_id"] == "wohnzimmer"

    def test_get_zone_truth_archetypes_empty(self) -> None:
        """Test GET /api/v1/zone-automation/truth/archetypes when empty."""
        with self.app.test_client() as client:
            response = client.get("/api/v1/zone-automation/truth/archetypes")
            data = response.get_json()
            
            assert response.status_code == 200
            assert data["ok"] is True
            assert "archetypes" in data
            assert data["count"] == 0

    def test_get_zone_truth_archetypes_with_registered(self) -> None:
        """Test archetypes endpoint with registered archetypes."""
        from copilot_core.storage.zone_truth import ZoneArchetypeV1
        
        archetype = ZoneArchetypeV1(
            zone_type="living",
            name_template="{name} Bereich",
            default_modules={"light", "motion"},
        )
        self.store.register_archetype(archetype)
        
        with self.app.test_client() as client:
            response = client.get("/api/v1/zone-automation/truth/archetypes")
            data = response.get_json()
            
            assert response.status_code == 200
            assert data["count"] == 1
            assert data["archetypes"][0]["zone_type"] == "living"

    def test_sync_definitions_writes_to_truth_store(self) -> None:
        """Test that sync-definitions endpoint writes to ZoneTruthStore."""
        from copilot_core.api.v1.zone_automation import sync_zone_definitions
        
        payload = {
            "source": "ha",
            "zones": [
                {
                    "zone_id": "bathroom",
                    "name": "Bad",
                    "zone_type": "bath",
                    "entities": [
                        {"entity_id": "light.bathroom_ceiling", "role": "lights"},
                        {"entity_id": "binary_sensor.bathroom_motion", "role": "motion"},
                    ],
                    "enabled_modules": ["light", "motion"],
                }
            ],
        }
        
        with self.app.test_request_context(
            "/api/v1/zone-automation/sync-definitions",
            method="POST",
            json=payload,
        ):
            response = sync_zone_definitions.__wrapped__()
            data = response.get_json()
        
        assert data["ok"] is True
        assert "bathroom" in data["synced"]
        
        # Verify zone was written to truth store
        zone = self.store.get_zone("bathroom")
        assert zone is not None
        assert zone.name == "Bad"
        assert zone.zone_type == "bath"
        assert len(zone.entities) == 2
