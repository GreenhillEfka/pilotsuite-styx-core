"""Voice Analytics Contract Tests — Slice 57."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import uuid

from copilot_core.analytics.voice_analytics import (
    VoiceAnalyticsStore,
    VoiceCommandEntryV1,
    VoiceCommandStatus,
    VoiceIntentType,
    VoiceCommandHistoryV1,
    VoiceIntentPatternEntryV1,
    VoiceIntentPatternsV1,
    VoiceEffectivenessMetricsV1,
    VoiceAnalyticsSummaryV1,
    get_voice_analytics_store,
)


@pytest.fixture
def temp_db():
    """Temporäre Datenbank für Tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "voice_analytics.db"
        yield db_path


@pytest.fixture
def store(temp_db):
    """Store-Fixture mit temporärer DB."""
    return VoiceAnalyticsStore(db_path=temp_db)


@pytest.fixture
def sample_command():
    """Sample Command Entry für Tests."""
    return VoiceCommandEntryV1(
        command_id=str(uuid.uuid4()),
        intent_type=VoiceIntentType.LIGHT_CONTROL.value,
        raw_command="Licht im Wohnzimmer an",
        zone_id="wohnzimmer",
        zone_name="Wohnzimmer",
        module_id="licht_module",
        module_name="Licht Modul",
        status=VoiceCommandStatus.SUCCESS.value,
        confidence_score=0.95,
        processing_time_ms=125.5,
        execution_time=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def populated_store(store):
    """Store mit Sample-Daten befüllen."""
    now = datetime.now(timezone.utc)

    entries = [
        VoiceCommandEntryV1(
            command_id=str(uuid.uuid4()),
            intent_type=VoiceIntentType.LIGHT_CONTROL.value,
            raw_command="Licht im Wohnzimmer an",
            zone_id="wohnzimmer",
            zone_name="Wohnzimmer",
            module_id="licht_module",
            module_name="Licht Modul",
            status=VoiceCommandStatus.SUCCESS.value,
            confidence_score=0.95,
            processing_time_ms=100.0,
            execution_time=(now - timedelta(hours=1)).isoformat(),
        ),
        VoiceCommandEntryV1(
            command_id=str(uuid.uuid4()),
            intent_type=VoiceIntentType.CLIMATE_CONTROL.value,
            raw_command="Temperatur auf 22 Grad",
            zone_id="schlafzimmer",
            zone_name="Schlafzimmer",
            module_id="heiz_module",
            module_name="Heizung Modul",
            status=VoiceCommandStatus.SUCCESS.value,
            confidence_score=0.88,
            processing_time_ms=150.0,
            execution_time=(now - timedelta(hours=2)).isoformat(),
        ),
        VoiceCommandEntryV1(
            command_id=str(uuid.uuid4()),
            intent_type=VoiceIntentType.LIGHT_CONTROL.value,
            raw_command="Licht in der Küche aus",
            zone_id="kueche",
            zone_name="Küche",
            module_id="licht_module",
            module_name="Licht Modul",
            status=VoiceCommandStatus.FAILED.value,
            confidence_score=0.72,
            processing_time_ms=50.0,
            execution_time=(now - timedelta(hours=3)).isoformat(),
            error_message="Module not responding",
        ),
        VoiceCommandEntryV1(
            command_id=str(uuid.uuid4()),
            intent_type=VoiceIntentType.SCENE_ACTIVATION.value,
            raw_command="Szene Abend aktivieren",
            zone_id="wohnzimmer",
            zone_name="Wohnzimmer",
            module_id=None,
            module_name=None,
            status=VoiceCommandStatus.SUCCESS.value,
            confidence_score=0.91,
            processing_time_ms=200.0,
            execution_time=(now - timedelta(hours=4)).isoformat(),
        ),
        VoiceCommandEntryV1(
            command_id=str(uuid.uuid4()),
            intent_type=VoiceIntentType.PROPOSAL_ACCEPT.value,
            raw_command="Ja, übernimm den Vorschlag",
            zone_id=None,
            zone_name=None,
            module_id=None,
            module_name=None,
            status=VoiceCommandStatus.SUCCESS.value,
            confidence_score=0.98,
            processing_time_ms=80.0,
            execution_time=(now - timedelta(hours=5)).isoformat(),
        ),
    ]

    for entry in entries:
        store.add_command_entry(entry)

    return store


class TestVoiceCommandEntryV1:
    """Tests für VoiceCommandEntryV1."""

    def test_entry_creation(self, sample_command):
        """Entry-Erstellung mit allen Feldern."""
        assert sample_command.command_id != ""
        assert sample_command.intent_type == "light_control"
        assert sample_command.raw_command == "Licht im Wohnzimmer an"
        assert sample_command.zone_id == "wohnzimmer"
        assert sample_command.zone_name == "Wohnzimmer"
        assert sample_command.module_id == "licht_module"
        assert sample_command.status == "success"
        assert sample_command.confidence_score == 0.95
        assert sample_command.processing_time_ms == 125.5

    def test_entry_with_error(self):
        """Entry mit Fehlerinformation."""
        entry = VoiceCommandEntryV1(
            command_id=str(uuid.uuid4()),
            intent_type=VoiceIntentType.CLIMATE_CONTROL.value,
            raw_command="Temperatur auf 25 Grad",
            zone_id="bad",
            zone_name="Bad",
            module_id="heiz_module",
            module_name="Heizung Modul",
            status=VoiceCommandStatus.FAILED.value,
            confidence_score=0.65,
            processing_time_ms=300.0,
            execution_time=datetime.now(timezone.utc).isoformat(),
            error_message="Timeout waiting for response",
        )
        assert entry.status == "failed"
        assert entry.error_message == "Timeout waiting for response"

    def test_entry_without_zone(self):
        """Entry ohne Zone (globale Commands)."""
        entry = VoiceCommandEntryV1(
            command_id=str(uuid.uuid4()),
            intent_type=VoiceIntentType.PROPOSAL_ACCEPT.value,
            raw_command="Ja",
            zone_id=None,
            zone_name=None,
            module_id=None,
            module_name=None,
            status=VoiceCommandStatus.SUCCESS.value,
            confidence_score=0.99,
            processing_time_ms=50.0,
            execution_time=datetime.now(timezone.utc).isoformat(),
        )
        assert entry.zone_id is None
        assert entry.module_id is None


class TestVoiceAnalyticsStore:
    """Tests für VoiceAnalyticsStore."""

    def test_store_initialization(self, temp_db):
        """Store-Initialisierung erstellt DB-Datei."""
        store = VoiceAnalyticsStore(db_path=temp_db)
        assert temp_db.exists()
        assert temp_db.suffix == ".db"

    def test_add_command_entry(self, store, sample_command):
        """Command-Eintrag hinzufügen."""
        revision = store.add_command_entry(sample_command)
        assert revision == 1

        history = store.build_history()
        assert history.total_count == 1
        assert len(history.entries) == 1
        assert history.entries[0].command_id == sample_command.command_id

    def test_build_history_with_filters(self, populated_store):
        """Historie mit Filtern."""
        # Nach intent_type filtern
        history = populated_store.build_history(intent_type="light_control")
        assert history.total_count == 2

        # Nach zone_id filtern
        history = populated_store.build_history(zone_id="wohnzimmer")
        assert history.total_count == 2

        # Nach status filtern
        history = populated_store.build_history(status="success")
        assert history.total_count == 4

    def test_build_history_with_time_range(self, populated_store):
        """Historie mit Zeitfilter."""
        now = datetime.now(timezone.utc)
        from_time = (now - timedelta(hours=4)).isoformat()
        to_time = (now - timedelta(hours=1)).isoformat()

        history = populated_store.build_history(from_time=from_time, to_time=to_time)
        assert history.total_count >= 2

    def test_build_history_with_limit_offset(self, populated_store):
        """Historie mit Limit und Offset."""
        history = populated_store.build_history(limit=2)
        assert len(history.entries) == 2
        assert history.total_count == 5

        history = populated_store.build_history(limit=2, offset=2)
        assert len(history.entries) == 2
        assert history.total_count == 5

    def test_build_intent_patterns(self, populated_store):
        """Intent Patterns aufbauen."""
        patterns = populated_store.build_intent_patterns(time_range_days=7)

        assert patterns.total_intents >= 3  # light_control, climate_control, scene_activation, proposal_accept
        assert patterns.active_intents >= 3

        # light_control Pattern prüfen
        light_pattern = next((p for p in patterns.patterns if p.intent_type == "light_control"), None)
        assert light_pattern is not None
        assert light_pattern.total_commands == 2
        assert light_pattern.success_count == 1
        assert light_pattern.failed_count == 1

    def test_get_effectiveness_metrics(self, populated_store):
        """Effectiveness-Metriken berechnen."""
        metrics = populated_store.get_effectiveness_metrics(time_range_days=7)

        assert metrics.total_commands_24h >= 5
        assert metrics.total_commands_7d >= 5
        assert 0.0 <= metrics.overall_success_rate <= 1.0
        assert 0.0 <= metrics.avg_confidence_score <= 1.0
        assert metrics.zone_coverage_total >= 2  # wohnzimmer, schlafzimmer, kueche
        assert "light_control" in metrics.intent_distribution

    def test_build_summary(self, populated_store):
        """Analytics Summary aufbauen."""
        summary = populated_store.build_summary(time_range_days=7)

        assert summary.revision >= 1
        assert summary.generated_at != ""
        assert "total_commands" in summary.history_summary
        assert "total_intents" in summary.patterns_summary
        assert "overall_success_rate" in summary.effectiveness_summary

    def test_revision_tracking(self, populated_store):
        """Revision-Tracking testen."""
        summary1 = populated_store.build_summary(time_range_days=7)

        # Neue Entry hinzufügen
        new_entry = VoiceCommandEntryV1(
            command_id=str(uuid.uuid4()),
            intent_type=VoiceIntentType.MEDIA_CONTROL.value,
            raw_command="Musik spielen",
            zone_id="kueche",
            zone_name="Küche",
            module_id="music_module",
            module_name="Music Modul",
            status=VoiceCommandStatus.SUCCESS.value,
            confidence_score=0.90,
            processing_time_ms=120.0,
            execution_time=datetime.now(timezone.utc).isoformat(),
        )
        populated_store.add_command_entry(new_entry)

        summary2 = populated_store.build_summary(time_range_days=7)
        assert summary2.revision > summary1.revision


class TestVoiceCommandStatus:
    """Tests für VoiceCommandStatus Enum."""

    def test_status_values(self):
        """Alle Status-Werte vorhanden."""
        assert VoiceCommandStatus.SUCCESS.value == "success"
        assert VoiceCommandStatus.PARTIAL.value == "partial"
        assert VoiceCommandStatus.FAILED.value == "failed"
        assert VoiceCommandStatus.REJECTED.value == "rejected"
        assert VoiceCommandStatus.TIMEOUT.value == "timeout"
        assert VoiceCommandStatus.CANCELLED.value == "cancelled"


class TestVoiceIntentType:
    """Tests für VoiceIntentType Enum."""

    def test_intent_values(self):
        """Alle Intent-Typen vorhanden."""
        assert VoiceIntentType.LIGHT_CONTROL.value == "light_control"
        assert VoiceIntentType.CLIMATE_CONTROL.value == "climate_control"
        assert VoiceIntentType.SCENE_ACTIVATION.value == "scene_activation"
        assert VoiceIntentType.PRESENCE_QUERY.value == "presence_query"
        assert VoiceIntentType.STATUS_QUERY.value == "status_query"
        assert VoiceIntentType.MEDIA_CONTROL.value == "media_control"
        assert VoiceIntentType.SCHEDULE_QUERY.value == "schedule_query"
        assert VoiceIntentType.PROPOSAL_ACCEPT.value == "proposal_accept"
        assert VoiceIntentType.PROPOSAL_REJECT.value == "proposal_reject"
        assert VoiceIntentType.GENERAL_COMMAND.value == "general_command"


class TestVoiceIntentPatternEntryV1:
    """Tests für VoiceIntentPatternEntryV1."""

    def test_pattern_creation(self):
        """Pattern-Eintrag erstellen."""
        pattern = VoiceIntentPatternEntryV1(
            intent_type="light_control",
            total_commands=100,
            success_count=85,
            partial_count=5,
            failed_count=5,
            rejected_count=5,
            success_rate=0.875,
            avg_confidence_score=0.92,
            avg_processing_time_ms=120.0,
            min_processing_time_ms=50.0,
            max_processing_time_ms=500.0,
            p95_processing_time_ms=350.0,
            last_command_time=datetime.now(timezone.utc).isoformat(),
            last_status="success",
            trend="improving",
            zone_coverage=5,
        )
        assert pattern.total_commands == 100
        assert pattern.success_rate == 0.875
        assert pattern.avg_confidence_score == 0.92
        assert pattern.trend == "improving"


class TestVoiceEffectivenessMetricsV1:
    """Tests für VoiceEffectivenessMetricsV1."""

    def test_metrics_creation(self):
        """Metrics-Eintrag erstellen."""
        metrics = VoiceEffectivenessMetricsV1(
            overall_success_rate=0.88,
            total_commands_24h=150,
            total_commands_7d=800,
            avg_confidence_score=0.91,
            avg_processing_time_ms=125.0,
            intent_distribution={"light_control": 400, "climate_control": 200},
            zone_coverage_total=8,
            rejection_rate=0.05,
            timeout_rate=0.02,
            revision=1,
        )
        assert metrics.overall_success_rate == 0.88
        assert metrics.total_commands_24h == 150
        assert metrics.avg_confidence_score == 0.91
        assert metrics.rejection_rate == 0.05


class TestVoiceAnalyticsGlobalStore:
    """Tests für globalen Store-Accessor."""

    def test_get_voice_analytics_store_singleton(self, temp_db, monkeypatch):
        """get_voice_analytics_store() liefert Singleton."""
        import copilot_core.analytics.voice_analytics as mod
        mod._store = None

        store1 = get_voice_analytics_store(db_path=temp_db)
        store2 = get_voice_analytics_store(db_path=temp_db)

        assert store1 is store2
