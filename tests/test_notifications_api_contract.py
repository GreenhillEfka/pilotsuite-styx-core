"""Notifications API Contract Tests — CORE-HARDEN-206"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1 import notifications
from unittest.mock import patch, MagicMock
from datetime import datetime
import uuid


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(notifications.bp, url_prefix="/api/v1/notifications")
    return app


def _patch_validate():
    return patch.object(notifications, '_validate_token', return_value=True)


def _mock_notification(**overrides):
    n = MagicMock()
    n.id = overrides.get('id', str(uuid.uuid4()))
    n.title = overrides.get('title', 'Test Notification')
    n.message = overrides.get('message', 'Test message content')
    n.priority = overrides.get('priority', 'normal')
    n.type = overrides.get('type', 'info')
    n.timestamp = overrides.get('timestamp', datetime.now().isoformat())
    n.read = overrides.get('read', False)
    n.to_dict.return_value = {
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'priority': n.priority,
        'type': n.type,
        'timestamp': n.timestamp,
        'read': n.read,
    }
    return n


def _mock_subscription(**overrides):
    """Return a dict-like mock subscription with to_dict() method."""
    data = {
        'subscription_id': overrides.get('subscription_id', str(uuid.uuid4())),
        'device_id': overrides.get('device_id', 'device-abc'),
        'device_name': overrides.get('device_name', 'Test Device'),
        'device_type': overrides.get('device_type', 'mobile'),
        'enabled': overrides.get('enabled', True),
        'notification_types': overrides.get('notification_types', ['alert', 'info']),
    }
    mock = MagicMock()
    mock.to_dict.return_value = data
    mock.subscription_id = data['subscription_id']
    return mock


# Real route map (from Flask URL map):
# POST+GET  /api/v1/notifications          (handle_notifications)
# POST      /api/v1/notifications/send    (send_notification)
# DELETE    /api/v1/notifications/<id>     (dismiss_notification)
# POST      /api/v1/notifications/<id>/read (mark_notification_read)
# POST      /api/v1/notifications/clear    (clear_notifications)
# POST      /api/v1/notifications/subscribe (subscribe_device)
# POST      /api/v1/notifications/unsubscribe (unsubscribe_device)
# GET       /api/v1/notifications/subscriptions (get_subscriptions)
# PUT       /api/v1/notifications/subscriptions/<device_id> (update_subscription)
# GET       /api/v1/notifications/stats   (get_notification_stats)
# GET       /api/v1/notifications/pending  (get_pending_notifications)
# GET       /api/v1/notifications/digest   (get_notification_digest)
# POST      /api/v1/notifications/ha/register (ha_register)
# GET       /api/v1/notifications/ha/devices
# DELETE    /api/v1/notifications/ha/devices/<device_id>
# POST      /api/v1/notifications/ha/devices/<device_id>/enable
# POST      /api/v1/notifications/ha/devices/<device_id>/disable
# POST      /api/v1/notifications/send/ha


class TestNotificationsSend:
    """POST /api/v1/notifications/send."""

    def test_send_requires_title_and_message(self):
        app = _make_app()
        with _patch_validate():
            client = app.test_client()
            r = client.post("/api/v1/notifications/send", json={})
            assert r.status_code == 400, f"expected 400, got {r.status_code}"
            r = client.post("/api/v1/notifications/send", json={"title": "Test"})
            assert r.status_code == 400, f"expected 400, got {r.status_code}"

    def test_send_accepts_valid_notification(self):
        app = _make_app()
        with _patch_validate():
            mock_notif = _mock_notification(title="Solar Alert", message="PV surplus")
            mock_manager = MagicMock()
            mock_manager.create_notification.return_value = mock_notif
            mock_manager.send_notification.return_value = None
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.post("/api/v1/notifications/send", json={
                    "title": "Solar Alert",
                    "message": "PV surplus",
                    "priority": "high",
                    "type": "alert",
                })
                assert r.status_code == 200, f"expected 200, got {r.status_code}, body={r.get_json()}"
                data = r.get_json()
                assert data["success"] is True
                assert "notification_id" in data["data"]

    def test_send_rejects_no_body(self):
        app = _make_app()
        with _patch_validate():
            client = app.test_client()
            r = client.post("/api/v1/notifications/send")
            assert r.status_code == 400

    def test_send_unauthorized_without_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/notifications/send", json={"title": "X", "message": "Y"})
        assert r.status_code in (401, 403)


class TestNotificationsList:
    """GET+POST /api/v1/notifications (handle_notifications)."""

    def test_get_notifications_returns_list(self):
        app = _make_app()
        with _patch_validate():
            mock_notif = _mock_notification(title="Test", message="Content")
            mock_manager = MagicMock()
            mock_manager.get_notifications.return_value = [mock_notif]
            mock_manager.get_unread_count.return_value = 1
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.get("/api/v1/notifications")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_notifications_with_filters(self):
        app = _make_app()
        with _patch_validate():
            mock_manager = MagicMock()
            mock_manager.get_notifications.return_value = []
            mock_manager.get_unread_count.return_value = 0
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.get("/api/v1/notifications?unread_only=true&type=alert&limit=5")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_post_creates_notification(self):
        app = _make_app()
        with _patch_validate():
            mock_notif = _mock_notification(title="Created", message="Via POST")
            mock_manager = MagicMock()
            mock_manager.create_notification.return_value = mock_notif
            mock_manager.send_notification.return_value = None
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.post("/api/v1/notifications", json={"title": "Created", "message": "Via POST"})
                assert r.status_code in (200, 201), f"expected 200/201, got {r.status_code}"

    def test_get_notifications_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/notifications")
        assert r.status_code in (401, 403)


class TestNotificationsRead:
    """POST /api/v1/notifications/<id>/read."""

    def test_mark_notification_read_returns_200(self):
        app = _make_app()
        with _patch_validate():
            mock_manager = MagicMock()
            mock_manager.mark_as_read.return_value = True
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.post("/api/v1/notifications/test-id-123/read")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_mark_notification_read_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/notifications/some-id/read")
        assert r.status_code in (401, 403)


class TestNotificationsDismiss:
    """DELETE /api/v1/notifications/<id>."""

    def test_dismiss_notification_returns_200(self):
        app = _make_app()
        with _patch_validate():
            mock_manager = MagicMock()
            mock_manager.dismiss_notification.return_value = True
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.delete("/api/v1/notifications/test-id-456")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_dismiss_not_found_returns_404(self):
        app = _make_app()
        with _patch_validate():
            mock_manager = MagicMock()
            mock_manager.dismiss_notification.return_value = False
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.delete("/api/v1/notifications/nonexistent-id")
                assert r.status_code in (404, 400)

    def test_dismiss_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.delete("/api/v1/notifications/some-id")
        assert r.status_code in (401, 403)


class TestNotificationsClear:
    """POST /api/v1/notifications/clear."""

    def test_clear_notifications_returns_200(self):
        app = _make_app()
        with _patch_validate():
            mock_manager = MagicMock()
            mock_manager.clear_notifications.return_value = 5
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.post("/api/v1/notifications/clear", json={})
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_clear_with_type_filter(self):
        app = _make_app()
        with _patch_validate():
            mock_manager = MagicMock()
            mock_manager.clear_notifications.return_value = 3
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.post("/api/v1/notifications/clear", json={"type": "alert"})
                assert r.status_code == 200

    def test_clear_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/notifications/clear", json={})
        assert r.status_code in (401, 403)


class TestNotificationsSubscribe:
    """Subscribe/unsubscribe/subscriptions endpoints."""

    def test_subscribe_device_returns_200(self):
        app = _make_app()
        with _patch_validate():
            mock_sub = _mock_subscription(device_id='device-abc')
            mock_manager = MagicMock()
            mock_manager.subscribe_device.return_value = mock_sub
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.post("/api/v1/notifications/subscribe", json={
                    "device_id": "device-abc",
                    "notification_types": ["alert", "info"],
                })
                assert r.status_code == 200, f"expected 200, got {r.status_code}, body={r.get_json()}"

    def test_subscribe_requires_device_id(self):
        app = _make_app()
        with _patch_validate():
            client = app.test_client()
            r = client.post("/api/v1/notifications/subscribe", json={"notification_types": ["alert"]})
            assert r.status_code == 400

    def test_unsubscribe_device_returns_200(self):
        app = _make_app()
        with _patch_validate():
            mock_manager = MagicMock()
            mock_manager.unsubscribe_device.return_value = True
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.post("/api/v1/notifications/unsubscribe", json={"device_id": "device-abc"})
                assert r.status_code == 200

    def test_get_subscriptions_returns_list(self):
        app = _make_app()
        with _patch_validate():
            mock_manager = MagicMock()
            mock_manager.get_subscriptions.return_value = []
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.get("/api/v1/notifications/subscriptions")
                assert r.status_code == 200

    def test_update_subscription_returns_200(self):
        app = _make_app()
        with _patch_validate():
            mock_sub = _mock_subscription(device_id='device-abc')
            mock_manager = MagicMock()
            mock_manager.update_subscription.return_value = mock_sub
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.put("/api/v1/notifications/subscriptions/device-abc", json={
                    "notification_types": ["alert", "info"],
                    "enabled": True,
                })
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_subscribe_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/notifications/subscribe", json={"device_id": "x"})
        assert r.status_code in (401, 403)


class TestNotificationsStats:
    """Stats/pending/digest endpoints."""

    def test_get_stats_returns_200(self):
        app = _make_app()
        with _patch_validate():
            mock_manager = MagicMock()
            mock_manager.get_unread_count.return_value = 3
            mock_manager._notifications = []
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.get("/api/v1/notifications/stats")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_pending_returns_200(self):
        app = _make_app()
        with _patch_validate():
            mock_manager = MagicMock()
            mock_manager.get_pending_notifications.return_value = []
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.get("/api/v1/notifications/pending")
                assert r.status_code == 200

    def test_get_digest_returns_200(self):
        app = _make_app()
        with _patch_validate():
            mock_manager = MagicMock()
            # _get_digest is monkey-patched onto NotificationManager at import time
            # When we mock the manager, the monkey-patched method is already bound
            # We need to make get_digest return a plain dict (not MagicMock)
            mock_manager.get_digest.return_value = {
                'period_hours': 12,
                'total': 0,
                'by_source': {},
            }
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.get("/api/v1/notifications/digest?hours=12")
                assert r.status_code == 200, f"expected 200, got {r.status_code}, body={r.get_json()}"


class TestNotificationsHA:
    """HA service integration endpoints."""

    def test_ha_register_returns_200(self):
        app = _make_app()
        with _patch_validate():
            mock_manager = MagicMock()
            mock_manager.set_ha_notify_service.return_value = None
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                # ha/register requires user_id AND ha_entity_id (must start with "notify.")
                r = client.post("/api/v1/notifications/ha/register", json={
                    "service": "notify.pilot_suite",
                    "user_id": "user-123",
                    "ha_entity_id": "notify.mobile_app_iphone",
                })
                assert r.status_code in (200, 201), f"expected 200/201, got {r.status_code}, body={r.get_json()}"

    def test_ha_get_devices_returns_200(self):
        app = _make_app()
        with _patch_validate():
            mock_manager = MagicMock()
            mock_manager.get_ha_devices.return_value = []
            with patch.object(notifications, 'get_notification_manager', return_value=mock_manager):
                client = app.test_client()
                r = client.get("/api/v1/notifications/ha/devices")
                assert r.status_code == 200


class TestNotificationsAllAuth:
    """All real endpoints require auth."""

    def test_all_endpoints_require_authorization(self):
        app = _make_app()
        client = app.test_client()
        real_endpoints = [
            ("POST", "/api/v1/notifications/send", {"title": "X", "message": "Y"}),
            ("GET", "/api/v1/notifications", None),
            ("POST", "/api/v1/notifications", {"title": "X", "message": "Y"}),
            ("POST", "/api/v1/notifications/test-id/read", None),
            ("DELETE", "/api/v1/notifications/test-id", None),
            ("POST", "/api/v1/notifications/clear", {}),
            ("POST", "/api/v1/notifications/subscribe", {"device_id": "x"}),
            ("POST", "/api/v1/notifications/unsubscribe", {"device_id": "x"}),
            ("GET", "/api/v1/notifications/subscriptions", None),
            ("PUT", "/api/v1/notifications/subscriptions/device-abc", {"enabled": True}),
            ("GET", "/api/v1/notifications/stats", None),
            ("GET", "/api/v1/notifications/pending", None),
            ("GET", "/api/v1/notifications/digest", None),
            ("POST", "/api/v1/notifications/ha/register", {"service": "x"}),
            ("GET", "/api/v1/notifications/ha/devices", None),
        ]
        for method, path, body in real_endpoints:
            r = client.open(path, method=method, json=body)
            assert r.status_code in (401, 403), f"{method} {path}: expected 401/403, got {r.status_code}"