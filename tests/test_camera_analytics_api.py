"""Camera Analytics API Contract Tests — Slice 50."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from copilot_core.camera.api import create_camera_analytics_blueprint


@pytest.fixture
def app():
    """Flask-App mit Camera Analytics Blueprint."""
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(create_camera_analytics_blueprint())
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Test-Client."""
    return app.test_client()


@pytest.fixture
def mock_store():
    """Mock-Store für API-Tests."""
    with patch("copilot_core.camera.api.get_camera_analytics_store") as mock_get:
        mock_store_instance = MagicMock()
        mock_get.return_value = mock_store_instance
        yield mock_store_instance


class TestCameraAnalyticsUsageAPI:
    """Tests für /api/v1/camera/analytics/usage."""

    def test_get_usage_history(self, client, mock_store):
        """Usage-Historie abrufen."""
        from copilot_core.camera.analytics import CameraUsageHistoryV1, CameraUsageEntryV1

        mock_usage = CameraUsageHistoryV1(
            entries=[
                CameraUsageEntryV1(
                    entry_id="entry-001",
                    zone_id="zone-wohnzimmer",
                    zone_name="Wohnzimmer",
                    camera_id="cam-001",
                    camera_name="Front Door",
                    event_type="motion_detected",
                    source="auto_motion",
                    snapshot_taken=True,
                    recording_started=True,
                    recording_duration_seconds=30,
                    thumbnail_generated=True,
                    notification_sent=True,
                    processed_at=datetime.now(timezone.utc).isoformat(),
                )
            ],
            total_events=1,
            total_snapshots=1,
            total_recordings=1,
            total_recording_duration_seconds=30,
            avg_recording_duration_seconds=30.0,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_usage_history.return_value = mock_usage

        response = client.get("/api/v1/camera/analytics/usage")

        assert response.status_code == 200
        data = response.get_json()
        assert "usage" in data
        assert data["usage"]["total_events"] == 1
        assert data["usage"]["total_snapshots"] == 1

    def test_get_usage_with_filters(self, client, mock_store):
        """Usage mit Filtern."""
        from copilot_core.camera.analytics import CameraUsageHistoryV1

        mock_usage = CameraUsageHistoryV1(
            entries=[],
            total_events=0,
            total_snapshots=0,
            total_recordings=0,
            total_recording_duration_seconds=0,
            avg_recording_duration_seconds=None,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_usage_history.return_value = mock_usage

        response = client.get(
            "/api/v1/camera/analytics/usage?"
            "zone_id=zone-test&"
            "event_type=motion_detected&"
            "limit=50"
        )

        assert response.status_code == 200
        mock_store.build_usage_history.assert_called_once_with(
            time_range_start=None,
            time_range_end=None,
            zone_id="zone-test",
            event_type="motion_detected",
            limit=50,
        )


class TestCameraAnalyticsPatternsAPI:
    """Tests für /api/v1/camera/analytics/patterns."""

    def test_get_zone_patterns(self, client, mock_store):
        """Zone-Patterns abrufen."""
        from copilot_core.camera.analytics import CameraZonePatternsV1, CameraZonePatternEntryV1

        mock_patterns = CameraZonePatternsV1(
            patterns=[
                CameraZonePatternEntryV1(
                    zone_id="zone-wohnzimmer",
                    zone_name="Wohnzimmer",
                    total_events=25,
                    motion_events=15,
                    person_events=10,
                    vehicle_events=0,
                    sound_events=0,
                    doorbell_events=0,
                    snapshots_taken=20,
                    recordings_started=10,
                    avg_recording_duration_seconds=35.5,
                    peak_activity_hour=18,
                    events_last_24_hours=10,
                    events_last_7_days=25,
                    most_common_event_type="motion_detected",
                    most_common_source="auto_motion",
                )
            ],
            total_zones=1,
            zones_with_camera_activity=1,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_zone_patterns.return_value = mock_patterns

        response = client.get("/api/v1/camera/analytics/patterns")

        assert response.status_code == 200
        data = response.get_json()
        assert "patterns" in data
        assert data["patterns"]["total_zones"] == 1
        assert data["patterns"]["zones_with_camera_activity"] == 1

    def test_get_patterns_with_zone_filter(self, client, mock_store):
        """Patterns mit Zone-Filter."""
        from copilot_core.camera.analytics import CameraZonePatternsV1

        mock_patterns = CameraZonePatternsV1(
            patterns=[],
            total_zones=0,
            zones_with_camera_activity=0,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_zone_patterns.return_value = mock_patterns

        response = client.get("/api/v1/camera/analytics/patterns?zone_ids=zone-a&zone_ids=zone-b")

        assert response.status_code == 200
        mock_store.build_zone_patterns.assert_called_once_with(zone_ids=["zone-a", "zone-b"])


class TestCameraAnalyticsEffectivenessAPI:
    """Tests für /api/v1/camera/analytics/effectiveness."""

    def test_get_effectiveness(self, client, mock_store):
        """Effectiveness-Metriken abrufen."""
        from copilot_core.camera.analytics import CameraEffectivenessMetricsV1

        mock_metrics = CameraEffectivenessMetricsV1(
            total_events_analyzed=100,
            events_by_type={"motion_detected": 50, "person_detected": 30, "vehicle_detected": 20},
            events_by_source={"auto_motion": 60, "schedule": 40},
            motion_to_person_ratio=0.6,
            false_positive_rate=None,
            notification_delivery_rate=0.95,
            snapshot_capture_rate=0.85,
            recording_trigger_rate=0.40,
            avg_events_per_zone=20.0,
            zones_with_regular_activity=3,
            zones_with_rare_activity=2,
            peak_activity_time="evening",
            engagement_score=0.72,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.get_effectiveness_metrics.return_value = mock_metrics

        response = client.get("/api/v1/camera/analytics/effectiveness")

        assert response.status_code == 200
        data = response.get_json()
        assert "effectiveness" in data
        assert data["effectiveness"]["total_events_analyzed"] == 100
        assert data["effectiveness"]["engagement_score"] == 0.72
        assert data["effectiveness"]["notification_delivery_rate"] == 0.95


class TestCameraAnalyticsSummaryAPI:
    """Tests für /api/v1/camera/analytics/summary."""

    def test_get_summary(self, client, mock_store):
        """Analytics-Zusammenfassung abrufen."""
        from copilot_core.camera.analytics import (
            CameraUsageHistoryV1,
            CameraZonePatternsV1,
            CameraEffectivenessMetricsV1,
            CameraAnalyticsSummaryV1,
        )

        mock_summary = CameraAnalyticsSummaryV1(
            usage=CameraUsageHistoryV1(
                entries=[],
                total_events=50,
                total_snapshots=40,
                total_recordings=20,
                total_recording_duration_seconds=600,
                avg_recording_duration_seconds=30.0,
                revision=1,
                latest_change_at=datetime.now(timezone.utc).isoformat(),
            ),
            patterns=CameraZonePatternsV1(
                patterns=[],
                total_zones=5,
                zones_with_camera_activity=4,
                revision=1,
                latest_change_at=datetime.now(timezone.utc).isoformat(),
            ),
            effectiveness=CameraEffectivenessMetricsV1(
                total_events_analyzed=50,
                events_by_type={},
                events_by_source={},
                motion_to_person_ratio=0.5,
                false_positive_rate=None,
                notification_delivery_rate=0.9,
                snapshot_capture_rate=0.8,
                recording_trigger_rate=0.4,
                avg_events_per_zone=10.0,
                zones_with_regular_activity=2,
                zones_with_rare_activity=2,
                peak_activity_time="evening",
                engagement_score=0.65,
                revision=1,
                latest_change_at=datetime.now(timezone.utc).isoformat(),
            ),
            summary_revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_summary.return_value = mock_summary

        response = client.get("/api/v1/camera/analytics/summary")

        assert response.status_code == 200
        data = response.get_json()
        assert "summary" in data
        assert data["summary"]["summary_revision"] == 1
        assert data["summary"]["usage"]["total_events"] == 50
        assert data["summary"]["patterns"]["zones_with_camera_activity"] == 4
        assert data["summary"]["effectiveness"]["engagement_score"] == 0.65


class TestCameraAnalyticsAPIIntegration:
    """Integrationstests für Camera Analytics API."""

    def test_full_analytics_flow(self, client, mock_store):
        """Vollständiger Analytics-Flow."""
        from copilot_core.camera.analytics import (
            CameraUsageEntryV1,
            CameraUsageHistoryV1,
            CameraZonePatternsV1,
            CameraEffectivenessMetricsV1,
            CameraAnalyticsSummaryV1,
        )

        # Mock alle Store-Methoden
        mock_store.build_usage_history.return_value = CameraUsageHistoryV1(
            entries=[],
            total_events=100,
            total_snapshots=80,
            total_recordings=50,
            total_recording_duration_seconds=1500,
            avg_recording_duration_seconds=30.0,
            revision=5,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_zone_patterns.return_value = CameraZonePatternsV1(
            patterns=[],
            total_zones=10,
            zones_with_camera_activity=8,
            revision=5,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.get_effectiveness_metrics.return_value = CameraEffectivenessMetricsV1(
            total_events_analyzed=100,
            events_by_type={"motion_detected": 60, "person_detected": 40},
            events_by_source={"auto_motion": 70, "schedule": 30},
            motion_to_person_ratio=0.67,
            false_positive_rate=None,
            notification_delivery_rate=0.92,
            snapshot_capture_rate=0.80,
            recording_trigger_rate=0.50,
            avg_events_per_zone=10.0,
            zones_with_regular_activity=5,
            zones_with_rare_activity=3,
            peak_activity_time="evening",
            engagement_score=0.75,
            revision=5,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_store.build_summary.return_value = CameraAnalyticsSummaryV1(
            usage=mock_store.build_usage_history.return_value,
            patterns=mock_store.build_zone_patterns.return_value,
            effectiveness=mock_store.get_effectiveness_metrics.return_value,
            summary_revision=5,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        # Alle Endpoints testen
        endpoints = [
            "/api/v1/camera/analytics/usage",
            "/api/v1/camera/analytics/patterns",
            "/api/v1/camera/analytics/effectiveness",
            "/api/v1/camera/analytics/summary",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, f"Endpoint {endpoint} failed"
