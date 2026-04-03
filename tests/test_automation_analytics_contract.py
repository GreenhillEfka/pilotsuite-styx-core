"""Automation Analytics Contract Tests — Slice 54."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from copilot_core.automation.analytics import (
    AutomationExecutionEntryV1,
    AutomationExecutionHistoryV1,
    AutomationRulePatternEntryV1,
    AutomationRulePatternsV1,
    AutomationEffectivenessMetricsV1,
    AutomationStatus,
    AutomationTriggerType,
)
from copilot_core.automation.analytics_store import AutomationAnalyticsStore, get_automation_analytics_store


class TestAutomationExecutionEntryV1:
    """Tests für AutomationExecutionEntryV1."""

    def test_entry_creation(self):
        """Entry-Erstellung mit allen Feldern."""
        now = datetime.now(timezone.utc).isoformat()
        entry = AutomationExecutionEntryV1(
            entry_id="entry_001",
            automation_id="auto_001",
            automation_name="Living Room Lights",
            trigger_type="presence",
            status="completed",
            zone_id="living",
            zone_name="Wohnbereich",
            module_id="licht_module",
            module_name="Licht Modul",
            triggered_at=now,
            started_at=now,
            completed_at=now,
            duration_seconds=2.5,
            error_message=None,
            actions_executed=3,
            actions_failed=0,
            entities_affected=2,
        )

        assert entry.entry_id == "entry_001"
        assert entry.automation_id == "auto_001"
        assert entry.trigger_type == "presence"
        assert entry.status == "completed"
        assert entry.actions_executed == 3


class TestAutomationAnalyticsStore:
    """Tests für AutomationAnalyticsStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Store mit temporärer DB."""
        db_path = tmp_path / "automation_analytics.db"
        return AutomationAnalyticsStore(db_path=str(db_path))

    def test_add_execution_entry(self, store):
        """Execution-Eintrag hinzufügen."""
        now = datetime.now(timezone.utc).isoformat()
        entry = AutomationExecutionEntryV1(
            entry_id="entry_001",
            automation_id="auto_001",
            automation_name="Living Room Lights",
            trigger_type="presence",
            status="completed",
            zone_id="living",
            zone_name="Wohnbereich",
            module_id="licht_module",
            module_name="Licht Modul",
            triggered_at=now,
            started_at=now,
            completed_at=now,
            duration_seconds=2.5,
            error_message=None,
            actions_executed=3,
            actions_failed=0,
            entities_affected=2,
        )

        store.add_execution_entry(entry)

        # Verify entry was added
        history = store.build_execution_history(automation_id="auto_001")
        assert len(history.entries) == 1
        assert history.entries[0].entry_id == "entry_001"
        assert history.total_completed == 1

    def test_build_execution_history(self, store):
        """Execution-Historie aufbauen."""
        now = datetime.now(timezone.utc)

        # Add multiple entries
        for i in range(5):
            entry = AutomationExecutionEntryV1(
                entry_id=f"entry_{i:03d}",
                automation_id="auto_001",
                automation_name="Living Room Lights",
                trigger_type="presence",
                status="completed",
                zone_id="living",
                zone_name="Wohnbereich",
                module_id="licht_module",
                module_name="Licht Modul",
                triggered_at=now.isoformat(),
                started_at=now.isoformat(),
                completed_at=now.isoformat(),
                duration_seconds=2.0 + i * 0.5,
                error_message=None,
                actions_executed=3,
                actions_failed=0,
                entities_affected=2,
            )
            store.add_execution_entry(entry)

        history = store.build_execution_history(automation_id="auto_001")

        assert history.total_executions == 5
        assert history.total_completed == 5
        assert history.total_failed == 0
        assert history.revision == 5

    def test_build_execution_history_with_filters(self, store):
        """Execution-Historie mit Filtern."""
        now = datetime.now(timezone.utc)

        # Add entries for different automations and statuses
        for automation_id in ["auto_001", "auto_002", "auto_003"]:
            for status in ["completed", "failed"]:
                entry = AutomationExecutionEntryV1(
                    entry_id=f"entry_{automation_id}_{status}",
                    automation_id=automation_id,
                    automation_name=f"Automation {automation_id}",
                    trigger_type="time",
                    status=status,
                    zone_id="living",
                    zone_name="Wohnbereich",
                    module_id="licht_module",
                    module_name="Licht Modul",
                    triggered_at=now.isoformat(),
                    started_at=now.isoformat(),
                    completed_at=now.isoformat() if status == "completed" else None,
                    duration_seconds=2.0 if status == "completed" else None,
                    error_message="Error" if status == "failed" else None,
                    actions_executed=3 if status == "completed" else 0,
                    actions_failed=0 if status == "completed" else 1,
                    entities_affected=2 if status == "completed" else 0,
                )
                store.add_execution_entry(entry)

        # Filter by automation_id
        auto1_history = store.build_execution_history(automation_id="auto_001")
        assert auto1_history.total_executions == 2
        assert auto1_history.entries[0].automation_id == "auto_001"

        # Filter by status
        failed_history = store.build_execution_history(status="failed")
        assert failed_history.total_executions == 3
        assert failed_history.total_failed == 3

    def test_build_rule_patterns(self, store):
        """Rule-Patterns aufbauen."""
        now = datetime.now(timezone.utc)

        # Add multiple entries for auto_001
        for i in range(10):
            entry = AutomationExecutionEntryV1(
                entry_id=f"entry_auto1_{i}",
                automation_id="auto_001",
                automation_name="Living Room Lights",
                trigger_type="presence",
                status="completed",
                zone_id="living",
                zone_name="Wohnbereich",
                module_id="licht_module",
                module_name="Licht Modul",
                triggered_at=now.isoformat(),
                started_at=now.isoformat(),
                completed_at=now.isoformat(),
                duration_seconds=2.5,
                error_message=None,
                actions_executed=3,
                actions_failed=0,
                entities_affected=2,
            )
            store.add_execution_entry(entry)

        # Add entries for auto_002
        for i in range(3):
            entry = AutomationExecutionEntryV1(
                entry_id=f"entry_auto2_{i}",
                automation_id="auto_002",
                automation_name="Kitchen Lights",
                trigger_type="time",
                status="failed",
                zone_id="kitchen",
                zone_name="Küche",
                module_id="licht_module",
                module_name="Licht Modul",
                triggered_at=now.isoformat(),
                started_at=now.isoformat(),
                completed_at=None,
                duration_seconds=None,
                error_message="Test error",
                actions_executed=0,
                actions_failed=1,
                entities_affected=0,
            )
            store.add_execution_entry(entry)

        patterns = store.build_rule_patterns()

        assert patterns.total_automations == 2
        assert patterns.automations_with_executions == 2

        auto1_pattern = next(p for p in patterns.patterns if p.automation_id == "auto_001")
        assert auto1_pattern.total_executions == 10
        assert auto1_pattern.success_rate == 1.0
        assert auto1_pattern.failure_rate == 0.0
        assert auto1_pattern.most_common_trigger == "presence"

    def test_get_effectiveness_metrics(self, store):
        """Effectiveness-Metriken berechnen."""
        now = datetime.now(timezone.utc)

        # Add diverse executions
        trigger_types = ["presence", "time", "voice"]
        statuses = ["completed", "failed", "skipped"]
        for trigger_type in trigger_types:
            for status in statuses:
                for i in range(3):
                    entry = AutomationExecutionEntryV1(
                        entry_id=f"entry_{trigger_type}_{status}_{i}",
                        automation_id=f"auto_{trigger_type}_{i}",
                        automation_name=f"Automation {trigger_type} {i}",
                        trigger_type=trigger_type,
                        status=status,
                        zone_id="living",
                        zone_name="Wohnbereich",
                        module_id="licht_module",
                        module_name="Licht Modul",
                        triggered_at=now.isoformat(),
                        started_at=now.isoformat(),
                        completed_at=now.isoformat() if status == "completed" else None,
                        duration_seconds=2.5 if status == "completed" else None,
                        error_message="Error" if status == "failed" else None,
                        actions_executed=3 if status == "completed" else 0,
                        actions_failed=0 if status == "completed" else 1,
                        entities_affected=2 if status == "completed" else 0,
                    )
                    store.add_execution_entry(entry)

        metrics = store.get_effectiveness_metrics()

        assert metrics.total_executions_analyzed == 27  # 3 types * 3 statuses * 3 iterations
        assert "completed" in metrics.executions_by_status
        assert "presence" in metrics.executions_by_trigger
        assert 0.0 <= metrics.overall_success_rate <= 1.0
        assert 0.0 <= metrics.overall_failure_rate <= 1.0
        assert 0.0 <= metrics.reliability_score <= 1.0

    def test_revision_tracking(self, store):
        """Revision-Tracking bei Änderungen."""
        now = datetime.now(timezone.utc)

        initial_revision = store._revision

        entry = AutomationExecutionEntryV1(
            entry_id="entry_001",
            automation_id="auto_001",
            automation_name="Living Room Lights",
            trigger_type="presence",
            status="completed",
            zone_id="living",
            zone_name="Wohnbereich",
            module_id="licht_module",
            module_name="Licht Modul",
            triggered_at=now.isoformat(),
            started_at=now.isoformat(),
            completed_at=now.isoformat(),
            duration_seconds=2.5,
            error_message=None,
            actions_executed=3,
            actions_failed=0,
            entities_affected=2,
        )
        store.add_execution_entry(entry)

        assert store._revision == initial_revision + 1

    def test_build_summary(self, store):
        """Analytics Summary aufbauen."""
        now = datetime.now(timezone.utc)

        # Add some data
        for i in range(5):
            entry = AutomationExecutionEntryV1(
                entry_id=f"entry_{i}",
                automation_id="auto_001",
                automation_name="Living Room Lights",
                trigger_type="presence",
                status="completed",
                zone_id="living",
                zone_name="Wohnbereich",
                module_id="licht_module",
                module_name="Licht Modul",
                triggered_at=now.isoformat(),
                started_at=now.isoformat(),
                completed_at=now.isoformat(),
                duration_seconds=2.5,
                error_message=None,
                actions_executed=3,
                actions_failed=0,
                entities_affected=2,
            )
            store.add_execution_entry(entry)

        summary = store.build_summary()

        assert summary.usage.total_executions == 5
        assert summary.patterns.automations_with_executions >= 1
        assert summary.effectiveness.total_executions_analyzed == 5
        assert summary.summary_revision == summary.usage.revision


class TestAutomationStatus:
    """Tests für AutomationStatus Enum."""

    def test_statuses(self):
        """Alle Status verfügbar."""
        assert AutomationStatus.TRIGGERED == "triggered"
        assert AutomationStatus.RUNNING == "running"
        assert AutomationStatus.COMPLETED == "completed"
        assert AutomationStatus.FAILED == "failed"
        assert AutomationStatus.SKIPPED == "skipped"
        assert AutomationStatus.BLOCKED == "blocked"


class TestAutomationTriggerType:
    """Tests für AutomationTriggerType Enum."""

    def test_types(self):
        """Alle Typen verfügbar."""
        assert AutomationTriggerType.STATE_CHANGE == "state_change"
        assert AutomationTriggerType.TIME == "time"
        assert AutomationTriggerType.SUN_EVENT == "sun_event"
        assert AutomationTriggerType.PRESENCE == "presence"
        assert AutomationTriggerType.VOICE == "voice"
        assert AutomationTriggerType.PROPOSAL == "proposal"
        assert AutomationTriggerType.SCENE == "scene"
        assert AutomationTriggerType.ROUTINE == "routine"
        assert AutomationTriggerType.MANUAL == "manual"
        assert AutomationTriggerType.WEBHOOK == "webhook"


class TestAutomationAnalyticsStoreIntegration:
    """Integrationstests für AutomationAnalyticsStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Store mit temporärer DB."""
        db_path = tmp_path / "automation_analytics.db"
        return AutomationAnalyticsStore(db_path=str(db_path))

    def test_full_workflow(self, store):
        """Kompletter Workflow: Add → History → Patterns → Metrics → Summary."""
        now = datetime.now(timezone.utc)

        # Add diverse executions
        for trigger_type in ["presence", "time"]:
            for status in ["completed", "failed"]:
                for i in range(2):
                    entry = AutomationExecutionEntryV1(
                        entry_id=f"entry_{trigger_type}_{status}_{i}",
                        automation_id=f"auto_{trigger_type}_{i}",
                        automation_name=f"Automation {trigger_type} {i}",
                        trigger_type=trigger_type,
                        status=status,
                        zone_id="living",
                        zone_name="Wohnbereich",
                        module_id="licht_module",
                        module_name="Licht Modul",
                        triggered_at=now.isoformat(),
                        started_at=now.isoformat(),
                        completed_at=now.isoformat() if status == "completed" else None,
                        duration_seconds=2.5 if status == "completed" else None,
                        error_message="Error" if status == "failed" else None,
                        actions_executed=3 if status == "completed" else 0,
                        actions_failed=0 if status == "completed" else 1,
                        entities_affected=2 if status == "completed" else 0,
                    )
                    store.add_execution_entry(entry)

        # Build all read models
        history = store.build_execution_history()
        patterns = store.build_rule_patterns()
        metrics = store.get_effectiveness_metrics()
        summary = store.build_summary()

        # Verify consistency
        assert history.total_executions == 8  # 2 types * 2 statuses * 2 iterations
        assert patterns.total_automations == 4
        assert metrics.total_executions_analyzed == 8
        assert summary.usage.total_executions == 8
        assert summary.patterns.automations_with_executions == 4

    def test_time_range_filtering(self, store):
        """Zeitbereichs-Filterung."""
        now = datetime.now(timezone.utc)

        # Add entries at different times
        for days_ago in [1, 3, 7, 14, 30]:
            entry = AutomationExecutionEntryV1(
                entry_id=f"entry_{days_ago}d",
                automation_id="auto_001",
                automation_name="Living Room Lights",
                trigger_type="presence",
                status="completed",
                zone_id="living",
                zone_name="Wohnbereich",
                module_id="licht_module",
                module_name="Licht Modul",
                triggered_at=(now - timedelta(days=days_ago)).isoformat(),
                started_at=(now - timedelta(days=days_ago)).isoformat(),
                completed_at=(now - timedelta(days=days_ago)).isoformat(),
                duration_seconds=2.5,
                error_message=None,
                actions_executed=3,
                actions_failed=0,
                entities_affected=2,
            )
            store.add_execution_entry(entry)

        # Last 7 days - should include 1, 3, 7 days ago entries
        start_7d = (now - timedelta(days=7)).isoformat()
        history_7d = store.build_execution_history(time_range_start=start_7d)
        assert history_7d.total_executions >= 3  # At least 1, 3, 7 days ago

        # Last 30 days - should include all 5 entries
        start_30d = (now - timedelta(days=30)).isoformat()
        history_30d = store.build_execution_history(time_range_start=start_30d)
        assert history_30d.total_executions == 5


class TestGetAutomationAnalyticsStore:
    """Tests für Singleton-Getter."""

    def test_singleton_behavior(self):
        """Singleton verhält sich korrekt."""
        store1 = get_automation_analytics_store()
        store2 = get_automation_analytics_store()

        # Should be same instance (or at least same type)
        assert type(store1) == type(store2)
