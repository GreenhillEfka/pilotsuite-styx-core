"""Weather Analytics API Contract Tests — Slice 51."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from copilot_core.weather.api import create_weather_analytics_blueprint


@pytest.fixture
def app():
    """Flask-App mit Weather Analytics Blueprint."""
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(create_weather_analytics_blueprint())
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Test-Client."""
    return app.test_client()


@pytest.fixture
def mock_store():
    """Mock-Store für API-Tests."""
    with patch("copilot_core.weather.api.get_weather_analytics_store") as mock_get:
        mock_store_instance = MagicMock()
        mock_get.return_value = mock_store_instance
        yield mock_store_instance


class TestWeatherAnalyticsUsageAPI:
    """Tests für /api/v1/weather/analytics/usage."""

    def test_get_observation_history(self, client, mock_store):
        """Observation-Historie abrufen."""
        from copilot_core.weather.analytics import WeatherObservationHistoryV1, WeatherObservationEntryV1

        mock_usage = WeatherObservationHistoryV1(
            entries=[
                WeatherObservationEntryV1(
                    entry_id="entry-001",
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
            ],
            total_observations=1,
            total_alerts=0,
            total_notifications=0,
            total_automations=0,
            avg_temperature_celsius=22.5,
            avg_humidity_percent=65.0,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_observation_history.return_value = mock_usage

        response = client.get("/api/v1/weather/analytics/usage")

        assert response.status_code == 200
        data = response.get_json()
        assert "usage" in data
        assert data["usage"]["total_observations"] == 1
        assert data["usage"]["avg_temperature_celsius"] == 22.5

    def test_get_usage_with_filters(self, client, mock_store):
        """Usage mit Filtern."""
        from copilot_core.weather.analytics import WeatherObservationHistoryV1

        mock_usage = WeatherObservationHistoryV1(
            entries=[],
            total_observations=0,
            total_alerts=0,
            total_notifications=0,
            total_automations=0,
            avg_temperature_celsius=None,
            avg_humidity_percent=None,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_observation_history.return_value = mock_usage

        response = client.get(
            "/api/v1/weather/analytics/usage?"
            "zone_id=zone-test&"
            "event_type=storm_warning&"
            "limit=50"
        )

        assert response.status_code == 200
        mock_store.build_observation_history.assert_called_once_with(
            time_range_start=None,
            time_range_end=None,
            zone_id="zone-test",
            event_type="storm_warning",
            limit=50,
        )


class TestWeatherAnalyticsPatternsAPI:
    """Tests für /api/v1/weather/analytics/patterns."""

    def test_get_zone_patterns(self, client, mock_store):
        """Zone-Patterns abrufen."""
        from copilot_core.weather.analytics import WeatherZonePatternsV1, WeatherZonePatternEntryV1

        mock_patterns = WeatherZonePatternsV1(
            patterns=[
                WeatherZonePatternEntryV1(
                    zone_id="zone-garten",
                    zone_name="Garten",
                    total_observations=50,
                    temperature_events=30,
                    precipitation_events=15,
                    wind_events=5,
                    alert_events=3,
                    avg_temperature_celsius=18.5,
                    min_temperature_celsius=5.0,
                    max_temperature_celsius=32.0,
                    avg_humidity_percent=62.0,
                    avg_wind_speed_kmh=15.0,
                    total_precipitation_mm=120.5,
                    observations_last_24_hours=8,
                    observations_last_7_days=50,
                    most_common_event_type="temperature_change",
                    most_common_source="wttr_in",
                    peak_alert_hour=14,
                )
            ],
            total_zones=1,
            zones_with_weather_data=1,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_zone_patterns.return_value = mock_patterns

        response = client.get("/api/v1/weather/analytics/patterns")

        assert response.status_code == 200
        data = response.get_json()
        assert "patterns" in data
        assert data["patterns"]["total_zones"] == 1
        assert data["patterns"]["zones_with_weather_data"] == 1

    def test_get_patterns_with_zone_filter(self, client, mock_store):
        """Patterns mit Zone-Filter."""
        from copilot_core.weather.analytics import WeatherZonePatternsV1

        mock_patterns = WeatherZonePatternsV1(
            patterns=[],
            total_zones=0,
            zones_with_weather_data=0,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_zone_patterns.return_value = mock_patterns

        response = client.get("/api/v1/weather/analytics/patterns?zone_ids=zone-a&zone_ids=zone-b")

        assert response.status_code == 200
        mock_store.build_zone_patterns.assert_called_once_with(zone_ids=["zone-a", "zone-b"])


class TestWeatherAnalyticsEffectivenessAPI:
    """Tests für /api/v1/weather/analytics/effectiveness."""

    def test_get_effectiveness(self, client, mock_store):
        """Effectiveness-Metriken abrufen."""
        from copilot_core.weather.analytics import WeatherEffectivenessMetricsV1

        mock_metrics = WeatherEffectivenessMetricsV1(
            total_observations_analyzed=200,
            observations_by_type={"temperature_change": 100, "precipitation": 50, "storm_warning": 50},
            observations_by_source={"wttr_in": 120, "dwd": 80},
            alert_accuracy_rate=None,
            notification_delivery_rate=0.90,
            automation_trigger_rate=0.35,
            avg_observations_per_zone=40.0,
            zones_with_regular_data=4,
            zones_with_rare_data=1,
            peak_weather_time="morning",
            forecast_accuracy_score=None,
            engagement_score=0.68,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.get_effectiveness_metrics.return_value = mock_metrics

        response = client.get("/api/v1/weather/analytics/effectiveness")

        assert response.status_code == 200
        data = response.get_json()
        assert "effectiveness" in data
        assert data["effectiveness"]["total_observations_analyzed"] == 200
        assert data["effectiveness"]["engagement_score"] == 0.68
        assert data["effectiveness"]["notification_delivery_rate"] == 0.90


class TestWeatherAnalyticsSummaryAPI:
    """Tests für /api/v1/weather/analytics/summary."""

    def test_get_summary(self, client, mock_store):
        """Analytics-Zusammenfassung abrufen."""
        from copilot_core.weather.analytics import (
            WeatherObservationHistoryV1,
            WeatherZonePatternsV1,
            WeatherEffectivenessMetricsV1,
            WeatherAnalyticsSummaryV1,
        )

        mock_summary = WeatherAnalyticsSummaryV1(
            usage=WeatherObservationHistoryV1(
                entries=[],
                total_observations=100,
                total_alerts=10,
                total_notifications=9,
                total_automations=5,
                avg_temperature_celsius=18.5,
                avg_humidity_percent=62.0,
                revision=1,
                latest_change_at=datetime.now(timezone.utc).isoformat(),
            ),
            patterns=WeatherZonePatternsV1(
                patterns=[],
                total_zones=5,
                zones_with_weather_data=5,
                revision=1,
                latest_change_at=datetime.now(timezone.utc).isoformat(),
            ),
            effectiveness=WeatherEffectivenessMetricsV1(
                total_observations_analyzed=100,
                observations_by_type={},
                observations_by_source={},
                alert_accuracy_rate=None,
                notification_delivery_rate=0.9,
                automation_trigger_rate=0.3,
                avg_observations_per_zone=20.0,
                zones_with_regular_data=3,
                zones_with_rare_data=2,
                peak_weather_time="morning",
                forecast_accuracy_score=None,
                engagement_score=0.60,
                revision=1,
                latest_change_at=datetime.now(timezone.utc).isoformat(),
            ),
            summary_revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_summary.return_value = mock_summary

        response = client.get("/api/v1/weather/analytics/summary")

        assert response.status_code == 200
        data = response.get_json()
        assert "summary" in data
        assert data["summary"]["summary_revision"] == 1
        assert data["summary"]["usage"]["total_observations"] == 100
        assert data["summary"]["patterns"]["zones_with_weather_data"] == 5
        assert data["summary"]["effectiveness"]["engagement_score"] == 0.60


class TestWeatherAnalyticsAPIIntegration:
    """Integrationstests für Weather Analytics API."""

    def test_full_analytics_flow(self, client, mock_store):
        """Vollständiger Analytics-Flow."""
        from copilot_core.weather.analytics import (
            WeatherObservationEntryV1,
            WeatherObservationHistoryV1,
            WeatherZonePatternsV1,
            WeatherEffectivenessMetricsV1,
            WeatherAnalyticsSummaryV1,
        )

        # Mock alle Store-Methoden
        mock_store.build_observation_history.return_value = WeatherObservationHistoryV1(
            entries=[],
            total_observations=150,
            total_alerts=15,
            total_notifications=14,
            total_automations=8,
            avg_temperature_celsius=19.0,
            avg_humidity_percent=60.0,
            revision=5,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_zone_patterns.return_value = WeatherZonePatternsV1(
            patterns=[],
            total_zones=10,
            zones_with_weather_data=8,
            revision=5,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.get_effectiveness_metrics.return_value = WeatherEffectivenessMetricsV1(
            total_observations_analyzed=150,
            observations_by_type={"temperature_change": 80, "precipitation": 70},
            observations_by_source={"wttr_in": 100, "dwd": 50},
            alert_accuracy_rate=None,
            notification_delivery_rate=0.93,
            automation_trigger_rate=0.40,
            avg_observations_per_zone=15.0,
            zones_with_regular_data=5,
            zones_with_rare_data=3,
            peak_weather_time="morning",
            forecast_accuracy_score=None,
            engagement_score=0.70,
            revision=5,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_summary.return_value = WeatherAnalyticsSummaryV1(
            usage=mock_store.build_observation_history.return_value,
            patterns=mock_store.build_zone_patterns.return_value,
            effectiveness=mock_store.get_effectiveness_metrics.return_value,
            summary_revision=5,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        # Alle Endpoints testen
        endpoints = [
            "/api/v1/weather/analytics/usage",
            "/api/v1/weather/analytics/patterns",
            "/api/v1/weather/analytics/effectiveness",
            "/api/v1/weather/analytics/summary",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, f"Endpoint {endpoint} failed"
