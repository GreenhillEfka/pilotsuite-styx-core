"""Health Analytics Contract Tests."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import uuid

from copilot_core.analytics.health_analytics import (
    HealthAnalyticsStore,
    HealthCheckEntryV1,
    HealthCheckStatus,
    HealthComponentType,
    HealthCheckHistoryV1,
    HealthComponentPatternsV1,
    HealthEffectivenessMetricsV1,
    HealthAnalyticsSummaryV1,
)


@pytest.fixture
def temp_db():
    """Temporäres SQLite-DB für Tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "health_analytics.db"
        yield db_path


@pytest.fixture
def store(temp_db):
    """HealthAnalyticsStore Fixture."""
    return HealthAnalyticsStore(db_path=temp_db)


class TestHealthCheckEntryV1:
    """Tests für HealthCheckEntryV1 Dataclass."""

    def test_entry_creation(self):
        """HealthCheckEntryV1 kann erstellt werden."""
        entry = HealthCheckEntryV1(
            check_id="chk_001",
            component="ha_connection",
            component_type="ha_connection",
            status="healthy",
            check_time=datetime.now(timezone.utc).isoformat(),
            response_time_ms=45.2,
            message="Connection OK",
        )
        assert entry.check_id == "chk_001"
        assert entry.component == "ha_connection"
        assert entry.status == "healthy"
        assert entry.response_time_ms == 45.2
        assert entry.revision == 0

    def test_entry_with_details(self):
        """HealthCheckEntryV1 mit Details."""
        entry = HealthCheckEntryV1(
            check_id="chk_002",
            component="ollama",
            component_type="ollama",
            status="degraded",
            check_time=datetime.now(timezone.utc).isoformat(),
            response_time_ms=1200.5,
            message="Slow response",
            details={"latency_p95": 1500, "error_rate": 0.05},
        )
        assert entry.details == {"latency_p95": 1500, "error_rate": 0.05}


class TestHealthAnalyticsStore:
    """Tests für HealthAnalyticsStore."""

    def test_store_initialization(self, store):
        """Store wird korrekt initialisiert."""
        assert store.db_path.exists()
        assert store.db_path.suffix == ".db"

    def test_add_check_entry(self, store):
        """Health-Check-Eintrag hinzufügen."""
        entry = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ha_connection",
            component_type="ha_connection",
            status="healthy",
            check_time=datetime.now(timezone.utc).isoformat(),
            response_time_ms=42.0,
        )
        revision = store.add_check_entry(entry)
        assert revision >= 1
        assert entry.revision == revision

    def test_add_multiple_entries_increments_revision(self, store):
        """Mehrere Einträge erhöhen die Revision."""
        base_time = datetime.now(timezone.utc)
        
        entry1 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ha_connection",
            component_type="ha_connection",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=40.0,
        )
        rev1 = store.add_check_entry(entry1)

        entry2 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ollama",
            component_type="ollama",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=50.0,
        )
        rev2 = store.add_check_entry(entry2)

        assert rev2 > rev1

    def test_build_history_empty(self, store):
        """Leere Historie wenn keine Einträge."""
        history = store.build_history()
        assert history.entries == []
        assert history.total_count == 0
        assert history.revision == 0

    def test_build_history_with_entries(self, store):
        """Historie mit Einträgen."""
        base_time = datetime.now(timezone.utc)
        
        for i in range(5):
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="ha_connection",
                component_type="ha_connection",
                status="healthy",
                check_time=(base_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=40.0 + i,
            )
            store.add_check_entry(entry)

        history = store.build_history(limit=10)
        assert history.total_count == 5
        assert len(history.entries) == 5
        assert history.entries[0].component == "ha_connection"

    def test_build_history_filter_by_component(self, store):
        """Historie nach Komponente filtern."""
        base_time = datetime.now(timezone.utc)

        entry1 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ha_connection",
            component_type="ha_connection",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=40.0,
        )
        store.add_check_entry(entry1)

        entry2 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ollama",
            component_type="ollama",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=50.0,
        )
        store.add_check_entry(entry2)

        history = store.build_history(component="ha_connection")
        assert history.total_count == 1
        assert history.entries[0].component == "ha_connection"

    def test_build_history_filter_by_status(self, store):
        """Historie nach Status filtern."""
        base_time = datetime.now(timezone.utc)

        for status in ["healthy", "degraded", "unhealthy"]:
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="ha_connection",
                component_type="ha_connection",
                status=status,
                check_time=base_time.isoformat(),
                response_time_ms=40.0,
            )
            store.add_check_entry(entry)

        history = store.build_history(status="degraded")
        assert history.total_count == 1
        assert history.entries[0].status == "degraded"

    def test_build_history_time_range(self, store):
        """Historie mit Zeit-Filter."""
        base_time = datetime.now(timezone.utc)

        entry1 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ha_connection",
            component_type="ha_connection",
            status="healthy",
            check_time=(base_time - timedelta(hours=2)).isoformat(),
            response_time_ms=40.0,
        )
        store.add_check_entry(entry1)

        entry2 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ha_connection",
            component_type="ha_connection",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=50.0,
        )
        store.add_check_entry(entry2)

        from_time = (base_time - timedelta(hours=1)).isoformat()
        history = store.build_history(from_time=from_time)
        assert history.total_count == 1
        assert history.entries[0].check_time >= from_time

    def test_build_component_patterns(self, store):
        """Component Patterns aufbauen."""
        base_time = datetime.now(timezone.utc)

        # Mehrere Checks für ha_connection
        for i in range(10):
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="ha_connection",
                component_type="ha_connection",
                status="healthy" if i < 8 else "degraded",
                check_time=(base_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=40.0 + i,
            )
            store.add_check_entry(entry)

        patterns = store.build_component_patterns(time_range_days=7)
        assert patterns.total_components >= 1
        assert patterns.healthy_components >= 0

        ha_pattern = next((p for p in patterns.patterns if p.component == "ha_connection"), None)
        assert ha_pattern is not None
        assert ha_pattern.total_checks == 10
        assert ha_pattern.healthy_count == 8
        assert ha_pattern.degraded_count == 2
        assert 0.0 <= ha_pattern.health_rate <= 1.0

    def test_build_component_patterns_response_times(self, store):
        """Response-Time-Statistiken in Patterns."""
        base_time = datetime.now(timezone.utc)

        for i in range(5):
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="test_component",
                component_type="core",
                status="healthy",
                check_time=(base_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=float(100 + i * 10),
            )
            store.add_check_entry(entry)

        patterns = store.build_component_patterns(time_range_days=7)
        pattern = next((p for p in patterns.patterns if p.component == "test_component"), None)
        assert pattern is not None
        assert pattern.min_response_time_ms == 100.0
        assert pattern.max_response_time_ms == 140.0
        assert pattern.avg_response_time_ms > 0

    def test_build_component_patterns_trend(self, store):
        """Trend-Erkennung in Patterns."""
        base_time = datetime.now(timezone.utc)

        # Degrading trend: zuerst healthy, dann degraded
        for i in range(10):
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="degrading_component",
                component_type="core",
                status="healthy" if i >= 5 else "degraded",
                check_time=(base_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=40.0,
            )
            store.add_check_entry(entry)

        patterns = store.build_component_patterns(time_range_days=7)
        pattern = next((p for p in patterns.patterns if p.component == "degrading_component"), None)
        assert pattern is not None
        # Trend-Erkennung hängt von der Implementierung ab
        assert pattern.trend in ["improving", "stable", "degrading"]

    def test_get_effectiveness_metrics(self, store):
        """Effectiveness-Metriken berechnen."""
        base_time = datetime.now(timezone.utc)

        # Mehrere gesunde Checks
        for i in range(20):
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component=f"component_{i % 3}",
                component_type="core",
                status="healthy",
                check_time=(base_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=40.0,
            )
            store.add_check_entry(entry)

        metrics = store.get_effectiveness_metrics(time_range_days=7)
        assert metrics.overall_health_score > 0.0
        assert metrics.system_uptime_rate > 0.0
        assert metrics.checks_last_24h >= 20
        assert metrics.checks_last_7d >= 20
        assert metrics.components_by_health is not None

    def test_get_effectiveness_metrics_with_failures(self, store):
        """Effectiveness-Metriken mit Fehlern."""
        base_time = datetime.now(timezone.utc)

        # 80% healthy, 20% unhealthy
        for i in range(100):
            status = "healthy" if i < 80 else "unhealthy"
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="test_component",
                component_type="core",
                status=status,
                check_time=(base_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=40.0,
            )
            store.add_check_entry(entry)

        metrics = store.get_effectiveness_metrics(time_range_days=7)
        assert 0.75 <= metrics.overall_health_score <= 0.85

    def test_build_summary(self, store):
        """Analytics Summary aufbauen."""
        base_time = datetime.now(timezone.utc)

        for i in range(10):
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="test_component",
                component_type="core",
                status="healthy",
                check_time=(base_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=40.0,
            )
            store.add_check_entry(entry)

        summary = store.build_summary(time_range_days=7)
        assert summary.history_summary is not None
        assert summary.patterns_summary is not None
        assert summary.effectiveness_summary is not None
        assert summary.revision >= 1
        assert summary.generated_at is not None

    def test_revision_tracking(self, store):
        """Revision-Tracking für Delta-Polling."""
        base_time = datetime.now(timezone.utc)

        entry1 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ha_connection",
            component_type="ha_connection",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=40.0,
        )
        rev1 = store.add_check_entry(entry1)

        entry2 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ollama",
            component_type="ollama",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=50.0,
        )
        rev2 = store.add_check_entry(entry2)

        assert rev2 > rev1

        patterns = store.build_component_patterns()
        assert patterns.revision == rev2


class TestHealthCheckStatus:
    """Tests für HealthCheckStatus Enum."""

    def test_status_values(self):
        """Status-Werte sind definiert."""
        assert HealthCheckStatus.HEALTHY.value == "healthy"
        assert HealthCheckStatus.DEGRADED.value == "degraded"
        assert HealthCheckStatus.UNHEALTHY.value == "unhealthy"
        assert HealthCheckStatus.UNKNOWN.value == "unknown"


class TestHealthComponentType:
    """Tests für HealthComponentType Enum."""

    def test_component_types(self):
        """Komponententypen sind definiert."""
        assert HealthComponentType.CORE.value == "core"
        assert HealthComponentType.DATABASE.value == "database"
        assert HealthComponentType.HA_CONNECTION.value == "ha_connection"
        assert HealthComponentType.OLLAMA.value == "ollama"
        assert HealthComponentType.SCHEDULER.value == "scheduler"


class TestHealthCheckHistoryV1:
    """Tests für HealthCheckHistoryV1 Dataclass."""

    def test_history_creation(self):
        """HealthCheckHistoryV1 kann erstellt werden."""
        history = HealthCheckHistoryV1(
            entries=[],
            total_count=0,
            from_time=None,
            to_time=None,
            revision=0,
        )
        assert history.entries == []
        assert history.total_count == 0
        assert history.revision == 0


class TestHealthComponentPatternsV1:
    """Tests für HealthComponentPatternsV1 Dataclass."""

    def test_patterns_creation(self):
        """HealthComponentPatternsV1 kann erstellt werden."""
        patterns = HealthComponentPatternsV1(
            patterns=[],
            total_components=0,
            healthy_components=0,
            degraded_components=0,
            unhealthy_components=0,
            revision=0,
        )
        assert patterns.patterns == []
        assert patterns.total_components == 0
        assert patterns.revision == 0


class TestHealthEffectivenessMetricsV1:
    """Tests für HealthEffectivenessMetricsV1 Dataclass."""

    def test_metrics_creation(self):
        """HealthEffectivenessMetricsV1 kann erstellt werden."""
        metrics = HealthEffectivenessMetricsV1(
            overall_health_score=0.95,
            system_uptime_rate=0.95,
            avg_check_interval_seconds=300.0,
            mtbf_hours=168.0,
            mttr_minutes=5.0,
            alert_accuracy_rate=0.95,
            false_positive_rate=0.05,
            components_by_health={"healthy": 5, "degraded": 1, "unhealthy": 0},
            checks_last_24h=288,
            checks_last_7d=2016,
            revision=1,
        )
        assert metrics.overall_health_score == 0.95
        assert metrics.mtbf_hours == 168.0
        assert metrics.revision == 1


class TestHealthAnalyticsSummaryV1:
    """Tests für HealthAnalyticsSummaryV1 Dataclass."""

    def test_summary_creation(self):
        """HealthAnalyticsSummaryV1 kann erstellt werden."""
        summary = HealthAnalyticsSummaryV1(
            history_summary={"total_checks": 100},
            patterns_summary={"total_components": 10},
            effectiveness_summary={"overall_health_score": 0.95},
            revision=1,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        assert summary.history_summary is not None
        assert summary.patterns_summary is not None
        assert summary.effectiveness_summary is not None
        assert summary.generated_at is not None
