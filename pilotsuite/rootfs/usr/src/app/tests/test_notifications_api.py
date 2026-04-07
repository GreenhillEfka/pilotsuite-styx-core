"""Tests for Notifications API Endpoints.

Tests both the API endpoints (when Flask is available) and the engine directly.
"""

import pytest

try:
    from copilot_core.notifications.engine import NotificationEngine, Priority
    ENGINE_AVAILABLE = True
except ModuleNotFoundError:
    ENGINE_AVAILABLE = False
    NotificationEngine = None

# Try to import Flask components
try:
    from copilot_core.app import create_app
    from copilot_core.api.v1.notifications import (
        bp as notifications_bp,
        get_notification_manager,
        NotificationManager,
    )
    FLASK_AVAILABLE = True
except ModuleNotFoundError:
    FLASK_AVAILABLE = False
    create_app = None
    notifications_bp = None
    get_notification_manager = None
    NotificationManager = None


@pytest.fixture
def notification_engine():
    """Create a fresh notification engine."""
    if not ENGINE_AVAILABLE:
        pytest.skip("Notifications module not available")
    return NotificationEngine(
        dedup_window_seconds=60,
        rate_limit_per_hour=100,
        digest_interval_minutes=5
    )


@pytest.fixture
def app_with_notifications(notification_engine):
    """Create test app with notifications API initialized."""
    if not FLASK_AVAILABLE:
        pytest.skip("Flask not installed")
    
    # Import and reset the notification manager
    from copilot_core.api.v1.notifications import (
        get_notification_manager,
        NotificationManager,
        Notification,
    )
    
    # Create fresh manager for testing
    import copilot_core.api.v1.notifications as notifications_module
    notifications_module._notification_manager = NotificationManager()
    
    app = create_app()
    if notifications_bp:
        app.register_blueprint(notifications_bp)
    
    return app


@pytest.fixture
def notification_manager():
    """Get the notification manager and reset it for testing."""
    if not FLASK_AVAILABLE:
        pytest.skip("Flask not installed")
    
    from copilot_core.api.v1.notifications import (
        get_notification_manager,
        NotificationManager,
    )
    
    import copilot_core.api.v1.notifications as notifications_module
    notifications_module._notification_manager = NotificationManager()
    
    return get_notification_manager()


# ═══════════════════════════════════════════════════════════════════════════
# Engine Tests (No Flask Required)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not ENGINE_AVAILABLE, reason="Notifications engine not available")
class TestNotificationEngine:
    """Test notification engine directly."""
    
    def test_notify_returns_notification(self, notification_engine):
        """Test that notify returns a notification object."""
        n = notification_engine.notify("energy", "Test", "Hello")
        assert n is not None
        assert n.source == "energy"
        assert n.title == "Test"
    
    def test_notification_has_id(self, notification_engine):
        """Test notification has unique ID."""
        n = notification_engine.notify("energy", "Test", "Hello")
        assert n.id.startswith("n-")
    
    def test_default_priority_is_normal(self, notification_engine):
        """Test default priority is NORMAL."""
        n = notification_engine.notify("energy", "Test", "Hello")
        assert n.priority == Priority.NORMAL
    
    def test_custom_priority(self, notification_engine):
        """Test custom priority setting."""
        n = notification_engine.notify("energy", "Alert", "Fire", Priority.CRITICAL)
        assert n.priority == Priority.CRITICAL
    
    def test_deduplication(self, notification_engine):
        """Test duplicate notifications are rejected."""
        n1 = notification_engine.notify("energy", "Same", "Message")
        n2 = notification_engine.notify("energy", "Same", "Message")
        assert n1 is not None
        assert n2 is None
    
    def test_critical_bypasses_dedup(self, notification_engine):
        """Test CRITICAL priority bypasses deduplication."""
        n1 = notification_engine.notify("energy", "Fire", "Now", Priority.CRITICAL)
        n2 = notification_engine.notify("energy", "Fire", "Now", Priority.CRITICAL)
        assert n1 is not None
        assert n2 is not None
    
    def test_history_tracking(self, notification_engine):
        """Test notification history is tracked."""
        notification_engine.notify("energy", "A", "1")
        notification_engine.notify("comfort", "B", "2")
        history = notification_engine.get_history()
        assert len(history) == 2
    
    def test_history_filter_by_source(self, notification_engine):
        """Test filtering history by source."""
        notification_engine.notify("energy", "A", "1")
        notification_engine.notify("comfort", "B", "2")
        notification_engine.notify("energy", "C", "3")
        
        history = notification_engine.get_history(source="energy")
        assert len(history) == 2
        assert all(h["source"] == "energy" for h in history)
    
    def test_digest_counts_by_source(self, notification_engine):
        """Test digest groups by source."""
        notification_engine.notify("energy", "A", "1")
        notification_engine.notify("comfort", "B", "2")
        notification_engine.notify("energy", "C", "3")
        
        digest = notification_engine.get_digest()
        assert digest.by_source["energy"] == 2
        assert digest.by_source["comfort"] == 1
    
    def test_stats_structure(self, notification_engine):
        """Test stats has required fields."""
        stats = notification_engine.get_stats()
        assert "total_notifications" in stats
        assert "rate_limit_per_hour" in stats
        assert "dedup_window_seconds" in stats


# ═══════════════════════════════════════════════════════════════════════════
# API Endpoint Tests (Flask Required)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestGetNotifications:
    """Test GET /api/v1/notifications endpoint."""
    
    def test_get_notifications_empty(self, app_with_notifications):
        """Test getting notifications when history is empty."""
        client = app_with_notifications.test_client()
        r = client.get("/api/v1/notifications")
        assert r.status_code == 200
        j = r.get_json()
        assert j["ok"] is True
        assert j["count"] == 0
    
    def test_get_notifications_with_history(self, app_with_notifications, notification_manager):
        """Test getting notifications with items in history."""
        notification_manager.create_notification("Test Title", "Test Message", type="info")
        notification_manager.create_notification("Another Title", "Another Message", type="warning")
        
        client = app_with_notifications.test_client()
        r = client.get("/api/v1/notifications")
        assert r.status_code == 200
        j = r.get_json()
        assert j["count"] == 2
    
    def test_get_notifications_limit(self, app_with_notifications, notification_manager):
        """Test notifications limit parameter."""
        for i in range(10):
            notification_manager.create_notification(f"Title {i}", f"Message {i}", type="info")
        
        client = app_with_notifications.test_client()
        r = client.get("/api/v1/notifications?limit=5")
        assert r.status_code == 200
        j = r.get_json()
        assert j["count"] <= 5


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestCreateNotification:
    """Test POST /api/v1/notifications endpoint."""
    
    def test_create_notification_minimal(self, app_with_notifications):
        """Test creating notification with minimal fields."""
        client = app_with_notifications.test_client()
        r = client.post("/api/v1/notifications", json={
            "title": "Test Alert",
            "message": "This is a test notification"
        })
        assert r.status_code == 201
        j = r.get_json()
        assert j["ok"] is True
        assert "id" in j
    
    def test_create_notification_with_priority(self, app_with_notifications):
        """Test creating notification with custom priority."""
        client = app_with_notifications.test_client()
        r = client.post("/api/v1/notifications", json={
            "title": "Critical Alert",
            "message": "Something urgent!",
            "priority": 1  # CRITICAL
        })
        assert r.status_code == 201
        j = r.get_json()
        assert j["priority"] == "CRITICAL"
    
    def test_create_notification_missing_title(self, app_with_notifications):
        """Test creating notification without title fails."""
        client = app_with_notifications.test_client()
        r = client.post("/api/v1/notifications", json={
            "message": "No title provided"
        })
        assert r.status_code == 400
        j = r.get_json()
        assert j["ok"] is False
    
    def test_create_notification_deduplicated(self, app_with_notifications):
        """Test that duplicate notifications are deduplicated."""
        client = app_with_notifications.test_client()
        
        # First notification should succeed
        r1 = client.post("/api/v1/notifications", json={
            "title": "Duplicate Test",
            "message": "Same message"
        })
        assert r1.status_code == 201
        
        # Second identical notification should be deduplicated
        r2 = client.post("/api/v1/notifications", json={
            "title": "Duplicate Test",
            "message": "Same message"
        })
        assert r2.status_code == 200
        j = r2.get_json()
        assert j["status"] == "deduplicated_or_rate_limited"


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestGetDigest:
    """Test GET /api/v1/notifications/digest endpoint."""
    
    def test_get_digest_empty(self, app_with_notifications):
        """Test getting digest when no notifications exist."""
        client = app_with_notifications.test_client()
        r = client.get("/api/v1/notifications/digest")
        assert r.status_code == 200
        j = r.get_json()
        assert j["ok"] is True
        assert j["digest"]["total"] == 0
    
    def test_get_digest_with_notifications(self, app_with_notifications, notification_manager):
        """Test getting digest with notifications."""
        notification_manager.create_notification("Alert 1", "Message 1", type="energy")
        notification_manager.create_notification("Alert 2", "Message 2", type="comfort")
        
        client = app_with_notifications.test_client()
        r = client.get("/api/v1/notifications/digest")
        assert r.status_code == 200
        j = r.get_json()
        assert j["ok"] is True
        assert j["digest"]["total"] == 2
        assert "by_source" in j["digest"]


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestGetPending:
    """Test GET /api/v1/notifications/pending endpoint."""
    
    def test_get_pending_empty(self, app_with_notifications):
        """Test getting pending notifications when none exist."""
        client = app_with_notifications.test_client()
        r = client.get("/api/v1/notifications/pending")
        assert r.status_code == 200
        j = r.get_json()
        assert j["ok"] is True
        assert j["count"] == 0
    
    def test_get_pending_with_notifications(self, app_with_notifications, notification_manager):
        """Test getting pending notifications."""
        notification_manager.create_notification("Pending Alert", "Needs delivery", type="warning")
        
        client = app_with_notifications.test_client()
        r = client.get("/api/v1/notifications/pending")
        assert r.status_code == 200
        j = r.get_json()
        assert j["count"] == 1


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestGetStats:
    """Test GET /api/v1/notifications/stats endpoint."""
    
    def test_get_stats_empty(self, app_with_notifications):
        """Test getting stats when no notifications sent."""
        client = app_with_notifications.test_client()
        r = client.get("/api/v1/notifications/stats")
        assert r.status_code == 200
        j = r.get_json()
        assert j["ok"] is True
        assert j["total_notifications"] == 0
    
    def test_get_stats_with_notifications(self, app_with_notifications, notification_manager):
        """Test getting stats after sending notifications."""
        for i in range(5):
            notification_manager.create_notification(f"Title {i}", f"Message {i}", type="info")
        
        client = app_with_notifications.test_client()
        r = client.get("/api/v1/notifications/stats")
        assert r.status_code == 200
        j = r.get_json()
        assert j["total_notifications"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
