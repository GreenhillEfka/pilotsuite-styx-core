"""Weather Analytics Contract Tests — Slice 51."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from copilot_core.weather.analytics import (
    WeatherObservationEntryV1,
    WeatherObservationHistoryV1,
    WeatherZonePatternEntryV1,
    WeatherZonePatternsV1,
    WeatherEffectivenessMetricsV1,
    WeatherAnalyticsSummaryV1,
    WeatherEventType,
    WeatherDataSource,
)
from copilot_core.weather.analytics_store import (
    WeatherAnalyticsStore,
    get_weather_analytics_store,
)


class TestWeatherObservationEntryV1:
    """Tests für WeatherObservationEntryV1."""

    def test_create_entry(self):
        """Entry kann erstellt werden."""
        entry = WeatherObservationEntryV1(
            entry_id="weather-entry-001",
            zone_id="zone-garten",
            zone_name="Garten",
            event_type="temperature_change",
            source="wttr_in",
            temperature_celsius=22.5,
            humidity_percent=65.0,
            wind_speed_kmh=12.0,
            precipitation_mm=0.0,
            pressure_hpa=1013.25,
            uv_index=5.0,
            air_quality_index=42,
            alert_triggered=False,
            notification_sent=False,
            automation_triggered=False,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )

        assert entry.entry_id == "weather-entry-001"
        assert entry.zone_id == "zone-garten"
        assert entry.event_type == "temperature_change"
        assert entry.temperature_celsius == 22.5

    def test_entry_with_alert(self):
        """Entry mit Alert."""
        entry = WeatherObservationEntryV1(
            entry_id="weather-entry-002",
            zone_id="zone-wohnzimmer",
            zone_name="Wohnzimmer",
            event_type="storm_warning",
            source="dwd",
            temperature_celsius=18.0,
            humidity_percent=80.0,
            wind_speed_kmh=85.0,
            precipitation_mm=5.0,
            pressure_hpa=995.0,
            uv_index=2.0,
            air_quality_index=None,
            alert_triggered=True,
            notification_sent=True,
            automation_triggered=True,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )

        assert entry.alert_triggered is True
        assert entry.notification_sent is True
        assert entry.automation_triggered is True


class TestWeatherAnalyticsStore:
    """Tests für WeatherAnalyticsStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Store mit temporärer DB."""
        db_path = tmp_path / "weather_analytics.db"
        return WeatherAnalyticsStore(db_path=str(db_path))

    def test_add_and_retrieve_entry(self, store):
        """Entry hinzufügen und abrufen."""
        entry = WeatherObservationEntryV1(
            entry_id="test-entry-001",
            zone_id="zone-test",
            zone_name="Test Zone",
            event_type="temperature_change",
            source="wttr_in",
            temperature_celsius=20.0,
            humidity_percent=60.0,
            wind_speed_kmh=10.0,
            precipitation_mm=0.0,
            pressure_hpa=1013.0,
            uv_index=3.0,
            air_quality_index=30,
            alert_triggered=False,
            notification_sent=False,
            automation_triggered=False,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )

        store.add_observation_entry(entry)
        usage = store.build_observation_history(limit=10)

        assert usage.total_observations == 1
        assert usage.total_alerts == 0
        assert usage.total_notifications == 0
        assert usage.avg_temperature_celsius == 20.0

    def test_observation_history_with_filters(self, store):
        """Observation-Historie mit Filtern."""
        now = datetime.now(timezone.utc)

        # Entries für verschiedene Zonen und Event-Typen
        entries = [
            WeatherObservationEntryV1(
                entry_id=f"entry-{i}",
                zone_id="zone-a" if i % 2 == 0 else "zone-b",
                zone_name="Zone A" if i % 2 == 0 else "Zone B",
                event_type="temperature_change" if i % 3 == 0 else "precipitation",
                source="wttr_in",
                temperature_celsius=20.0 + i,
                humidity_percent=50.0 + i,
                wind_speed_kmh=10.0,
                precipitation_mm=0.0,
                pressure_hpa=1013.0,
                uv_index=3.0,
                air_quality_index=30,
                alert_triggered=i % 4 == 0,
                notification_sent=i % 4 == 0,
                automation_triggered=i % 5 == 0,
                observed_at=(now - timedelta(hours=i)).isoformat(),
            )
            for i in range(10)
        ]

        for entry in entries:
            store.add_observation_entry(entry)

        # Filter nach Zone
        usage_zone_a = store.build_observation_history(zone_id="zone-a", limit=10)
        assert usage_zone_a.total_observations <= 5

        # Filter nach Event-Typ
        usage_temp = store.build_observation_history(event_type="temperature_change", limit=10)
        assert usage_temp.total_observations <= 4

    def test_zone_patterns(self, store):
        """Zone-Patterns aufbauen."""
        now = datetime.now(timezone.utc)

        # Mehrere Entries für eine Zone
        for i in range(25):
            entry = WeatherObservationEntryV1(
                entry_id=f"pattern-entry-{i}",
                zone_id="zone-pattern-test",
                zone_name="Pattern Test Zone",
                event_type="temperature_change" if i % 2 == 0 else "precipitation",
                source="wttr_in",
                temperature_celsius=15.0 + (i % 10),
                humidity_percent=50.0 + (i % 30),
                wind_speed_kmh=10.0 + (i % 20),
                precipitation_mm=float(i % 5),
                pressure_hpa=1013.0,
                uv_index=3.0,
                air_quality_index=30,
                alert_triggered=i % 10 == 0,
                notification_sent=i % 10 == 0,
                automation_triggered=i % 15 == 0,
                observed_at=(now - timedelta(hours=i)).isoformat(),
            )
            store.add_observation_entry(entry)

        patterns = store.build_zone_patterns()

        assert patterns.total_zones >= 1
        assert patterns.zones_with_weather_data >= 1

        if patterns.patterns:
            pattern = patterns.patterns[0]
            assert pattern.total_observations >= 25
            assert pattern.temperature_events > 0 or pattern.precipitation_events > 0
            assert pattern.avg_temperature_celsius is not None

    def test_effectiveness_metrics(self, store):
        """Effectiveness-Metriken berechnen."""
        now = datetime.now(timezone.utc)

        # Verschiedene Event-Typen hinzufügen
        event_types = [
            "temperature_change", "precipitation", "wind_alert",
            "storm_warning", "frost_warning", "heat_warning"
        ]
        sources = ["wttr_in", "open_meteo", "dwd", "manual"]

        for i in range(50):
            entry = WeatherObservationEntryV1(
                entry_id=f"effect-entry-{i}",
                zone_id=f"zone-{i % 5}",
                zone_name=f"Zone {i % 5}",
                event_type=event_types[i % len(event_types)],
                source=sources[i % len(sources)],
                temperature_celsius=15.0 + (i % 15),
                humidity_percent=40.0 + (i % 40),
                wind_speed_kmh=5.0 + (i % 30),
                precipitation_mm=float(i % 10),
                pressure_hpa=1013.0,
                uv_index=3.0,
                air_quality_index=30,
                alert_triggered=i % 5 == 0,
                notification_sent=i % 6 != 0,
                automation_triggered=i % 8 == 0,
                observed_at=(now - timedelta(minutes=i)).isoformat(),
            )
            store.add_observation_entry(entry)

        metrics = store.get_effectiveness_metrics()

        assert metrics.total_observations_analyzed == 50
        assert len(metrics.observations_by_type) > 0
        assert len(metrics.observations_by_source) > 0
        assert 0.0 <= metrics.notification_delivery_rate <= 1.0
        assert 0.0 <= metrics.automation_trigger_rate <= 1.0
        assert 0.0 <= metrics.engagement_score <= 1.0

    def test_revision_tracking(self, store):
        """Revisionstracking bei Änderungen."""
        initial_revision = store._revision

        entry = WeatherObservationEntryV1(
            entry_id="rev-entry-001",
            zone_id="zone-rev",
            zone_name="Rev Zone",
            event_type="temperature_change",
            source="wttr_in",
            temperature_celsius=20.0,
            humidity_percent=60.0,
            wind_speed_kmh=10.0,
            precipitation_mm=0.0,
            pressure_hpa=1013.0,
            uv_index=3.0,
            air_quality_index=30,
            alert_triggered=False,
            notification_sent=False,
            automation_triggered=False,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )

        store.add_observation_entry(entry)

        assert store._revision > initial_revision

    def test_build_summary(self, store):
        """Zusammenfassung aller Analytics."""
        now = datetime.now(timezone.utc)

        # Einige Test-Einträge
        for i in range(5):
            entry = WeatherObservationEntryV1(
                entry_id=f"summary-entry-{i}",
                zone_id="zone-summary",
                zone_name="Summary Zone",
                event_type="temperature_change",
                source="wttr_in",
                temperature_celsius=20.0 + i,
                humidity_percent=60.0,
                wind_speed_kmh=10.0,
                precipitation_mm=0.0,
                pressure_hpa=1013.0,
                uv_index=3.0,
                air_quality_index=30,
                alert_triggered=False,
                notification_sent=False,
                automation_triggered=False,
                observed_at=(now - timedelta(hours=i)).isoformat(),
            )
            store.add_observation_entry(entry)

        summary = store.build_summary()

        assert summary.usage.total_observations == 5
        assert summary.patterns.zones_with_weather_data >= 1
        assert summary.effectiveness.total_observations_analyzed == 5
        assert summary.summary_revision == store._revision


class TestWeatherAnalyticsSingleton:
    """Tests für Singleton-Getter."""

    @patch("copilot_core.weather.analytics_store.WeatherAnalyticsStore")
    def test_get_weather_analytics_store(self, mock_store_class):
        """Singleton-Getter liefert Store."""
        mock_instance = MagicMock()
        mock_store_class.return_value = mock_instance

        # Reset global variable
        import copilot_core.weather.analytics_store as mod
        mod._weather_analytics_store = None

        store1 = get_weather_analytics_store()
        store2 = get_weather_analytics_store()

        assert store1 is store2
        mock_store_class.assert_called_once()


class TestWeatherEventTypes:
    """Tests für WeatherEventType Enum."""

    def test_all_event_types(self):
        """Alle Event-Typen verfügbar."""
        expected_types = [
            "temperature_change",
            "precipitation",
            "wind_alert",
            "storm_warning",
            "frost_warning",
            "heat_warning",
            "uv_index_high",
            "air_quality_alert",
            "pollen_high",
            "humidity_extreme",
            "pressure_drop",
            "sunrise",
            "sunset",
        ]

        for event_type in expected_types:
            assert event_type in [e.value for e in WeatherEventType]


class TestWeatherDataSources:
    """Tests für WeatherDataSource Enum."""

    def test_all_sources(self):
        """Alle Source-Typen verfügbar."""
        expected_sources = [
            "wttr_in",
            "open_meteo",
            "dwd",
            "met_no",
            "manual",
            "home_sensor",
            "zone_sensor",
            "schedule",
            "alert_trigger",
        ]

        for source in expected_sources:
            assert source in [s.value for s in WeatherDataSource]


class TestWeatherZonePatternsV1:
    """Tests für WeatherZonePatternsV1."""

    def test_empty_patterns(self):
        """Leere Patterns."""
        patterns = WeatherZonePatternsV1(
            patterns=[],
            total_zones=0,
            zones_with_weather_data=0,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        assert patterns.total_zones == 0
        assert patterns.zones_with_weather_data == 0
        assert len(patterns.patterns) == 0


class TestWeatherEffectivenessMetricsV1:
    """Tests für WeatherEffectivenessMetricsV1."""

    def test_metrics_with_zero_observations(self):
        """Metriken mit null Observations."""
        metrics = WeatherEffectivenessMetricsV1(
            total_observations_analyzed=0,
            observations_by_type={},
            observations_by_source={},
            alert_accuracy_rate=None,
            notification_delivery_rate=0.0,
            automation_trigger_rate=0.0,
            avg_observations_per_zone=0.0,
            zones_with_regular_data=0,
            zones_with_rare_data=0,
            peak_weather_time=None,
            forecast_accuracy_score=None,
            engagement_score=0.0,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        assert metrics.total_observations_analyzed == 0
        assert metrics.engagement_score == 0.0
        assert metrics.alert_accuracy_rate is None
        assert metrics.forecast_accuracy_score is None
