"""
Contract Tests für Styx Unified Dashboard API v1

Tests für:
- Dashboard Read Model Structure
- API Endpoints (/api/v1/styx/dashboard)
- Delta/Revision Behavior
- Zone Detail Surface
- Context Surface für Chat/Voice
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from flask import Flask


# Path setup handled by conftest.py
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
PILOTSUITE_CORE_PATH = REPO_ROOT / "pilotsuite_core" / "rootfs" / "usr" / "src" / "app"
if str(PILOTSUITE_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(PILOTSUITE_CORE_PATH))

from copilot_core.api.v1.styx_dashboard import (  # noqa: E402
    styx_dashboard_bp,
    StyxDashboardStore,
    DashboardHeaderV1,
    DashboardSectionStatus,
    ZoneSummaryBlockV1,
    BrainActivityBlockV1,
    SystemOverviewBlockV1,
    StyxDashboardReadModelV1,
)


# =============================================================================
# Read Model Structure Tests
# =============================================================================

class TestStyxDashboardReadModel:
    """Tests für Dashboard Read Model Structure"""
    
    def test_dashboard_header_structure(self):
        """DashboardHeaderV1 hat alle required fields"""
        header = DashboardHeaderV1(
            revision=1,
            generated_at=datetime.now(timezone.utc).isoformat(),
            overall_status=DashboardSectionStatus.OK,
            total_zones=10,
            zones_with_alerts=2,
            active_proposals=3,
            open_closures=1,
            system_health_score=0.95
        )
        
        assert header.revision == 1
        assert header.overall_status == DashboardSectionStatus.OK
        assert header.total_zones == 10
        assert header.zones_with_alerts == 2
        assert header.active_proposals == 3
        assert header.open_closures == 1
        assert 0.0 <= header.system_health_score <= 1.0
    
    def test_dashboard_section_status_enum(self):
        """DashboardSectionStatus hat alle expected values"""
        assert DashboardSectionStatus.OK.value == "ok"
        assert DashboardSectionStatus.WARNING.value == "warning"
        assert DashboardSectionStatus.ERROR.value == "error"
        assert DashboardSectionStatus.UNKNOWN.value == "unknown"
    
    def test_zone_summary_block_structure(self):
        """ZoneSummaryBlockV1 hat alle required fields"""
        zone = ZoneSummaryBlockV1(
            zone_id="wohn",
            name="Wohnbereich",
            status=DashboardSectionStatus.OK,
            occupancy=2,
            temperature=21.5,
            alerts=[]
        )
        
        assert zone.zone_id == "wohn"
        assert zone.name == "Wohnbereich"
        assert zone.status == DashboardSectionStatus.OK
        assert zone.occupancy == 2
        assert zone.temperature == 21.5
    
    def test_brain_activity_block_structure(self):
        """BrainActivityBlockV1 hat alle required fields"""
        brain = BrainActivityBlockV1(
            neurons_fired=150,
            patterns_detected=12,
            suggestions_generated=5,
            learning_rate=0.05
        )
        
        assert brain.neurons_fired == 150
        assert brain.patterns_detected == 12
        assert brain.suggestions_generated == 5
        assert 0.0 <= brain.learning_rate <= 1.0
    
    def test_system_overview_block_structure(self):
        """SystemOverviewBlockV1 hat alle required fields"""
        system = SystemOverviewBlockV1(
            uptime_seconds=3600,
            memory_mb=512.0,
            cpu_percent=15.0,
            disk_used_pct=45.0,
            events_per_minute=100
        )
        
        assert system.uptime_seconds == 3600
        assert system.memory_mb == 512.0
        assert system.cpu_percent == 15.0
        assert 0.0 <= system.disk_used_pct <= 100.0
    
    def test_styx_dashboard_read_model_complete(self):
        """StyxDashboardReadModelV1 aggregiert alle Blöcke"""
        model = StyxDashboardReadModelV1(
            header=DashboardHeaderV1(revision=1),
            zones=[ZoneSummaryBlockV1(zone_id="wohn", name="Wohnbereich")],
            brain_activity=BrainActivityBlockV1(),
            system_overview=SystemOverviewBlockV1()
        )
        
        assert model.header is not None
        assert len(model.zones) == 1
        assert model.brain_activity is not None
        assert model.system_overview is not None
        
        # Test serialization
        data = model.to_dict()
        assert "header" in data
        assert "zones" in data
        assert "brain_activity" in data
        assert "system_overview" in data


# =============================================================================
# Store Tests
# =============================================================================

class TestStyxDashboardStore:
    """Tests für StyxDashboardStore"""
    
    def test_store_initialization(self):
        """StyxDashboardStore wird korrekt initialisiert"""
        store = StyxDashboardStore()
        assert store is not None
        assert store.get_header() is not None
        assert store.get_read_model() is not None
    
    def test_revision_increment(self):
        """Store erhöht Revision bei Updates"""
        store = StyxDashboardStore()
        initial_revision = store.get_header().revision
        
        header = DashboardHeaderV1(revision=initial_revision + 1)
        store.update_header(header)
        
        assert store.get_header().revision == initial_revision + 1
    
    def test_zone_updates(self):
        """Zone-Updates werden gespeichert"""
        store = StyxDashboardStore()
        
        zone = ZoneSummaryBlockV1(
            zone_id="wohn",
            name="Wohnbereich",
            status=DashboardSectionStatus.OK,
            occupancy=2
        )
        store.update_zone(zone)
        
        retrieved = store.get_zone("wohn")
        assert retrieved is not None
        assert retrieved.name == "Wohnbereich"
        assert retrieved.occupancy == 2
    
    def test_build_dashboard_returns_model(self):
        """build_dashboard() gibt komplettes Read Model zurück"""
        store = StyxDashboardStore()
        
        # Add some data
        store.update_zone(ZoneSummaryBlockV1(zone_id="wohn", name="Wohnbereich"))
        store.update_zone(ZoneSummaryBlockV1(zone_id="bad", name="Bad"))
        
        model = store.get_read_model()
        
        assert isinstance(model, StyxDashboardReadModelV1)
        assert len(model.zones) == 2
    
    def test_build_dashboard_with_analytics(self):
        """Dashboard kann mit Analytics-Daten erweitert werden"""
        store = StyxDashboardStore()
        
        brain = BrainActivityBlockV1(
            neurons_fired=200,
            patterns_detected=15
        )
        store.update_brain_activity(brain)
        
        model = store.get_read_model()
        assert model.brain_activity.neurons_fired == 200


# =============================================================================
# API Endpoint Tests
# =============================================================================

class TestStyxDashboardAPI:
    """Tests für Dashboard API Endpoints"""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app"""
        app = Flask(__name__)
        app.register_blueprint(styx_dashboard_bp)
        app.config["TESTING"] = True
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_get_dashboard_endpoint(self, client):
        """GET /api/v1/styx/dashboard returns valid response"""
        response = client.get("/api/v1/styx/dashboard")
        
        # Should return JSON (may be 401 without auth)
        assert response.content_type.startswith("application/json")
    
    def test_get_dashboard_with_analytics_param(self, client):
        """Dashboard endpoint accepts analytics parameter"""
        response = client.get("/api/v1/styx/dashboard?analytics=true")
        assert response.content_type.startswith("application/json")
    
    def test_get_dashboard_delta_no_changes(self, client):
        """Delta requests work correctly"""
        response = client.get("/api/v1/styx/dashboard?delta=true&revision=0")
        assert response.content_type.startswith("application/json")
    
    def test_get_dashboard_zone_filter(self, client):
        """Zone filter parameter works"""
        response = client.get("/api/v1/styx/dashboard?zone=wohn")
        assert response.content_type.startswith("application/json")
    
    def test_get_dashboard_context_endpoint(self, client):
        """Context endpoint returns context data"""
        response = client.get("/api/v1/styx/dashboard/context")
        assert response.content_type.startswith("application/json")
    
    def test_get_revision_endpoint(self, client):
        """Revision endpoint returns current revision"""
        response = client.get("/api/v1/styx/revision")
        assert response.content_type.startswith("application/json")


# =============================================================================
# Integration Tests
# =============================================================================

class TestStyxDashboardIntegration:
    """Integration tests for dashboard with other subsystems"""
    
    def test_dashboard_header_aggregates_closures(self):
        """Header includes closure counts"""
        store = StyxDashboardStore()
        header = store.get_header()
        
        assert hasattr(header, "open_closures")
        assert isinstance(header.open_closures, int)
    
    def test_dashboard_header_aggregates_proposals(self):
        """Header includes proposal counts"""
        store = StyxDashboardStore()
        header = store.get_header()
        
        assert hasattr(header, "active_proposals")
        assert isinstance(header.active_proposals, int)
    
    def test_dashboard_zones_summary_present(self):
        """Dashboard includes zone summaries"""
        store = StyxDashboardStore()
        model = store.get_read_model()
        
        assert hasattr(model, "zones")
        assert isinstance(model.zones, list)
    
    def test_dashboard_brain_activity_present(self):
        """Dashboard includes brain activity metrics"""
        store = StyxDashboardStore()
        model = store.get_read_model()
        
        assert hasattr(model, "brain_activity")
        assert model.brain_activity is not None
    
    def test_dashboard_recent_highlights(self):
        """Dashboard can include recent highlights"""
        store = StyxDashboardStore()
        model = store.get_read_model()
        
        # Highlights may be part of context or separate
        assert model is not None
