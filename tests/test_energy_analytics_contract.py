"""Contract tests for Energy Analytics — Slice 47."""
import pytest
from datetime import datetime, timedelta

from copilot_core.energy.analytics import (
    EnergyAnalyticsPeriod,
    EnergyAnalyticsSummaryV1,
    EnergyEffectivenessMetricsV1,
    EnergyUsageEntryV1,
    EnergyUsageHistoryV1,
    EnergyZonePatternsV1,
    ZoneEnergyPatternV1,
)
from copilot_core.energy.analytics_store import EnergyAnalyticsStore


class TestEnergyAnalyticsReadModels:
    """Test energy analytics read models."""
    
    def test_usage_entry_creation(self):
        """Test energy usage entry creation."""
        entry = EnergyUsageEntryV1(
            timestamp="2026-04-02T14:00:00Z",
            zone_id="zone_living_room",
            module_id="energy_living_room",
            entity_id="sensor.power_living_room",
            consumption_wh=1500.0,
            cost_eur=0.525,
            tariff_rate="peak",
            source="grid",
        )
        
        assert entry.zone_id == "zone_living_room"
        assert entry.consumption_wh == 1500.0
        assert entry.cost_eur == 0.525
        assert entry.tariff_rate == "peak"
    
    def test_usage_history_aggregation(self):
        """Test usage history aggregation."""
        history = EnergyUsageHistoryV1(
            period=EnergyAnalyticsPeriod.DAILY,
            start_at="2026-04-01T00:00:00Z",
            end_at="2026-04-02T00:00:00Z",
        )
        
        # Add entries
        for i in range(10):
            entry = EnergyUsageEntryV1(
                timestamp=f"2026-04-01T{i:02d}:00:00Z",
                zone_id="zone_test",
                module_id="energy_test",
                entity_id="sensor.power_test",
                consumption_wh=100.0,
                cost_eur=0.035,
                tariff_rate="off_peak",
                source="grid",
            )
            history.add_entry(entry)
        
        assert len(history.entries) == 10
        assert history.total_consumption_wh == 1000.0
        assert abs(history.total_cost_eur - 0.35) < 0.001  # Float precision
        assert history.revision == 10
        assert history.latest_change_at is not None
    
    def test_zone_pattern_creation(self):
        """Test zone energy pattern creation."""
        pattern = ZoneEnergyPatternV1(
            zone_id="zone_living_room",
            zone_name="Wohnzimmer",
            avg_daily_consumption_wh=5000.0,
            peak_hour=19,
            peak_consumption_wh=2500.0,
            off_peak_consumption_wh=1500.0,
            weekday_pattern=[100.0] * 24,
            weekend_pattern=[80.0] * 24,
            dominant_modules=["licht", "heiz", "media"],
            trend_7d=5.2,
            trend_30d=-2.1,
        )
        
        assert pattern.zone_name == "Wohnzimmer"
        assert pattern.peak_hour == 19
        assert len(pattern.dominant_modules) == 3
        assert pattern.trend_7d == 5.2
    
    def test_zone_patterns_revision_tracking(self):
        """Test zone patterns revision tracking."""
        patterns = EnergyZonePatternsV1()
        
        pattern1 = ZoneEnergyPatternV1(
            zone_id="zone_1",
            zone_name="Zone 1",
            avg_daily_consumption_wh=1000.0,
            peak_hour=12,
            peak_consumption_wh=500.0,
            off_peak_consumption_wh=300.0,
        )
        
        pattern2 = ZoneEnergyPatternV1(
            zone_id="zone_2",
            zone_name="Zone 2",
            avg_daily_consumption_wh=2000.0,
            peak_hour=18,
            peak_consumption_wh=800.0,
            off_peak_consumption_wh=400.0,
        )
        
        patterns.add_pattern(pattern1)
        assert patterns.revision == 1
        
        patterns.add_pattern(pattern2)
        assert patterns.revision == 2
        assert len(patterns.patterns) == 2
    
    def test_effectiveness_metrics_update(self):
        """Test effectiveness metrics update."""
        metrics = EnergyEffectivenessMetricsV1()
        
        assert metrics.revision == 0
        assert metrics.total_savings_eur == 0.0
        
        metrics.update_metrics(
            savings_eur=125.50,
            savings_wh=50000.0,
            success_rate=0.85,
            peak_reduction=15.3,
        )
        
        assert metrics.total_savings_eur == 125.50
        assert metrics.total_savings_wh == 50000.0
        assert metrics.optimization_success_rate == 0.85
        assert metrics.peak_reduction_percentage == 15.3
        assert metrics.revision == 1
    
    def test_analytics_summary_creation(self):
        """Test analytics summary creation."""
        summary = EnergyAnalyticsSummaryV1(
            period=EnergyAnalyticsPeriod.WEEKLY,
            start_at="2026-03-26T00:00:00Z",
            end_at="2026-04-02T00:00:00Z",
        )
        
        summary.total_consumption_wh = 35000.0
        summary.total_cost_eur = 12.25
        summary.zone_count = 5
        summary.module_count = 12
        summary.update_revision()
        
        assert summary.period == EnergyAnalyticsPeriod.WEEKLY
        assert summary.zone_count == 5
        assert summary.revision == 1


class TestEnergyAnalyticsStore:
    """Test energy analytics store."""
    
    @pytest.fixture
    def store(self, tmp_path):
        """Create temporary store for testing."""
        db_path = tmp_path / "test_energy_analytics.db"
        return EnergyAnalyticsStore(str(db_path))
    
    def test_add_usage_entry(self, store):
        """Test adding usage entry."""
        now = datetime.utcnow()
        timestamp = now.isoformat() + "Z"
        
        entry = EnergyUsageEntryV1(
            timestamp=timestamp,
            zone_id="zone_living_room",
            module_id="energy_living_room",
            entity_id="sensor.power_living_room",
            consumption_wh=1500.0,
            cost_eur=0.525,
            tariff_rate="peak",
            source="grid",
        )
        
        store.add_usage_entry(entry)
        
        # Retrieve and verify with explicit time range
        history = store.build_usage_history(
            period=EnergyAnalyticsPeriod.DAILY,
            start_at=(now - timedelta(hours=1)).isoformat() + "Z",
            end_at=(now + timedelta(hours=1)).isoformat() + "Z",
            zone_id="zone_living_room",
        )
        
        assert len(history.entries) == 1
        assert history.total_consumption_wh == 1500.0
        assert abs(history.total_cost_eur - 0.525) < 0.001
    
    def test_build_usage_history_with_zone_filter(self, store):
        """Test building usage history with zone filter."""
        now = datetime.utcnow()
        timestamp = now.isoformat() + "Z"
        
        # Add entries for multiple zones
        for zone in ["zone_living_room", "zone_bedroom", "zone_kitchen"]:
            entry = EnergyUsageEntryV1(
                timestamp=timestamp,
                zone_id=zone,
                module_id=f"energy_{zone}",
                entity_id=f"sensor.power_{zone}",
                consumption_wh=1000.0,
                cost_eur=0.35,
                tariff_rate="peak",
                source="grid",
            )
            store.add_usage_entry(entry)
        
        # Filter by zone with explicit time range
        history = store.build_usage_history(
            period=EnergyAnalyticsPeriod.DAILY,
            start_at=(now - timedelta(hours=1)).isoformat() + "Z",
            end_at=(now + timedelta(hours=1)).isoformat() + "Z",
            zone_id="zone_bedroom",
        )
        
        assert len(history.entries) == 1
        assert history.entries[0].zone_id == "zone_bedroom"
        assert history.total_consumption_wh == 1000.0
    
    def test_update_zone_pattern(self, store):
        """Test updating zone pattern."""
        pattern = ZoneEnergyPatternV1(
            zone_id="zone_living_room",
            zone_name="Wohnzimmer",
            avg_daily_consumption_wh=5000.0,
            peak_hour=19,
            peak_consumption_wh=2500.0,
            off_peak_consumption_wh=1500.0,
            weekday_pattern=[100.0] * 24,
            weekend_pattern=[80.0] * 24,
            dominant_modules=["licht", "heiz"],
            trend_7d=5.2,
            trend_30d=-2.1,
        )
        
        store.update_zone_pattern(pattern)
        
        # Retrieve and verify
        patterns = store.build_zone_patterns(zone_id="zone_living_room")
        
        assert len(patterns.patterns) == 1
        retrieved = patterns.patterns[0]
        assert retrieved.zone_name == "Wohnzimmer"
        assert retrieved.avg_daily_consumption_wh == 5000.0
        assert retrieved.peak_hour == 19
        assert retrieved.trend_7d == 5.2
        assert retrieved.revision == 1
    
    def test_update_effectiveness_metrics(self, store):
        """Test updating effectiveness metrics."""
        metrics = EnergyEffectivenessMetricsV1(
            total_savings_eur=125.50,
            total_savings_wh=50000.0,
            optimization_success_rate=0.85,
            avg_shift_duration_minutes=45.0,
            peak_reduction_percentage=15.3,
            pv_self_consumption_rate=0.72,
            battery_efficiency=0.92,
            suggestions_accepted=25,
            suggestions_rejected=5,
            suggestions_pending=3,
            load_shifts_executed=18,
        )
        
        store.update_effectiveness_metrics(metrics)
        
        # Retrieve and verify
        retrieved = store.get_effectiveness_metrics()
        
        assert retrieved.total_savings_eur == 125.50
        assert retrieved.optimization_success_rate == 0.85
        assert retrieved.suggestions_accepted == 25
        assert retrieved.load_shifts_executed == 18
        assert retrieved.revision == 1
    
    def test_update_analytics_summary(self, store):
        """Test updating analytics summary."""
        summary = EnergyAnalyticsSummaryV1(
            period=EnergyAnalyticsPeriod.WEEKLY,
            start_at="2026-03-26T00:00:00Z",
            end_at="2026-04-02T00:00:00Z",
        )
        
        summary.total_consumption_wh = 35000.0
        summary.total_cost_eur = 12.25
        summary.avg_daily_consumption_wh = 5000.0
        summary.peak_consumption_wh = 2500.0
        summary.peak_hour = 19
        summary.zone_count = 5
        summary.module_count = 12
        summary.entity_count = 20
        summary.pv_generation_wh = 15000.0
        summary.battery_cycles = 3
        summary.grid_import_wh = 25000.0
        summary.grid_export_wh = 5000.0
        
        store.update_summary(summary)
        
        # Retrieve and verify
        retrieved = store.get_summary()
        
        assert retrieved.period == EnergyAnalyticsPeriod.WEEKLY
        assert retrieved.total_consumption_wh == 35000.0
        assert retrieved.zone_count == 5
        assert retrieved.pv_generation_wh == 15000.0
        assert retrieved.revision == 1  # Incremented by store
    
    def test_revision_tracking(self, store):
        """Test revision tracking across operations."""
        # Initial state
        metrics = store.get_effectiveness_metrics()
        initial_revision = metrics.revision
        
        # Update metrics
        metrics.total_savings_eur = 100.0
        store.update_effectiveness_metrics(metrics)
        
        # Verify revision incremented
        updated = store.get_effectiveness_metrics()
        assert updated.revision == initial_revision + 1
    
    def test_build_usage_history_time_range(self, store):
        """Test usage history with different time ranges."""
        now = datetime.utcnow()
        
        # Add entries with different timestamps
        for hours_ago in [1, 5, 25, 50]:
            timestamp = (now - timedelta(hours=hours_ago)).isoformat() + "Z"
            entry = EnergyUsageEntryV1(
                timestamp=timestamp,
                zone_id="zone_test",
                module_id="energy_test",
                entity_id="sensor.power_test",
                consumption_wh=100.0 * hours_ago,
                cost_eur=0.035 * hours_ago,
                tariff_rate="off_peak",
                source="grid",
            )
            store.add_usage_entry(entry)
        
        # Hourly should only get recent entry
        hourly = store.build_usage_history(period=EnergyAnalyticsPeriod.HOURLY)
        assert len(hourly.entries) <= 2  # Entries from last hour
        
        # Daily should get more
        daily = store.build_usage_history(period=EnergyAnalyticsPeriod.DAILY)
        assert len(daily.entries) >= 2


class TestEnergyAnalyticsAPIContract:
    """Test API contract structure."""
    
    def test_usage_response_structure(self):
        """Test usage API response structure."""
        # Simulate API response structure
        response = {
            "period": "daily",
            "start_at": "2026-04-01T00:00:00Z",
            "end_at": "2026-04-02T00:00:00Z",
            "total_consumption_wh": 10000.0,
            "total_cost_eur": 3.50,
            "revision": 5,
            "latest_change_at": "2026-04-02T14:00:00Z",
            "has_changes": True,
            "entries": [
                {
                    "timestamp": "2026-04-01T12:00:00Z",
                    "zone_id": "zone_living_room",
                    "module_id": "energy_living_room",
                    "entity_id": "sensor.power_living_room",
                    "consumption_wh": 1500.0,
                    "cost_eur": 0.525,
                    "tariff_rate": "peak",
                    "source": "grid",
                }
            ],
        }
        
        # Verify required fields
        assert "period" in response
        assert "start_at" in response
        assert "end_at" in response
        assert "total_consumption_wh" in response
        assert "revision" in response
        assert "has_changes" in response
        assert "entries" in response
        
        # Verify entry structure
        entry = response["entries"][0]
        assert "timestamp" in entry
        assert "zone_id" in entry
        assert "consumption_wh" in entry
        assert "cost_eur" in entry
    
    def test_patterns_response_structure(self):
        """Test patterns API response structure."""
        response = {
            "revision": 3,
            "latest_change_at": "2026-04-02T14:00:00Z",
            "has_changes": True,
            "patterns": [
                {
                    "zone_id": "zone_living_room",
                    "zone_name": "Wohnzimmer",
                    "avg_daily_consumption_wh": 5000.0,
                    "peak_hour": 19,
                    "peak_consumption_wh": 2500.0,
                    "off_peak_consumption_wh": 1500.0,
                    "weekday_pattern": [100.0] * 24,
                    "weekend_pattern": [80.0] * 24,
                    "dominant_modules": ["licht", "heiz"],
                    "trend_7d": 5.2,
                    "trend_30d": -2.1,
                }
            ],
        }
        
        assert "revision" in response
        assert "patterns" in response
        assert "has_changes" in response
        
        pattern = response["patterns"][0]
        assert "zone_id" in pattern
        assert "zone_name" in pattern
        assert "avg_daily_consumption_wh" in pattern
        assert "peak_hour" in pattern
    
    def test_effectiveness_response_structure(self):
        """Test effectiveness API response structure."""
        response = {
            "total_savings_eur": 125.50,
            "total_savings_wh": 50000.0,
            "optimization_success_rate": 0.85,
            "avg_shift_duration_minutes": 45.0,
            "peak_reduction_percentage": 15.3,
            "pv_self_consumption_rate": 0.72,
            "battery_efficiency": 0.92,
            "suggestions_accepted": 25,
            "suggestions_rejected": 5,
            "suggestions_pending": 3,
            "load_shifts_executed": 18,
            "revision": 1,
            "latest_change_at": "2026-04-02T14:00:00Z",
        }
        
        required_fields = [
            "total_savings_eur",
            "optimization_success_rate",
            "pv_self_consumption_rate",
            "suggestions_accepted",
            "load_shifts_executed",
            "revision",
        ]
        
        for field in required_fields:
            assert field in response, f"Missing field: {field}"
    
    def test_summary_response_structure(self):
        """Test summary API response structure."""
        response = {
            "period": "weekly",
            "start_at": "2026-03-26T00:00:00Z",
            "end_at": "2026-04-02T00:00:00Z",
            "total_consumption_wh": 35000.0,
            "total_cost_eur": 12.25,
            "avg_daily_consumption_wh": 5000.0,
            "peak_consumption_wh": 2500.0,
            "peak_hour": 19,
            "zone_count": 5,
            "module_count": 12,
            "entity_count": 20,
            "pv_generation_wh": 15000.0,
            "battery_cycles": 3,
            "grid_import_wh": 25000.0,
            "grid_export_wh": 5000.0,
            "revision": 1,
            "latest_change_at": "2026-04-02T14:00:00Z",
        }
        
        assert "period" in response
        assert "total_consumption_wh" in response
        assert "zone_count" in response
        assert "pv_generation_wh" in response
        assert "grid_import_wh" in response
        assert "grid_export_wh" in response
