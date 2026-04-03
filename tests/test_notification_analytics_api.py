"""Notification Analytics API Contract Tests — Slice 52."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from copilot_core.notifications.analytics_store import NotificationAnalyticsStore, get_notification_analytics_store


class TestNotificationAnalyticsAPI:
    """API-Tests für Notification Analytics Endpoints."""

    @pytest.fixture
    def app(self):
        """Flask-App für Testing."""
        from copilot_core.app import create_app
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Test-Client."""
        return app.test_client()

    @pytest.fixture
    def store_with_data(self, tmp_path):
        """Store mit Testdaten."""
        db_path = tmp_path / "notification_analytics.db"
        store = NotificationAnalyticsStore(db_path=str(db_path))
        now = datetime.now(timezone.utc)

        # Add test data
        for i in range(5):
            from copilot_core.notifications.analytics import NotificationDeliveryEntryV1
            entry = NotificationDeliveryEntryV1(
                entry_id=f"entry_{i}",
                notification_id=f"notif_{i}",
                channel="telegram",
                notification_type="alert",
                recipient_id="user_123",
                zone_id="living",
                zone_name="Wohnbereich",
                title=f"Alert {i}",
                body="Body",
                priority="high",
                status="delivered",
                sent_at=now.isoformat(),
                delivered_at=now.isoformat(),
                read_at=None,
                acknowledged_at=None,
                failed_reason=None,
                retry_count=0,
            )
            store.add_delivery_entry(entry)

        # Patch the singleton
        with patch('copilot_core.notifications.api.get_notification_analytics_store', return_value=store):
            yield store

    def test_get_delivery_history(self, client, store_with_data):
        """GET /api/v1/notifications/analytics/delivery."""
        response = client.get("/api/v1/notifications/analytics/delivery")
        assert response.status_code == 200

        data = response.get_json()
        assert "delivery" in data
        assert "entries" in data["delivery"]
        assert "total_notifications" in data["delivery"]
        assert data["delivery"]["total_notifications"] == 5
        assert "revision" in data["delivery"]

    def test_get_delivery_history_with_filters(self, client, store_with_data):
        """GET /api/v1/notifications/analytics/delivery mit Filtern."""
        response = client.get("/api/v1/notifications/analytics/delivery?channel=telegram&limit=3")
        assert response.status_code == 200

        data = response.get_json()
        assert len(data["delivery"]["entries"]) <= 3

    def test_get_channel_patterns(self, client, store_with_data):
        """GET /api/v1/notifications/analytics/channels."""
        response = client.get("/api/v1/notifications/analytics/channels")
        assert response.status_code == 200

        data = response.get_json()
        assert "channels" in data
        assert "patterns" in data["channels"]
        assert "total_channels" in data["channels"]
        assert data["channels"]["total_channels"] >= 1
        assert "revision" in data["channels"]

    def test_get_channel_patterns_with_filter(self, client, store_with_data):
        """GET /api/v1/notifications/analytics/channels mit Channel-Filter."""
        response = client.get("/api/v1/notifications/analytics/channels?channels=telegram")
        assert response.status_code == 200

        data = response.get_json()
        assert len(data["channels"]["patterns"]) == 1
        assert data["channels"]["patterns"][0]["channel"] == "telegram"

    def test_get_effectiveness(self, client, store_with_data):
        """GET /api/v1/notifications/analytics/effectiveness."""
        response = client.get("/api/v1/notifications/analytics/effectiveness")
        assert response.status_code == 200

        data = response.get_json()
        assert "effectiveness" in data
        assert "total_notifications_analyzed" in data["effectiveness"]
        assert "overall_delivery_rate" in data["effectiveness"]
        assert "engagement_score" in data["effectiveness"]
        assert "revision" in data["effectiveness"]

    def test_get_summary(self, client, store_with_data):
        """GET /api/v1/notifications/analytics/summary."""
        response = client.get("/api/v1/notifications/analytics/summary")
        assert response.status_code == 200

        data = response.get_json()
        assert "summary" in data
        assert "delivery" in data["summary"]
        assert "channels" in data["summary"]
        assert "effectiveness" in data["summary"]
        assert "summary_revision" in data["summary"]

        # Verify nested structure
        assert "total_notifications" in data["summary"]["delivery"]
        assert "total_channels" in data["summary"]["channels"]
        assert "total_notifications_analyzed" in data["summary"]["effectiveness"]

    def test_delivery_history_empty(self, tmp_path):
        """Delivery-Historie ohne Daten."""
        db_path = tmp_path / "notification_analytics.db"
        store = NotificationAnalyticsStore(db_path=str(db_path))

        with patch('copilot_core.notifications.api.get_notification_analytics_store', return_value=store):
            from copilot_core.app import create_app
            app = create_app()
            client = app.test_client()

            response = client.get("/api/v1/notifications/analytics/delivery")
            assert response.status_code == 200

            data = response.get_json()
            assert data["delivery"]["total_notifications"] == 0
            assert data["delivery"]["entries"] == []

    def test_channel_patterns_structure(self, client, store_with_data):
        """Channel-Patterns Struktur-Test."""
        response = client.get("/api/v1/notifications/analytics/channels")
        assert response.status_code == 200

        data = response.get_json()
        pattern = data["channels"]["patterns"][0]

        # Verify all expected fields
        required_fields = [
            "channel", "total_notifications", "sent_count", "delivered_count",
            "failed_count", "read_count", "acknowledged_count",
            "avg_delivery_time_seconds", "failure_rate", "most_common_type",
            "peak_delivery_hour", "notifications_last_24_hours",
            "notifications_last_7_days", "unique_recipients"
        ]
        for field in required_fields:
            assert field in pattern

    def test_effectiveness_metrics_structure(self, client, store_with_data):
        """Effectiveness-Metriken Struktur-Test."""
        response = client.get("/api/v1/notifications/analytics/effectiveness")
        assert response.status_code == 200

        data = response.get_json()
        metrics = data["effectiveness"]

        # Verify all expected fields
        required_fields = [
            "total_notifications_analyzed", "notifications_by_type",
            "notifications_by_channel", "overall_delivery_rate",
            "overall_read_rate", "overall_ack_rate",
            "avg_delivery_time_by_channel", "failure_rate_by_type",
            "zones_with_notifications", "peak_notification_time",
            "engagement_score", "revision", "latest_change_at"
        ]
        for field in required_fields:
            assert field in metrics

    def test_summary_structure(self, client, store_with_data):
        """Summary Struktur-Test."""
        response = client.get("/api/v1/notifications/analytics/summary")
        assert response.status_code == 200

        data = response.get_json()
        summary = data["summary"]

        # Verify top-level structure
        assert "delivery" in summary
        assert "channels" in summary
        assert "effectiveness" in summary
        assert "summary_revision" in summary
        assert "latest_change_at" in summary

    def test_revision_in_all_endpoints(self, client, store_with_data):
        """Revision in allen Endpoints vorhanden."""
        endpoints = [
            "/api/v1/notifications/analytics/delivery",
            "/api/v1/notifications/analytics/channels",
            "/api/v1/notifications/analytics/effectiveness",
            "/api/v1/notifications/analytics/summary",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200
            data = response.get_json()
            # Check that revision is present somewhere in the response
            assert "revision" in str(data)
