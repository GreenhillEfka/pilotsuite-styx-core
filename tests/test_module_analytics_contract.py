"""Contract-Tests für Module Analytics Surface."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import uuid

from copilot_core.analytics.module_analytics import (
    ModuleAnalyticsStore,
    ModuleExecutionEntryV1,
    ModuleExecutionStatus,
    ModuleTriggerType,
    ModuleExecutionHistoryV1,
    ModulePatternsV1,
    ModulePatternEntryV1,
    ModuleEffectivenessMetricsV1,
    ModuleAnalyticsSummaryV1,
)


@pytest.fixture
def temp_db():
    """Temporäre Datenbank für Tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "module_analytics.db"
        yield db_path


@pytest.fixture
def store(temp_db):
    """Store-Fixture mit temporärer DB."""
    return ModuleAnalyticsStore(db_path=temp_db)


@pytest.fixture
def sample_execution():
    """Sample Execution Entry für Tests."""
    return ModuleExecutionEntryV1(
        execution_id=str(uuid.uuid4()),
        module_id="licht_module",
        module_name="Licht Modul",
        module_type="lighting",
        zone_id="wohnzimmer",
        zone_name="Wohnzimmer",
        status=ModuleExecutionStatus.SUCCESS.value,
        trigger_type=ModuleTriggerType.SCHEDULED.value,
        execution_time=datetime.now(timezone.utc).isoformat(),
        duration_ms=125.5,
        inputs_count=5,
        outputs_count=2,
    )


class TestModuleExecutionEntryV1:
    """Tests für ModuleExecutionEntryV1."""

    def test_entry_creation(self, sample_execution):
        """Entry-Erstellung mit allen Feldern."""
        assert sample_execution.execution_id != ""
        assert sample_execution.module_id == "licht_module"
        assert sample_execution.module_name == "Licht Modul"
        assert sample_execution.module_type == "lighting"
        assert sample_execution.zone_id == "wohnzimmer"
        assert sample_execution.zone_name == "Wohnzimmer"
        assert sample_execution.status == "success"
        assert sample_execution.trigger_type == "scheduled"
        assert sample_execution.duration_ms == 125.5
        assert sample_execution.inputs_count == 5
        assert sample_execution.outputs_count == 2

    def test_entry_with_error(self):
        """Entry mit Fehlerinformation."""
        entry = ModuleExecutionEntryV1(
            execution_id=str(uuid.uuid4()),
            module_id="heiz_module",
            module_name="Heizung Modul",
            module_type="heating",
            zone_id="schlafzimmer",
            zone_name="Schlafzimmer",
            status=ModuleExecutionStatus.FAILED.value,
            trigger_type=ModuleTriggerType.EVENT_DRIVEN.value,
            execution_time=datetime.now(timezone.utc).isoformat(),
            duration_ms=50.0,
            inputs_count=3,
            outputs_count=0,
            error_message="Connection timeout",
        )
        assert entry.status == "failed"
        assert entry.error_message == "Connection timeout"
        assert entry.outputs_count == 0

    def test_entry_with_metadata(self):
        """Entry mit Metadaten."""
        entry = ModuleExecutionEntryV1(
            execution_id=str(uuid.uuid4()),
            module_id="music_module",
            module_name="Music Modul",
            module_type="media",
            zone_id="kueche",
            zone_name="Küche",
            status=ModuleExecutionStatus.SUCCESS.value,
            trigger_type=ModuleTriggerType.VOICE.value,
            execution_time=datetime.now(timezone.utc).isoformat(),
            duration_ms=200.0,
            inputs_count=1,
            outputs_count=1,
            metadata={"track": "Example Song", "artist": "Test Artist"},
        )
        assert entry.metadata == {"track": "Example Song", "artist": "Test Artist"}


class TestModuleAnalyticsStore:
    """Tests für ModuleAnalyticsStore."""

    def test_store_initialization(self, temp_db):
        """Store-Initialisierung erstellt DB-Datei."""
        store = ModuleAnalyticsStore(db_path=temp_db)
        assert temp_db.exists()
        assert temp_db.suffix == ".db"

    def test_add_execution_entry(self, store, sample_execution):
        """Execution-Eintrag hinzufügen."""
        revision = store.add_execution_entry(sample_execution)
        assert revision == 1

        history = store.build_history()
        assert history.total_count == 1
        assert len(history.entries) == 1
        assert history.entries[0].execution_id == sample_execution.execution_id
        assert history.entries[0].module_id == "licht_module"
        assert history.entries[0].status == "success"

    def test_add_multiple_entries(self, store):
        """Mehrere Execution-Einträge hinzufügen."""
        now = datetime.now(timezone.utc)
        entries = []
        for i in range(5):
            entry = ModuleExecutionEntryV1(
                execution_id=str(uuid.uuid4()),
                module_id=f"module_{i}",
                module_name=f"Module {i}",
                module_type="test",
                zone_id="zone_a",
                zone_name="Zone A",
                status=ModuleExecutionStatus.SUCCESS.value,
                trigger_type=ModuleTriggerType.SCHEDULED.value,
                execution_time=(now - timedelta(hours=i)).isoformat(),
                duration_ms=100.0 + i * 10,
                inputs_count=5,
                outputs_count=2,
            )
            entries.append(entry)
            store.add_execution_entry(entry)

        history = store.build_history()
        assert history.total_count == 5
        assert len(history.entries) == 5

    def test_build_history_with_filters(self, store):
        """Historie mit Filtern."""
        now = datetime.now(timezone.utc)

        # Verschiedene Entries hinzufügen
        entries = [
            ModuleExecutionEntryV1(
                execution_id=str(uuid.uuid4()),
                module_id="licht_module",
                module_name="Licht Modul",
                module_type="lighting",
                zone_id="wohnzimmer",
                zone_name="Wohnzimmer",
                status=ModuleExecutionStatus.SUCCESS.value,
                trigger_type=ModuleTriggerType.SCHEDULED.value,
                execution_time=now.isoformat(),
                duration_ms=100.0,
                inputs_count=5,
                outputs_count=2,
            ),
            ModuleExecutionEntryV1(
                execution_id=str(uuid.uuid4()),
                module_id="heiz_module",
                module_name="Heizung Modul",
                module_type="heating",
                zone_id="wohnzimmer",
                zone_name="Wohnzimmer",
                status=ModuleExecutionStatus.FAILED.value,
                trigger_type=ModuleTriggerType.EVENT_DRIVEN.value,
                execution_time=now.isoformat(),
                duration_ms=50.0,
                inputs_count=3,
                outputs_count=0,
                error_message="Failed",
            ),
            ModuleExecutionEntryV1(
                execution_id=str(uuid.uuid4()),
                module_id="licht_module",
                module_name="Licht Modul",
                module_type="lighting",
                zone_id="kueche",
                zone_name="Küche",
                status=ModuleExecutionStatus.SUCCESS.value,
                trigger_type=ModuleTriggerType.VOICE.value,
                execution_time=now.isoformat(),
                duration_ms=150.0,
                inputs_count=2,
                outputs_count=1,
            ),
        ]

        for entry in entries:
            store.add_execution_entry(entry)

        # Nach module_id filtern
        history = store.build_history(module_id="licht_module")
        assert history.total_count == 2

        # Nach zone_id filtern
        history = store.build_history(zone_id="wohnzimmer")
        assert history.total_count == 2

        # Nach status filtern
        history = store.build_history(status="success")
        assert history.total_count == 2

        # Nach trigger_type filtern
        history = store.build_history(trigger_type="scheduled")
        assert history.total_count == 1

    def test_build_history_with_limit_offset(self, store):
        """Historie mit Limit und Offset."""
        now = datetime.now(timezone.utc)
        for i in range(20):
            entry = ModuleExecutionEntryV1(
                execution_id=str(uuid.uuid4()),
                module_id=f"module_{i % 5}",
                module_name=f"Module {i % 5}",
                module_type="test",
                zone_id="zone_a",
                zone_name="Zone A",
                status=ModuleExecutionStatus.SUCCESS.value,
                trigger_type=ModuleTriggerType.SCHEDULED.value,
                execution_time=(now - timedelta(minutes=i)).isoformat(),
                duration_ms=100.0,
                inputs_count=5,
                outputs_count=2,
            )
            store.add_execution_entry(entry)

        # Limit testen
        history = store.build_history(limit=5)
        assert len(history.entries) == 5
        assert history.total_count == 20

        # Offset testen
        history = store.build_history(limit=5, offset=5)
        assert len(history.entries) == 5
        assert history.total_count == 20
        # Entries sollten anders sein als beim ersten Request

    def test_build_module_patterns(self, store):
        """Module Patterns aufbauen."""
        now = datetime.now(timezone.utc)

        # Mehrere Entries für dasselbe Modul
        for i in range(10):
            entry = ModuleExecutionEntryV1(
                execution_id=str(uuid.uuid4()),
                module_id="licht_module",
                module_name="Licht Modul",
                module_type="lighting",
                zone_id=f"zone_{i % 3}",
                zone_name=f"Zone {i % 3}",
                status=ModuleExecutionStatus.SUCCESS.value if i < 8 else ModuleExecutionStatus.FAILED.value,
                trigger_type=ModuleTriggerType.SCHEDULED.value,
                execution_time=(now - timedelta(hours=i)).isoformat(),
                duration_ms=100.0 + i * 5,
                inputs_count=5,
                outputs_count=2,
            )
            store.add_execution_entry(entry)

        patterns = store.build_module_patterns(time_range_days=7)
        assert patterns.total_modules == 1
        assert patterns.active_modules == 1  # Letzter Status ist failed, aber >50% success

        pattern = patterns.patterns[0]
        assert pattern.module_id == "licht_module"
        assert pattern.total_executions == 10
        assert pattern.success_count == 8
        assert pattern.failed_count == 2
        assert pattern.success_rate >= 0.8
        assert pattern.zone_coverage == 3  # zone_0, zone_1, zone_2

    def test_get_effectiveness_metrics(self, store):
        """Effectiveness-Metriken berechnen."""
        now = datetime.now(timezone.utc)

        # Verschiedene Entries hinzufügen
        for i in range(20):
            status = ModuleExecutionStatus.SUCCESS.value if i < 16 else ModuleExecutionStatus.FAILED.value
            entry = ModuleExecutionEntryV1(
                execution_id=str(uuid.uuid4()),
                module_id=f"module_{i % 4}",
                module_name=f"Module {i % 4}",
                module_type="test",
                zone_id=f"zone_{i % 5}",
                zone_name=f"Zone {i % 5}",
                status=status,
                trigger_type=ModuleTriggerType.SCHEDULED.value,
                execution_time=(now - timedelta(hours=i)).isoformat(),
                duration_ms=100.0 + i * 2,
                inputs_count=5,
                outputs_count=2,
            )
            store.add_execution_entry(entry)

        metrics = store.get_effectiveness_metrics(time_range_days=7)
        assert metrics.total_executions_24h >= 20
        assert metrics.total_executions_7d >= 20
        assert metrics.overall_success_rate > 0.75
        assert metrics.zone_coverage_total >= 5
        assert "scheduled" in metrics.trigger_type_distribution

    def test_build_summary(self, store, sample_execution):
        """Analytics Summary aufbauen."""
        store.add_execution_entry(sample_execution)

        summary = store.build_summary(time_range_days=7)
        assert summary.revision >= 1
        assert summary.generated_at != ""
        assert "total_executions" in summary.history_summary
        assert "total_modules" in summary.patterns_summary
        assert "overall_success_rate" in summary.effectiveness_summary

    def test_revision_tracking(self, store):
        """Revision-Tracking testen."""
        entries = []
        for i in range(5):
            entry = ModuleExecutionEntryV1(
                execution_id=str(uuid.uuid4()),
                module_id="test_module",
                module_name="Test Module",
                module_type="test",
                zone_id="zone_a",
                zone_name="Zone A",
                status=ModuleExecutionStatus.SUCCESS.value,
                trigger_type=ModuleTriggerType.SCHEDULED.value,
                execution_time=datetime.now(timezone.utc).isoformat(),
                duration_ms=100.0,
                inputs_count=5,
                outputs_count=2,
            )
            entries.append(entry)
            revision = store.add_execution_entry(entry)
            assert revision == i + 1

        # Revision sollte monoton steigen
        history = store.build_history()
        revisions = [e.revision for e in history.entries]
        assert len(set(revisions)) == 5  # Alle Revisionen eindeutig


class TestModuleExecutionStatus:
    """Tests für ModuleExecutionStatus Enum."""

    def test_status_values(self):
        """Alle Status-Werte vorhanden."""
        assert ModuleExecutionStatus.SUCCESS.value == "success"
        assert ModuleExecutionStatus.PARTIAL.value == "partial"
        assert ModuleExecutionStatus.FAILED.value == "failed"
        assert ModuleExecutionStatus.SKIPPED.value == "skipped"
        assert ModuleExecutionStatus.TIMEOUT.value == "timeout"


class TestModuleTriggerType:
    """Tests für ModuleTriggerType Enum."""

    def test_trigger_values(self):
        """Alle Trigger-Typen vorhanden."""
        assert ModuleTriggerType.SCHEDULED.value == "scheduled"
        assert ModuleTriggerType.EVENT_DRIVEN.value == "event_driven"
        assert ModuleTriggerType.MANUAL.value == "manual"
        assert ModuleTriggerType.PREDICTIVE.value == "predictive"
        assert ModuleTriggerType.HABITUS.value == "habitus"
        assert ModuleTriggerType.VOICE.value == "voice"
        assert ModuleTriggerType.API.value == "api"


class TestModulePatternEntryV1:
    """Tests für ModulePatternEntryV1."""

    def test_pattern_creation(self):
        """Pattern-Eintrag erstellen."""
        pattern = ModulePatternEntryV1(
            module_id="test_module",
            module_name="Test Module",
            module_type="test",
            total_executions=100,
            success_count=80,
            partial_count=10,
            failed_count=5,
            skipped_count=5,
            success_rate=0.85,
            avg_duration_ms=150.0,
            min_duration_ms=50.0,
            max_duration_ms=500.0,
            p95_duration_ms=400.0,
            avg_inputs_count=5.0,
            avg_outputs_count=2.0,
            last_execution_time=datetime.now(timezone.utc).isoformat(),
            last_status="success",
            trend="improving",
            primary_trigger_type="scheduled",
            zone_coverage=3,
        )
        assert pattern.total_executions == 100
        assert pattern.success_rate == 0.85
        assert pattern.trend == "improving"
        assert pattern.zone_coverage == 3


class TestModuleEffectivenessMetricsV1:
    """Tests für ModuleEffectivenessMetricsV1."""

    def test_metrics_creation(self):
        """Metrics-Eintrag erstellen."""
        metrics = ModuleEffectivenessMetricsV1(
            overall_success_rate=0.9,
            total_executions_24h=100,
            total_executions_7d=500,
            avg_duration_ms=125.0,
            mtbf_hours=48.0,
            mttr_minutes=5.0,
            modules_by_status={"success": 8, "failed": 2},
            trigger_type_distribution={"scheduled": 80, "event_driven": 20},
            zone_coverage_total=10,
            revision=1,
        )
        assert metrics.overall_success_rate == 0.9
        assert metrics.total_executions_24h == 100
        assert metrics.mtbf_hours == 48.0
        assert metrics.zone_coverage_total == 10
