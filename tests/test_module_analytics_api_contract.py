"""Module Analytics API Contract Tests — Slice 56."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import uuid
import json

from copilot_core.analytics.module_analytics import (
    ModuleAnalyticsStore,
    ModuleExecutionEntryV1,
    ModuleExecutionStatus,
    ModuleTriggerType,
    get_module_analytics_store,
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


@pytest.fixture
def populated_store(store):
    """Store mit Sample-Daten befüllen."""
    now = datetime.now(timezone.utc)

    # Verschiedene Module und Zonen
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
            execution_time=(now - timedelta(hours=1)).isoformat(),
            duration_ms=100.0,
            inputs_count=5,
            outputs_count=2,
        ),
        ModuleExecutionEntryV1(
            execution_id=str(uuid.uuid4()),
            module_id="heiz_module",
            module_name="Heizung Modul",
            module_type="heating",
            zone_id="schlafzimmer",
            zone_name="Schlafzimmer",
            status=ModuleExecutionStatus.SUCCESS.value,
            trigger_type=ModuleTriggerType.EVENT_DRIVEN.value,
            execution_time=(now - timedelta(hours=2)).isoformat(),
            duration_ms=150.0,
            inputs_count=3,
            outputs_count=1,
        ),
        ModuleExecutionEntryV1(
            execution_id=str(uuid.uuid4()),
            module_id="licht_module",
            module_name="Licht Modul",
            module_type="lighting",
            zone_id="kueche",
            zone_name="Küche",
            status=ModuleExecutionStatus.FAILED.value,
            trigger_type=ModuleTriggerType.VOICE.value,
            execution_time=(now - timedelta(hours=3)).isoformat(),
            duration_ms=50.0,
            inputs_count=2,
            outputs_count=0,
            error_message="Connection timeout",
        ),
    ]

    for entry in entries:
        store.add_execution_entry(entry)

    return store


class TestModuleAnalyticsAPIContract:
    """API-Contract-Tests für Module Analytics Endpoints."""

    def test_get_executions_basic(self, populated_store):
        """GET /executions — Basis-Response."""
        history = populated_store.build_history()

        assert "entries" in dir(history)
        assert "total_count" in dir(history)
        assert "revision" in dir(history)
        assert history.total_count == 3
        assert len(history.entries) == 3

    def test_get_executions_with_module_filter(self, populated_store):
        """GET /executions?module_id=licht_module — Filter nach Modul."""
        history = populated_store.build_history(module_id="licht_module")

        assert history.total_count == 2
        assert all(e.module_id == "licht_module" for e in history.entries)

    def test_get_executions_with_zone_filter(self, populated_store):
        """GET /executions?zone_id=wohnzimmer — Filter nach Zone."""
        history = populated_store.build_history(zone_id="wohnzimmer")

        assert history.total_count == 1
        assert history.entries[0].zone_id == "wohnzimmer"

    def test_get_executions_with_status_filter(self, populated_store):
        """GET /executions?status=success — Filter nach Status."""
        history = populated_store.build_history(status="success")

        assert history.total_count == 2
        assert all(e.status == "success" for e in history.entries)

    def test_get_executions_with_trigger_filter(self, populated_store):
        """GET /executions?trigger_type=scheduled — Filter nach Trigger."""
        history = populated_store.build_history(trigger_type="scheduled")

        assert history.total_count == 1
        assert history.entries[0].trigger_type == "scheduled"

    def test_get_executions_with_time_range(self, populated_store):
        """GET /executions?from_time=...&to_time=... — Zeitfilter."""
        now = datetime.now(timezone.utc)
        from_time = (now - timedelta(hours=4)).isoformat()
        to_time = (now - timedelta(hours=1)).isoformat()

        history = populated_store.build_history(from_time=from_time, to_time=to_time)

        assert history.total_count >= 1
        for entry in history.entries:
            assert entry.execution_time >= from_time
            assert entry.execution_time <= to_time

    def test_get_executions_with_limit_offset(self, populated_store):
        """GET /executions?limit=2&offset=1 — Pagination."""
        history = populated_store.build_history(limit=2, offset=1)

        assert len(history.entries) == 2
        assert history.total_count == 3

    def test_get_patterns_basic(self, populated_store):
        """GET /patterns — Basis-Response."""
        patterns = populated_store.build_module_patterns(time_range_days=7)

        assert "patterns" in dir(patterns)
        assert "total_modules" in dir(patterns)
        assert "active_modules" in dir(patterns)
        assert "revision" in dir(patterns)

    def test_get_patterns_structure(self, populated_store):
        """GET /patterns — Pattern-Struktur."""
        patterns = populated_store.build_module_patterns(time_range_days=7)

        assert patterns.total_modules >= 2  # licht_module und heiz_module

        for pattern in patterns.patterns:
            assert pattern.module_id != ""
            assert pattern.module_name != ""
            assert pattern.module_type != ""
            assert pattern.total_executions >= 1
            assert 0.0 <= pattern.success_rate <= 1.0
            assert pattern.trend in ["improving", "stable", "degrading"]

    def test_get_patterns_time_range(self, populated_store):
        """GET /patterns?time_range_days=1 — Zeitbereich."""
        patterns_7d = populated_store.build_module_patterns(time_range_days=7)
        patterns_1d = populated_store.build_module_patterns(time_range_days=1)

        # Bei 1 Tag sollten weniger Executions gezählt werden
        assert patterns_1d.total_modules <= patterns_7d.total_modules

    def test_get_effectiveness_basic(self, populated_store):
        """GET /effectiveness — Basis-Response."""
        metrics = populated_store.get_effectiveness_metrics(time_range_days=7)

        assert "overall_success_rate" in dir(metrics)
        assert "total_executions_24h" in dir(metrics)
        assert "total_executions_7d" in dir(metrics)
        assert "mtbf_hours" in dir(metrics)
        assert "revision" in dir(metrics)

    def test_get_effectiveness_metrics_range(self, populated_store):
        """GET /effectiveness — Metrik-Bereiche."""
        metrics = populated_store.get_effectiveness_metrics(time_range_days=7)

        assert 0.0 <= metrics.overall_success_rate <= 1.0
        assert metrics.total_executions_24h >= 0
        assert metrics.total_executions_7d >= 0
        assert metrics.mtbf_hours >= 0.0
        assert metrics.zone_coverage_total >= 0

    def test_get_effectiveness_modules_by_status(self, populated_store):
        """GET /effectiveness — Modules by Status."""
        metrics = populated_store.get_effectiveness_metrics(time_range_days=7)

        assert "modules_by_status" in dir(metrics)
        assert isinstance(metrics.modules_by_status, dict)

    def test_get_effectiveness_trigger_distribution(self, populated_store):
        """GET /effectiveness — Trigger-Type-Verteilung."""
        metrics = populated_store.get_effectiveness_metrics(time_range_days=7)

        assert "trigger_type_distribution" in dir(metrics)
        assert isinstance(metrics.trigger_type_distribution, dict)

    def test_get_summary_basic(self, populated_store):
        """GET /summary — Basis-Response."""
        summary = populated_store.build_summary(time_range_days=7)

        assert "history_summary" in dir(summary)
        assert "patterns_summary" in dir(summary)
        assert "effectiveness_summary" in dir(summary)
        assert "revision" in dir(summary)
        assert "generated_at" in dir(summary)

    def test_get_summary_structure(self, populated_store):
        """GET /summary — Summary-Struktur."""
        summary = populated_store.build_summary(time_range_days=7)

        assert summary.revision >= 1
        assert summary.generated_at != ""
        assert "total_executions" in summary.history_summary
        assert "total_modules" in summary.patterns_summary
        assert "overall_success_rate" in summary.effectiveness_summary

    def test_revision_monotonic(self, populated_store):
        """Revision muss monoton steigen."""
        summary1 = populated_store.build_summary(time_range_days=7)

        # Neue Entry hinzufügen
        new_entry = ModuleExecutionEntryV1(
            execution_id=str(uuid.uuid4()),
            module_id="new_module",
            module_name="New Module",
            module_type="test",
            zone_id="test_zone",
            zone_name="Test Zone",
            status=ModuleExecutionStatus.SUCCESS.value,
            trigger_type=ModuleTriggerType.MANUAL.value,
            execution_time=datetime.now(timezone.utc).isoformat(),
            duration_ms=75.0,
            inputs_count=1,
            outputs_count=1,
        )
        populated_store.add_execution_entry(new_entry)

        summary2 = populated_store.build_summary(time_range_days=7)

        assert summary2.revision >= summary1.revision

    def test_empty_store_patterns(self, store):
        """GET /patterns — leerer Store."""
        patterns = store.build_module_patterns(time_range_days=7)

        assert patterns.total_modules == 0
        assert patterns.active_modules == 0
        assert len(patterns.patterns) == 0

    def test_empty_store_effectiveness(self, store):
        """GET /effectiveness — leerer Store."""
        metrics = store.get_effectiveness_metrics(time_range_days=7)

        assert metrics.overall_success_rate == 0.0
        assert metrics.total_executions_24h == 0
        assert metrics.total_executions_7d == 0

    def test_empty_store_summary(self, store):
        """GET /summary — leerer Store."""
        summary = store.build_summary(time_range_days=7)

        assert summary.revision == 0
        assert summary.generated_at != ""


class TestModuleAnalyticsGlobalStore:
    """Tests für globalen Store-Accessor."""

    def test_get_module_analytics_store_singleton(self, temp_db, monkeypatch):
        """get_module_analytics_store() liefert Singleton."""
        # Globalen Store zurücksetzen
        import copilot_core.analytics.module_analytics as mod
        mod._store = None

        store1 = get_module_analytics_store(db_path=temp_db)
        store2 = get_module_analytics_store(db_path=temp_db)

        assert store1 is store2
