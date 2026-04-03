"""
Contract tests for Insights API and Store.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from copilot_core.insights.contracts import (
    InsightV1,
    InsightSummaryV1,
    InsightDeltaV1,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    InsightSource,
)
from copilot_core.insights.store import InsightStore
from copilot_core.insights.generators import (
    PerformanceInsightGenerator,
    AnomalyInsightGenerator,
    TrendInsightGenerator,
    OptimizationInsightGenerator,
    HealthInsightGenerator,
    UsageInsightGenerator,
    PredictionInsightGenerator,
    EfficiencyInsightGenerator,
    run_all_generators,
)


@pytest.fixture
def temp_db(tmp_path):
    """Create temporary database path."""
    return str(tmp_path / "insights.db")


@pytest.fixture
def store(temp_db):
    """Create InsightStore instance."""
    return InsightStore(temp_db)


class TestInsightContracts:
    """Test insight contract classes."""
    
    def test_insight_v1_creation(self):
        """Test InsightV1 can be created with all fields."""
        insight = InsightV1(
            insight_id=str(uuid.uuid4()),
            category=InsightCategory.PERFORMANCE,
            severity=InsightSeverity.HIGH,
            status=InsightStatus.NEW,
            source=InsightSource.MODULE,
            title="Test Insight",
            description="Test description",
            recommendation="Test recommendation",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            zone_id="wohnzimmer",
            metric_name="avg_duration",
            metric_value=150.0,
            baseline_value=100.0,
            confidence=0.85,
        )
        
        assert insight.insight_id is not None
        assert insight.category == InsightCategory.PERFORMANCE
        assert insight.severity == InsightSeverity.HIGH
        assert insight.status == InsightStatus.NEW
        assert insight.source == InsightSource.MODULE
        assert insight.zone_id == "wohnzimmer"
        assert insight.confidence == 0.85
    
    def test_insight_v1_to_dict(self):
        """Test InsightV1 serializes to dictionary."""
        insight = InsightV1(
            insight_id="test-123",
            category=InsightCategory.ANOMALY,
            severity=InsightSeverity.CRITICAL,
            status=InsightStatus.NEW,
            source=InsightSource.ENERGY,
            title="Energy Anomaly",
            description="High consumption detected",
            recommendation="Check heating schedule",
            created_at=datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc),
            confidence=0.92,
        )
        
        d = insight.to_dict()
        
        assert d["insight_id"] == "test-123"
        assert d["category"] == "anomaly"
        assert d["severity"] == "critical"
        assert d["status"] == "new"
        assert d["source"] == "energy"
        assert d["confidence"] == 0.92
        assert "2026-04-03T12:00:00" in d["created_at"]
    
    def test_insight_summary_v1(self):
        """Test InsightSummaryV1 structure."""
        summary = InsightSummaryV1(
            total_insights=42,
            by_category={"performance": 10, "anomaly": 5},
            by_severity={"critical": 3, "high": 8},
            by_status={"new": 15, "resolved": 20},
            by_source={"module": 12, "energy": 8},
            new_count=15,
            acknowledged_count=5,
            in_progress_count=2,
            resolved_count=20,
            dismissed_count=0,
            critical_count=3,
            high_count=8,
            latest_revision=5,
            latest_change_at=datetime.now(timezone.utc),
        )
        
        d = summary.to_dict()
        
        assert d["total_insights"] == 42
        assert d["by_category"]["performance"] == 10
        assert d["new_count"] == 15
        assert d["latest_revision"] == 5
    
    def test_insight_delta_v1(self):
        """Test InsightDeltaV1 structure."""
        delta = InsightDeltaV1(
            has_changes=True,
            revision=10,
            changes_since_revision=[
                {"insight_id": "abc", "title": "New insight"},
            ],
        )
        
        d = delta.to_dict()
        
        assert d["has_changes"] is True
        assert d["revision"] == 10
        assert len(d["changes_since_revision"]) == 1
    
    def test_enums(self):
        """Test all enum values are defined."""
        assert len(InsightCategory) == 8
        assert len(InsightSeverity) == 5
        assert len(InsightStatus) == 5
        assert len(InsightSource) == 16


class TestInsightStore:
    """Test InsightStore operations."""
    
    def test_store_initialization(self, store):
        """Test store initializes correctly."""
        assert str(store.db_path).endswith("insights.db")
        assert store._revision == 0
    
    def test_add_insight(self, store):
        """Test adding an insight."""
        insight = InsightV1(
            insight_id="test-insight-1",
            category=InsightCategory.PERFORMANCE,
            severity=InsightSeverity.MEDIUM,
            status=InsightStatus.NEW,
            source=InsightSource.MODULE,
            title="Performance Issue",
            description="Modules running slow",
            recommendation="Check logs",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        result = store.add_insight(insight)
        
        assert result.insight_id == "test-insight-1"
        assert result.revision == 1
        assert store._revision == 1
    
    def test_get_insight(self, store):
        """Test retrieving a single insight."""
        insight = InsightV1(
            insight_id="test-insight-2",
            category=InsightCategory.HEALTH,
            severity=InsightSeverity.HIGH,
            status=InsightStatus.NEW,
            source=InsightSource.HEALTH,
            title="Health Check Failed",
            description="API timeout",
            recommendation="Retry",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        store.add_insight(insight)
        retrieved = store.get_insight("test-insight-2")
        
        assert retrieved is not None
        assert retrieved.title == "Health Check Failed"
        assert retrieved.severity == InsightSeverity.HIGH
    
    def test_get_insight_not_found(self, store):
        """Test retrieving non-existent insight."""
        result = store.get_insight("non-existent")
        assert result is None
    
    def test_get_insights_filtered(self, store):
        """Test filtering insights."""
        # Add multiple insights
        for i, cat in enumerate([
            InsightCategory.PERFORMANCE,
            InsightCategory.ANOMALY,
            InsightCategory.PERFORMANCE,
        ]):
            store.add_insight(InsightV1(
                insight_id=f"insight-{i}",
                category=cat,
                severity=InsightSeverity.MEDIUM,
                status=InsightStatus.NEW,
                source=InsightSource.MODULE,
                title=f"Insight {i}",
                description="Test",
                recommendation="Test",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
        
        # Filter by category
        filtered = store.get_insights(category=InsightCategory.PERFORMANCE)
        
        assert len(filtered) == 2
        assert all(i.category == InsightCategory.PERFORMANCE for i in filtered)
    
    def test_get_insights_by_severity(self, store):
        """Test filtering by severity."""
        for i, sev in enumerate([
            InsightSeverity.CRITICAL,
            InsightSeverity.LOW,
            InsightSeverity.CRITICAL,
        ]):
            store.add_insight(InsightV1(
                insight_id=f"sev-{i}",
                category=InsightCategory.HEALTH,
                severity=sev,
                status=InsightStatus.NEW,
                source=InsightSource.HEALTH,
                title=f"Severity {i}",
                description="Test",
                recommendation="Test",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
        
        filtered = store.get_insights(severity=InsightSeverity.CRITICAL)
        
        assert len(filtered) == 2
    
    def test_get_insights_by_status(self, store):
        """Test filtering by status."""
        for i, status in enumerate([
            InsightStatus.NEW,
            InsightStatus.RESOLVED,
            InsightStatus.NEW,
        ]):
            store.add_insight(InsightV1(
                insight_id=f"status-{i}",
                category=InsightCategory.TREND,
                severity=InsightSeverity.INFO,
                status=status,
                source=InsightSource.ENERGY,
                title=f"Status {i}",
                description="Test",
                recommendation="Test",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
        
        filtered = store.get_insights(status=InsightStatus.NEW)
        
        assert len(filtered) == 2
    
    def test_get_insights_by_source(self, store):
        """Test filtering by source."""
        for i, src in enumerate([
            InsightSource.VOICE,
            InsightSource.MODULE,
            InsightSource.VOICE,
        ]):
            store.add_insight(InsightV1(
                insight_id=f"source-{i}",
                category=InsightCategory.USAGE,
                severity=InsightSeverity.INFO,
                status=InsightStatus.NEW,
                source=src,
                title=f"Source {i}",
                description="Test",
                recommendation="Test",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
        
        filtered = store.get_insights(source=InsightSource.VOICE)
        
        assert len(filtered) == 2
    
    def test_get_insights_by_zone(self, store):
        """Test filtering by zone_id."""
        for i, zone in enumerate(["wohnzimmer", "kuche", "wohnzimmer"]):
            store.add_insight(InsightV1(
                insight_id=f"zone-{i}",
                category=InsightCategory.USAGE,
                severity=InsightSeverity.INFO,
                status=InsightStatus.NEW,
                source=InsightSource.ZONE_PRESENCE,
                title=f"Zone {i}",
                description="Test",
                recommendation="Test",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                zone_id=zone,
            ))
        
        filtered = store.get_insights(zone_id="wohnzimmer")
        
        assert len(filtered) == 2
    
    def test_get_insights_since_revision(self, store):
        """Test delta polling with since_revision."""
        # Add initial insights
        store.add_insight(InsightV1(
            insight_id="initial-1",
            category=InsightCategory.PERFORMANCE,
            severity=InsightSeverity.MEDIUM,
            status=InsightStatus.NEW,
            source=InsightSource.MODULE,
            title="Initial 1",
            description="Test",
            recommendation="Test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
        
        initial_revision = store._revision
        
        # Add more insights
        store.add_insight(InsightV1(
            insight_id="new-1",
            category=InsightCategory.ANOMALY,
            severity=InsightSeverity.HIGH,
            status=InsightStatus.NEW,
            source=InsightSource.CAMERA,
            title="New 1",
            description="Test",
            recommendation="Test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
        
        # Query with since_revision
        filtered = store.get_insights(since_revision=initial_revision)
        
        assert len(filtered) == 1
        assert filtered[0].insight_id == "new-1"
    
    def test_update_insight_status(self, store):
        """Test updating insight status."""
        insight = InsightV1(
            insight_id="status-update-1",
            category=InsightCategory.HEALTH,
            severity=InsightSeverity.HIGH,
            status=InsightStatus.NEW,
            source=InsightSource.HEALTH,
            title="Health Issue",
            description="Test",
            recommendation="Test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        store.add_insight(insight)
        
        # Update status
        updated = store.update_insight_status(
            "status-update-1",
            InsightStatus.IN_PROGRESS,
        )
        
        assert updated is not None
        assert updated.status == InsightStatus.IN_PROGRESS
        assert updated.revision == 2
    
    def test_update_nonexistent_insight(self, store):
        """Test updating non-existent insight."""
        result = store.update_insight_status(
            "non-existent",
            InsightStatus.RESOLVED,
        )
        assert result is None
    
    def test_get_summary(self, store):
        """Test summary generation."""
        # Add various insights
        for cat in [
            InsightCategory.PERFORMANCE,
            InsightCategory.ANOMALY,
            InsightCategory.HEALTH,
        ]:
            for sev in [InsightSeverity.CRITICAL, InsightSeverity.HIGH]:
                store.add_insight(InsightV1(
                    insight_id=f"sum-{cat.value}-{sev.value}",
                    category=cat,
                    severity=sev,
                    status=InsightStatus.NEW,
                    source=InsightSource.MODULE,
                    title="Test",
                    description="Test",
                    recommendation="Test",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ))
        
        summary = store.get_summary()
        
        assert summary.total_insights == 6
        assert summary.by_category["performance"] == 2
        assert summary.by_severity["critical"] == 3
        assert summary.by_status["new"] == 6
        assert summary.critical_count == 3
        assert summary.high_count == 3
    
    def test_get_delta(self, store):
        """Test delta polling."""
        # Initial state
        delta = store.get_delta(since_revision=0)
        assert delta.has_changes is False
        assert delta.revision == 0
        
        # Add insight
        store.add_insight(InsightV1(
            insight_id="delta-1",
            category=InsightCategory.TREND,
            severity=InsightSeverity.INFO,
            status=InsightStatus.NEW,
            source=InsightSource.ENERGY,
            title="Delta Test",
            description="Test",
            recommendation="Test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
        
        # Check delta
        delta = store.get_delta(since_revision=0)
        
        assert delta.has_changes is True
        assert delta.revision == 1
        assert len(delta.changes_since_revision) == 1
    
    def test_revision_bumps_on_add(self, store):
        """Test revision increments on each add."""
        initial = store._revision
        
        store.add_insight(InsightV1(
            insight_id="rev-1",
            category=InsightCategory.USAGE,
            severity=InsightSeverity.LOW,
            status=InsightStatus.NEW,
            source=InsightSource.VOICE,
            title="Rev 1",
            description="Test",
            recommendation="Test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
        
        assert store._revision == initial + 1
        
        store.add_insight(InsightV1(
            insight_id="rev-2",
            category=InsightCategory.EFFICIENCY,
            severity=InsightSeverity.INFO,
            status=InsightStatus.NEW,
            source=InsightSource.NOTIFICATIONS,
            title="Rev 2",
            description="Test",
            recommendation="Test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
        
        assert store._revision == initial + 2


class TestInsightGenerators:
    """Test insight generator classes."""
    
    def test_performance_generator(self, store):
        """Test PerformanceInsightGenerator."""
        gen = PerformanceInsightGenerator(store)
        insights = gen.generate()
        
        assert len(insights) > 0
        assert all(i.category == InsightCategory.PERFORMANCE for i in insights)
    
    def test_anomaly_generator(self, store):
        """Test AnomalyInsightGenerator."""
        gen = AnomalyInsightGenerator(store)
        insights = gen.generate()
        
        assert len(insights) > 0
        assert all(i.category == InsightCategory.ANOMALY for i in insights)
    
    def test_trend_generator(self, store):
        """Test TrendInsightGenerator."""
        gen = TrendInsightGenerator(store)
        insights = gen.generate()
        
        assert len(insights) > 0
        assert all(i.category == InsightCategory.TREND for i in insights)
    
    def test_optimization_generator(self, store):
        """Test OptimizationInsightGenerator."""
        gen = OptimizationInsightGenerator(store)
        insights = gen.generate()
        
        assert len(insights) > 0
        assert all(i.category == InsightCategory.OPTIMIZATION for i in insights)
    
    def test_health_generator(self, store):
        """Test HealthInsightGenerator."""
        gen = HealthInsightGenerator(store)
        insights = gen.generate()
        
        assert len(insights) > 0
        assert all(i.category == InsightCategory.HEALTH for i in insights)
    
    def test_usage_generator(self, store):
        """Test UsageInsightGenerator."""
        gen = UsageInsightGenerator(store)
        insights = gen.generate()
        
        assert len(insights) > 0
        assert all(i.category == InsightCategory.USAGE for i in insights)
    
    def test_prediction_generator(self, store):
        """Test PredictionInsightGenerator."""
        gen = PredictionInsightGenerator(store)
        insights = gen.generate()
        
        assert len(insights) > 0
        assert all(i.category == InsightCategory.PREDICTION for i in insights)
    
    def test_efficiency_generator(self, store):
        """Test EfficiencyInsightGenerator."""
        gen = EfficiencyInsightGenerator(store)
        insights = gen.generate()
        
        assert len(insights) > 0
        assert all(i.category == InsightCategory.EFFICIENCY for i in insights)
    
    def test_run_all_generators(self, store):
        """Test running all generators together."""
        insights = run_all_generators(store)
        
        assert len(insights) >= 8  # At least one from each generator
        
        categories = set(i.category for i in insights)
        assert InsightCategory.PERFORMANCE in categories
        assert InsightCategory.ANOMALY in categories
        assert InsightCategory.TREND in categories
        assert InsightCategory.OPTIMIZATION in categories
        assert InsightCategory.HEALTH in categories
        assert InsightCategory.USAGE in categories
        assert InsightCategory.PREDICTION in categories
        assert InsightCategory.EFFICIENCY in categories


class TestInsightStorePersistence:
    """Test store persistence across instances."""
    
    def test_persistence(self, temp_db):
        """Test insights persist across store instances."""
        # Create and populate first store
        store1 = InsightStore(temp_db)
        store1.add_insight(InsightV1(
            insight_id="persist-1",
            category=InsightCategory.HEALTH,
            severity=InsightSeverity.HIGH,
            status=InsightStatus.NEW,
            source=InsightSource.HEALTH,
            title="Persist Test",
            description="Test",
            recommendation="Test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
        revision1 = store1._revision
        
        # Create second store with same DB
        store2 = InsightStore(temp_db)
        
        # Verify data persisted
        assert store2._revision == revision1
        retrieved = store2.get_insight("persist-1")
        assert retrieved is not None
        assert retrieved.title == "Persist Test"
